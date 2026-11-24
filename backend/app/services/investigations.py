from fastapi import HTTPException
from app.services.clock import now_utc, wire_utc
from app.models import InvestigationEntry, Technician


def record_entry(db, record_type, record_id, kind, body, user=None, *, created_at=None):
    db.add(InvestigationEntry(record_type=record_type, record_id=record_id,
                              kind=kind, body=body, author_id=user.id if user else None,
                              created_at=created_at or now_utc()))


def timeline(db, record_type, record_id):
    entries = db.query(InvestigationEntry).filter_by(record_type=record_type, record_id=record_id).order_by(
        InvestigationEntry.created_at, InvestigationEntry.id
    ).all()
    return [{"id": entry.id, "kind": entry.kind, "body": entry.body,
             "author_id": entry.author_id, "created_at": wire_utc(entry.created_at)} for entry in entries]


def update_investigation(db, record_type, record, data, user):
    if data.technician_id:
        technician = db.get(Technician, data.technician_id)
        if not technician:
            raise HTTPException(404, "Technician not found")
        if not technician.availability:
            raise HTTPException(409, "Technician is unavailable")
        record.assigned_technician = technician.name
        record_entry(db, record_type, record.id, "Assignment", technician.name, user)
    for field, kind in (("note", "Note"), ("resolution", "Resolution"), ("confirmed_cause", "Confirmed cause")):
        value = getattr(data, field)
        if value:
            if field != "note":
                if not hasattr(record, field):
                    raise HTTPException(422, "Confirmed cause is available on incidents")
                setattr(record, field, value)
            record_entry(db, record_type, record.id, kind, value, user)
    if data.status and data.status != record.status:
        record_entry(db, record_type, record.id, "Status", f"{record.status} → {data.status}", user)
        record.status = data.status
