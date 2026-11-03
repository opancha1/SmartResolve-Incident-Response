from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SecurityEvent, User
from app.services.auth import require_roles
from app.schemas import SecurityCreate, SecurityOut
from app.services.intelligence import security_risk, security_severity
router=APIRouter(prefix="/api/security-events",tags=["Security"],dependencies=[Depends(require_roles("technician","admin"))])
def security_authorized(user:User=Depends(require_roles("technician","admin"))):
    if user.role!="admin" and not user.security_access: raise HTTPException(403,"Security-event access is not enabled for this account")
    return user
@router.get("",response_model=list[SecurityOut])
def list_events(q:str|None=None,db:Session=Depends(get_db),user:User=Depends(security_authorized)):
    events=db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).all();return[e for e in events if not q or q.lower() in f"{e.event_type} {e.username} {e.location}".lower()]
@router.post("",response_model=SecurityOut,status_code=201)
def create_event(data:SecurityCreate,db:Session=Depends(get_db),user:User=Depends(security_authorized)):
    score=security_risk(data.failed_attempts,data.event_type); event=SecurityEvent(**data.model_dump(),risk_score=score,severity=security_severity(score));db.add(event);db.commit();db.refresh(event);return event
@router.post("/generate/{scenario}",response_model=SecurityOut)
def generate(scenario:str,db:Session=Depends(get_db),user:User=Depends(security_authorized)):
    data=SecurityCreate(event_type="Suspicious activity" if scenario=="suspicious" else "Failed login",username="demo.student",location="Woodward",failed_attempts=7 if scenario=="suspicious" else 4);return create_event(data,db)
