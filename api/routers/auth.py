"""
راوتر المصادقة — تسجيل الدخول عبر Google (مستخدم عادي) + الأدمِن الثابت،
وإصدار رمز جلسة (session token) يُستخدم في ترويسة Authorization.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from api.schemas import GoogleLoginRequest, AdminLoginRequest, AuthResponse, UserOut
from api.security import (
    verify_google_id_token, GoogleTokenError,
    verify_password, create_session_token, decode_session_token, utcnow,
)
from database.models import User
from database.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Dependencies ─────────────────────────────────────────────────────────────
def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """يستخرج المستخدم من رمز الجلسة في ترويسة Authorization: Bearer <token>."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="مطلوب تسجيل الدخول")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_session_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="جلسة غير صالحة أو منتهية")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود")
    return user


def require_admin(current: User = Depends(get_current_user)) -> User:
    if current.role != "super_admin":
        raise HTTPException(status_code=403, detail="صلاحيات المشرف مطلوبة")
    return current


# ── Google login (regular users) ─────────────────────────────────────────────
@router.post("/google", response_model=AuthResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        info = verify_google_id_token(payload.credential)
    except GoogleTokenError as e:
        raise HTTPException(status_code=401, detail=str(e))

    email = info["email"]
    if not email:
        raise HTTPException(status_code=400, detail="لم يُرجِع Google بريداً إلكترونياً")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            name=info["name"], email=email, role="user",
            auth_provider="google", google_sub=info["sub"],
            avatar_url=info.get("picture"),
        )
        db.add(user)
    else:
        # تحديث بيانات الحساب من Google عند كل دخول
        user.google_sub = info["sub"] or user.google_sub
        user.avatar_url = info.get("picture") or user.avatar_url
        if user.auth_provider != "super_admin":
            user.auth_provider = "google"
    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)

    token = create_session_token(user.id, user.role)
    return AuthResponse(token=token, user=UserOut.model_validate(user))


# ── Admin login (fixed account) ──────────────────────────────────────────────
@router.post("/admin-login", response_model=AuthResponse)
def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or user.role != "super_admin":
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)

    token = create_session_token(user.id, user.role)
    return AuthResponse(token=token, user=UserOut.model_validate(user))


# ── Current session ──────────────────────────────────────────────────────────
@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current


# ── Admin: list all registered users ─────────────────────────────────────────
@router.get("/users", response_model=list[UserOut])
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.created_at.desc()).all()
