from fastapi.testclient import TestClient
from app.main import app
from test_api import authorize_operations


def test_integrated_demo_workflows(monkeypatch):
    monkeypatch.setenv("SMARTRESOLVE_DEMO_ENABLED", "1")
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_ENABLED", "false")
    with TestClient(app) as client:
        authorize_operations(client, role="technician")

        def get(path):
            response = client.get("/api" + path)
            assert response.status_code == 200, response.text
            return response.json()

        def post(path, payload=None, expected=200):
            response = client.post("/api" + path, json=payload or {})
            assert response.status_code == expected, response.text
            return response.json()

        normal = post("/tickets", {"title": "Preserve my account issue", "description": "Password reset needed",
                                  "location": "Atkins Library"}, 201)
        scenarios = post("/demo/load")["scenarios"]
        assert scenarios == post("/demo/load")["scenarios"]
        outage = scenarios["network-outage"]
        endpoint = next(item for item in get("/network-availability") if item["building"] == "Atkins Library")
        assert endpoint["status"] == "Offline"
        endpoint_path = f"/network-availability/{endpoint['id']}"
        assert [row["result"] for row in get(endpoint_path + "/history")[:2]] == ["Failed", "Failed"]
        incident_path = f"/incidents/{outage['incident_id']}"
        assert {row["type"] for row in get(incident_path)["relationships"]} == {"ticket", "network", "availability"}
        assert get(f"/tickets/{outage['ticket_ids'][0]}/intelligence")["matches"]
        assert client.patch("/api" + incident_path, json={"status": "Investigating", "note": "Checking endpoint"}).status_code == 200
        post("/demo/network-recovery")
        assert next(item for item in get("/network-availability") if item["id"] == endpoint["id"])["status"] == "Online"
        assert get(endpoint_path + "/suggestion")["recovered"]
        post("/demo/network-recovery")
        assert sum(row["item"].get("event_type") == "Simulated endpoint recovery"
                   for row in get(incident_path)["relationships"]) == 1
        assert get(incident_path)["incident"]["status"] == "Investigating"
        post("/demo/network-unknown")
        assert next(item for item in get("/network-availability") if item["id"] == endpoint["id"])["status"] == "Unknown"
        assert get(f"/tickets/{outage['ticket_ids'][0]}")["status"] == "Open"

        security = next(item for item in get("/security-events") if item["demo_key"] == "suspicious-login:event:2")
        event_path = f"/security-events/{security['id']}"
        detail = get(event_path)
        assert detail["event"]["risk_score"] == 95
        assert sum(detail["risk_factors"].values()) == 95
        assert detail["incidents"][0]["id"] == scenarios["suspicious-login"]["incident_id"]
        assert detail["tickets"][0]["id"] == scenarios["suspicious-login"]["ticket_ids"][0]
        assert client.patch("/api" + event_path, json={"status": "Resolved", "note": "Reviewed",
                                                        "resolution": "Synthetic identity verified"}).status_code == 200
        assert {entry["kind"] for entry in get(event_path)["timeline"]} == {"Note", "Resolution", "Status"}

        duplicate = get(f"/tickets/{scenarios['duplicate-tickets']['ticket_ids'][0]}/intelligence")
        av = get(f"/tickets/{scenarios['classroom-av']['ticket_ids'][0]}/intelligence")
        assert duplicate["matches"][0]["possible_duplicate"]
        assert av["classification"]["category"] == "Classroom Technology"
        recommendations = get("/incidents/recommendations")
        software = next(group for group in recommendations if group["category"] == "Software" and group["demo"])
        assert software["reported_impact"] == 135
        payload = {key: software[key] for key in ("title", "description", "category", "location", "ticket_ids")}
        manual = post("/incidents", payload, 201)
        assert manual["priority"] > 50
        post("/incidents", payload, 409)
        manual_path = f"/incidents/{manual['id']}"
        ticket_path = f"{manual_path}/tickets/{software['ticket_ids'][0]}"
        assert client.delete("/api" + ticket_path).status_code == 204
        assert client.put("/api" + ticket_path).status_code == 204
        assert client.patch("/api" + manual_path, json={"status": "Resolved", "confirmed_cause": "Version conflict",
                                 "resolution": "Rolled back the demo update"}).status_code == 200
        assert get(manual_path)["incident"]["confirmed_cause"] == "Version conflict"
        assert client.patch("/api" + manual_path, json={"status": "Open"}).status_code == 200
        assert get(manual_path)["incident"]["resolved_at"] is None
        assert get("/dashboard")["metrics"]["security_alerts"] == sum(
            event["status"] != "Resolved" and event["severity"] in {"High", "Critical"}
            for event in get("/security-events")
        )

        post("/demo/reset", expected=422)
        assert post("/demo/reset", {"confirm": True})["removed"]["ticket"] == 11
        assert get(f"/tickets/{normal['id']}")["title"] == normal["title"]
        assert get(manual_path)["relationships"] == []
        assert not any(row["demo_key"] for row in get("/tickets"))
        assert not any(row["demo_key"] for row in get("/security-events"))
        assert post("/demo/reset", {"confirm": True})["removed"]["ticket"] == 0


def test_demo_permission_and_production_guards(monkeypatch):
    monkeypatch.setenv("SMARTRESOLVE_DEMO_ENABLED", "1")
    with TestClient(app) as client:
        user = client.post("/api/auth/register", json={"email": "demo-guard@example.invalid", "full_name": "Demo Guard",
                                                       "password": "example-password-for-test"}).json()
        assert client.post("/api/demo/network-outage", json={}, headers={
            "Authorization": "Bearer " + user["access_token"]
        }).status_code == 403
        authorize_operations(client, role="technician", security_access=False)
        for action in ("suspicious-login", "load", "reset"):
            assert client.post(f"/api/demo/{action}", json={"confirm": True}).status_code == 403
        monkeypatch.setenv("SMARTRESOLVE_ENV", "production")
        assert not client.get("/api/demo").json()["enabled"]
        assert client.post("/api/demo/network-outage", json={}).status_code == 404
