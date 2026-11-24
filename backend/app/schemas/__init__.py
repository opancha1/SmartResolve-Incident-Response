from app.services.clock import UtcTimestamp
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

TechnicianSpecialization=Literal["Network","Security","Hardware","Software","Classroom Technology","Account"]
TechnicianLocation=Literal["Woodward","Atkins","Mebane","Grainger","Friday","Science Hall","Campus Center","Library"]

TicketCategory = Literal["Network", "Hardware", "Software", "Classroom Technology", "Account", "Security", "Printing and Scanning", "Email and Collaboration", "Other"]

class TicketCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=5000)
    location: str = Field(min_length=2, max_length=100)
    affected_users: int = Field(default=1, ge=1, le=10000)
    category: TicketCategory | None = None
    severity: Literal["Low","Medium","High","Critical"] = "Medium"
class TicketUpdate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    category: TicketCategory | None = None
    title: str | None = Field(default=None, min_length=3, max_length=160)
    description: str | None = Field(default=None, min_length=3, max_length=5000)
    location: str | None = Field(default=None, min_length=2, max_length=100)
    affected_users: int | None = Field(default=None, ge=1, le=10000)
    status: Literal["Open","Investigating","Resolved"] | None = None
    severity: Literal["Low","Medium","High","Critical"] | None = None
class TicketOut(BaseModel):
    updated_at: UtcTimestamp | None = None
    demo_key: str | None = None
    id:int; title:str; description:str; category:str; priority:int; location:str; affected_users:int; severity:str; status:str; assigned_technician:str|None; created_at:UtcTimestamp; resolved_at:UtcTimestamp|None
    model_config = {"from_attributes": True}

class EventNetworkCreate(BaseModel):
    location:str; latency:float=Field(ge=0); packet_loss:float=Field(ge=0, le=100); availability:bool=True; event_type:str="Network check"
class NetworkOut(EventNetworkCreate):
    id:int; severity:str; timestamp:UtcTimestamp
    demo_key: str | None = None
    model_config={"from_attributes":True}
class SecurityCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    event_type: str = Field(min_length=3, max_length=80)
    username: str = Field(min_length=2, max_length=100)
    location: str = Field(default="", max_length=100)
    failed_attempts: int = Field(default=0, ge=0, le=1000000)
class SecurityOut(SecurityCreate):
    demo_key: str | None = None
    status: str = "Open"
    assigned_technician: str | None = None
    resolution: str | None = None
    id:int; risk_score:int; severity:str; timestamp:UtcTimestamp
    model_config={"from_attributes":True}
class TechnicianOut(BaseModel):
    demo_key: str | None = None
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
    updated_at: UtcTimestamp | None = None
    demo_context: bool = False
    demo_key: str | None = None
    assigned_technician: str | None = None
    resolution: str | None = None
    confirmed_cause: str | None = None
    id:int; title:str; description:str; category:str; location:str; priority:int; status:str; recommended_technician:str|None; created_at:UtcTimestamp; resolved_at:UtcTimestamp|None
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
    model_config = {"str_strip_whitespace": True}
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=5000)
    location: str = Field(min_length=2, max_length=100)
    category: TicketCategory | None = None
    affected_users: int = Field(default=1, ge=1, le=10000)
    severity: Literal["Low","Medium","High","Critical"] = "Medium"
class TicketMessageCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
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
    is_test: bool = False
    scheduled_monitoring: bool = False
    id:int; building:str; mode:str; source:str; enabled:bool; failure_threshold:int
    monitor_interval_seconds:int
    status:str; consecutive_failures:int; last_checked_at:UtcTimestamp|None
    last_success_at:UtcTimestamp|None; response_ms:float|None; error_details:str|None
    open_ticket_count:int=0; related_tickets:list[TicketOut]=Field(default_factory=list)
class AvailabilityCheckOut(BaseModel):
    id:int; result:str; status_after_check:str; response_ms:float|None; error_details:str|None; checked_at:UtcTimestamp
    model_config={"from_attributes":True}

class InvestigationUpdate(BaseModel):
    model_config = {"str_strip_whitespace": True, "extra": "forbid"}
    status: Literal["Open", "Investigating", "Resolved"] | None = None
    technician_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, min_length=1, max_length=4000)
    resolution: str | None = Field(default=None, min_length=1, max_length=4000)
    confirmed_cause: str | None = Field(default=None, min_length=1, max_length=4000)


class IncidentCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=3, max_length=5000)
    category: TicketCategory
    location: str = Field(min_length=2, max_length=100)
    ticket_ids: list[int] = Field(default_factory=list, max_length=100)
