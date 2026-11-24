from datetime import datetime
from hashlib import sha256
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DismissedRecommendation, AvailabilityState, Incident, IncidentRelationship, NetworkEvent, SecurityEvent, Ticket, User
from app.schemas import IncidentCreate, IncidentOut, InvestigationUpdate, StatusUpdate
from app.services.auth import require_roles
from app.services.correlation import active_overlap, building_for, link, similar_tickets, pair_evidence
from app.services.clock import utc_naive
from app.services.intelligence import calculate_priority, recommend_technician
from app.services.investigations import record_entry, timeline, update_investigation
from app.services.workload import recalculate_workloads

operations = require_roles("technician", "admin")
router = APIRouter(prefix="/api/incidents", tags=["Incidents"], dependencies=[Depends(operations)])
EVIDENCE_MODELS = {"ticket": Ticket, "network": NetworkEvent, "security": SecurityEvent, "availability": AvailabilityState}
POSSIBLE_CAUSES = {
    "Network": "Check whether the endpoint, wireless access equipment, or upstream connectivity explains the reports.",
    "Security": "Review authentication context for repeated credentials, a stale client, or another source of login failures.",
    "Classroom Technology": "Inspect the shared display, signal path, source device, and input configuration.",
    "Software": "Compare application version, deployment timing, and errors reported by affected users.",
}


def get_incident(db, incident_id):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident


def make_incident(db, title, description, category, location, tickets, evidence=False):
    technician, _ = recommend_technician(recalculate_workloads(db), category, location)
    severity_rank = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    severity = max((ticket.severity for ticket in tickets), key=lambda item: severity_rank.get(item, 1), default="Medium")
    incident = Incident(title=title, description=description, category=category, location=location,
                        demo_context=bool(tickets and all(ticket.demo_key for ticket in tickets)),
                        priority=calculate_priority(sum(ticket.affected_users for ticket in tickets), severity,
                                                    location, category == "Security", evidence),
                        recommended_technician=technician.name if technician else None)
    db.add(incident)
    db.flush()
    for ticket in tickets:
        link(db, incident.id, "ticket", ticket.id, "Grouped during technician review")
    return incident


@router.get("")
def list_incidents(q: str | None = None, db: Session = Depends(get_db)):
    counts = dict(db.query(IncidentRelationship.incident_id, func.count()).filter_by(related_type="ticket")
                  .group_by(IncidentRelationship.incident_id).all())
    items = db.query(Incident).filter(Incident.status.not_in(["Recommended", "Dismissed"])).order_by(Incident.created_at.desc(), Incident.id.desc()).all()
    return [{**IncidentOut.model_validate(item).model_dump(mode="json"), "related_ticket_count": counts.get(item.id, 0)}
            for item in items if not q or q.casefold() in f"{item.title} {item.location} {item.category}".casefold()]


@router.get("/recommendations")
def recommendations(db: Session = Depends(get_db), user: User = Depends(operations)):
    groups = []
    excluded = {row[0] for row in db.query(IncidentRelationship.related_id).join(
        Incident, Incident.id == IncidentRelationship.incident_id
    ).filter(IncidentRelationship.related_type == "ticket")}
    dismissed = {row[0] for row in db.query(DismissedRecommendation.fingerprint)}
    tickets = db.query(Ticket).filter(Ticket.status != "Resolved", Ticket.id.not_in(excluded)).order_by(Ticket.id).all()
    used = set()
    for ticket in tickets:
        if ticket.id in used:
            continue
        group = [ticket]
        matches = []
        for candidate in tickets:
            if candidate.id <= ticket.id or candidate.id in used:
                continue
            evidence = [pair_evidence(member, candidate) for member in group]
            if all(item and item["same_building"] for item in evidence):
                group.append(candidate)
                matches.append(evidence[0])
        if not matches:
            continue
        ids = [item.id for item in group]
        fingerprint = sha256(",".join(f"{item.id}:{item.created_at.isoformat()}" for item in group).encode()).hexdigest()
        if fingerprint in dismissed:
            continue
        used.update(ids)
        groups.append({"id": fingerprint, "title": f"Shared issue: {ticket.title}", "category": ticket.category,
                       "location": building_for(ticket.location), "ticket_ids": ids,
                       "description": "Reports share an equipment or service signal, category, building and a 48-hour submission window.",
                       "similarity_evidence": matches, "reported_impact": sum(item.affected_users for item in group),
                       "demo": bool(ticket.demo_key)})
    staged = db.query(Incident).filter_by(status="Recommended").all()
    for incident in staged:
        if incident.category == "Security" and not user.can_view_security:
            continue
        rows = db.query(Ticket).join(IncidentRelationship, IncidentRelationship.related_id == Ticket.id).filter(
            IncidentRelationship.incident_id == incident.id, IncidentRelationship.related_type == "ticket",
            Ticket.status != "Resolved"
        ).all()
        if rows:
            groups.append({"id": f"incident-{incident.id}", "incident_id": incident.id, "title": incident.title,
                           "category": incident.category, "location": incident.location,
                           "ticket_ids": [row.id for row in rows], "demo": bool(incident.demo_key),
                           "reported_impact": sum(row.affected_users for row in rows),
                           "description": incident.description,
                           "similarity_evidence": [match for row in rows[1:] if (match := pair_evidence(rows[0], row))]})
    return groups


@router.post("/recommendations/{recommendation_id}/dismiss", status_code=204)
def dismiss_recommendation(recommendation_id: str, db: Session = Depends(get_db), user: User = Depends(operations)):
    db.execute(text("BEGIN IMMEDIATE"))
    matched = next((item for item in recommendations(db, user) if item["id"] == recommendation_id), None)
    if not matched:
        if db.get(DismissedRecommendation, recommendation_id):
            return
        raise HTTPException(404, "Pending recommendation not found")
    if matched.get("incident_id"):
        incident = get_incident(db, matched["incident_id"])
        incident.status = "Dismissed"
        record_entry(db, "incident", incident.id, "Recommendation", "Recommendation dismissed", user)
    else:
        db.add(DismissedRecommendation(fingerprint=recommendation_id))
    db.commit()


@router.post("/recommendations/{incident_id}/accept", response_model=IncidentOut)
def accept_recommendation(incident_id: int, db: Session = Depends(get_db), user: User = Depends(operations)):
    db.execute(text("BEGIN IMMEDIATE"))
    incident = get_incident(db, incident_id)
    if incident.category == "Security" and not user.can_view_security:
        raise HTTPException(403, "Security access required")
    if incident.status != "Recommended":
        raise HTTPException(409, "Recommendation is no longer pending")
    if not any(item.get("incident_id") == incident_id for item in recommendations(db, user)):
        raise HTTPException(409, "The recommendation no longer has unresolved reports")
    incident.status = "Open"
    record_entry(db, "incident", incident.id, "Recommendation", "Recommendation accepted", user)
    db.commit()
    return incident


@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(data: IncidentCreate, db: Session = Depends(get_db), user: User = Depends(operations)):
    db.execute(text("BEGIN IMMEDIATE"))
    ids = set(data.ticket_ids)
    tickets = db.query(Ticket).filter(Ticket.id.in_(ids)).all()
    if len(tickets) != len(ids):
        raise HTTPException(404, "One or more tickets do not exist")
    duplicate = active_overlap(db, ids) if ids else None
    duplicate = duplicate or db.query(Incident).filter(
        Incident.status.not_in(["Resolved", "Dismissed"]), func.lower(Incident.title) == data.title.casefold(),
        func.lower(Incident.location) == data.location.casefold(),
    ).first()
    if duplicate:
        raise HTTPException(409, f"Related active incident #{duplicate.id} already exists")
    incident = make_incident(db, data.title, data.description, data.category, data.location, tickets)
    record_entry(db, "incident", incident.id, "Created", "Incident opened for investigation", user)
    db.commit()
    return incident


@router.post("/correlate")
def correlate(db: Session = Depends(get_db)):
    db.execute(text("BEGIN IMMEDIATE"))
    tickets = db.query(Ticket).filter(Ticket.status != "Resolved", Ticket.category == "Network").all()
    events = db.query(NetworkEvent).filter(NetworkEvent.severity.in_(["High", "Critical"])).all()
    created = []
    for event in events:
        if event.demo_key and not event.demo_key.startswith("legacy-network:"):
            continue
        location = building_for(event.location)
        related = [ticket for ticket in tickets if not ticket.demo_key and
                   building_for(ticket.location).casefold() == location.casefold() and
                   abs((utc_naive(ticket.created_at) - utc_naive(event.timestamp)).total_seconds()) <= 48 * 3600]
        shared = [ticket for ticket in related if any(
            other.id != ticket.id and pair_evidence(ticket, other) for other in related)]
        if len(shared) < 2:
            continue
        related = shared
        incident = active_overlap(db, [ticket.id for ticket in related])
        if incident is None:
            previous = db.query(IncidentRelationship).filter_by(related_type="network", related_id=event.id)
            linked_tickets = {row.related_id for row in db.query(IncidentRelationship).filter(
                IncidentRelationship.related_type == "ticket",
                IncidentRelationship.incident_id.in_(previous.with_entities(IncidentRelationship.incident_id).statement)
            )}
            if all(ticket.id in linked_tickets for ticket in related):
                continue
            incident = make_incident(db, f"Network disruption — {location}",
                                     "Multiple network reports coincide with a network event.",
                                     "Network", location, related, evidence=True)
            created.append(incident.id)
        for ticket in related:
            link(db, incident.id, "ticket", ticket.id, "Network report at the same building")
        link(db, incident.id, "network", event.id, "Network event at the same building")
    db.commit()
    return {"created_or_updated_incidents": created, "message": "Correlation completed"}


@router.get("/{incident_id}")
def detail(incident_id: int, db: Session = Depends(get_db), user: User = Depends(operations)):
    incident = get_incident(db, incident_id)
    evidence = []
    for relation in db.query(IncidentRelationship).filter_by(incident_id=incident_id):
        model = EVIDENCE_MODELS.get(relation.related_type)
        if model is None or (model is SecurityEvent and not user.can_view_security):
            continue
        item = db.get(model, relation.related_id)
        if item is not None:
            evidence.append({"id": relation.id, "type": relation.related_type, "reason": relation.reason, "item": item})
    return {"incident": IncidentOut.model_validate(incident), "relationships": evidence,
            "timeline": timeline(db, "incident", incident_id), "possible_cause": POSSIBLE_CAUSES.get(incident.category)}


@router.patch("/{incident_id}", response_model=IncidentOut)
def update(incident_id: int, data: InvestigationUpdate, db: Session = Depends(get_db), user: User = Depends(operations)):
    incident = get_incident(db, incident_id)
    if incident.status in {"Recommended", "Dismissed"} and incident.category == "Security" and not user.can_view_security:
        raise HTTPException(403, "Security access required")
    update_investigation(db, "incident", incident, data, user)
    if data.status:
        incident.resolved_at = (incident.resolved_at or datetime.utcnow()) if data.status == "Resolved" else None
    incident.updated_at = datetime.utcnow()
    db.commit()
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentOut)
def update_status(incident_id: int, data: StatusUpdate, db: Session = Depends(get_db), user: User = Depends(operations)):
    if data.status not in {"Open", "Investigating", "Resolved"}:
        raise HTTPException(422, "Status must be Open, Investigating, or Resolved")
    return update(incident_id, InvestigationUpdate(status=data.status), db, user)


@router.put("/{incident_id}/tickets/{ticket_id}", status_code=204)
def attach_ticket(incident_id: int, ticket_id: int, db: Session = Depends(get_db), user: User = Depends(operations)):
    db.execute(text("BEGIN IMMEDIATE"))
    incident = get_incident(db, incident_id)
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if incident.demo_key and not ticket.demo_key:
        raise HTTPException(409, "Generated incidents can link only generated tickets")
    existing = active_overlap(db, [ticket_id])
    if existing and existing.id != incident_id:
        raise HTTPException(409, f"Ticket belongs to active incident #{existing.id}")
    if not db.query(IncidentRelationship).filter_by(incident_id=incident_id, related_type="ticket",
                                                    related_id=ticket_id).first():
        link(db, incident_id, "ticket", ticket_id, "Linked by technician")
        record_entry(db, "incident", incident_id, "Link", f"Linked ticket #{ticket_id}", user)
        incident.updated_at = datetime.utcnow()
    db.commit()


@router.delete("/{incident_id}/tickets/{ticket_id}", status_code=204)
def detach_ticket(incident_id: int, ticket_id: int, db: Session = Depends(get_db), user: User = Depends(operations)):
    incident = get_incident(db, incident_id)
    removed = db.query(IncidentRelationship).filter_by(incident_id=incident_id, related_type="ticket",
                                                       related_id=ticket_id).delete()
    if removed:
        record_entry(db, "incident", incident_id, "Link", f"Unlinked ticket #{ticket_id}", user)
        incident.updated_at = datetime.utcnow()
    db.commit()
