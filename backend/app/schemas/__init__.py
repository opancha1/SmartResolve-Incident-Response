from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

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

class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)
class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    can_view_security: bool = False
    model_config = {"from_attributes": True}
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=20)

class PortalTicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=5000)
    location: str = Field(min_length=2, max_length=100)
    category: str | None = None
    affected_users: int = Field(default=1, ge=1, le=10000)
    severity: Literal["Low","Medium","High","Critical"] = "Medium"
class TicketMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=3000)

class AvailabilityEndpointCreate(BaseModel):
    building: str = Field(min_length=2, max_length=160)
    mode: Literal["demo","live"] = "demo"
    target_url: str | None = Field(default=None, max_length=500)
    timeout_seconds: float = Field(default=2.0, ge=0.5, le=10)
    failure_threshold: int = Field(default=2, ge=1, le=10)
    demo_scenario: Literal["online","offline","unknown","cycle"] = "online"
    enabled: bool = True
    @field_validator("building")
    @classmethod
    def trim_building(cls,value):
        value=value.strip()
        if not value: raise ValueError("Building name is required")
        return value
    @model_validator(mode="after")
    def validate_mode_target(self):
        if self.mode=="live" and not self.target_url: raise ValueError("Live endpoints require an approved target URL")
        if self.mode=="demo" and self.target_url: raise ValueError("Demo endpoints cannot specify a live target URL")
        return self
class AvailabilityEndpointOut(BaseModel):
    id:int; building:str; mode:str; source:str; enabled:bool; failure_threshold:int
    monitor_interval_seconds:int
    status:str; consecutive_failures:int; last_checked_at:datetime|None
    last_success_at:datetime|None; response_ms:float|None; error_details:str|None
    open_ticket_count:int=0; related_tickets:list[TicketOut]=Field(default_factory=list)
class AvailabilityCheckOut(BaseModel):
    id:int; result:str; status_after_check:str; response_ms:float|None; error_details:str|None; checked_at:datetime
    model_config={"from_attributes":True}
