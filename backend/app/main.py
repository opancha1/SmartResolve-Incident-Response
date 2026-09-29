from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.database import Base, engine
from app.routers import dashboard, incidents, locations, network, security, technicians, tickets
from app.seed import seed
app=FastAPI(title="SmartResolve API",version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tickets.router);app.include_router(network.router);app.include_router(security.router);app.include_router(technicians.router);app.include_router(incidents.router);app.include_router(dashboard.router);app.include_router(locations.router)
def migrate_legacy_network_locations():
    # Update only the location field; IDs, metrics, timestamps and severities stay put.
    with engine.begin() as connection:
        legacy=connection.execute(text("SELECT id FROM network_events WHERE location='Test Hall' ORDER BY timestamp, id")).all()
        buildings=("Atkins","Mebane","Grainger","Friday")
        for index,row in enumerate(legacy):
            connection.execute(text("UPDATE network_events SET location=:location WHERE id=:id"),{"location":buildings[index%len(buildings)],"id":row.id})
@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    # Keep existing demo databases usable when adding nullable/defaulted model fields.
    columns={column["name"] for column in inspect(engine).get_columns("tickets")}
    if "severity" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE tickets ADD COLUMN severity VARCHAR(30) NOT NULL DEFAULT 'Medium'"))
    # One-time, in-place correction of legacy synthetic locations.
    migrate_legacy_network_locations()
    seed()
@app.get("/api/health")
def health():return {"status":"ok"}
