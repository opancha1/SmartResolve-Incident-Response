from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SecurityEvent
from app.schemas import SecurityCreate, SecurityOut
from app.services.intelligence import security_risk, security_severity
router=APIRouter(prefix="/api/security-events",tags=["Security"])
@router.get("",response_model=list[SecurityOut])
def list_events(q:str|None=None,db:Session=Depends(get_db)):
    events=db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).all();return[e for e in events if not q or q.lower() in f"{e.event_type} {e.username} {e.location}".lower()]
@router.post("",response_model=SecurityOut,status_code=201)
def create_event(data:SecurityCreate,db:Session=Depends(get_db)):
    score=security_risk(data.failed_attempts,data.event_type); event=SecurityEvent(**data.model_dump(),risk_score=score,severity=security_severity(score));db.add(event);db.commit();db.refresh(event);return event
@router.post("/generate/{scenario}",response_model=SecurityOut)
def generate(scenario:str,db:Session=Depends(get_db)):
    data=SecurityCreate(event_type="Suspicious activity" if scenario=="suspicious" else "Failed login",username="demo.student",location="Woodward",failed_attempts=7 if scenario=="suspicious" else 4);return create_event(data,db)
