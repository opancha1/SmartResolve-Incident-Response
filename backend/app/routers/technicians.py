from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.services.auth import require_roles
from app.models import Incident, Technician, Ticket, User
from app.schemas import TechnicianCreate, TechnicianOut, TechnicianUpdate
from app.services.intelligence import recommend_technician
from app.services.workload import recalculate_workloads

router=APIRouter(prefix="/api/technicians",tags=["Technicians"],dependencies=[Depends(require_roles("technician", "admin"))])

def get_technician_or_404(technician_id:int,db:Session)->Technician:
    technician=db.get(Technician,technician_id)
    if not technician: raise HTTPException(404,"Technician not found")
    return technician

@router.get("",response_model=list[TechnicianOut])
def list_technicians(db:Session=Depends(get_db)):
    technicians=recalculate_workloads(db)
    db.commit()
    return technicians

@router.get("/recommend")
def recommend(category:str,location:str,db:Session=Depends(get_db)):
    technicians=recalculate_workloads(db)
    db.commit()
    tech,explanation=recommend_technician(technicians,category,location)
    return {"technician":TechnicianOut.model_validate(tech) if tech else None,"explanation":explanation}

@router.post("",response_model=TechnicianOut,status_code=201)
def create_technician(data:TechnicianCreate,db:Session=Depends(get_db),user:User=Depends(require_roles("admin"))):
    existing=db.query(Technician).filter(Technician.name.ilike(data.name)).first()
    if existing: raise HTTPException(409,"A technician with this name already exists")
    technician=Technician(**data.model_dump(),current_workload=0)
    db.add(technician)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"A technician with this name already exists")
    db.refresh(technician)
    return technician

@router.get("/{technician_id}",response_model=TechnicianOut)
def get_technician(technician_id:int,db:Session=Depends(get_db)):
    technician=get_technician_or_404(technician_id,db)
    recalculate_workloads(db,[technician]);db.commit()
    return technician

@router.put("/{technician_id}",response_model=TechnicianOut)
def update_technician(technician_id:int,data:TechnicianUpdate,db:Session=Depends(get_db),user:User=Depends(require_roles("admin"))):
    technician=get_technician_or_404(technician_id,db)
    existing=db.query(Technician).filter(Technician.name.ilike(data.name),Technician.id!=technician_id).first()
    if existing: raise HTTPException(409,"A technician with this name already exists")
    old_name=technician.name
    values=data.model_dump()
    if old_name!=values["name"]:
        db.query(Ticket).filter(Ticket.assigned_technician==old_name).update({Ticket.assigned_technician:values["name"]},synchronize_session=False)
        db.query(Incident).filter(Incident.recommended_technician==old_name).update({Incident.recommended_technician:values["name"]},synchronize_session=False)
    for key,value in values.items(): setattr(technician,key,value)
    recalculate_workloads(db,[technician])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"A technician with this name already exists")
    db.refresh(technician)
    return technician

@router.delete("/{technician_id}",status_code=204)
def delete_technician(technician_id:int,db:Session=Depends(get_db),user:User=Depends(require_roles("admin"))):
    technician=get_technician_or_404(technician_id,db)
    active_tickets=db.query(Ticket).filter(Ticket.assigned_technician==technician.name,Ticket.status!="Resolved").count()
    active_incidents=db.query(Incident).filter(Incident.recommended_technician==technician.name,Incident.status!="Resolved").count()
    if active_tickets or active_incidents:
        raise HTTPException(409,"Cannot delete this technician because they have active assignments. Please reassign or unassign their active tickets first.")
    # Clear inactive historical string references before removal so no record
    # points to a technician that no longer exists.
    db.query(Ticket).filter(Ticket.assigned_technician==technician.name).update({Ticket.assigned_technician:None},synchronize_session=False)
    db.query(Incident).filter(Incident.recommended_technician==technician.name).update({Incident.recommended_technician:None},synchronize_session=False)
    db.delete(technician);db.commit()
