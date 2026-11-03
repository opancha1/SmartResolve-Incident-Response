from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AvailabilityCheck, AvailabilityState, Incident, IncidentRelationship, MonitoredEndpoint, Technician, Ticket, User
from app.schemas import AvailabilityCheckOut, AvailabilityEndpointCreate, AvailabilityEndpointOut, IncidentOut, TicketOut
from app.services.auth import require_roles
from app.services.availability import (AvailabilityRateLimited, related_open_tickets,
    effective_endpoint_status, monitor_interval_seconds, run_check, validate_live_target)
from app.services.intelligence import calculate_priority, recommend_technician

router=APIRouter(prefix="/api/network-availability",tags=["Network Availability"],
    dependencies=[Depends(require_roles("technician","admin"))])

def get_endpoint_or_404(endpoint_id:int,db:Session)->MonitoredEndpoint:
    endpoint=db.get(MonitoredEndpoint,endpoint_id)
    if not endpoint: raise HTTPException(404,"Monitored endpoint not found")
    return endpoint

def to_output(endpoint:MonitoredEndpoint,db:Session,include_tickets:bool=True)->AvailabilityEndpointOut:
    state=db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
    status,reason=effective_endpoint_status(endpoint,state)
    tickets=related_open_tickets(db,endpoint.building) if include_tickets else []
    return AvailabilityEndpointOut(id=endpoint.id,building=endpoint.building,mode=endpoint.mode,
        source="Simulated Demo" if endpoint.mode=="demo" else "Live Endpoint",enabled=endpoint.enabled,
        failure_threshold=endpoint.failure_threshold,status=status,
        monitor_interval_seconds=monitor_interval_seconds(),
        consecutive_failures=state.consecutive_failures if state else 0,
        last_checked_at=state.last_checked_at if state else None,last_success_at=state.last_success_at if state else None,
        response_ms=state.response_ms if state and status!="Unknown" else None,error_details=reason,
        open_ticket_count=len(tickets),related_tickets=[TicketOut.model_validate(t) for t in tickets])

@router.get("",response_model=list[AvailabilityEndpointOut])
def list_endpoints(db:Session=Depends(get_db)):
    endpoints=db.query(MonitoredEndpoint).order_by(MonitoredEndpoint.building).all()
    return [to_output(endpoint,db) for endpoint in endpoints]

@router.post("/{endpoint_id}/check",response_model=AvailabilityEndpointOut)
def check_endpoint(endpoint_id:int,db:Session=Depends(get_db)):
    endpoint=get_endpoint_or_404(endpoint_id,db)
    try:
        run_check(db,endpoint)
        db.commit()
    except AvailabilityRateLimited as exc:
        db.rollback();raise HTTPException(429,str(exc))
    except Exception:
        db.rollback();raise HTTPException(500,"The availability check could not be saved")
    db.refresh(endpoint)
    return to_output(endpoint,db)

@router.get("/{endpoint_id}/history",response_model=list[AvailabilityCheckOut])
def check_history(endpoint_id:int,limit:int=50,db:Session=Depends(get_db)):
    endpoint=get_endpoint_or_404(endpoint_id,db)
    limit=max(1,min(limit,100))
    return db.query(AvailabilityCheck).filter_by(endpoint_id=endpoint.id).order_by(AvailabilityCheck.checked_at.desc()).limit(limit).all()

@router.get("/{endpoint_id}/suggestion")
def incident_suggestion(endpoint_id:int,db:Session=Depends(get_db)):
    endpoint=get_endpoint_or_404(endpoint_id,db)
    state=db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
    status,_=effective_endpoint_status(endpoint,state)
    tickets=related_open_tickets(db,endpoint.building)
    eligible=bool(state and status=="Offline" and len(tickets)>=2)
    ticket_ids={ticket.id for ticket in tickets}
    active_incidents=[]
    if eligible:
        for incident in db.query(Incident).filter(Incident.status!="Resolved",Incident.category=="Network").all():
            linked=db.query(IncidentRelationship).filter_by(incident_id=incident.id,related_type="ticket").all()
            if ticket_ids.intersection({item.related_id for item in linked}): active_incidents.append(incident)
    reason=(f"{endpoint.building} endpoint is Offline after {state.consecutive_failures} consecutive failed checks; "
            f"{len(tickets)} open ticket(s) match the building.") if eligible else None
    return {"suggested":eligible,"reason":reason,"endpoint":{"id":endpoint.id,"building":endpoint.building,
        "status":status,"source":"Simulated Demo" if endpoint.mode=="demo" else "Live Endpoint",
        "consecutive_failures":state.consecutive_failures if state else 0,"failure_threshold":endpoint.failure_threshold,
        "last_checked_at":state.last_checked_at if state else None},
        "tickets":[TicketOut.model_validate(ticket) for ticket in tickets],
        "existing_incident":IncidentOut.model_validate(active_incidents[0]) if active_incidents else None}

@router.post("/{endpoint_id}/incident")
def create_or_link_incident(endpoint_id:int,db:Session=Depends(get_db)):
    endpoint=get_endpoint_or_404(endpoint_id,db)
    state=db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
    status,_=effective_endpoint_status(endpoint,state)
    tickets=related_open_tickets(db,endpoint.building)
    if not state or status!="Offline" or len(tickets)<2:
        raise HTTPException(409,"Review requires an Offline endpoint and at least two matching open tickets")
    ticket_ids={ticket.id for ticket in tickets}
    existing=None
    for incident in db.query(Incident).filter(Incident.status!="Resolved",Incident.category=="Network").all():
        linked=db.query(IncidentRelationship).filter_by(incident_id=incident.id,related_type="ticket").all()
        if ticket_ids.intersection({item.related_id for item in linked}):
            existing=incident;break
    created=existing is None
    if existing:
        incident=existing
    else:
        tech,_=recommend_technician(db.query(Technician).all(),"Network",endpoint.building)
        priority=calculate_priority(sum(ticket.affected_users for ticket in tickets),"High",endpoint.building,evidence=True)
        incident=Incident(title=f"Possible network outage — {endpoint.building}",
            description=f"Technician-reviewed correlation suggestion. Evidence: {endpoint.building} monitored endpoint is Offline after {state.consecutive_failures} consecutive failed checks (threshold {endpoint.failure_threshold}); last checked {state.last_checked_at.isoformat() if state.last_checked_at else 'unknown'}. Related ticket locations match this building. Monitoring source: {'simulated demo' if endpoint.mode=='demo' else 'live endpoint'}.",
            category="Network",location=endpoint.building,priority=priority,
            recommended_technician=tech.name if tech else None,status="Open")
        db.add(incident);db.flush()
    existing_relations={(rel.related_type,rel.related_id) for rel in db.query(IncidentRelationship).filter_by(incident_id=incident.id).all()}
    linked_ids=[]
    for ticket in tickets:
        if ("ticket",ticket.id) not in existing_relations:
            db.add(IncidentRelationship(incident_id=incident.id,related_type="ticket",related_id=ticket.id,
                reason=f"Open ticket at {ticket.location}; same building as Offline monitored endpoint."))
        linked_ids.append(ticket.id)
    if ("availability",endpoint.id) not in existing_relations:
        db.add(IncidentRelationship(incident_id=incident.id,related_type="availability",related_id=endpoint.id,
            reason=f"{endpoint.building}: Offline after {state.consecutive_failures} consecutive failed checks; source is {'Simulated Demo' if endpoint.mode=='demo' else 'Live Endpoint'}."))
    db.commit();db.refresh(incident)
    return {"created":created,"incident":IncidentOut.model_validate(incident),"linked_ticket_ids":linked_ids}

@router.post("/endpoints",response_model=AvailabilityEndpointOut,status_code=201,
    dependencies=[Depends(require_roles("admin"))])
def add_endpoint(data:AvailabilityEndpointCreate,db:Session=Depends(get_db)):
    if db.query(MonitoredEndpoint).filter_by(building=data.building).first(): raise HTTPException(409,"A monitored endpoint already exists for this building")
    if data.mode=="live":
        try: validate_live_target(data.target_url or "")
        except ValueError as exc: raise HTTPException(422,str(exc))
    endpoint=MonitoredEndpoint(**data.model_dump());db.add(endpoint);db.flush()
    db.add(AvailabilityState(endpoint_id=endpoint.id,status="Unknown",consecutive_failures=0,
        error_details="No health check has run yet."))
    db.commit();db.refresh(endpoint);return to_output(endpoint,db)

@router.put("/endpoints/{endpoint_id}",response_model=AvailabilityEndpointOut,
    dependencies=[Depends(require_roles("admin"))])
def update_endpoint(endpoint_id:int,data:AvailabilityEndpointCreate,db:Session=Depends(get_db)):
    endpoint=get_endpoint_or_404(endpoint_id,db)
    duplicate=db.query(MonitoredEndpoint).filter(MonitoredEndpoint.building==data.building,MonitoredEndpoint.id!=endpoint_id).first()
    if duplicate: raise HTTPException(409,"A monitored endpoint already exists for this building")
    if data.mode=="live":
        try: validate_live_target(data.target_url or "")
        except ValueError as exc: raise HTTPException(422,str(exc))
    state=db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
    if state:
        # A new scenario/target must not inherit availability from the old one.
        state.status="Unknown";state.consecutive_failures=0;state.last_checked_at=None
        state.last_success_at=None;state.response_ms=None
        state.error_details="Configuration changed; run a new availability check."
    for key,value in data.model_dump().items(): setattr(endpoint,key,value)
    db.commit();db.refresh(endpoint);return to_output(endpoint,db)
