from datetime import datetime, timezone
from typing import Annotated
from pydantic import PlainSerializer


def utc_naive(value):
    """SQLite stores UTC wall-clock values without an offset."""
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def wire_utc(value):
    return utc_naive(value).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


UtcTimestamp = Annotated[datetime, PlainSerializer(wire_utc, return_type=str, when_used="json")]
