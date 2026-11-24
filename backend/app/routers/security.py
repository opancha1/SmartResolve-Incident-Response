from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Incident, IncidentRelationship, SecurityEvent, Ticket, User
from app.schemas import InvestigationUpdate, SecurityCreate, SecurityOut
from app.services.auth import require_roles
from app.services.demo_config import demo_enabled
from app.services.intelligence import security_factors, security_risk, security_severity
from app.services.investigations import timeline, update_investigation

DEMO_EVIDENCE = {
    "Multiple failed login attempts": "The simulator recorded repeated rejected sign-ins for the same fictional account.",
    "Suspicious authentication activity": "Rejected sign-ins clustered in the same simulated investigation window.",
    "Account lockout": "The synthetic identity provider recorded a lockout after repeated rejected sign-ins.",
    "Potential phishing report": "A fictional requester reported an unexpected credential prompt. No interaction was confirmed.",
    "Unusual login location": "The simulator detected a sign-in location outside the fictional account’s usual pattern.",
    "Unusual account activity": "The simulator recorded sign-in activity outside the fictional account’s normal schedule.",
    "Suspicious endpoint activity": "The fictional lab device produced an activity signal during the same investigation window.",
    "Unauthorized access attempt": "The synthetic audit trail recorded a denied attempt to access a restricted resource.",
}

router = APIRouter(prefix="/api/security-events", tags=["Security"])


def security_authorized(user: User = Depends(require_roles("technician", "admin"))):
    if not user.can_view_security:
        raise HTTPException(403, "Security-event access is not enabled for this account")
    return user


@router.get("")
def list_events(q: str | None = None, db: Session = Depends(get_db), user: User = Depends(security_authorized)):
    events = db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc(), SecurityEvent.id.desc()).all()
    links = dict(db.query(IncidentRelationship.related_id, func.count()).filter_by(related_type="security")
                 .group_by(IncidentRelationship.related_id).all())
    return [{**SecurityOut.model_validate(event).model_dump(mode="json"), "incident_count": links.get(event.id, 0)}
            for event in events if not q or q.casefold() in f"{event.event_type} {event.username} {event.location}".casefold()]


def create_event(data: SecurityCreate, db: Session):
    score = security_risk(data.failed_attempts, data.event_type)
    event = SecurityEvent(**data.model_dump(), risk_score=score, severity=security_severity(score))
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post("", response_model=SecurityOut, status_code=201)
def submit_event(data: SecurityCreate, db: Session = Depends(get_db), user: User = Depends(security_authorized)):
    return create_event(data, db)


@router.post("/generate/{scenario}", response_model=SecurityOut)
def generate(scenario: str, db: Session = Depends(get_db), user: User = Depends(security_authorized)):
    if not demo_enabled():
        raise HTTPException(404, "Demo mode is disabled")
    from app.routers.demo import execute, DemoAction
    if scenario not in {"suspicious", "failed-login"}:
        raise HTTPException(404, "Unknown demo scenario")
    execute("suspicious-login", DemoAction(), db, user)
    key = "suspicious-login:event:2" if scenario == "suspicious" else "suspicious-login:event:1"
    return db.query(SecurityEvent).filter_by(demo_key=key).one()


def get_event(db, event_id):
    event = db.get(SecurityEvent, event_id)
    if not event:
        raise HTTPException(404, "Security event not found")
    return event


@router.get("/{event_id}")
def detail(event_id: int, db: Session = Depends(get_db), user: User = Depends(security_authorized)):
    event = get_event(db, event_id)
    incident_ids = db.query(IncidentRelationship.incident_id).filter_by(related_type="security", related_id=event_id)
    incidents = db.query(Incident.id, Incident.title).filter(Incident.id.in_(incident_ids.statement)).all()
    ticket_ids = db.query(IncidentRelationship.related_id).filter(
        IncidentRelationship.related_type == "ticket", IncidentRelationship.incident_id.in_(incident_ids.statement))
    tickets = db.query(Ticket.id, Ticket.title).filter(Ticket.id.in_(ticket_ids.statement)).all()
    evidence = [f"{event.failed_attempts} failed attempts reported"]
    if event.evidence_note:
        evidence.append(event.evidence_note)
    elif event.demo_key and event.event_type in DEMO_EVIDENCE:
        evidence.append(DEMO_EVIDENCE[event.event_type])
    return {
        "event": SecurityOut.model_validate(event),
        "risk_factors": security_factors(event.failed_attempts, event.event_type),
        "description": f"{event.event_type} recorded for {event.username}.",
        "evidence": evidence,
        "recommended_steps": ["Review related reports and the authentication timeline.",
                              "Verify account activity through the approved identity support process.",
                              "Record findings and review the incident before closure."],
        "incidents": [row._asdict() for row in incidents], "tickets": [row._asdict() for row in tickets],
        "timeline": timeline(db, "security", event_id),
    }


@router.patch("/{event_id}", response_model=SecurityOut)
def update(event_id: int, data: InvestigationUpdate, db: Session = Depends(get_db),
           user: User = Depends(security_authorized)):
    event = get_event(db, event_id)
    update_investigation(db, "security", event, data, user)
    db.commit()
    return event
