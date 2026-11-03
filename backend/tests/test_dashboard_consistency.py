"""Verify overview counts against the records consumed by the frontend."""
from fastapi.testclient import TestClient
from app.main import app
from test_api import authorize_operations


def test_overview_metrics_match_detail_api_records(monkeypatch):
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_ENABLED", "false")
    with TestClient(app) as client:
        authorize_operations(client)
        def get(path):
            response = client.get(f"/api/{path}")
            assert response.status_code == 200
            return response.json()
        tickets = get("tickets")
        incidents = get("incidents")
        endpoints = get("network-availability")
        security = get("security-events")
        metrics = get("dashboard")["metrics"]
        assert metrics["open_tickets"] == sum(t["status"] != "Resolved" for t in tickets)
        assert metrics["active_incidents"] == sum(i["status"] != "Resolved" for i in incidents)
        assert metrics["critical_issues"] == sum(r["status"] != "Resolved" and r["priority"] > 75 for r in tickets + incidents)
        assert metrics["monitored_endpoints"] == len(endpoints)
        assert metrics["offline_endpoints"] == sum(e["status"] == "Offline" for e in endpoints)
        assert metrics["security_alerts"] == sum(e["severity"] in ("High", "Critical") for e in security)
        for technician in get("technicians"):
            assert technician["current_workload"] == sum(t["status"] != "Resolved" and t["assigned_technician"] == technician["name"] for t in tickets)
        if tickets:
            assert get(f"tickets/{tickets[0]['id']}")["id"] == tickets[0]["id"]
        if incidents:
            assert get(f"incidents/{incidents[0]['id']}")["incident"]["id"] == incidents[0]["id"]
