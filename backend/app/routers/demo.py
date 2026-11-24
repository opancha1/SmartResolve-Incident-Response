from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.capstone import load_capstone
from app.services.auth import require_roles
from app.services.demo import REPORTS, reset_scenarios, run_scenario
from app.services.demo_config import demo_enabled

router = APIRouter(prefix="/api/demo", tags=["Demo control center"])
operations = require_roles("technician", "admin")
Action = Literal["network-outage", "suspicious-login", "classroom-av", "duplicate-tickets", "campus-software",
                 "network-recovery", "network-unknown", "load", "capstone", "reset"]


class DemoAction(BaseModel):
    confirm: bool = False


@router.get("")
def demo_status(user: User = Depends(operations)):
    return {"enabled": demo_enabled(), "security_actions": user.can_view_security}


@router.post("/{action}")
def execute(action: Action, data: DemoAction, db: Session = Depends(get_db), user: User = Depends(operations)):
    if not demo_enabled():
        raise HTTPException(404, "Demo mode is disabled")
    if action in {"suspicious-login", "load", "capstone", "reset"} and not user.can_view_security:
        raise HTTPException(403, "Security access is required for this action")
    if action == "reset" and not data.confirm:
        raise HTTPException(422, "Confirm the demo reset")
    # Serializes repeat triggers and resets in SQLite.
    db.execute(text("BEGIN IMMEDIATE"))
    if action == "reset":
        result = {"message": "Generated scenario records were reset.", "removed": reset_scenarios(db)}
    elif action == "capstone":
        result = load_capstone(db)
    elif action == "load":
        result = {"message": "Integrated demo dataset loaded.",
                  "scenarios": {scenario: run_scenario(db, scenario) for scenario in REPORTS}}
    else:
        result = run_scenario(db, action)
    db.commit()
    return result
