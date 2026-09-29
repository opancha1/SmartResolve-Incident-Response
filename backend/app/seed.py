from app.database import Base, SessionLocal, engine
from app.models import Technician
from app.routers.network import create_event
from app.routers.security import create_event as create_security
from app.routers.tickets import create_ticket
from app.schemas import EventNetworkCreate, SecurityCreate, TicketCreate
def seed():
    Base.metadata.create_all(engine);db=SessionLocal()
    if db.query(Technician).count(): db.close();return
    db.add_all([Technician(name="Maya Chen",specialization="Network",location="Woodward",current_workload=1,availability=True),Technician(name="Jordan Rivera",specialization="Security",location="Campus Center",current_workload=2,availability=True),Technician(name="Sam Wilson",specialization="Hardware",location="Woodward",current_workload=0,availability=True)])
    db.commit()
    create_ticket(TicketCreate(title="Wi-Fi keeps disconnecting",description="Wi-Fi keeps disconnecting in Woodward lecture hall.",location="Woodward",affected_users=8,severity="High"),db)
    create_ticket(TicketCreate(title="Cannot connect to Wi-Fi",description="Students cannot connect to the Woodward Wi-Fi network.",location="Woodward",affected_users=12,severity="High"),db)
    create_ticket(TicketCreate(title="Internet extremely slow",description="Extremely slow internet during class in Woodward.",location="Woodward",affected_users=25,severity="High"),db)
    create_event(EventNetworkCreate(location="Woodward",latency=240,packet_loss=21,availability=True,event_type="High latency and packet loss"),db)
    create_security(SecurityCreate(event_type="Failed login",username="demo.student",location="Library",failed_attempts=3),db)
    db.close()
if __name__=="__main__":seed()
