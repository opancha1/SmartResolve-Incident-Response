from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth import require_roles
from app.models import AvailabilityState, Incident, MonitoredEndpoint, NetworkEvent, SecurityEvent, Technician, Ticket, User
from app.services.workload import recalculate_workloads
from app.services.availability import effective_endpoint_status
router=APIRouter(prefix="/api/dashboard",tags=["Dashboard"],dependencies=[Depends(require_roles("technician", "admin"))])
@router.get("")
def dashboard(db:Session=Depends(get_db),user:User=Depends(require_roles("technician","admin"))):
    recalculate_workloads(db)
    tickets=db.query(Ticket).order_by(Ticket.created_at.desc()).all(); incidents=db.query(Incident).order_by(Incident.created_at.desc()).all(); network=db.query(NetworkEvent).order_by(NetworkEvent.timestamp.desc()).all(); security=db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).all()
    endpoints=db.query(MonitoredEndpoint).all()
    availability={endpoint.id:(db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()) for endpoint in endpoints}
    endpoint_statuses=[effective_endpoint_status(endpoint,availability[endpoint.id])[0] for endpoint in endpoints]
    critical = sum(t.priority > 75 and t.status != "Resolved" for t in tickets) + sum(i.priority > 75 and i.status != "Resolved" for i in incidents)
    can_view_security=user.role=="admin" or user.security_access
    return {"metrics":{"open_tickets":sum(t.status!="Resolved" for t in tickets),"active_incidents":sum(i.status!="Resolved" for i in incidents),"network_anomalies":sum(n.severity in ["High","Critical"] for n in network),"monitored_endpoints":len(endpoints),"online_endpoints":endpoint_statuses.count("Online"),"offline_endpoints":endpoint_statuses.count("Offline"),"unknown_endpoints":endpoint_statuses.count("Unknown"),"security_alerts":sum(s.severity in ["High","Critical"] for s in security) if can_view_security else None,"critical_issues":critical,"can_view_security":can_view_security},"tickets":tickets[:6],"incidents":incidents[:6],"network_events":network[:6],"availability_endpoints":[{"id":endpoint.id,"building":endpoint.building,"status":effective_endpoint_status(endpoint,availability[endpoint.id])[0],"error_details":effective_endpoint_status(endpoint,availability[endpoint.id])[1],"source":"Simulated Demo" if endpoint.mode=="demo" else "Live Endpoint","response_ms":availability[endpoint.id].response_ms if availability[endpoint.id] and effective_endpoint_status(endpoint,availability[endpoint.id])[0]!="Unknown" else None} for endpoint in endpoints[:6]],"security_events":security[:6] if can_view_security else [],"technicians":db.query(Technician).order_by(Technician.current_workload).all()}
