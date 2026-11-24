"""Building endpoint availability, safe live-target checks, and stable demo data."""
from datetime import datetime, timedelta
import ipaddress
import os
import socket
import time
from urllib.parse import urlparse
import httpx
from sqlalchemy.orm import Session
from app.services.clock import now_utc, utc_naive
from app.services.locations import same_building as ticket_matches_building
from app.services.demo_config import demo_enabled
from app.models import AvailabilityCheck, AvailabilityState, MonitoredEndpoint, Ticket

MIN_CHECK_INTERVAL_SECONDS = 15
DEFAULT_MONITOR_INTERVAL_SECONDS = 120
STALE_INTERVAL_MULTIPLIER = 3
DEMO_BUILDINGS = (
    ("Woodward Hall", "online"),
    ("Atkins Library", "offline"),
    ("Student Union", "unknown"),
    ("College of Computing and Informatics building", "online"),
    ("Demo Cycle Building", "cycle"),
)
class AvailabilityRateLimited(Exception):
    pass


def related_open_tickets(db: Session, building: str) -> list[Ticket]:
    tickets=db.query(Ticket).filter(Ticket.status!="Resolved").order_by(Ticket.created_at.desc()).all()
    return [ticket for ticket in tickets if ticket_matches_building(ticket.location,building)]

def approved_live_targets() -> set[str]:
    return {item.strip() for item in os.environ.get("SMARTRESOLVE_APPROVED_ENDPOINTS","").split(";") if item.strip()}

def monitor_interval_seconds() -> int:
    try:
        value=int(os.environ.get("SMARTRESOLVE_MONITOR_INTERVAL_SECONDS",str(DEFAULT_MONITOR_INTERVAL_SECONDS)))
    except ValueError:
        value=DEFAULT_MONITOR_INTERVAL_SECONDS
    return max(30,min(value,3600))

def effective_status(state: AvailabilityState | None, now: datetime | None=None) -> tuple[str,str|None]:
    if state is None or state.last_checked_at is None:
        return "Unknown", "No valid availability check has been recorded yet."
    now=utc_naive(now) if now is not None else now_utc()
    if (now-utc_naive(state.last_checked_at)).total_seconds()>monitor_interval_seconds()*STALE_INTERVAL_MULTIPLIER:
        return "Unknown", f"Monitoring data is stale; the last check was more than {STALE_INTERVAL_MULTIPLIER} monitoring intervals ago."
    if utc_naive(state.last_checked_at) > now + timedelta(seconds=5):
        return "Unknown", "The latest check is ahead of the server clock."
    return state.status,state.error_details

def effective_endpoint_status(endpoint: MonitoredEndpoint, state: AvailabilityState | None,
                              now: datetime | None=None) -> tuple[str,str|None]:
    if not endpoint.enabled:
        return "Unknown","Monitoring is disabled for this endpoint."
    return effective_status(state,now)

def validate_live_target(target_url: str) -> str:
    target=target_url.strip()
    if target not in approved_live_targets():
        raise ValueError("The live endpoint URL is not in SMARTRESOLVE_APPROVED_ENDPOINTS")
    parsed=urlparse(target)
    if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only approved HTTP or HTTPS endpoint URLs are supported")
    hostname=parsed.hostname.casefold().rstrip(".")
    if hostname in {"localhost","metadata","metadata.google.internal","169.254.169.254"} or hostname.endswith(".localhost"):
        raise ValueError("Local and cloud metadata targets are not allowed")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("Live targets must use an approved DNS hostname, not an IP literal")
    if parsed.port and parsed.port not in {80,443}:
        raise ValueError("Only standard HTTP and HTTPS ports are allowed")
    return target

def _resolve_approved_target(target: str) -> None:
    hostname=urlparse(target).hostname
    try:
        addresses={entry[4][0] for entry in socket.getaddrinfo(hostname,None,type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise LookupError("The approved endpoint hostname could not be resolved") from exc
    if not addresses:
        raise LookupError("The approved endpoint hostname has no resolved address")
    for address in addresses:
        ip=ipaddress.ip_address(address)
        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise ValueError("The approved endpoint resolved to a prohibited address")

def probe_endpoint(endpoint: MonitoredEndpoint, demo_index: int=0) -> tuple[str,float|None,str|None]:
    """Return Online, Failed, or Unknown; never leak transport exception details."""
    if endpoint.mode=="demo":
        scenario = (endpoint.scenario_override if demo_enabled() else None) or endpoint.demo_scenario
        if scenario=="online": return "Online", 34.0 if "Woodward" in endpoint.building else 52.0, None
        if scenario=="offline": return "Failed", None, "Synthetic demo endpoint did not respond."
        if scenario=="cycle":
            # Persisted check count selects the next deterministic phase.
            phases=("Online","Online","Failed","Failed","Unknown")
            phase=phases[demo_index%len(phases)]
            if phase=="Online": return "Online", 38.0, None
            if phase=="Failed": return "Failed", None, "Synthetic demo endpoint did not respond (repeatable cycle)."
            return "Unknown",None,"Synthetic demo monitor is unavailable in this cycle phase."
        return "Unknown", None, "Synthetic demo monitor is unavailable for this endpoint."
    try:
        target=validate_live_target(endpoint.target_url or "")
        _resolve_approved_target(target)
    except (ValueError,LookupError):
        return "Unknown",None,"Live endpoint configuration or name resolution is unavailable."
    started=time.perf_counter()
    try:
        response=httpx.get(target,timeout=endpoint.timeout_seconds,follow_redirects=False,trust_env=False,
                           headers={"User-Agent":"SmartResolve-Availability/1.0"})
        elapsed=round((time.perf_counter()-started)*1000,1)
        if 200<=response.status_code<300:
            return "Online",elapsed,None
        return "Failed",elapsed,f"Endpoint returned HTTP {response.status_code}."
    except httpx.TimeoutException:
        return "Unknown",None,"Health check timed out; availability could not be confirmed."
    except httpx.ConnectError:
        return "Failed",None,"Approved endpoint did not accept a connection."
    except httpx.RequestError:
        return "Unknown",None,"The monitoring request could not be completed."

def seed_demo_endpoints(db: Session) -> None:
    """Insert stable illustrative results without overwriting existing configuration."""
    existing = {endpoint.building for endpoint in db.query(MonitoredEndpoint).all()}
    for building, scenario in DEMO_BUILDINGS:
        if building in existing:
            continue
        endpoint = MonitoredEndpoint(building=building, mode="demo", demo_scenario=scenario, enabled=True,
                                     timeout_seconds=2.0, failure_threshold=2)
        db.add(endpoint)
        db.flush()
        if scenario == "cycle":
            db.add(AvailabilityState(endpoint_id=endpoint.id, status="Unknown", consecutive_failures=0,
                                     error_details="Waiting for the first scheduled demo check."))
            continue
        checks = endpoint.failure_threshold if scenario == "offline" else 1
        for _ in range(checks):
            run_check(db, endpoint, scenario_check=True)
    db.commit()

def run_check(db: Session, endpoint: MonitoredEndpoint, now: datetime | None=None, *, scenario_check=False) -> tuple[AvailabilityState,AvailabilityCheck]:
    now=utc_naive(now) if now is not None else now_utc()
    state=db.query(AvailabilityState).filter_by(endpoint_id=endpoint.id).first()
    if not state:
        state=AvailabilityState(endpoint_id=endpoint.id,status="Unknown",consecutive_failures=0)
        db.add(state);db.flush()
    elapsed = (now - utc_naive(state.last_checked_at)).total_seconds() if state.last_checked_at else None
    if not scenario_check and elapsed is not None and 0 <= elapsed < MIN_CHECK_INTERVAL_SECONDS:
        raise AvailabilityRateLimited("Please wait at least 15 seconds between checks for this endpoint.")
    if not endpoint.enabled:
        outcome,response_ms,error="Unknown",None,"Monitoring is disabled for this endpoint."
    else:
        demo_index=db.query(AvailabilityCheck).filter_by(endpoint_id=endpoint.id).count()
        try:
            outcome,response_ms,error=probe_endpoint(endpoint,demo_index)
        except Exception:
            outcome,response_ms,error="Unknown",None,"The health check failed unexpectedly; availability could not be confirmed."
    if outcome=="Online":
        state.status="Online";state.consecutive_failures=0;state.last_success_at=now;state.error_details=None
    elif outcome=="Failed":
        state.consecutive_failures = min(endpoint.failure_threshold, state.consecutive_failures + 1)
        if state.consecutive_failures>=endpoint.failure_threshold:
            state.status="Offline"
            state.error_details=error or "Endpoint did not respond."
        else:
            state.status = effective_status(state, now)[0]
            state.error_details = f"{state.consecutive_failures} of {endpoint.failure_threshold} consecutive checks failed."
    else:
        state.status="Unknown";state.consecutive_failures=0
        state.error_details=error or "Monitoring could not confirm endpoint availability."
    state.last_checked_at=now;state.response_ms=response_ms
    check=AvailabilityCheck(endpoint_id=endpoint.id,result=outcome,status_after_check=state.status,
                            response_ms=response_ms,error_details=error,checked_at=now,
                            generated_demo=bool(endpoint.scenario_override and demo_enabled()))
    db.add(check);db.flush()
    return state,check
