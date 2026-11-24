from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth import require_roles
from app.models import IncidentRelationship, Ticket, Technician, TicketMessage, User
from app.services.workload import recalculate_workloads
from app.schemas import TicketCreate, TicketOut, TicketUpdate, TechnicianAssignment, TicketMessageCreate
from app.services.intelligence import calculate_priority, classify_ticket, classification_details, priority_factors, recommend_technician

from app.services.correlation import active_overlap, similar_tickets

router=APIRouter(prefix="/api/tickets", tags=["Tickets"], dependencies=[Depends(require_roles("technician", "admin"))])
@router.get("", response_model=list[TicketOut])
def list_tickets(q:str|None=None, status:str|None=None, db:Session=Depends(get_db)):
    items=db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return [t for t in items if (not q or q.lower() in f"{t.title} {t.description} {t.location}".lower()) and (not status or t.status==status)]
@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(data:TicketCreate, db:Session=Depends(get_db)):
    category=data.category or classify_ticket(data.title, data.description)
    ticket=Ticket(**data.model_dump(exclude={"category"}), category=category, classification_corrected=bool(data.category), priority=calculate_priority(data.affected_users,data.severity,data.location,category=="Security"))
    db.add(ticket); db.commit(); db.refresh(ticket); return ticket
@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id:int, db:Session=Depends(get_db)):
    ticket=db.get(Ticket,ticket_id)
    if not ticket: raise HTTPException(404,"Ticket not found")
    return ticket
@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id:int,data:TicketUpdate,db:Session=Depends(get_db)):
    ticket=db.get(Ticket,ticket_id)
    if not ticket: raise HTTPException(404,"Ticket not found")
    changes=data.model_dump(exclude_none=True, exclude={"severity"})
    if data.status is not None and data.status not in {"Open","Investigating","Resolved"}:
        raise HTTPException(422,"Status must be Open, Investigating, or Resolved")
    for key,value in changes.items(): setattr(ticket,key,value)
    if "category" in changes:
        ticket.classification_corrected=True
    elif not ticket.classification_corrected and ("title" in changes or "description" in changes):
        ticket.category=classify_ticket(ticket.title,ticket.description)
    if data.severity is not None: ticket.severity=data.severity
    if data.severity is not None or "affected_users" in changes or "location" in changes or "title" in changes or "description" in changes or "category" in changes:
        ticket.priority=calculate_priority(ticket.affected_users,ticket.severity,ticket.location,ticket.category=="Security", has_evidence(db, ticket.id))
    if ticket.status=="Resolved":
        if not ticket.resolved_at: ticket.resolved_at=datetime.utcnow()
    else: ticket.resolved_at=None
    recalculate_workloads(db)
    db.commit(); db.refresh(ticket); return ticket
@router.post("/{ticket_id}/resolve", response_model=TicketOut)
def resolve_ticket(ticket_id:int,db:Session=Depends(get_db)):
    return update_ticket(ticket_id,TicketUpdate(status="Resolved"),db)

@router.post("/{ticket_id}/assign",response_model=TicketOut)
def assign_ticket(ticket_id:int,data:TechnicianAssignment,db:Session=Depends(get_db)):
    ticket=db.get(Ticket,ticket_id)
    if not ticket: raise HTTPException(404,"Ticket not found")
    tech=db.get(Technician,data.technician_id)
    if not tech: raise HTTPException(404,"Technician not found")
    if not tech.availability: raise HTTPException(409,"Technician is unavailable")
    if ticket.assigned_technician == tech.name: return ticket
    ticket.assigned_technician=tech.name
    recalculate_workloads(db)
    db.commit();db.refresh(ticket);return ticket

@router.delete("/{ticket_id}/assign",response_model=TicketOut)
def unassign_ticket(ticket_id:int,db:Session=Depends(get_db)):
    ticket=db.get(Ticket,ticket_id)
    if not ticket: raise HTTPException(404,"Ticket not found")
    if ticket.assigned_technician:
        ticket.assigned_technician=None
    recalculate_workloads(db)
    db.commit();db.refresh(ticket);return ticket

@router.post("/{ticket_id}/messages",status_code=201)
def add_technician_message(ticket_id:int,data:TicketMessageCreate,db:Session=Depends(get_db),user:User=Depends(require_roles("technician","admin"))):
    ticket=db.get(Ticket,ticket_id)
    if not ticket: raise HTTPException(404,"Ticket not found")
    message=TicketMessage(ticket_id=ticket_id,user_id=user.id,body=data.body.strip())
    db.add(message);db.commit();db.refresh(message)
    return {"id":message.id,"body":message.body,"created_at":message.created_at,"author":user.full_name}

@router.get("/{ticket_id}/messages")
def list_ticket_messages(ticket_id:int,db:Session=Depends(get_db)):
    if not db.get(Ticket,ticket_id): raise HTTPException(404,"Ticket not found")
    messages=db.query(TicketMessage).filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
    return [{"id":m.id,"body":m.body,"created_at":m.created_at,"author":(db.get(User,m.user_id).full_name if db.get(User,m.user_id) else "IT Support")} for m in messages]

def has_evidence(db, ticket_id):
    incident = active_overlap(db, [ticket_id])
    return bool(incident and db.query(IncidentRelationship).filter(
        IncidentRelationship.incident_id == incident.id,
        IncidentRelationship.related_type.in_(["availability", "network", "security"]),
    ).first())


@router.get("/{ticket_id}/intelligence")
def intelligence(ticket_id: int, db: Session = Depends(get_db)):
    ticket = get_ticket(ticket_id, db)
    matches = similar_tickets(db, ticket)
    classification = classification_details(ticket.title, ticket.description)
    factors = priority_factors(ticket.affected_users, ticket.severity, ticket.location, ticket.category == "Security",
                               has_evidence(db, ticket.id))
    technician, explanation = recommend_technician(recalculate_workloads(db), ticket.category, ticket.location)
    incident = active_overlap(db, [ticket.id])
    return {
        "classification": {**classification, "assigned_category": ticket.category, "corrected": ticket.classification_corrected},
        "priority": {"stored_score": ticket.priority, "suggested_score": min(100, sum(factors.values())), "factors": factors},
        "matches": matches,
        "reported_impact": {"ticket": ticket.affected_users,
                            "related_total": ticket.affected_users + sum(item["affected_users"] for item in matches if item["same_building"] and not item["possible_duplicate"])},
        "incident": {"id": incident.id, "title": incident.title} if incident else None,
        "recommend_grouping": not incident and any(item["same_building"] for item in matches),
        "technician": {"id": technician.id, "name": technician.name, "reason": explanation} if technician else None,
    }
