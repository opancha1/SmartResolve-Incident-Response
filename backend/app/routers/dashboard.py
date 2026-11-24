from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.locations import test_endpoint
from app.services.clock import wire_utc
from app.models import AvailabilityState, Incident, InvestigationEntry, MonitoredEndpoint, NetworkEvent, SecurityEvent, Ticket, User
from app.schemas import IncidentOut, NetworkOut, SecurityOut, TicketOut
from app.services.auth import require_roles
from app.services.availability import effective_endpoint_status
from app.services.workload import recalculate_workloads

operations = require_roles("technician", "admin")
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"], dependencies=[Depends(operations)])


def recent_activity(db, tickets, incidents):
    events = []
    for page, kind, items in (("tickets", "Ticket", tickets), ("incidents", "Incident", incidents)):
        for item in items:
            events.append({"key": f"{page}-{item.id}-created", "page": page, "id": item.id,
                           "title": item.title, "label": f"{kind} created", "at": wire_utc(item.created_at)})
            if item.resolved_at:
                events.append({"key": f"{page}-{item.id}-resolved", "page": page, "id": item.id,
                               "title": item.title, "label": f"{kind} resolved", "at": wire_utc(item.resolved_at)})
    names = {item.id: item.title for item in incidents}
    entries = db.query(InvestigationEntry).filter(
        InvestigationEntry.record_type == "incident",
        InvestigationEntry.kind.in_(["Status", "Assignment", "Note", "Link"]),
    ).order_by(InvestigationEntry.created_at.desc(), InvestigationEntry.id.desc()).limit(20).all()
    for entry in entries:
        if entry.record_id not in names or (entry.kind == "Status" and entry.body.endswith(" → Resolved")):
            continue
        events.append({"key": f"investigation-{entry.id}", "page": "incidents", "id": entry.record_id,
                       "title": names[entry.record_id], "label": f"Incident {entry.kind.lower()}",
                       "at": wire_utc(entry.created_at)})
    return sorted(events, key=lambda item: (item["at"], item["key"]), reverse=True)[:6]


@router.get("")
def dashboard(db: Session = Depends(get_db), user: User = Depends(operations)):
    technicians = recalculate_workloads(db)
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
    incidents = db.query(Incident).filter(Incident.status.not_in(["Recommended", "Dismissed"])).order_by(Incident.created_at.desc(), Incident.id.desc()).all()
    network = db.query(NetworkEvent).order_by(NetworkEvent.timestamp.desc(), NetworkEvent.id.desc()).all()
    security = (db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc(), SecurityEvent.id.desc()).all()
                if user.can_view_security else [])
    availability = []
    for endpoint, state in db.query(MonitoredEndpoint, AvailabilityState).outerjoin(
        AvailabilityState, AvailabilityState.endpoint_id == MonitoredEndpoint.id
    ).order_by(MonitoredEndpoint.building):
        status, reason = effective_endpoint_status(endpoint, state)
        availability.append({"id": endpoint.id, "building": endpoint.building, "status": status,
                             "error_details": reason, "source": "Simulated Demo" if endpoint.mode == "demo" else "Live Endpoint",
                             "response_ms": state.response_ms if state and status != "Unknown" else None})
    statuses = [item["status"] for item in availability]
    campus = [item for item in availability if not test_endpoint(item["building"])]
    return {
        "metrics": {
            "open_tickets": sum(ticket.status != "Resolved" for ticket in tickets),
            "open_status_tickets": sum(ticket.status == "Open" for ticket in tickets),
            "active_incidents": sum(incident.status != "Resolved" for incident in incidents),
            "network_anomalies": sum(event.severity in {"High", "Critical"} for event in network),
            "monitored_endpoints": len(availability),
            "campus_endpoints": len(campus),
            "campus_offline_endpoints": sum(item["status"] == "Offline" for item in campus),
            "online_endpoints": statuses.count("Online"),
            "offline_endpoints": statuses.count("Offline"),
            "unknown_endpoints": statuses.count("Unknown"),
            "security_alerts": (sum(event.status != "Resolved" and event.severity in {"High", "Critical"} for event in security)
                                if user.can_view_security else None),
            "critical_issues": sum(item.priority > 75 and item.status != "Resolved" for item in [*tickets, *incidents]),
            "can_view_security": user.can_view_security,
        },
        "tickets": [TicketOut.model_validate(item) for item in tickets[:6]],
        "incidents": [IncidentOut.model_validate(item) for item in incidents[:6]],
        "network_events": [NetworkOut.model_validate(item) for item in network[:6]],
        "availability_endpoints": availability[:6],
        "security_events": [SecurityOut.model_validate(item) for item in security[:6]],
        "technicians": sorted(technicians, key=lambda item: (item.current_workload, item.name)),
        "recent_activity": recent_activity(db, tickets, incidents),
    }
