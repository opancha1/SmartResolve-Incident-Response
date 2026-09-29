from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Incident, NetworkEvent, SecurityEvent, Technician, Ticket
from app.services.workload import recalculate_workloads
router=APIRouter(prefix="/api/dashboard",tags=["Dashboard"])
@router.get("")
def dashboard(db:Session=Depends(get_db)):
    recalculate_workloads(db)
    tickets=db.query(Ticket).order_by(Ticket.created_at.desc()).all(); incidents=db.query(Incident).order_by(Incident.created_at.desc()).all(); network=db.query(NetworkEvent).order_by(NetworkEvent.timestamp.desc()).all(); security=db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).all()
    critical = sum(t.priority > 75 and t.status != "Resolved" for t in tickets) + sum(i.priority > 75 and i.status != "Resolved" for i in incidents)
    return {"metrics":{"open_tickets":sum(t.status!="Resolved" for t in tickets),"active_incidents":sum(i.status!="Resolved" for i in incidents),"network_anomalies":sum(n.severity in ["High","Critical"] for n in network),"security_alerts":sum(s.severity in ["High","Critical"] for s in security),"critical_issues":critical},"tickets":tickets[:6],"incidents":incidents[:6],"network_events":network[:6],"security_events":security[:6],"technicians":db.query(Technician).order_by(Technician.current_workload).all()}
