"""Provision local SmartResolve Operations accounts without public role assignment.

Run ``python -m app.provision --local-demo`` for the explicitly opted-in,
localhost-only capstone account. Existing credentials are never reset unless
``--reset-password`` is supplied.
"""
import argparse
import os
from getpass import getpass
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Technician, User
from app.services.auth import hash_password

LOCAL_DEMO_EMAIL = "demo.technician@smartresolve.local"
LOCAL_DEMO_PASSWORD = "SmartResolve-Demo-Only-2026!"
LOCAL_DEMO_TECHNICIAN = "Maya Chen"


def provision_account(db: Session, *, email: str, name: str, password: str,
                      technician_id: int | None = None, role: str = "technician",
                      security_access: bool = False, reset_password: bool = False) -> tuple[User, str]:
    """Create an Operations account once, or explicitly reset its password."""
    email = email.strip().lower()
    technician = db.get(Technician, technician_id) if technician_id is not None else None
    if technician_id is not None and not technician:
        raise ValueError("Technician ID not found")
    if technician and technician.name.casefold() != name.strip().casefold():
        raise ValueError("Name must match the selected technician record")
    existing = db.query(User).filter_by(email=email).first()
    if existing:
        if existing.role != role or existing.technician_id != (technician.id if technician else None):
            raise ValueError("That email already belongs to a different account; no changes were made")
        if reset_password:
            existing.password_hash = hash_password(password)
            db.commit()
            return existing, "password-reset"
        return existing, "unchanged"
    if technician and db.query(User).filter_by(technician_id=technician.id).first():
        raise ValueError("That technician already has a login; no account was created")
    user = User(email=email, full_name=name.strip(), password_hash=hash_password(password),
                role=role, technician_id=technician.id if technician else None,
                security_access=security_access or role == "admin")
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("An account or technician login already exists; no changes were made") from exc
    db.refresh(user)
    return user, "created"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a local SmartResolve Operations login")
    parser.add_argument("--local-demo", action="store_true", help="Use safe localhost-only demo defaults (explicit opt-in)")
    parser.add_argument("--email", help="Account email; required outside --local-demo")
    parser.add_argument("--name", help="Display name; for technicians this must match the technician record")
    parser.add_argument("--technician-id", type=int, help="Bind this account to an existing technician")
    parser.add_argument("--admin", action="store_true", help="Create an administrator account")
    parser.add_argument("--security-access", action="store_true", help="Authorize access to synthetic security events")
    parser.add_argument("--reset-password", action="store_true", help="Explicitly reset an existing matching account password")
    args = parser.parse_args(argv)

    if args.local_demo:
        if os.environ.get("SMARTRESOLVE_ENV", "development").lower() not in {"local", "dev", "development"}:
            parser.error("--local-demo is disabled unless SMARTRESOLVE_ENV is local/development")
        if args.admin or args.technician_id is not None or args.email or args.name:
            parser.error("--local-demo uses its local demo identity; do not combine it with account overrides")
        email = os.environ.get("SMARTRESOLVE_DEMO_TECH_EMAIL", LOCAL_DEMO_EMAIL)
        password = os.environ.get("SMARTRESOLVE_DEMO_TECH_PASSWORD", LOCAL_DEMO_PASSWORD)
        name = os.environ.get("SMARTRESOLVE_DEMO_TECH_NAME", LOCAL_DEMO_TECHNICIAN)
        role = "technician"
        reset = args.reset_password
        security_access = True
    else:
        if not args.email or not args.name:
            parser.error("--email and --name are required unless --local-demo is used")
        if args.admin and args.technician_id is not None:
            parser.error("An admin account cannot be bound to a technician record")
        email, name = args.email, args.name
        role = "admin" if args.admin else "technician"
        password = os.environ.get("SMARTRESOLVE_TECH_PASSWORD") or getpass("Password (minimum 10 characters): ")
        reset = args.reset_password
        security_access = args.security_access or args.admin

    if len(password) < 10:
        parser.error("Password must be at least 10 characters")

    # Apply the project's normal additive migrations and idempotent synthetic seed.
    from app.main import initialize_database
    initialize_database()
    db = SessionLocal()
    try:
        technician_id = args.technician_id
        if args.local_demo:
            technician = db.query(Technician).filter_by(name=name).first()
            if not technician:
                parser.error(f"Seed technician {name!r} was not found; choose a seeded technician or set SMARTRESOLVE_DEMO_TECH_NAME")
            technician_id = technician.id
        user, result = provision_account(db, email=email, name=name, password=password,
            technician_id=technician_id, role=role, security_access=security_access, reset_password=reset)
        if result == "created":
            print(f"Created local {user.role} account for {user.email}" + (" with synthetic security access" if user.security_access else ""))
        elif result == "password-reset":
            print(f"Reset password for existing local {user.role} account {user.email}; role and permissions were unchanged")
        else:
            print(f"Local {user.role} account {user.email} already exists; left unchanged")
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        db.close()


if __name__ == "__main__":
    main()
