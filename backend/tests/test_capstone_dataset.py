from fastapi.testclient import TestClient

from app.main import app
from app.services.intelligence import security_risk
from test_api import authorize_operations


def test_capstone_dataset_integrity(monkeypatch):
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_ENABLED", "false")
    with TestClient(app) as client:
        authorize_operations(client)
        assert client.post("/api/demo/reset", json={"confirm": True}).status_code == 200

        counts = client.post("/api/demo/capstone", json={})
        assert counts.status_code == 200, counts.text
        assert [(counts.json()[key]) for key in ("tickets", "incidents", "endpoints", "security_events")] == [20, 8, 8, 12]
        assert client.post("/api/demo/capstone", json={}).json() == counts.json()

        def capstone(path):
            return [row for row in client.get(path).json() if (row.get("demo_key") or "").startswith("capstone:")]

        tickets = capstone("/api/tickets")
        incidents = capstone("/api/incidents")
        events = capstone("/api/security-events")
        assert len(tickets) == 20 and len(incidents) == 8 and len(events) == 12
        assert {ticket["status"] for ticket in tickets} == {"Open", "Investigating", "Resolved"}
        assert {event["severity"] for event in events} == {"Low", "Medium", "High", "Critical"}
        assert all(event["risk_score"] == security_risk(event["failed_attempts"], event["event_type"]) for event in events)
        for incident in incidents:
            detail = client.get(f"/api/incidents/{incident['id']}").json()
            assert any(item["type"] == "ticket" for item in detail["relationships"])
            assert detail["timeline"] == sorted(detail["timeline"], key=lambda item: (item["created_at"], item["id"]))
        recommendations = client.get("/api/incidents/recommendations").json()
        assert any("Zoom Room" in row["title"] for row in recommendations)
        endpoints = client.get("/api/network-availability").json()
        atkins = next(row for row in endpoints if row["building"] == "Atkins Library")
        assert atkins["status"] == "Offline"
        assert len([ticket for ticket in atkins["related_tickets"] if (ticket["demo_key"] or "").startswith("capstone:")]) == 2
        assert len({row["status"] for row in endpoints}) == 3

        assert client.post("/api/demo/reset", json={"confirm": True}).status_code == 200
        assert not capstone("/api/tickets")
        assert not capstone("/api/incidents")
        assert not capstone("/api/security-events")
