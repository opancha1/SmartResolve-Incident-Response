from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator

TechnicianSpecialization=Literal["Network","Security","Hardware","Software","Classroom Technology"]
TechnicianLocation=Literal["Woodward","Atkins","Mebane","Grainger","Friday","Science Hall","Campus Center","Library"]

class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3)
    location: str = Field(min_length=2, max_length=100)
    affected_users: int = Field(default=1, ge=1, le=10000)
    category: str | None = None
    severity: Literal["Low","Medium","High","Critical"] = "Medium"
class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    description: str | None = Field(default=None, min_length=3)
    location: str | None = Field(default=None, min_length=2, max_length=100)
    affected_users: int | None = Field(default=None, ge=1, le=10000)
    status: Literal["Open","Investigating","Resolved"] | None = None
    severity: Literal["Low","Medium","High","Critical"] | None = None
class TicketOut(BaseModel):
    id:int; title:str; description:str; category:str; priority:int; location:str; affected_users:int; severity:str; status:str; assigned_technician:str|None; created_at:datetime; resolved_at:datetime|None
    model_config = {"from_attributes": True}

class EventNetworkCreate(BaseModel):
    location:str; latency:float=Field(ge=0); packet_loss:float=Field(ge=0, le=100); availability:bool=True; event_type:str="Network check"
class NetworkOut(EventNetworkCreate):
    id:int; severity:str; timestamp:datetime
    model_config={"from_attributes":True}
class SecurityCreate(BaseModel):
    event_type:str; username:str; location:str; failed_attempts:int=Field(default=0, ge=0)
class SecurityOut(SecurityCreate):
    id:int; risk_score:int; severity:str; timestamp:datetime
    model_config={"from_attributes":True}
class TechnicianOut(BaseModel):
    id:int; name:str; specialization:str; location:str; current_workload:int; availability:bool
    model_config={"from_attributes":True}
class TechnicianCreate(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    specialization:TechnicianSpecialization
    location:TechnicianLocation
    availability:bool
    @field_validator("name")
    @classmethod
    def trim_name(cls,value):
        value=value.strip()
        if not value: raise ValueError("Technician name is required")
        return value
class TechnicianUpdate(TechnicianCreate):
    pass
class IncidentOut(BaseModel):
    id:int; title:str; description:str; category:str; location:str; priority:int; status:str; recommended_technician:str|None; created_at:datetime; resolved_at:datetime|None
    model_config={"from_attributes":True}
class StatusUpdate(BaseModel): status:str
class TechnicianAssignment(BaseModel): technician_id:int
