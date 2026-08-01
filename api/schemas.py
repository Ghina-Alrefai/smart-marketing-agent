from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr

class UserOut(BaseModel):
    id: int; name: str; email: str; plan: str; created_at: datetime
    model_config = {"from_attributes": True}


class BrandCreate(BaseModel):
    brand_name: str
    business_description: str | None = None
    tone_of_voice: str | None = None
    content_style: str | None = None
    visual_style: str | None = None
    brand_colors: list[str] = []
    target_audience: str | None = None
    language: str = "ar"
    must_use_words: list[str] = []
    forbidden_words: list[str] = []
    preferred_cta: str | None = None
    preferred_content_types: list[str] = []

class BrandUpdate(BrandCreate):
    brand_name: str | None = None

class BrandOut(BrandCreate):
    id: int; user_id: int
    logo_url: str | None = None
    template_url: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class BrandExampleCreate(BaseModel):
    example_type: str
    content: str | None = None

class BrandExampleOut(BrandExampleCreate):
    id: int; brand_id: int; image_url: str | None = None
    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    title: str
    description: str | None = None
    price: float | None = None
    category: str | None = None

class ProductOut(ProductCreate):
    id: int; user_id: int
    image_url: str | None = None
    post_count: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class ContentPlanCreate(BaseModel):
    brand_id: int
    campaign_name: str | None = None
    start_date: datetime | None = None
    days: int = 7
    campaign_goal: str | None = None

class ContentPlanOut(ContentPlanCreate):
    id: int; user_id: int; status: str; created_at: datetime
    model_config = {"from_attributes": True}


class PostApprovalUpdate(BaseModel):
    approved: bool

class GeneratedPostOut(BaseModel):
    id: int; content_plan_id: int; product_id: int | None
    day_number: int; post_type: str; post_goal: str
    hook: str; caption: str; cta: str; hashtags: list[str]
    image_prompt: str; image_url: str | None
    status: str; approved: bool; review_notes: str | None
    scheduled_at: datetime | None; created_at: datetime
    model_config = {"from_attributes": True}


class GenerationStatusOut(BaseModel):
    plan_id: int; status: str
    posts_generated: int | None = None
    message: str | None = None
