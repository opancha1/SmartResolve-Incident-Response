"""Small local auth layer: PBKDF2 password hashes and short-lived signed bearer tokens."""
import base64, hashlib, hmac, os, secrets, time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

_ITERATIONS = 310_000
_bearer = HTTPBearer(auto_error=False)

_PROCESS_SECRET = secrets.token_bytes(32)
def _secret():
    # An explicit secret keeps sessions valid across restarts. The random fallback
    # is private to this process, so an unset development secret cannot be guessed.
    return os.environ.get("SMARTRESOLVE_SECRET_KEY", "").encode() or _PROCESS_SECRET

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256": return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError): return False

def issue_token(user: User) -> str:
    payload = f"{user.id}:{int(time.time()) + 86400}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode().rstrip("=")

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if not credentials: raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate":"Bearer"})
    try:
        raw = base64.urlsafe_b64decode(credentials.credentials + "=" * (-len(credentials.credentials) % 4)).decode()
        user_id, expiry, signature = raw.split(":", 2)
        payload = f"{user_id}:{expiry}"
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected) or int(expiry) < int(time.time()): raise ValueError()
        user = db.get(User, int(user_id))
    except (ValueError, TypeError): user = None
    if not user: raise HTTPException(401, "Invalid or expired session", headers={"WWW-Authenticate":"Bearer"})
    return user

def require_roles(*roles):
    def dependency(user: User = Depends(current_user)):
        if user.role not in roles: raise HTTPException(403, "Insufficient permissions")
        return user
    return dependency
