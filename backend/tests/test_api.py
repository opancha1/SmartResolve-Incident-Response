from fastapi.testclient import TestClient
from app.main import app, migrate_legacy_network_locations
from app.database import engine
from sqlalchemy import text

def test_health_and_ticket_crud():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        response = client.post("/api/tickets", json={"title":"Projector is flickering","description":"Projector flickers during a class.","location":"Science Hall","affected_users":3,"severity":"Medium"})
        assert response.status_code == 201
        ticket = response.json()
        assert ticket["category"] == "Classroom Technology"
        assert client.patch(f"/api/tickets/{ticket['id']}", json={"status":"Resolved"}).json()["status"] == "Resolved"

def test_network_event_api():
    with TestClient(app) as client:
        response = client.post("/api/network-events", json={"location":"Atkins","latency":240,"packet_loss":21,"availability":True,"event_type":"Test anomaly"})
        assert response.status_code == 201
        assert response.json()["location"]=="Atkins"
        assert response.json()["severity"] == "High"
        assert all(event["location"]!="Test Hall" for event in client.get("/api/network-events").json())
        woodward=next(event for event in client.get("/api/network-events").json() if event["location"]=="Woodward")
        assert (woodward["latency"],woodward["packet_loss"],woodward["availability"],woodward["severity"])==(240,21,True,"High")

def test_generated_events_rotate_campus_buildings():
    with TestClient(app) as client:
        generated=[client.post("/api/network-events/generate/normal").json() for _ in range(4)]
        assert [event["location"] for event in generated]==["Mebane","Grainger","Friday","Atkins"]
        assert all(event["severity"]=="Normal" for event in generated)

def test_legacy_test_hall_migration_preserves_metrics_and_api_values():
    with TestClient(app) as client:
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
        empty=client.post("/api/technicians",json={"name":"   ","specialization":"Network","location":"Woodward","availability":True})
        invalid=client.post("/api/technicians",json={"name":"Invalid Tech","specialization":"Anything","location":"Woodward","availability":True})
        assert empty.status_code==422
        assert invalid.status_code==422

def test_incident_status_persists_and_clears_resolution_timestamp():
    with TestClient(app) as client:
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
        response = client.options(
            "/api/dashboard",
            headers={
                "Origin": "http://localhost:5175",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers["access-control-allow-origin"] == "http://localhost:5175"
