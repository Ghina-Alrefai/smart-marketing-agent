import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from api.schemas import BrandCreate, BrandUpdate, BrandOut, BrandExampleCreate, BrandExampleOut
from database.models import Brand, BrandExample
from database.session import get_db
from config import settings

router = APIRouter(prefix="/brands", tags=["brands"])

TEMPLATES_DIR = Path(settings.UPLOAD_DIR) / "templates"
EXAMPLES_DIR  = Path(settings.UPLOAD_DIR) / "examples"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/", response_model=BrandOut, status_code=201)
def create_brand(user_id: int, payload: BrandCreate, db: Session = Depends(get_db)):
    brand = Brand(user_id=user_id, **payload.model_dump())
    db.add(brand); db.commit(); db.refresh(brand)
    return brand

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
    b = db.query(Brand).filter(Brand.id == brand_id).first()
    if not b: raise HTTPException(404, "Brand not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(b, k, v)
    db.commit(); db.refresh(b)
    return b

@router.post("/{brand_id}/template")
async def upload_template(brand_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a brand design template PNG. Transparent area will be filled with AI-generated image."""
    b = db.query(Brand).filter(Brand.id == brand_id).first()
    if not b: raise HTTPException(404, "Brand not found")
    ext = Path(file.filename).suffix or ".png"
    fname = f"{uuid.uuid4().hex}{ext}"
    with open(TEMPLATES_DIR / fname, "wb") as f:
        f.write(await file.read())
    b.template_url = f"/uploads/templates/{fname}"
    db.commit()
    return {"template_url": b.template_url}

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
