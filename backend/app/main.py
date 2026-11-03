import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.database import Base, SessionLocal, engine
from app.routers import auth, availability, dashboard, incidents, locations, network, portal, security, technicians, tickets
from app.services.availability import seed_demo_endpoints
from app.services.monitor_scheduler import monitor_scheduler_loop, scheduler_enabled
from app.seed import seed
app=FastAPI(title="SmartResolve API",version="1.0.0")
monitor_task=None
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router);app.include_router(portal.router);app.include_router(tickets.router);app.include_router(network.router);app.include_router(availability.router);app.include_router(security.router);app.include_router(technicians.router);app.include_router(incidents.router);app.include_router(dashboard.router);app.include_router(locations.router)
def migrate_legacy_network_locations():
    # Update only the location field; IDs, metrics, timestamps and severities stay put.
    with engine.begin() as connection:
        legacy=connection.execute(text("SELECT id FROM network_events WHERE location='Test Hall' ORDER BY timestamp, id")).all()
        buildings=("Atkins","Mebane","Grainger","Friday")
        for index,row in enumerate(legacy):
            connection.execute(text("UPDATE network_events SET location=:location WHERE id=:id"),{"location":buildings[index%len(buildings)],"id":row.id})
def initialize_database():
    Base.metadata.create_all(engine)
    # Keep existing demo databases usable when adding nullable/defaulted model fields.
    columns={column["name"] for column in inspect(engine).get_columns("tickets")}
    if "severity" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE tickets ADD COLUMN severity VARCHAR(30) NOT NULL DEFAULT 'Medium'"))
    if "owner_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE tickets ADD COLUMN owner_id INTEGER REFERENCES users(id)"))
    user_columns={column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        if "technician_id" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN technician_id INTEGER"))
        if "security_access" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN security_access BOOLEAN NOT NULL DEFAULT 0"))
    # One-time, in-place correction of legacy synthetic locations.
    migrate_legacy_network_locations()
    seed()
    with SessionLocal() as db:
        seed_demo_endpoints(db)

@app.on_event("startup")
async def startup():
    global monitor_task
    initialize_database()
    if scheduler_enabled():
        monitor_task=asyncio.create_task(monitor_scheduler_loop())

@app.on_event("shutdown")
async def shutdown():
    global monitor_task
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        monitor_task=None
@app.get("/api/health")
def health():return {"status":"ok"}
