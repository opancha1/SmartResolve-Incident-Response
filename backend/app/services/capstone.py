"""Curated fictional operations records for the capstone walkthrough."""
from datetime import timedelta

from app.models import AvailabilityCheck, AvailabilityState, Incident, MonitoredEndpoint, NetworkEvent, SecurityEvent, Technician, Ticket
from app.services.availability import run_check
from app.services.clock import now_utc
from app.services.correlation import link
from app.services.demo import generated
from app.services.intelligence import calculate_priority, classify_ticket, recommend_technician, security_risk, security_severity
from app.services.investigations import record_entry
from app.services.workload import recalculate_workloads

PREFIX = "capstone:"
WOODWARD = "Woodward Hall"
ATKINS = "Atkins Library"
# Key, location, title, report, affected users, severity, status.
REPORTS = (
    ("wifi", "Atkins Library, Room 210", "Wi-Fi disconnects every few minutes", "Laptops drop from campus wireless after joining. Three study groups reproduced it near the east stacks.", 14, "High", "Investigating"),
    ("internet", "Atkins Library, Room 214", "Wireless connected but internet unavailable", "Students remain connected to Wi-Fi but cannot reach course sites. A separate study group observed the same interruption.", 9, "High", "Open"),
    ("projector", "Woodward Hall, Room 130", "Projector blanks during lecture", "The classroom projector loses its image after warming up. The podium preview stays visible.", 32, "High", "Resolved"),
    ("podium", "Woodward Hall, Room 130", "Podium controls cannot restore projector image", "The source selection on the classroom podium works locally while the projector blanks after warm-up.", 18, "Medium", "Resolved"),
    ("lockdown-lab", "Campus-wide, Exam Lab A", "LockDown Browser exits at exam launch", "LockDown Browser exits after the exam handoff following the client update. The morning lab switched to a backup room.", 46, "High", "Investigating"),
    ("lockdown-remote", "Campus-wide, Remote exam cohort", "LockDown Browser cannot launch the practice exam", "LockDown Browser closes after the launch handoff. A remote cohort reported the same client version.", 27, "High", "Open"),
    ("login", "Student Union, Room 204", "Account locked after repeated login attempts", "The fictional requester received an account lock notification while trying to sign in to the student portal.", 1, "Medium", "Investigating"),
    ("mfa", "Student Union, Room 204", "Suspicious MFA prompts during account lockout", "The requester denied several unexpected MFA approvals before the same fictional account locked.", 1, "High", "Investigating"),
    ("phish", "Fretwell Building, Room 112", "Phishing email impersonates campus payroll", "Several recipients reported a fictional payroll message with an unexpected credential prompt. No interaction was confirmed.", 7, "High", "Investigating"),
    ("attachment", "Fretwell Building, Room 112", "Phishing email attachment was blocked", "The mail gateway blocked the attachment from another copy of the same simulated payroll lure.", 3, "Medium", "Open"),
    ("printer", "Friday Building, Room 108", "Printer jobs stall in the shared queue", "The printer is reachable, but new print jobs remain pending after a print-service restart.", 8, "Medium", "Resolved"),
    ("printing", "Friday Building, Room 108", "Print queue cannot release held jobs", "The same Friday 108 queue accepts documents but does not release them. Other queues are unaffected.", 4, "Medium", "Resolved"),
    ("mic", "Science Building, Room 210", "Classroom microphone cuts out during lecture", "The wireless lavalier audio drops intermittently; recorded playback is also missing the instructor's audio.", 24, "Medium", "Investigating"),
    ("hdmi", "EPIC Building, Room 104", "HDMI connection drops on classroom display", "The classroom display loses the wired podium feed when switching inputs. The local preview remains stable.", 21, "High", "Open"),
    ("doccam", "EPIC Building, Room 104", "Document camera image disappears from classroom display", "The document camera preview works locally, but its output disappears through the same HDMI switching path.", 16, "Medium", "Open"),
    ("dock", "Burson Building, Room 118", "Docking station stops detecting the external monitor", "A laptop charges at this docking station but loses the external monitor after waking from sleep.", 1, "Low", "Open"),
    ("hardware", "Burson Building, Room 120", "Computer keyboard keys repeat intermittently", "The lab computer's keyboard repeats keystrokes on two keys after reconnecting it.", 1, "Low", "Resolved"),
    ("canvas-teams", "Fretwell Building, Room 202", "Canvas handoff to Microsoft Teams fails", "The course link in Canvas opens Microsoft Teams and loops back to the handoff page. Opening Teams directly works.", 12, "Medium", "Open"),
    ("zoom-one", "Woodward Hall, Room 142", "Zoom Room camera freezes during sessions", "The Zoom Room camera freezes and drops the video feed in the classroom. Two sessions reproduced it after switching views.", 11, "Medium", "Open"),
    ("zoom-two", "Woodward Hall, Room 142", "Zoom Room camera video freezes after view switch", "The Zoom Room camera freezes during sessions when the classroom switches views. The video feed drops for remote viewers.", 9, "Medium", "Open"),
)

# Key, title, summary, status, ticket keys, finding.
CASES = (
    ("wireless", "Atkins Library wireless connectivity disruption", "Reports from two study rooms coincide with repeated endpoint failures.", "Investigating", ("wifi", "internet"), "Compare the synthetic endpoint failures with the wireless incident window."),
    ("projector", "Woodward 130 projector failure", "Podium preview continued while the projector failed after warm-up.", "Resolved", ("projector", "podium"), "Replaced the faulty projector unit and verified a full lecture test."),
    ("lockdown", "Campus-wide LockDown Browser issue", "Two cohorts reported the same launch failure after a client update.", "Investigating", ("lockdown-lab", "lockdown-remote"), "Compare the installed versions and reproduce the exam handoff in a test room."),
    ("auth", "Suspicious authentication activity", "Unexpected approval prompts and a lockout affect the same fictional identity.", "Investigating", ("login", "mfa"), "Review rejected sign-ins and verify the requester through the simulated identity process."),
    ("phishing", "Potential phishing campaign", "Two reports describe the same simulated payroll lure.", "Investigating", ("phish", "attachment"), "Compare the reported message and attachment verdict. User interaction is unconfirmed."),
    ("printing", "Printing service disruption", "Two reports identify stalled jobs in the same Friday 108 queue.", "Resolved", ("printer", "printing"), "Rebuilt the affected queue and verified sample jobs released successfully."),
    ("audio", "Classroom audio failure", "Lecture audio drops on the Science 210 microphone and recording.", "Investigating", ("mic",), "Compare the microphone receiver output against the recording input."),
    ("display", "Classroom display connectivity issue", "Two sources lose the same EPIC 104 classroom display path.", "Open", ("hdmi", "doccam"), "Check HDMI switching and compare output from both sources."),
)

# Building, ordered probe phases.
MONITORS = {
    WOODWARD: ("online", "offline", "offline", "online", "online"),
    ATKINS: ("online", "online", "offline", "offline", "offline"),
    "Student Union": ("online", "online", "online", "unknown", "unknown"),
    "Friday Building": ("online", "online", "online", "online", "online"),
    "Science Building": ("online", "offline", "offline", "online", "online"),
    "Fretwell Building": ("online", "online", "online", "online", "online"),
    "EPIC Building": ("online", "online", "online", "online", "online"),
    "Burson Building": ("online", "online", "online", "unknown", "unknown"),
}
IDENTITY = "demo.riley@example.invalid"
MAILBOX = "demo.payroll-recipient@example.invalid"
SIGNALS = (
    ("failed-login", "Repeated failed login attempts", IDENTITY, "Student Union", 7, "Investigating", "auth"),
    ("mfa", "Suspicious MFA requests", IDENTITY, "Student Union", 6, "Investigating", "auth"),
    ("lockout", "Account lockout", IDENTITY, "Student Union", 7, "Resolved", "auth"),
    ("location", "Unusual login location", IDENTITY, "Student Union", 0, "Open", "auth"),
    ("reset", "Multiple password reset requests", IDENTITY, "Student Union", 0, "Open", "auth"),
    ("phishing", "Potential phishing email", MAILBOX, "Fretwell Building", 0, "Investigating", "phishing"),
    ("attachment", "Blocked suspicious attachment", MAILBOX, "Fretwell Building", 0, "Resolved", "phishing"),
    ("endpoint", "Suspicious endpoint activity", "demo-lab-device-04", "Burson Building", 0, "Investigating", None),
    ("denied", "Unauthorized access attempt", "demo.avery@example.invalid", "EPIC Building", 2, "Open", None),
    ("protection", "Endpoint protection disabled", "demo-lab-device-07", "Burson Building", 0, "Investigating", None),
    ("privileged", "Unexpected privileged access request", "demo.morgan@example.invalid", "Science Building", 0, "Open", None),
    ("routine-lock", "Account lockout", "demo.cam@example.invalid", "Friday Building", 0, "Resolved", None),
)

EVIDENCE = {
    "failed-login": "Seven rejected sign-ins were recorded for the fictional identity before lockout.",
    "mfa": "The simulator recorded six rejected authentication requests and the user reported unexpected approval prompts.",
    "lockout": "The fictional identity provider temporarily locked the account after seven failures.",
    "location": "A successful test sign-in appeared in a region absent from the simulated account baseline.",
    "reset": "Two password reset requests arrived within ten minutes. Neither token was redeemed.",
    "phishing": "Two reports share a fictional payroll subject and credential prompt pattern.",
    "attachment": "The synthetic gateway quarantined the attachment before delivery. No open event was logged.",
    "endpoint": "The test sensor recorded an unusual application launch during a scheduled lab session.",
    "denied": "Two rejected attempts to open a restricted test resource were logged.",
    "protection": "The fictional lab device missed protection heartbeats and reported the agent disabled.",
    "privileged": "A privilege request for a fictional role arrived outside the approved maintenance window.",
    "routine-lock": "A help-desk simulation confirmed an expired password and restored normal test access.",
}

PROFILES = (
    ("Maya Chen", "Network", "Woodward"),
    ("Jordan Rivera", "Security", "Campus Center"),
    ("Sam Wilson", "Hardware", "Woodward"),
    ("Avery Brooks", "Classroom Technology", "Woodward"),
    ("Noah Patel", "Software", "Woodward"),
    ("Elena Ortiz", "Account", "Campus Center"),
)


def monitor_history(db, building, phases, now):
    endpoint = db.query(MonitoredEndpoint).filter_by(building=building).first()
    if not endpoint or endpoint.mode != "demo" or not endpoint.enabled:
        name = building if endpoint is None else f"{building} (Simulated)"
        endpoint = generated(db, MonitoredEndpoint, PREFIX + "endpoint:" + building,
                             building=name, mode="demo", demo_scenario=phases[-1], enabled=True)
    state = db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
    existing = db.query(AvailabilityCheck).filter_by(endpoint_id=endpoint.id, demo_key=PREFIX + "check:" + building + ":0").first()
    if existing:
        return state
    # Preserve the order of any history already present on a reused monitor.
    previous = state.last_checked_at if state else None
    start = max(now - timedelta(minutes=8), previous + timedelta(microseconds=1)) if previous else now - timedelta(minutes=8)
    latest = max(now, start + timedelta(microseconds=len(phases)))
    spacing = (latest - start) / (len(phases) - 1)
    for index, phase in enumerate(phases):
        endpoint.scenario_override = phase
        state, check = run_check(db, endpoint, start + spacing * index, scenario_check=True)
        check.demo_key = PREFIX + f"check:{building}:{index}"
    return state


def load_capstone(db):
    now = now_utc()
    for name, specialization, location in PROFILES:
        if not db.query(Technician).filter_by(name=name).first():
            generated(db, Technician, PREFIX + "technician:" + name, name=name,
                      specialization=specialization, location=location, availability=True)
    technicians = recalculate_workloads(db)
    states = {name: monitor_history(db, name, phases, now) for name, phases in MONITORS.items()}
    evidence_ticket_ids = {"wifi", "internet", "login", "mfa", "phish", "attachment"}
    tickets = {}
    for index, (key, location, title, description, affected, severity, status) in enumerate(REPORTS):
        category = classify_ticket(title, description)
        technician, _ = recommend_technician(technicians, category, location)
        created = now - timedelta(hours=8, minutes=index * 4)
        resolved = created + timedelta(hours=2) if status == "Resolved" else None
        ticket = generated(db, Ticket, PREFIX + "ticket:" + key, title=title, description=description,
                           category=category, location=location, affected_users=affected, severity=severity,
                           priority=calculate_priority(affected, severity, location, category == "Security", key in evidence_ticket_ids),
                           status=status, assigned_technician=technician.name if technician else None,
                           created_at=created, updated_at=resolved or created, resolved_at=resolved)
        tickets[key] = ticket
        recalculate_workloads(db, technicians)

    cases = {}
    for key, title, description, status, ticket_keys, finding in CASES:
        related = [tickets[name] for name in ticket_keys]
        category = "Security" if key in {"auth", "phishing"} else related[0].category
        location = related[0].location if key != "wireless" else ATKINS
        technician, _ = recommend_technician(technicians, category, location)
        created = max(ticket.created_at for ticket in related) + timedelta(minutes=15)
        resolved = created + timedelta(hours=3) if status == "Resolved" else None
        identity = PREFIX + "incident:" + key
        new = not db.query(Incident).filter_by(demo_key=identity).first()
        incident = generated(db, Incident, identity, title=title, description=description, status=status,
                             category=category, location=location, assigned_technician=technician.name if technician else None,
                             priority=calculate_priority(sum(ticket.affected_users for ticket in related), related[0].severity,
                                                         location, category == "Security", key in {"wireless", "auth", "phishing"}),
                             demo_context=True, created_at=created, updated_at=resolved or created + timedelta(minutes=30),
                             resolved_at=resolved, resolution=finding if resolved else None)
        cases[key] = incident
        if new:
            for ticket in related:
                link(db, incident.id, "ticket", ticket.id, description)
            seed_timeline(db, "incident", incident.id, created, status, finding, technician, resolved)
    outage = generated(db, NetworkEvent, PREFIX + "network:atkins", location=ATKINS, latency=0, packet_loss=100,
                       availability=False, severity="Critical", event_type="Simulated repeated failed endpoint checks",
                       timestamp=states[ATKINS].last_checked_at)
    link(db, cases["wireless"].id, "network", outage.id, "Repeated Atkins endpoint failures")
    link(db, cases["wireless"].id, "availability", states[ATKINS].id, "Current Atkins endpoint evidence")
    for index, (key, event_type, identity, location, failed_attempts, status, case) in enumerate(SIGNALS):
        detected = now - timedelta(hours=8, minutes=15 - index)
        demo_key = PREFIX + "security:" + key
        new = not db.query(SecurityEvent).filter_by(demo_key=demo_key).first()
        score = security_risk(failed_attempts, event_type)
        technician, _ = recommend_technician(technicians, "Security", location)
        note = "Reviewed the fictional signal and documented the outcome." if status == "Resolved" else "Review the synthetic signal, timing and corroborating reports."
        event = generated(db, SecurityEvent, demo_key, event_type=event_type, username=identity,
                          location=location, failed_attempts=failed_attempts, risk_score=score,
                          severity=security_severity(score), evidence_note=EVIDENCE[key], timestamp=detected, status=status,
                          assigned_technician=technician.name if technician else None, resolution=note if status == "Resolved" else None)
        if new:
            if case:
                link(db, cases[case].id, "security", event.id, "Same fictional identity or simulated email campaign")
            seed_timeline(db, "security", event.id, detected, status, note, technician,
                          detected + timedelta(hours=1) if status == "Resolved" else None)

    return {"message": "Capstone dataset is ready.", "tickets": len(tickets), "incidents": len(cases),
            "endpoints": len(states), "security_events": len(SIGNALS), "technicians": len(technicians)}


def seed_timeline(db, kind, record_id, opened, status, note, technician, resolved):
    record_entry(db, kind, record_id, "Created", "Fictional report opened for triage.", created_at=opened)
    if technician:
        record_entry(db, kind, record_id, "Assignment", technician.name, created_at=opened + timedelta(minutes=5))
    if status != "Open":
        record_entry(db, kind, record_id, "Status", "Open → Investigating", created_at=opened + timedelta(minutes=10))
    record_entry(db, kind, record_id, "Note", note, created_at=opened + timedelta(minutes=20))
    if resolved:
        record_entry(db, kind, record_id, "Resolution", note, created_at=resolved)
        record_entry(db, kind, record_id, "Status", "Investigating → Resolved", created_at=resolved)
