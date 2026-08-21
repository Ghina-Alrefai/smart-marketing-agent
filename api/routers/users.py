import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api.schemas import UserCreate, UserOut
from api.routers.auth import get_current_user, require_admin
from database.models import User
from database.session import get_db

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger("smartsocial.users")


@router.post("/", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    logger.info("user.create_started")
    try:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            logger.warning("user.create_rejected reason=email_exists")
            raise HTTPException(status_code=409, detail="البريد الإلكتروني مسجل مسبقاً.")
        user = User(**payload.model_dump())
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("user.create_succeeded user_id=%s", user.id)
        return user
    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception("user.create_failed error_type=IntegrityError")
        raise HTTPException(status_code=409, detail="البريد الإلكتروني مسجل مسبقاً.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("user.create_failed error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="حدث خطأ في قاعدة البيانات أثناء إنشاء المستخدم.",
        ) from exc


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != "super_admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="لا يمكنك الوصول إلى مستخدم آخر")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
