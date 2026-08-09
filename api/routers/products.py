import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from api.schemas import ProductCreate, ProductOut
from database.models import Product
from database.session import get_db
from config import settings
from tools.product_import import parse_products_xlsx

router = APIRouter(prefix="/products", tags=["products"])

PRODUCTS_DIR = Path(settings.UPLOAD_DIR) / "products"
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/", response_model=ProductOut, status_code=201)
def create_product(user_id: int, payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product(user_id=user_id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.post("/bulk-upload")
async def bulk_upload_products(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    رفع ملف Excel (.xlsx) لإضافة عدة منتجات دفعة واحدة، مع دعم صور متعددة لكل منتج
    (روابط في عمود «الصور» مفصولة بـ «|»).
    """
    fname = (file.filename or "").lower()
    if not fname.endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "الرجاء رفع ملف Excel بصيغة .xlsx")

    content = await file.read()
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


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@router.get("/user/{user_id}", response_model=list[ProductOut])
def list_products(user_id: int, db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.user_id == user_id).all()


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Product not found")
    db.delete(p)
    db.commit()


@router.post("/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Product not found")

    ext = Path(file.filename).suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = PRODUCTS_DIR / filename

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    p.image_url = f"/uploads/products/{filename}"
    db.commit()
    return {"image_url": p.image_url}
