from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AvailabilityState, MonitoredEndpoint, Ticket, TicketMessage, User
from app.schemas import PortalTicketCreate, TicketMessageCreate, TicketOut, UserOut
from app.services.auth import require_roles
from app.services.availability import effective_status, ticket_matches_building
from app.services.intelligence import calculate_priority, classify_ticket

router = APIRouter(prefix="/api/portal", tags=["User portal"])
@router.get("/network-status")
def relevant_network_status(location:str,user:User=Depends(require_roles("user")),db:Session=Depends(get_db)):
    endpoints=db.query(MonitoredEndpoint).filter_by(enabled=True).order_by(MonitoredEndpoint.building).all()
    relevant=[endpoint for endpoint in endpoints if ticket_matches_building(location,endpoint.building)]
    result=[]
    for endpoint in relevant:
        state=db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
        status,reason=effective_status(state)
        source="Simulated Demo" if endpoint.mode=="demo" else "Live Endpoint"
        item={"building":endpoint.building,"status":status,"source":source,"last_checked_at":state.last_checked_at if state else None}
        if status=="Offline":
            item["notice"]=(f"A monitored endpoint associated with {endpoint.building} is currently Offline. "
                f"{state.consecutive_failures if state else 0} consecutive failed check(s). "
                f"Source: {source}. Your ticket can still be submitted.")
        elif status=="Unknown":
            item["notice"]=reason or "Availability could not be confirmed. Your ticket can still be submitted."
        result.append(item)
    return result
@router.get("/tickets", response_model=list[TicketOut])
def my_tickets(q: str | None = None, status: str | None = None, user: User = Depends(require_roles("user")), db: Session = Depends(get_db)):
    query = db.query(Ticket).filter(Ticket.owner_id == user.id).order_by(Ticket.created_at.desc())
    if status: query = query.filter(Ticket.status == status)
    tickets = query.all()
    return [t for t in tickets if not q or q.casefold() in f"{t.title} {t.description} {t.location}".casefold()]
@router.post("/tickets", status_code=201, response_model=TicketOut)
def create_my_ticket(data: PortalTicketCreate, user: User = Depends(require_roles("user")), db: Session = Depends(get_db)):
    category = data.category or classify_ticket(data.title, data.description)
    ticket = Ticket(**data.model_dump(exclude={"category"}), category=category, owner_id=user.id,
        priority=calculate_priority(data.affected_users, data.severity, data.location, category == "Security"))
    db.add(ticket); db.commit(); db.refresh(ticket); return ticket
@router.get("/tickets/{ticket_id}")
def ticket_detail(ticket_id: int, user: User = Depends(require_roles("user")), db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter_by(id=ticket_id, owner_id=user.id).first()
    if not ticket: raise HTTPException(404, "Ticket not found")
    messages = db.query(TicketMessage).filter_by(ticket_id=ticket.id).order_by(TicketMessage.created_at).all()
    return {"ticket": TicketOut.model_validate(ticket), "messages":[{"id":m.id,"body":m.body,"created_at":m.created_at,"author":"You" if m.user_id==user.id else "IT Support"} for m in messages]}
@router.post("/tickets/{ticket_id}/messages", status_code=201)
def add_message(ticket_id: int, data: TicketMessageCreate, user: User = Depends(require_roles("user")), db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter_by(id=ticket_id, owner_id=user.id).first()
    if not ticket: raise HTTPException(404, "Ticket not found")
    message = TicketMessage(ticket_id=ticket_id, user_id=user.id, body=data.body.strip())
    db.add(message); db.commit(); db.refresh(message)
    return {"id":message.id,"body":message.body,"created_at":message.created_at}
@router.post("/assistant")
def assistant(data: dict, user: User = Depends(require_roles("user")), db: Session = Depends(get_db)):
    # Controlled no-LLM fallback; it suggests safe checks and never performs actions.
    message = str(data.get("message", "")).strip()[:2000]
    if not message: raise HTTPException(422, "Message is required")
    low = message.lower()
    if any(word in low for word in ("wifi", "wi-fi", "internet", "network")):
        reply = "I’m using the rule-based support guide. Please check whether other devices in the same room can connect, then toggle Wi-Fi off and on. What building and room are you in, and is this affecting anyone else?"
    elif any(word in low for word in ("projector", "display", "monitor", "screen")):
        reply = "I’m using the rule-based support guide. Check that the display input matches the connected cable, then reconnect the cable and use your device’s display mirror shortcut. What building and room is this in, and what device are you connecting?"
    elif any(word in low for word in ("password", "login", "account", "sign in")):
        reply = "I’m using the rule-based support guide. Confirm your username and try the official password reset flow. Don’t share your password here. Are you seeing an error message, and which service is affected?"
    else:
        reply = "I’m using the rule-based support guide. Tell me what you were trying to do, what happened instead, and the building and room. I can suggest a check or help prepare a support ticket."
    return {"reply":reply,"mode":"rule-based","ticket_created":False}
