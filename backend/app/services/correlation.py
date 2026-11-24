import re
from app.services.clock import utc_naive
from app.models import Incident, IncidentRelationship, Ticket
from app.services.locations import location_parts
from app.services.intelligence import cosine_similarity


def building_for(location):
    return location_parts(location)[0]

def link(db, incident_id, kind, record_id, reason):
    if not db.query(IncidentRelationship).filter_by(incident_id=incident_id, related_type=kind,
                                                    related_id=record_id).first():
        db.add(IncidentRelationship(incident_id=incident_id, related_type=kind, related_id=record_id, reason=reason))
        db.flush()


def active_overlap(db, ticket_ids):
    return db.query(Incident).join(IncidentRelationship, IncidentRelationship.incident_id == Incident.id).filter(
        Incident.status.not_in(["Resolved", "Dismissed"]), IncidentRelationship.related_type == "ticket",
        IncidentRelationship.related_id.in_(ticket_ids),
    ).first()


def similar_tickets(db, ticket):
    candidates = db.query(Ticket).filter(Ticket.id != ticket.id, Ticket.category == ticket.category,
                                         Ticket.status != "Resolved").all()
    matches = [match for candidate in candidates if (match := pair_evidence(ticket, candidate))]
    return sorted(matches, key=lambda match: (-match["similarity"], match["id"]))[:8]


# Match the reported service or device before comparing surrounding prose.
ISSUES = {
    "docking station": r"\b(?:dock(?:ing station)?)\b",
    "document camera": r"\b(?:doc(?:ument)? cam(?:era)?)\b",
    "webcam": r"\bwebcam\b",
    "projector": r"\bprojectors?\b",
    "Wi-Fi": r"\b(?:wi[ -]?fi|wireless)\b",
    "LockDown Browser": r"\b(?:lockdown browser|respondus)\b",
    "authentication": r"\b(?:account lock(?:ed|out)|sign[ -]?in|log[ -]?in|authentication)\b",
    "printing": r"\b(?:printer|print queue|printing)\b",
}
GENERIC = set("cannot keeps issues issue working stopped not work help same again please problem problems still says currently device laptop room building hall classroom library campus report error failed failure unable today".split())


def issue_names(text):
    return {name for name, pattern in ISSUES.items() if re.search(pattern, text, re.I)}


def informative(text, location):
    excluded = GENERIC | set(re.findall(r"[a-z]+", location.casefold()))
    return " ".join(token for token in re.findall(r"[a-z]{2,}", text.casefold()) if token not in excluded)


def pair_evidence(ticket, candidate):
    if ticket.category != candidate.category or bool(ticket.demo_key) != bool(candidate.demo_key):
        return None
    if abs((utc_naive(ticket.created_at) - utc_naive(candidate.created_at)).total_seconds()) > 48 * 3600:
        return None
    building, room = location_parts(ticket.location)
    other_building, other_room = location_parts(candidate.location)
    same_building = bool(building) and building.casefold() == other_building.casefold()
    same_room = bool(room) and room == other_room and same_building
    if ticket.category == "Classroom Technology" and room and other_room and not same_room:
        return None
    text = f"{ticket.title} {ticket.title} {ticket.description}"
    other_text = f"{candidate.title} {candidate.title} {candidate.description}"
    left = issue_names(ticket.title) or issue_names(text)
    right = issue_names(candidate.title) or issue_names(other_text)
    common = left & right
    if left and right and not common:
        return None
    first = informative(text, ticket.location)
    second = informative(other_text, candidate.location)
    score = cosine_similarity(first, second)
    shared = set(first.split()) & set(second.split())
    if score < (.30 if common else .62) or (not common and len(shared) < 3):
        return None
    return {"id": candidate.id, "title": candidate.title, "similarity": round(score, 2),
            "same_building": same_building, "same_room": same_room,
            "possible_duplicate": same_building and room == other_room and score >= .67,
            "affected_users": candidate.affected_users,
            "evidence": sorted(common) or sorted(shared)[:4]}
