from datetime import datetime, timedelta
from app.models import (
    AvailabilityCheck, AvailabilityState, Incident, IncidentRelationship, InvestigationEntry,
    MonitoredEndpoint, NetworkEvent, SecurityEvent, Ticket, TicketMessage,
)
from app.services.availability import effective_endpoint_status, run_check
from app.services.correlation import link
from app.services.intelligence import calculate_priority, classify_ticket, security_risk, security_severity, recommend_technician
from app.services.workload import recalculate_workloads

ATKINS = "Atkins Library"
REPORTS = {
    "network-outage": (ATKINS, "Wi-Fi cannot connect", "Wi-Fi cannot connect in the library study area. The wireless network is unavailable.", (12, 18, 9)),
    "suspicious-login": ("Student Union", "Account locked after login attempts", "The synthetic student account is locked after repeated login attempts.", (1,)),
    "classroom-av": ("Woodward Hall, Room 120", "Classroom projector flickering", "The classroom projector is flickering and the display goes black during lectures.", (24, 10)),
    "duplicate-tickets": ("Woodward Hall, Room 124", "Docking station not working", "The docking station does not detect the monitor or charge the laptop.", (1, 1)),
    "campus-software": ("Campus-wide", "LockDown Browser crashes on launch", "LockDown Browser crashes when launching the exam after a software update.", (60, 45, 30)),
}


def generated(db, model, key, **fields):
    record = db.query(model).filter_by(demo_key=key).first()
    if record is None:
        record = model(demo_key=key, **fields)
        db.add(record)
        db.flush()
    return record


def atkins_endpoint(db):
    existing = db.query(MonitoredEndpoint).filter(
        MonitoredEndpoint.building.in_([ATKINS, "Atkins"])
    ).order_by(MonitoredEndpoint.id).all()
    endpoint = next((item for item in existing if item.mode == "demo" and item.enabled), None)
    if endpoint:
        return endpoint
    return generated(db, MonitoredEndpoint, "scenario:atkins", building=f"{ATKINS} (Simulated)",
                     mode="demo", demo_scenario="online", enabled=True)


def transition(db, phase, now):
    endpoint = atkins_endpoint(db)
    state = db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
    expected = {"online": "Online", "offline": "Offline", "unknown": "Unknown"}[phase]
    if endpoint.scenario_override != phase or not state or effective_endpoint_status(endpoint, state, now)[0] != expected:
        endpoint.scenario_override = phase
        checks = endpoint.failure_threshold if phase == "offline" else 1
        for index in range(checks):
            state, _ = run_check(db, endpoint, now + timedelta(microseconds=index), scenario_check=True)
    return state


def run_scenario(db, scenario):
    now = datetime.utcnow()
    if scenario in {"network-recovery", "network-unknown"}:
        recovery = scenario == "network-recovery"
        state = transition(db, "online" if recovery else "unknown", now)
        incidents = db.query(Incident).filter(
            Incident.demo_key.in_(["network-outage:incident", "capstone:incident:wireless"])
        ).all()
        if recovery and incidents:
            generated_checks = db.query(AvailabilityCheck).filter_by(endpoint_id=state.endpoint_id, generated_demo=True)
            prior_failure = generated_checks.filter(AvailabilityCheck.result != "Online").order_by(
                AvailabilityCheck.id.desc()).first()
            check = generated_checks.filter(
                AvailabilityCheck.result == "Online",
                AvailabilityCheck.id > (prior_failure.id if prior_failure else 0),
            ).order_by(AvailabilityCheck.id).first()
            if check is None:
                return {"message": "Simulated endpoint is Online. Incident and ticket statuses were retained."}
            event = generated(db, NetworkEvent, f"network-recovery:check:{check.id}", location=ATKINS,
                              latency=check.response_ms or 0, packet_loss=0, availability=True,
                              event_type="Simulated endpoint recovery", severity="Normal", timestamp=check.checked_at)
            for incident in incidents:
                link(db, incident.id, "network", event.id, "Successful endpoint check. Technician closure review required.")
        return {"message": f"Simulated endpoint is {state.status}. Incident and ticket statuses were retained."}

    location, title, description, impact = REPORTS[scenario]
    category = classify_ticket(title, description)
    severity = "High" if scenario in {"network-outage", "campus-software"} else "Medium"
    evidence = scenario in {"network-outage", "suspicious-login"}
    areas = ("Exam Lab A", "Exam Lab B", "Remote exam cohort") if scenario == "campus-software" else ()
    tickets = [
        generated(db, Ticket, f"{scenario}:ticket:{index}", title=title,
                  description=description, location=f"{location}, {areas[index - 1]}" if areas else location,
                  category=category, affected_users=count,
                  severity=severity, priority=calculate_priority(count, severity, location, category == "Security", evidence),
                  created_at=now, updated_at=now)
        for index, count in enumerate(impact, 1)
    ]
    related_events = []
    new_security_events = []
    if scenario == "network-outage":
        state = transition(db, "offline", now)
        event = generated(db, NetworkEvent, f"{scenario}:event", location=location, latency=0,
                          packet_loss=100, availability=False, event_type="Simulated failed endpoint checks",
                          severity="Critical", timestamp=now)
        related_events.extend([("network", event.id, "Repeated failed synthetic endpoint checks"),
                               ("availability", state.id, "Current monitored endpoint state")])
    if scenario == "suspicious-login":
        event_types = [
            ("Multiple failed login attempts", 7), ("Suspicious authentication activity", 7),
            ("Account lockout", 0), ("Potential phishing report", 0),
            ("Unusual account activity", 0), ("Suspicious endpoint activity", 0),
            ("Unauthorized access attempt", 1), ("Unusual login location", 0),
        ]
        for index, (event_type, attempts) in enumerate(event_types, 1):
            score = security_risk(attempts, event_type)
            event = generated(db, SecurityEvent, f"{scenario}:event:{index}", event_type=event_type,
                              username="demo.lab-device-01" if "endpoint" in event_type else "demo.student@example.invalid", location=location, failed_attempts=attempts,
                              risk_score=score, severity=security_severity(score), timestamp=now)
            relation = ("security", event.id, "Synthetic signal from the same investigation window")
            related_events.append(relation)
            if event.timestamp == now:
                new_security_events.append(relation)
    incident = None
    if related_events:
        previous = db.query(Incident).filter_by(demo_key=f"{scenario}:incident").first()
        if previous:
            for kind, record_id, reason in new_security_events:
                link(db, previous.id, kind, record_id, reason)
            return {"message": "Scenario records are ready for technician review.",
                    "ticket_ids": [ticket.id for ticket in tickets], "incident_id": previous.id}
        recommended, _ = recommend_technician(recalculate_workloads(db), "Security" if scenario == "suspicious-login" else category, location)
        incident = generated(db, Incident, f"{scenario}:incident", title=(
            "Possible Atkins Library endpoint outage" if scenario == "network-outage" else "Suspicious student account authentication"),
            description=("Repeated simulated failures coincide with related Wi-Fi reports." if scenario == "network-outage"
                         else "Repeated synthetic authentication failures coincide with an account lockout report."),
            location=location, category="Security" if scenario == "suspicious-login" else category,
            priority=calculate_priority(sum(impact), severity, location, scenario == "suspicious-login", True),
            recommended_technician=recommended.name if recommended else None, status="Recommended", created_at=now, updated_at=now)
        for ticket in tickets:
            link(db, incident.id, "ticket", ticket.id, "Same simulated scenario and affected service")
        for kind, record_id, reason in related_events:
            link(db, incident.id, kind, record_id, reason)

    return {"message": "Scenario records are ready for technician review.", "ticket_ids": [t.id for t in tickets],
            "incident_id": incident.id if incident else None}


def restore_monitor(db):
    for endpoint in db.query(MonitoredEndpoint).filter(MonitoredEndpoint.scenario_override.is_not(None)).all():
        endpoint.scenario_override = None
        generated_checks = db.query(AvailabilityCheck).filter_by(endpoint_id=endpoint.id, generated_demo=True)
        generated_checks.delete(synchronize_session=False)
        state = db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
        history = db.query(AvailabilityCheck).filter_by(endpoint_id=endpoint.id).order_by(
            AvailabilityCheck.checked_at.desc(), AvailabilityCheck.id.desc()
        ).all()
        if not state:
            continue
        if endpoint.demo_key and not history and not db.query(IncidentRelationship).filter_by(
            related_type="availability", related_id=state.id
        ).first():
            db.delete(state)
            db.delete(endpoint)
            continue
        latest = history[0] if history else None
        success = next((check for check in history if check.result == "Online"), None)
        state.status = latest.status_after_check if latest else "Unknown"
        state.last_checked_at = latest.checked_at if latest else None
        state.last_success_at = success.checked_at if success else None
        state.response_ms = latest.response_ms if latest else None
        state.error_details = latest.error_details if latest else None
        state.consecutive_failures = min(endpoint.failure_threshold, next((index for index, check in enumerate(history)
                                           if check.result != "Failed"), len(history)))


def reset_scenarios(db):
    removed = {}
    for kind, model in (("ticket", Ticket), ("network", NetworkEvent), ("security", SecurityEvent), ("incident", Incident)):
        query = db.query(model).filter(model.demo_key.is_not(None))
        ids = [row.id for row in query]
        if kind == "ticket":
            db.query(TicketMessage).filter(TicketMessage.ticket_id.in_(ids)).delete(synchronize_session=False)
        if kind == "incident":
            db.query(IncidentRelationship).filter(IncidentRelationship.incident_id.in_(ids)).delete(synchronize_session=False)
        else:
            db.query(IncidentRelationship).filter(IncidentRelationship.related_type == kind,
                                                  IncidentRelationship.related_id.in_(ids)).delete(synchronize_session=False)
        db.query(InvestigationEntry).filter(InvestigationEntry.record_type == kind,
                                            InvestigationEntry.record_id.in_(ids)).delete(synchronize_session=False)
        removed[kind] = query.delete(synchronize_session=False)
    restore_monitor(db)
    recalculate_workloads(db)
    return removed
