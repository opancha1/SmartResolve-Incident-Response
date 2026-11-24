from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AvailabilityState, MonitoredEndpoint
from app.services.availability import effective_status, run_check
from app.services.clock import now_utc
from app.services.locations import same_building
from app.services.monitor_scheduler import _lease
from test_api import authorize_operations


def test_utc_staleness_and_location_boundaries(monkeypatch):
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_INTERVAL_SECONDS", "120")
    check = datetime(2026, 11, 24, 14, 0)
    state = AvailabilityState(status="Online", last_checked_at=check)
    east = timezone(timedelta(hours=-5))
    assert effective_status(state, datetime(2026, 11, 24, 9, 3, tzinfo=east))[0] == "Online"
    assert effective_status(state, check + timedelta(seconds=361))[0] == "Unknown"
    assert effective_status(state, check - timedelta(seconds=15))[0] == "Unknown"
    for location in ("Atkins", "Library", "Atkins Library, Room 240", "Atkins 240"):
        assert same_building(location, "Atkins Library")
    assert not same_building("Library Annex", "Atkins Library")


def test_failure_threshold_and_recovery(monkeypatch):
    with TestClient(app), SessionLocal() as db:
        endpoint = MonitoredEndpoint(building="Refinement Test endpoint", mode="demo", demo_scenario="offline",
                                     failure_threshold=2)
        db.add(endpoint)
        db.flush()
        start = now_utc()
        for offset in range(8):
            state, _ = run_check(db, endpoint, start + timedelta(seconds=20 * offset))
        assert state.status == "Offline" and state.consecutive_failures == 2
        endpoint.demo_scenario = "online"
        state, check = run_check(db, endpoint, (start + timedelta(seconds=160)).replace(tzinfo=timezone.utc))
        assert state.status == check.result == "Online"
        assert state.consecutive_failures == 0
        assert state.last_checked_at == state.last_success_at
        db.rollback()


def test_worker_lease_is_exclusive(monkeypatch):
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_ENABLED", "false")
    with TestClient(app):
        boundary = Barrier(2)
        instant = now_utc()

        def compete(owner):
            boundary.wait()
            return _lease(owner, 120, instant)

        owners = ["refinement-test-one", "refinement-test-two"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(compete, owners)) == [False, True]
        for owner in owners:
            _lease(owner, 0, instant, release=True)


def test_live_api_monitoring_and_recommendations(monkeypatch):
    monkeypatch.setenv("SMARTRESOLVE_MONITOR_ENABLED", "false")
    with TestClient(app) as client:
        authorize_operations(client)
        def post(path, data=None):
            return client.post("/api" + path, json=data or {})

        def get(path):
            response = client.get("/api" + path)
            assert response.status_code == 200, response.text
            return response.json()

        av_ids = []
        for name in ("Docking station", "Document camera", "Webcam"):
            result = post("/tickets", {"title": f"{name} not working",
                                       "description": f"{name} not working in the classroom, please help.",
                                       "location": "Woodward Hall, Room 792", "category": "Classroom Technology"})
            assert result.status_code == 201
            av_ids.append(result.json()["id"])
        assert not any(len(set(group["ticket_ids"]) & set(av_ids)) > 1 for group in get("/incidents/recommendations"))
        av_ids = post("/demo/classroom-av").json()["ticket_ids"]
        group = next(item for item in get("/incidents/recommendations") if item["ticket_ids"] == av_ids)
        assert group["similarity_evidence"][0]["evidence"] == ["projector"]
        assert post(f"/incidents/recommendations/{group['id']}/dismiss").status_code == 204
        assert group["id"] not in {item["id"] for item in get("/incidents/recommendations")}
        outage = post("/demo/network-outage").json()
        incident_id = outage["incident_id"]
        assert all(item["id"] != incident_id for item in get("/incidents"))
        assert any(item.get("incident_id") == incident_id for item in get("/incidents/recommendations"))
        assert post(f"/incidents/recommendations/{incident_id}/accept").json()["status"] == "Open"
        assert post(f"/incidents/recommendations/{incident_id}/accept").status_code == 409
        assert all(item.get("incident_id") != incident_id for item in get("/incidents/recommendations"))
        endpoint = next(item for item in get("/network-availability") if item["building"] == "Atkins Library")
        assert endpoint["last_checked_at"].endswith("Z")
        assert endpoint["open_ticket_count"] == len(endpoint["related_tickets"])
        summary = get(f"/network-availability/{endpoint['id']}/availability-summary")
        assert summary["counts"]["Failed"] >= 2
        metrics = get("/dashboard")["metrics"]
        assert metrics["campus_endpoints"] == sum(not row["is_test"] for row in get("/network-availability"))
        security_scenario = post("/demo/suspicious-login").json()
        assert post("/demo/suspicious-login").json() == security_scenario
        security_events = [row for row in get("/security-events") if (row["demo_key"] or "").startswith("suspicious-login:")]
        assert len(security_events) == len({row["event_type"] for row in security_events}) == 8
        assert any(row["event_type"] == "Unusual login location" for row in security_events)
        assert all(row["incident_count"] == 1 for row in security_events)
        assert post("/demo/reset", {"confirm": True}).status_code == 200
