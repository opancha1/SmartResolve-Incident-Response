from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import Technician, Ticket

def recalculate_workloads(db:Session,technicians:list[Technician]|None=None)->list[Technician]:
    """Synchronize the cached workload column from active ticket assignments."""
    db.flush()
    technicians=technicians if technicians is not None else db.query(Technician).all()
    assigned=db.query(Ticket.assigned_technician,func.count(Ticket.id)).filter(
        Ticket.status!="Resolved",Ticket.assigned_technician.is_not(None)
    ).group_by(Ticket.assigned_technician).all()
    counts=dict(assigned)
    changed=False
    for tech in technicians:
        count=int(counts.get(tech.name,0))
        if tech.current_workload!=count:
            tech.current_workload=count
            changed=True
    if changed: db.flush()
    return technicians
