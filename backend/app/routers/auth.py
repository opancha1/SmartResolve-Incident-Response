from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, UserOut
from app.services.auth import current_user, hash_password, issue_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
@router.post("/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"): raise HTTPException(422, "Enter a valid email address")
    if db.query(User).filter(User.email == email).first(): raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, full_name=data.full_name.strip(), password_hash=hash_password(data.password), role="user")
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": issue_token(user), "token_type":"bearer", "user":UserOut(id=user.id,email=user.email,full_name=user.full_name,role=user.role,can_view_security=user.security_access or user.role=="admin")}
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Email or password is incorrect")
    return {"access_token": issue_token(user), "token_type":"bearer", "user":UserOut(id=user.id,email=user.email,full_name=user.full_name,role=user.role,can_view_security=user.security_access or user.role=="admin")}
@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user
