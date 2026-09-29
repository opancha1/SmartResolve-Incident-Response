from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Incident, IncidentRelationship, NetworkEvent, SecurityEvent, Ticket, Technician
from app.schemas import IncidentOut, StatusUpdate
from app.services.intelligence import cosine_similarity, recommend_technician
router=APIRouter(prefix="/api/incidents",tags=["Incidents"])
@router.get("",response_model=list[IncidentOut])
def list_incidents(q:str|None=None,db:Session=Depends(get_db)):
    items=db.query(Incident).order_by(Incident.created_at.desc()).all();return[i for i in items if not q or q.lower() in f"{i.title} {i.location} {i.category}".lower()]
@router.get("/{incident_id}")
def detail(incident_id:int,db:Session=Depends(get_db)):
    incident=db.get(Incident,incident_id)
    if not incident: raise HTTPException(404,"Incident not found")
    rels=db.query(IncidentRelationship).filter_by(incident_id=incident_id).all()
    lookup={"ticket":Ticket,"network":NetworkEvent,"security":SecurityEvent}
    evidence=[{"type":r.related_type,"reason":r.reason,"item":db.get(lookup[r.related_type],r.related_id)} for r in rels]
    return {"incident":IncidentOut.model_validate(incident),"relationships":evidence}
@router.patch("/{incident_id}/status",response_model=IncidentOut)
def update_status(incident_id:int,data:StatusUpdate,db:Session=Depends(get_db)):
    if data.status not in {"Open","Investigating","Resolved"}: raise HTTPException(422,"Status must be Open, Investigating, or Resolved")
    incident=db.get(Incident,incident_id)
    if not incident: raise HTTPException(404,"Incident not found")
    incident.status=data.status
    if data.status=="Resolved":
        if not incident.resolved_at: incident.resolved_at=datetime.utcnow()
    else: incident.resolved_at=None
    db.commit();db.refresh(incident);return incident
@router.post("/correlate")
def correlate(db:Session=Depends(get_db)):
    tickets=db.query(Ticket).filter(Ticket.status!="Resolved").all(); events=db.query(NetworkEvent).filter(NetworkEvent.severity.in_(["High","Critical"])).all()
    created=[]
    for event in events:
        related=[t for t in tickets if t.location.lower()==event.location.lower() and t.category=="Network"]
        if len(related)>=2:
            incident=db.query(Incident).filter_by(location=event.location,category="Network").filter(Incident.status!="Resolved").first()
            if not incident:
                tech, _=recommend_technician(db.query(Technician).all(),"Network",event.location)
                incident=Incident(title=f"Network disruption — {event.location}",description="Multiple related network tickets correlate with an anomalous network event.",category="Network",location=event.location,priority=min(100,60+sum(t.affected_users for t in related)*3),recommended_technician=tech.name if tech else None);db.add(incident);db.flush();created.append(incident.id)
            existing={(r.related_type,r.related_id) for r in db.query(IncidentRelationship).filter_by(incident_id=incident.id)}
            for ticket in related:
                if ("ticket",ticket.id) not in existing:db.add(IncidentRelationship(incident_id=incident.id,related_type="ticket",related_id=ticket.id,reason=f"Same location; similarity evidence {max((cosine_similarity(ticket.description,x.description) for x in related if x.id!=ticket.id),default=0):.2f}"))
            if ("network",event.id) not in existing:db.add(IncidentRelationship(incident_id=incident.id,related_type="network",related_id=event.id,reason="Network anomaly at same location"))
    db.commit();return {"created_or_updated_incidents":created,"message":"Correlation completed"}
