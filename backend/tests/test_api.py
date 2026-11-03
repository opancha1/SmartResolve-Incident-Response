from fastapi.testclient import TestClient
from app.main import app, migrate_legacy_network_locations
from app.database import engine
from sqlalchemy import text
from app.database import SessionLocal
from app.models import User, Technician
from app.services.auth import hash_password, issue_token
import uuid

def authorize_operations(client, role="admin", security_access=True):
    db=SessionLocal()
    tech=db.query(Technician).filter_by(name="Maya Chen").first()
    email=f"{role}-{uuid.uuid4().hex}@example.edu"
    user=User(email=email,full_name=f"Local {role}",password_hash=hash_password("test-password-123"),role=role,technician_id=tech.id if role=="technician" and tech else None,security_access=security_access)
    db.add(user);db.commit();db.refresh(user);token=issue_token(user);db.close()
    client.headers.update({"Authorization":f"Bearer {token}"})
    return client

def test_health_and_ticket_crud():
    with TestClient(app) as client:
        authorize_operations(client)
        assert client.get("/api/health").json()["status"] == "ok"
        response = client.post("/api/tickets", json={"title":"Projector is flickering","description":"Projector flickers during a class.","location":"Science Hall","affected_users":3,"severity":"Medium"})
        assert response.status_code == 201
        ticket = response.json()
        assert ticket["category"] == "Classroom Technology"
        assert client.patch(f"/api/tickets/{ticket['id']}", json={"status":"Resolved"}).json()["status"] == "Resolved"

def test_network_event_api():
    with TestClient(app) as client:
        authorize_operations(client)
        response = client.post("/api/network-events", json={"location":"Atkins","latency":240,"packet_loss":21,"availability":True,"event_type":"Test anomaly"})
        assert response.status_code == 201
        assert response.json()["location"]=="Atkins"
        assert response.json()["severity"] == "High"
        assert all(event["location"]!="Test Hall" for event in client.get("/api/network-events").json())
        woodward=next(event for event in client.get("/api/network-events").json() if event["location"]=="Woodward")
        assert (woodward["latency"],woodward["packet_loss"],woodward["availability"],woodward["severity"])==(240,21,True,"High")

def test_generated_events_rotate_campus_buildings():
    with TestClient(app) as client:
        authorize_operations(client)
        generated=[client.post("/api/network-events/generate/normal").json() for _ in range(4)]
        assert [event["location"] for event in generated]==["Mebane","Grainger","Friday","Atkins"]
        assert all(event["severity"]=="Normal" for event in generated)

def test_legacy_test_hall_migration_preserves_metrics_and_api_values():
    with TestClient(app) as client:
        authorize_operations(client)
        with engine.begin() as connection:
            for n in range(4):
                connection.execute(text("INSERT INTO network_events (location,latency,packet_loss,availability,event_type,severity,timestamp) VALUES ('Test Hall',240,21,1,'Legacy demo anomaly','High',:timestamp)"),{"timestamp":f"2026-08-01 00:00:0{n}"})
            ids=[row[0] for row in connection.execute(text("SELECT id FROM network_events WHERE event_type='Legacy demo anomaly' ORDER BY timestamp"))]
        migrate_legacy_network_locations()
        returned={event["id"]:event for event in client.get("/api/network-events").json()}
        migrated=[returned[event_id] for event_id in ids]
        assert [event["location"] for event in migrated]==["Atkins","Mebane","Grainger","Friday"]
        assert all((event["latency"],event["packet_loss"],event["availability"],event["severity"])==(240,21,True,"High") for event in migrated)
        assert not any(event["location"]=="Test Hall" for event in returned.values())

def test_ticket_assignment_workflow_and_recommendation():
    with TestClient(app) as client:
        authorize_operations(client)
        created=client.post("/api/tickets",json={"title":"Laptop keyboard failure","description":"Keyboard has stopped working.","location":"Woodward","affected_users":2,"severity":"High"})
        assert created.status_code==201
        ticket=created.json(); ticket_id=ticket["id"]
        assert ticket["severity"]=="High"
        ticket=client.patch(f"/api/tickets/{ticket_id}",json={"title":"Wi-Fi adapter disconnects","description":"Wi-Fi disconnects repeatedly.","location":"Woodward","affected_users":10,"severity":"Critical"}).json()
        assert ticket["category"]=="Network" and ticket["severity"]=="Critical" and ticket["priority"]>75
        before=client.get("/api/technicians").json()
        maya=next(t for t in before if t["name"]=="Maya Chen")
        rec=client.get("/api/technicians/recommend",params={"category":ticket["category"],"location":ticket["location"]}).json()
        assert rec["technician"] is not None and rec["explanation"]
        assigned=client.post(f"/api/tickets/{ticket_id}/assign",json={"technician_id":maya["id"]})
        assert assigned.status_code==200 and assigned.json()["assigned_technician"]=="Maya Chen"
        assert next(t for t in client.get("/api/technicians").json() if t["id"]==maya["id"])["current_workload"]==maya["current_workload"]+1
        assert client.get("/api/tickets/{ticket_id}".format(ticket_id=ticket_id)).json()["assigned_technician"]=="Maya Chen"
        assert client.patch(f"/api/tickets/{ticket_id}",json={"status":"Investigating"}).json()["status"]=="Investigating"
        resolved=client.patch(f"/api/tickets/{ticket_id}",json={"status":"Resolved"}).json()
        assert resolved["resolved_at"] is not None
        assert client.get("/api/dashboard").json()["metrics"]["open_tickets"]==sum(t["status"]=="Open" for t in client.get("/api/tickets").json())
        reopened=client.patch(f"/api/tickets/{ticket_id}",json={"status":"Open"}).json()
        assert reopened["resolved_at"] is None
        assert next(t for t in client.get("/api/technicians").json() if t["id"]==maya["id"])["current_workload"]==maya["current_workload"]+1
        unassigned=client.delete(f"/api/tickets/{ticket_id}/assign")
        assert unassigned.status_code==200 and unassigned.json()["assigned_technician"] is None
        assert next(t for t in client.get("/api/technicians").json() if t["id"]==maya["id"])["current_workload"]==maya["current_workload"]
        assert client.delete(f"/api/tickets/{ticket_id}/assign").json()["assigned_technician"] is None

def test_technician_crud_persistence_and_assignment_protection():
    with TestClient(app) as client:
        authorize_operations(client)
        locations=client.get("/api/locations")
        assert locations.status_code==200 and "Woodward" in locations.json()
        created=client.post("/api/technicians",json={"name":"CRUD Technician","specialization":"Network","location":"Atkins","availability":True})
        assert created.status_code==201
        technician=created.json()
        assert technician["current_workload"]==0
        technician_id=technician["id"]
        assert client.get(f"/api/technicians/{technician_id}").json()["name"]=="CRUD Technician"
        assert client.post("/api/technicians",json={"name":"CRUD Technician","specialization":"Network","location":"Atkins","availability":True}).status_code==409

        updated=client.put(f"/api/technicians/{technician_id}",json={"name":"CRUD Technician Updated","specialization":"Network","location":"Mebane","availability":False})
        assert updated.status_code==200
        assert (updated.json()["name"],updated.json()["location"],updated.json()["availability"])==("CRUD Technician Updated","Mebane",False)
        assert client.get(f"/api/technicians/{technician_id}").json()["location"]=="Mebane"

        ticket=client.post("/api/tickets",json={"title":"CRUD assignment workload check","description":"Check workload source of truth.","location":"Mebane","affected_users":1,"severity":"Medium"}).json()
        assigned=client.post(f"/api/tickets/{ticket['id']}/assign",json={"technician_id":technician_id})
        assert assigned.status_code==409  # Unavailable technicians cannot be assigned.
        client.put(f"/api/technicians/{technician_id}",json={"name":"CRUD Technician Updated","specialization":"Network","location":"Mebane","availability":True})
        assert client.post(f"/api/tickets/{ticket['id']}/assign",json={"technician_id":technician_id}).status_code==200
        assert client.get(f"/api/technicians/{technician_id}").json()["current_workload"]==1
        blocked=client.delete(f"/api/technicians/{technician_id}")
        assert blocked.status_code==409 and "active assignments" in blocked.json()["detail"]

        client.patch(f"/api/tickets/{ticket['id']}",json={"status":"Resolved"})
        assert client.get(f"/api/technicians/{technician_id}").json()["current_workload"]==0
        deleted=client.delete(f"/api/technicians/{technician_id}")
        assert deleted.status_code==204
        assert client.get(f"/api/technicians/{technician_id}").status_code==404

def test_technician_validation_rejects_empty_name_and_invalid_values():
    with TestClient(app) as client:
        authorize_operations(client)
        empty=client.post("/api/technicians",json={"name":"   ","specialization":"Network","location":"Woodward","availability":True})
        invalid=client.post("/api/technicians",json={"name":"Invalid Tech","specialization":"Anything","location":"Woodward","availability":True})
        assert empty.status_code==422
        assert invalid.status_code==422

def test_incident_status_persists_and_clears_resolution_timestamp():
    with TestClient(app) as client:
        authorize_operations(client)
        for title in ("Wi-Fi outage in room 1","Network connection issue in room 2"):
            client.post("/api/tickets",json={"title":title,"description":"Woodward Wi-Fi network keeps disconnecting.","location":"Woodward","affected_users":2,"severity":"High"})
        client.post("/api/network-events",json={"location":"Woodward","latency":240,"packet_loss":21,"availability":True,"event_type":"Test anomaly"})
        client.post("/api/incidents/correlate")
        incidents=client.get("/api/incidents").json()
        assert incidents
        incident=incidents[0]
        resolved=client.patch(f"/api/incidents/{incident['id']}/status",json={"status":"Resolved"}).json()
        assert resolved["resolved_at"] is not None
        reopened=client.patch(f"/api/incidents/{incident['id']}/status",json={"status":"Open"}).json()
        assert reopened["resolved_at"] is None

def test_local_vite_cors_origin():
    with TestClient(app) as client:
        authorize_operations(client)
        response = client.options(
            "/api/dashboard",
            headers={
                "Origin": "http://localhost:5175",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers["access-control-allow-origin"] == "http://localhost:5175"

def test_portal_auth_private_tickets_and_assistant_confirmation_boundary():
    with TestClient(app) as client:
        one = client.post("/api/auth/register", json={"email":"alex@example.edu","full_name":"Alex Student","password":"correct-horse-123"})
        two = client.post("/api/auth/register", json={"email":"taylor@example.edu","full_name":"Taylor Student","password":"correct-horse-456"})
        assert one.status_code == 201 and two.status_code == 201
        token_one = one.json()["access_token"]
        token_two = two.json()["access_token"]
        assert client.get("/api/portal/tickets").status_code == 401
        headers_one = {"Authorization":f"Bearer {token_one}"}
        headers_two = {"Authorization":f"Bearer {token_two}"}
        created = client.post("/api/portal/tickets", headers=headers_one, json={"title":"Projector has no image","description":"Classroom projector powers on but shows no image.","location":"Woodward 210","severity":"High"})
        assert created.status_code == 201
        ticket_id = created.json()["id"]
        assert [t["id"] for t in client.get("/api/portal/tickets",headers=headers_one).json()] == [ticket_id]
        assert client.get(f"/api/portal/tickets/{ticket_id}",headers=headers_two).status_code == 404
        assert client.post(f"/api/portal/tickets/{ticket_id}/messages",headers=headers_two,json={"body":"Private follow-up"}).status_code == 404
        assistant = client.post("/api/portal/assistant",headers=headers_one,json={"message":"The classroom projector is blank"})
        assert assistant.status_code == 200
        assert assistant.json()["mode"] == "rule-based"
        assert assistant.json()["ticket_created"] is False
        valid_login=client.post("/api/auth/login",json={"email":"alex@example.edu","password":"correct-horse-123"})
        assert valid_login.status_code==200 and valid_login.json()["user"]["role"]=="user"
        assert client.post("/api/auth/login",json={"email":"alex@example.edu","password":"wrong-password"}).status_code == 401

def test_roles_protect_operations_and_expose_user_ticket_updates():
    with TestClient(app) as public:
        registered=public.post("/api/auth/register",json={"email":"role-check@example.edu","full_name":"Role Check","password":"long-safe-password","role":"technician"})
        assert registered.status_code==201
        assert registered.json()["user"]["role"]=="user"
        user_token=registered.json()["access_token"]
        user_headers={"Authorization":f"Bearer {user_token}"}
        assert public.get("/api/auth/me",headers=user_headers).json()["can_view_security"] is False
        assert public.get("/api/tickets",headers=user_headers).status_code==403
        assert public.get("/api/dashboard",headers=user_headers).status_code==403
        assert public.get("/api/security-events",headers=user_headers).status_code==403
        assert public.get("/api/incidents",headers=user_headers).status_code==403
        assert public.get("/api/network-events",headers=user_headers).status_code==403
        assert public.get("/api/technicians",headers=user_headers).status_code==403
        created=public.post("/api/portal/tickets",headers=user_headers,json={"title":"User portal Wi-Fi issue","description":"My Wi-Fi disconnects frequently in class.","location":"Atkins 105","severity":"High"})
        assert created.status_code==201
        ticket_id=created.json()["id"]
        assert public.get(f"/api/portal/tickets/{ticket_id}",headers={}).status_code==401

    with TestClient(app) as technician_client:
        authorize_operations(technician_client,role="technician",security_access=False)
        assert technician_client.get("/api/auth/me").json()["can_view_security"] is False
        team_tickets=technician_client.get("/api/tickets").json()
        assert any(ticket["id"]==ticket_id for ticket in team_tickets)
        assert technician_client.patch(f"/api/tickets/{ticket_id}",json={"status":"Investigating"}).json()["status"]=="Investigating"
        assert technician_client.post(f"/api/tickets/{ticket_id}/messages",json={"body":"We are investigating the affected access point."}).status_code==201
        assert technician_client.get("/api/security-events").status_code==403
        assert technician_client.post("/api/technicians",json={"name":"Not Authorized","specialization":"Network","location":"Atkins","availability":True}).status_code==403
        dashboard=technician_client.get("/api/dashboard").json()
        assert dashboard["security_events"]==[] and dashboard["metrics"]["security_alerts"] is None

    with TestClient(app) as user_client:
        detail=user_client.get(f"/api/portal/tickets/{ticket_id}",headers=user_headers).json()
        assert detail["ticket"]["status"]=="Investigating"
        assert any("investigating" in update["body"].lower() for update in detail["messages"])

def test_local_demo_technician_provision_is_repeatable_and_authenticates_by_role():
    from app.provision import LOCAL_DEMO_EMAIL, LOCAL_DEMO_PASSWORD, provision_account
    from app.services.auth import verify_password
    with TestClient(app) as client:
        db=SessionLocal()
        maya=db.query(Technician).filter_by(name="Sam Wilson").first()
        assert maya is not None
        demo_email="demo.testtech@smartresolve.local"
        account,result=provision_account(db,email=demo_email,name=maya.name,password=LOCAL_DEMO_PASSWORD,
            technician_id=maya.id,role="technician",security_access=True)
        assert result=="created"
        original_hash=account.password_hash
        same,result=provision_account(db,email=demo_email,name=maya.name,password="A-different-password-not-used",
            technician_id=maya.id,role="technician",security_access=True)
        assert result=="unchanged" and same.password_hash==original_hash
        assert verify_password(LOCAL_DEMO_PASSWORD,same.password_hash)
        reset,result=provision_account(db,email=demo_email,name=maya.name,password="Explicit-reset-password-2026!",
            technician_id=maya.id,role="technician",security_access=True,reset_password=True)
        assert result=="password-reset"
        assert verify_password("Explicit-reset-password-2026!",reset.password_hash)
        assert reset.role=="technician" and reset.technician_id==maya.id
        db.close()
        login=client.post("/api/auth/login",json={"email":demo_email,"password":"Explicit-reset-password-2026!"})
        assert login.status_code==200 and login.json()["user"]["role"]=="technician"
        technician_headers={"Authorization":f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/dashboard",headers=technician_headers).status_code==200
        user=client.post("/api/auth/register",json={"email":"cannot-promote@example.edu","full_name":"Public User","password":"safe-user-password","role":"technician"})
        assert user.status_code==201 and user.json()["user"]["role"]=="user"
        user_headers={"Authorization":f"Bearer {user.json()['access_token']}"}
        assert client.get("/api/dashboard",headers=user_headers).status_code==403

def test_building_availability_demo_roles_tickets_and_approved_live_config(monkeypatch):
    from app.services.availability import DEMO_BUILDINGS, run_check
    from app.models import AvailabilityState, MonitoredEndpoint
    from datetime import datetime, timedelta
    with TestClient(app) as client:
        authorize_operations(client,role="admin",security_access=True)
        endpoints=client.get("/api/network-availability")
        assert endpoints.status_code==200
        values=endpoints.json()
        assert len(values)>=len(DEMO_BUILDINGS)
        assert {item["status"] for item in values if item["source"]=="Simulated Demo"}>={"Online","Offline","Unknown"}
        assert all(item["source"]=="Simulated Demo" for item in values[:4])
        counts={status:sum(item["status"]==status for item in values) for status in ("Online","Offline","Unknown")}
        assert sum(counts.values())==len(values)

        woodward=next(item for item in values if item["building"]=="Woodward Hall")
        db=SessionLocal()
        woodward_state=db.query(AvailabilityState).filter_by(endpoint_id=woodward["id"]).first()
        woodward_state.last_checked_at=datetime.utcnow()-timedelta(minutes=1)
        db.commit();db.close()
        checked=client.post(f"/api/network-availability/{woodward['id']}/check")
        assert checked.status_code==200 and checked.json()["status"]=="Online"
        assert checked.json()["response_ms"] is not None
        history=client.get(f"/api/network-availability/{woodward['id']}/history").json()
        assert history and history[0]["result"]=="Online"

        # Exercise failure hysteresis with controlled probe outcomes and timestamps.
        db=SessionLocal()
        endpoint=MonitoredEndpoint(building="Availability Test Building",mode="demo",demo_scenario="offline",failure_threshold=2)
        db.add(endpoint);db.flush()
        state=AvailabilityState(endpoint_id=endpoint.id,status="Online",consecutive_failures=0,
            last_checked_at=datetime.utcnow()-timedelta(minutes=1),last_success_at=datetime.utcnow()-timedelta(minutes=1))
        db.add(state);db.commit()
        import app.services.availability as availability_service
        monkeypatch.setattr(availability_service,"probe_endpoint",lambda *_: ("Failed",None,"controlled test failure"))
        base=datetime.utcnow()
        first,_=run_check(db,endpoint,base)
        assert first.status=="Online" and first.consecutive_failures==1
        second,_=run_check(db,endpoint,base+timedelta(seconds=16))
        assert second.status=="Offline" and second.consecutive_failures==2
        monkeypatch.setattr(availability_service,"probe_endpoint",lambda *_: ("Unknown",None,"controlled monitor failure"))
        unknown,_=run_check(db,endpoint,base+timedelta(seconds=32))
        assert unknown.status=="Unknown" and unknown.consecutive_failures==0
        db.commit();db.close()

        # Two same-building tickets produce a reviewable suggestion, never an automatic incident.
        ticket_ids=[]
        for n in range(2):
            response=client.post("/api/tickets",json={"title":f"Atkins wireless issue {n}","description":"Wi-Fi is not connecting in the library.","location":f"Atkins Library {200+n}","affected_users":3,"severity":"High"})
            assert response.status_code==201
            ticket_ids.append(response.json()["id"])
        atkins=next(item for item in client.get("/api/network-availability").json() if item["building"]=="Atkins Library")
        review=client.get(f"/api/network-availability/{atkins['id']}/suggestion").json()
        assert review["suggested"] is True and len(review["tickets"])>=2
        assert client.get("/api/incidents").json()  # Existing incident workflow remains available.
        link=client.post(f"/api/network-availability/{atkins['id']}/incident")
        assert link.status_code==200 and set(ticket_ids).issubset(set(link.json()["linked_ticket_ids"]))
        assert link.json()["incident"]["id"]

        monkeypatch.setenv("SMARTRESOLVE_APPROVED_ENDPOINTS","https://health.example.edu/check")
        config=client.post("/api/network-availability/endpoints",json={"building":"Approved Live Test","mode":"live","target_url":"https://health.example.edu/check","timeout_seconds":2,"failure_threshold":2})
        assert config.status_code==201
        assert config.json()["source"]=="Live Endpoint" and "target_url" not in config.json()
        monkeypatch.setenv("SMARTRESOLVE_APPROVED_ENDPOINTS","http://169.254.169.254/")
        blocked=client.post("/api/network-availability/endpoints",json={"building":"Metadata Test","mode":"live","target_url":"http://169.254.169.254/","timeout_seconds":2,"failure_threshold":2})
        assert blocked.status_code==422

    with TestClient(app) as public:
        user=public.post("/api/auth/register",json={"email":"availability-user@example.edu","full_name":"Availability User","password":"safe-availability-password"})
        assert user.status_code==201
        headers={"Authorization":f"Bearer {user.json()['access_token']}"}
        assert public.get("/api/network-availability",headers=headers).status_code==403
        assert public.post("/api/network-availability/endpoints",headers=headers,json={"building":"Forbidden","mode":"demo"}).status_code==403
        public_status=public.get("/api/portal/network-status",params={"location":"Atkins Library 210"},headers=headers)
        assert public_status.status_code==200 and any(item["status"]=="Offline" for item in public_status.json())
        assert all("target_url" not in item for item in public_status.json())

def test_automatic_monitor_demo_cycle_stale_and_probe_failure(monkeypatch):
    from datetime import datetime, timedelta
    from app.models import AvailabilityState, MonitoredEndpoint
    from app.services.availability import effective_status, run_check
    from app.services.monitor_scheduler import _lease

    db=SessionLocal()
    cycle=MonitoredEndpoint(building=f"Cycle {uuid.uuid4().hex[:8]}",mode="demo",demo_scenario="cycle",failure_threshold=2)
    db.add(cycle);db.flush()
    cycle_id=cycle.id
    states=[]
    for index in range(5):
        state,check=run_check(db,cycle,datetime.utcnow()+timedelta(seconds=index*16))
        states.append((check.result,state.status))
    assert states==[("Online","Online"),("Online","Online"),("Failed","Online"),("Failed","Offline"),("Unknown","Unknown")]
    db.commit()
    stale=db.query(AvailabilityState).filter_by(endpoint_id=cycle.id).first()
    stale.status="Online";stale.consecutive_failures=0
    stale.last_checked_at=datetime.utcnow()-timedelta(minutes=20)
    db.commit()
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_INTERVAL_SECONDS","30")
    assert effective_status(stale)[0]=="Unknown"
    assert "stale" in effective_status(stale)[1]
    stale_endpoint=MonitoredEndpoint(building=f"Stale {uuid.uuid4().hex[:8]}",mode="demo",demo_scenario="online")
    stale_building=stale_endpoint.building
    db.add(stale_endpoint);db.flush()
    stale_api_state=AvailabilityState(endpoint_id=stale_endpoint.id,status="Offline",consecutive_failures=2,
        last_checked_at=datetime.utcnow()-timedelta(minutes=20),error_details="Old outage")
    db.add(stale_api_state);db.commit();db.close()
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_ENABLED","false")
    with TestClient(app) as client:
        authorize_operations(client)
        response=client.get("/api/network-availability")
        stale_view=next(row for row in response.json() if row["building"]==stale_building)
        assert stale_view["status"]=="Unknown" and "stale" in stale_view["error_details"]

    db=SessionLocal()
    import app.services.availability as availability_service
    real_probe=availability_service.probe_endpoint
    monkeypatch.setattr(availability_service,"probe_endpoint",lambda *_: (_ for _ in ()).throw(RuntimeError("private detail")))
    cycle=db.get(MonitoredEndpoint,cycle_id)
    cycle_state=db.query(AvailabilityState).filter_by(endpoint_id=cycle_id).first()
    cycle_state.last_checked_at=datetime.utcnow()-timedelta(minutes=1)
    state,check=run_check(db,cycle,datetime.utcnow()+timedelta(minutes=1))
    assert state.status=="Unknown" and "unexpectedly" in state.error_details
    assert check.result=="Unknown" and "private detail" not in (check.error_details or "")
    live=MonitoredEndpoint(building="Live Failure Test",mode="live",target_url="https://approved.example/health",failure_threshold=2)
    monkeypatch.setattr(availability_service,"probe_endpoint",real_probe)
    monkeypatch.setattr(availability_service,"validate_live_target",lambda target:target)
    monkeypatch.setattr(availability_service,"_resolve_approved_target",lambda target:None)
    class UnavailableResponse:
        status_code=503
    monkeypatch.setattr(availability_service.httpx,"get",lambda *args,**kwargs:UnavailableResponse())
    assert availability_service.probe_endpoint(live)[0]=="Failed"
    def timeout(*args,**kwargs):
        import httpx
        raise httpx.TimeoutException("secret target detail")
    monkeypatch.setattr(availability_service.httpx,"get",timeout)
    timeout_result=availability_service.probe_endpoint(live)
    assert timeout_result[0]=="Unknown" and "secret target detail" not in str(timeout_result)
    db.commit();db.close()

    now=datetime.utcnow()
    assert _lease("worker-a",60,now) is True
    assert _lease("worker-b",60,now+timedelta(seconds=1)) is False
    assert _lease("worker-b",60,now+timedelta(seconds=61)) is True
    _lease("worker-b",0,now+timedelta(seconds=62),release=True)
