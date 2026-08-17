import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api.schemas import BrandCreate, BrandUpdate, BrandOut, BrandExampleCreate, BrandExampleOut
from database.models import Brand, BrandExample, User
from database.session import get_db
from config import settings

router = APIRouter(prefix="/brands", tags=["brands"])
logger = logging.getLogger("smartsocial.brands")

TEMPLATES_DIR = Path(settings.UPLOAD_DIR) / "templates"
EXAMPLES_DIR  = Path(settings.UPLOAD_DIR) / "examples"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/", response_model=BrandOut, status_code=201)
def create_brand(user_id: int, payload: BrandCreate, db: Session = Depends(get_db)):
    logger.info("brand.create_started user_id=%s", user_id)
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("brand.create_rejected user_id=%s reason=user_not_found", user_id)
            raise HTTPException(
                status_code=404,
                detail=(
                    "المستخدم المرتبط بالبراند غير موجود. قد تكون قاعدة البيانات أُعيد إنشاؤها "
                    "بينما بقيت بيانات قديمة في المتصفح؛ افتح الإعدادات وأنشئ المستخدم من جديد."
                ),
            )

        brand = Brand(user_id=user_id, **payload.model_dump())
        db.add(brand)
        db.commit()
        db.refresh(brand)
        logger.info("brand.create_succeeded user_id=%s brand_id=%s", user_id, brand.id)
        return brand
    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception(
            "brand.create_failed user_id=%s error_type=IntegrityError",
            user_id,
        )
        raise HTTPException(
            status_code=409,
            detail="تعذر إنشاء البراند بسبب تعارض في بيانات قاعدة البيانات.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "brand.create_failed user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="حدث خطأ في قاعدة البيانات أثناء إنشاء البراند.",
        ) from exc

@router.get("/user/{user_id}", response_model=list[BrandOut])
def list_brands(user_id: int, db: Session = Depends(get_db)):
    return db.query(Brand).filter(Brand.user_id == user_id).all()

@router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: int, db: Session = Depends(get_db)):
    b = db.query(Brand).filter(Brand.id == brand_id).first()
    if not b: raise HTTPException(404, "Brand not found")
    return b

@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: int, payload: BrandUpdate, db: Session = Depends(get_db)):
    logger.info("brand.update_started brand_id=%s", brand_id)
    try:
        b = db.query(Brand).filter(Brand.id == brand_id).first()
        if not b:
            raise HTTPException(404, "Brand not found")
        for k, v in payload.model_dump(exclude_none=True).items():
            setattr(b, k, v)
        # Rebuild the stable profile from the edited human-approved identity on the
        # next request. Adaptive Memory remains separate and is not erased.
        b.dna_status = "uninitialized"
        b.dna_profile = {}
        b.dna_profile_version = None
        b.dna_model_scope = "none"
        b.dna_training_post_count = 0
        db.commit()
        db.refresh(b)
        logger.info("brand.update_succeeded brand_id=%s", brand_id)
        return b
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "brand.update_failed brand_id=%s error_type=%s",
            brand_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="حدث خطأ في قاعدة البيانات أثناء تحديث البراند.",
        ) from exc

@router.post("/{brand_id}/template")
async def upload_template(brand_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a brand design template PNG. Transparent area will be filled with AI-generated image."""
    logger.info("brand.template_upload_started brand_id=%s", brand_id)
    b = db.query(Brand).filter(Brand.id == brand_id).first()
    if not b: raise HTTPException(404, "Brand not found")
    ext = Path(file.filename or "").suffix or ".png"
    fname = f"{uuid.uuid4().hex}{ext}"
    try:
        with open(TEMPLATES_DIR / fname, "wb") as f:
            f.write(await file.read())
        b.template_url = f"/uploads/templates/{fname}"
        b.dna_status = "uninitialized"
        b.dna_profile = {}
        b.dna_profile_version = None
        db.commit()
        logger.info("brand.template_upload_succeeded brand_id=%s", brand_id)
        return {"template_url": b.template_url}
    except (OSError, SQLAlchemyError) as exc:
        db.rollback()
        logger.exception(
            "brand.template_upload_failed brand_id=%s error_type=%s",
            brand_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="تم حفظ البراند، لكن تعذر حفظ قالب التصميم.",
        ) from exc

@router.post("/{brand_id}/examples", response_model=BrandExampleOut, status_code=201)
def add_text_example(brand_id: int, payload: BrandExampleCreate, db: Session = Depends(get_db)):
    ex = BrandExample(brand_id=brand_id, **payload.model_dump())
    db.add(ex); db.commit(); db.refresh(ex)
    return ex

@router.post("/{brand_id}/examples/image", response_model=BrandExampleOut, status_code=201)
async def upload_design_example(brand_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    b = db.query(Brand).filter(Brand.id == brand_id).first()
    if not b: raise HTTPException(404, "Brand not found")
    ext = Path(file.filename).suffix or ".png"
    fname = f"{uuid.uuid4().hex}{ext}"
    with open(EXAMPLES_DIR / fname, "wb") as f:
        f.write(await file.read())
    ex = BrandExample(brand_id=brand_id, example_type="design", image_url=f"/uploads/examples/{fname}")
    db.add(ex); db.commit(); db.refresh(ex)
    return ex

@router.delete("/examples/{example_id}", status_code=204)
def delete_example(example_id: int, db: Session = Depends(get_db)):
    ex = db.query(BrandExample).filter(BrandExample.id == example_id).first()
    if not ex: raise HTTPException(404, "Not found")
    db.delete(ex); db.commit()

@router.get("/{brand_id}/examples", response_model=list[BrandExampleOut])
def list_examples(brand_id: int, db: Session = Depends(get_db)):
    return db.query(BrandExample).filter(BrandExample.brand_id == brand_id).all()
