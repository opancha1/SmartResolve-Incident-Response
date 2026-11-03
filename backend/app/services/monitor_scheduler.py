"""Database-leased background monitor; safe across reloads and API workers."""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models import AvailabilityState, MonitoredEndpoint, MonitorSchedulerLease
from app.services.availability import (AvailabilityRateLimited, monitor_interval_seconds,
    run_check)

logger=logging.getLogger(__name__)
LEASE_ID=1

def scheduler_enabled() -> bool:
    return os.environ.get("SMARTRESOLVE_MONITOR_ENABLED","true").strip().lower() not in {"0","false","no","off"}

def _lease(owner_id: str, lease_seconds: int, now: datetime, release: bool=False) -> bool:
    db=SessionLocal()
    try:
        lease=db.get(MonitorSchedulerLease,LEASE_ID)
        if release:
            if lease and lease.owner_id==owner_id:
                db.delete(lease);db.commit()
            return False
        if lease and lease.owner_id!=owner_id and lease.lease_until>now:
            return False
        if lease is None:
            lease=MonitorSchedulerLease(id=LEASE_ID,owner_id=owner_id,lease_until=now+timedelta(seconds=lease_seconds))
            db.add(lease)
        else:
            lease.owner_id=owner_id
            lease.lease_until=now+timedelta(seconds=lease_seconds)
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    finally:
        db.close()

def run_monitor_cycle() -> None:
    db=SessionLocal()
    try:
        endpoints=db.query(MonitoredEndpoint).filter_by(enabled=True).order_by(MonitoredEndpoint.id).all()
        for endpoint in endpoints:
            try:
                run_check(db,endpoint)
                db.commit()
            except AvailabilityRateLimited:
                db.rollback()
            except Exception:
                db.rollback()
                logger.exception("Unexpected availability monitor failure for endpoint id=%s",endpoint.id)
                # Record a non-diagnostic Unknown result if storage is still available.
                try:
                    state=db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
                    if state:
                        state.status="Unknown";state.consecutive_failures=0;state.response_ms=None
                        state.error_details="Monitoring cycle failed unexpectedly; availability could not be confirmed."
                        state.last_checked_at=datetime.utcnow()
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("Could not persist Unknown status for endpoint id=%s",endpoint.id)
    finally:
        db.close()

async def monitor_scheduler_loop() -> None:
    owner_id=f"{os.getpid()}-{uuid.uuid4().hex}"
    interval=monitor_interval_seconds()
    try:
        while True:
            try:
                # Leave time for a full cycle of bounded (<=10 second) endpoint checks.
                with SessionLocal() as db:
                    count=db.query(MonitoredEndpoint).filter_by(enabled=True).count()
                lease_seconds=max(interval*2,interval+count*12+30)
                if _lease(owner_id,lease_seconds,datetime.utcnow()):
                    await asyncio.to_thread(run_monitor_cycle)
                    delay=interval
                else:
                    delay=min(15,max(5,interval//4))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Availability monitor scheduler cycle failed")
                delay=min(15,max(5,interval//4))
            await asyncio.sleep(delay)
    finally:
        await asyncio.to_thread(_lease,owner_id,0,datetime.utcnow(),True)
