from app.database import SessionLocal
from app.models import Technician
from app.routers.network import create_event
from app.routers.security import create_event as create_security
from app.routers.tickets import create_ticket
from app.schemas import EventNetworkCreate, SecurityCreate, TicketCreate
def seed():
    db=SessionLocal()
    if db.query(Technician).count(): db.close();return
    db.add_all([Technician(name="Maya Chen",specialization="Network",location="Woodward",current_workload=1,availability=True),Technician(name="Jordan Rivera",specialization="Security",location="Campus Center",current_workload=2,availability=True),Technician(name="Sam Wilson",specialization="Hardware",location="Woodward",current_workload=0,availability=True)])
    db.commit()
    create_ticket(TicketCreate(title="Wi-Fi keeps disconnecting",description="Wi-Fi keeps disconnecting in Woodward lecture hall.",location="Woodward",affected_users=8,severity="High"),db)
    create_ticket(TicketCreate(title="Cannot connect to Wi-Fi",description="Students cannot connect to the Woodward Wi-Fi network.",location="Woodward",affected_users=12,severity="High"),db)
    create_ticket(TicketCreate(title="Internet extremely slow",description="Extremely slow internet during class in Woodward.",location="Woodward",affected_users=25,severity="High"),db)
    create_event(EventNetworkCreate(location="Woodward",latency=240,packet_loss=21,availability=True,event_type="High latency and packet loss"),db)
    create_security(SecurityCreate(event_type="Failed login",username="demo.student",location="Library",failed_attempts=3),db)
    db.close()
if __name__=="__main__":
    import argparse
    import json
    from sqlalchemy import text
    from app.main import initialize_database
    from app.services.capstone import load_capstone
    from app.services.demo_config import demo_enabled

    parser = argparse.ArgumentParser(description="Load SmartResolve synthetic demo data.")
    parser.add_argument("--capstone", action="store_true", help="Load the curated presentation dataset.")
    args = parser.parse_args()
    if not demo_enabled():
        raise SystemExit("Set SMARTRESOLVE_DEMO_ENABLED=1 in a development environment")
    initialize_database()
    if args.capstone:
        with SessionLocal() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            summary = load_capstone(db)
            db.commit()
        print(json.dumps(summary))
