from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), default="Other")
    priority: Mapped[int] = mapped_column(Integer, default=25)
    location: Mapped[str] = mapped_column(String(100))
    affected_users: Mapped[int] = mapped_column(Integer, default=1)
    severity: Mapped[str] = mapped_column(String(30), default="Medium")
    status: Mapped[str] = mapped_column(String(30), default="Open")
    assigned_technician: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="user")
    technician_id: Mapped[int | None] = mapped_column(ForeignKey("technicians.id"), nullable=True)
    security_access: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def can_view_security(self) -> bool:
        return self.role == "admin" or self.security_access

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    location: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(30), default="Open")
    recommended_technician: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class IncidentRelationship(Base):
    __tablename__ = "incident_relationships"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"))
    related_type: Mapped[str] = mapped_column(String(30))
    related_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(255))

class NetworkEvent(Base):
    __tablename__ = "network_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    location: Mapped[str] = mapped_column(String(100))
    latency: Mapped[float] = mapped_column(Float)
    packet_loss: Mapped[float] = mapped_column(Float)
    availability: Mapped[bool] = mapped_column(Boolean, default=True)
    event_type: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(30))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MonitoredEndpoint(Base):
    __tablename__ = "monitored_endpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    building: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="demo")
    target_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=2)
    demo_scenario: Mapped[str] = mapped_column(String(20), default="online")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AvailabilityState(Base):
    __tablename__ = "availability_states"
    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("monitored_endpoints.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="Unknown")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_details: Mapped[str | None] = mapped_column(String(240), nullable=True)

class AvailabilityCheck(Base):
    __tablename__ = "availability_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("monitored_endpoints.id"), index=True)
    result: Mapped[str] = mapped_column(String(20))
    status_after_check: Mapped[str] = mapped_column(String(20))
    response_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_details: Mapped[str | None] = mapped_column(String(240), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class MonitorSchedulerLease(Base):
    __tablename__ = "monitor_scheduler_leases"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    owner_id: Mapped[str] = mapped_column(String(80))
    lease_until: Mapped[datetime] = mapped_column(DateTime, index=True)

class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    username: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(100))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(30))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Technician(Base):
    __tablename__ = "technicians"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    specialization: Mapped[str] = mapped_column(String(60))
    location: Mapped[str] = mapped_column(String(100))
    current_workload: Mapped[int] = mapped_column(Integer, default=0)
    availability: Mapped[bool] = mapped_column(Boolean, default=True)
