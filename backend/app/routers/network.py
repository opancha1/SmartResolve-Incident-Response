from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import NetworkEvent
from app.schemas import EventNetworkCreate, NetworkOut
from app.services.intelligence import network_severity, network_reason
router=APIRouter(prefix="/api/network-events", tags=["Network"])
DEMO_LOCATIONS=("Atkins","Mebane","Grainger","Friday")
@router.get("", response_model=list[NetworkOut])
def list_events(q:str|None=None,db:Session=Depends(get_db)):
    events=db.query(NetworkEvent).order_by(NetworkEvent.timestamp.desc()).all(); return [e for e in events if not q or q.lower() in f"{e.location} {e.event_type} {e.severity}".lower()]
@router.post("", response_model=NetworkOut, status_code=201)
def create_event(data:EventNetworkCreate,db:Session=Depends(get_db)):
    event=NetworkEvent(**data.model_dump(),severity=network_severity(data.latency,data.packet_loss,data.availability)); db.add(event);db.commit();db.refresh(event);return event
@router.post("/generate/{scenario}",response_model=NetworkOut)
def generate(scenario:str,location:str|None=None,db:Session=Depends(get_db)):
    options={"normal":(28,0.1,True,"Routine network check"),"latency":(240,21,True,"High latency and packet loss"),"packet-loss":(70,21,True,"High packet loss"),"unavailable":(0,100,False,"Service unavailable"),"failure":(180,35,False,"Connection failure")}
    latency,loss,available,event_type=options.get(scenario,options["normal"])
    if not location:
        building_events=db.query(NetworkEvent).filter(NetworkEvent.location.in_(DEMO_LOCATIONS)).count()
        location=DEMO_LOCATIONS[building_events%len(DEMO_LOCATIONS)]
    return create_event(EventNetworkCreate(location=location,latency=latency,packet_loss=loss,availability=available,event_type=event_type),db)
@router.get("/{event_id}/reason")
def anomaly_reason(event_id:int,db:Session=Depends(get_db)):
    event=db.get(NetworkEvent,event_id)
    if not event: from fastapi import HTTPException; raise HTTPException(404,"Network event not found")
    return {"reason":network_reason(event)}
