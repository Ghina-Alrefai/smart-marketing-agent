import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from api.ownership import require_product, require_user
from api.routers.auth import get_current_user
from api.upload_validation import read_upload_limited, validate_image_upload
from api.schemas import ProductCreate, ProductOut
from database.models import GeneratedPost, Product, User
from database.session import get_db
from config import settings
from tools.product_import import parse_products_xlsx

router = APIRouter(prefix="/products", tags=["products"])

PRODUCTS_DIR = Path(settings.UPLOAD_DIR) / "products"
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/", response_model=ProductOut, status_code=201)
def create_product(
    user_id: int,
    payload: ProductCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_user(user_id, current, db)
    product = Product(user_id=user_id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.post("/bulk-upload")
async def bulk_upload_products(
    user_id: int,
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    رفع ملف Excel (.xlsx) لإضافة عدة منتجات دفعة واحدة، مع دعم صور متعددة لكل منتج
    (روابط في عمود «الصور» مفصولة بـ «|»).
    """
    require_user(user_id, current, db)
    fname = (file.filename or "").lower()
    if not fname.endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "الرجاء رفع ملف Excel بصيغة .xlsx")

    content = await read_upload_limited(file)
    products, errors = parse_products_xlsx(content)

    created = 0
    for p in products:
        db.add(Product(user_id=user_id, **p))
        created += 1
    if created:
        db.commit()

    return {
        "created": created,
        "skipped": 0,
        "errors": errors,
        "message": (f"تمت إضافة {created} منتجاً بنجاح ✅"
                    if created else "لم تتم إضافة أي منتج."),
    }


@router.get("/user/{user_id}", response_model=list[ProductOut])
def list_products(
    user_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_user(user_id, current, db)
    return db.query(Product).filter(Product.user_id == user_id).all()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return require_product(product_id, current, db)


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = require_product(product_id, current, db)
    if db.query(GeneratedPost.id).filter(GeneratedPost.product_id == product_id).first():
        raise HTTPException(
            409,
            "لا يمكن حذف منتج مرتبط بمنشورات حملة محفوظة؛ احتفظ به لحماية سجل الحملة.",
        )
    db.delete(p)
    db.commit()


@router.post("/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = require_product(product_id, current, db)

    image = await validate_image_upload(file)
    filename = f"{uuid.uuid4().hex}{image.extension}"
    filepath = PRODUCTS_DIR / filename

    with open(filepath, "wb") as f:
        f.write(image.content)

    p.image_url = f"/uploads/products/{filename}"
    db.commit()
    return {"image_url": p.image_url}
