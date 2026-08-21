from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    name: str
    email: EmailStr

class UserOut(BaseModel):
    id: int; name: str; email: str; plan: str
    role: str = "user"
    auth_provider: str = "google"
    avatar_url: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Authentication ───────────────────────────────────────────────────────────
class GoogleLoginRequest(BaseModel):
    credential: str          # الـ ID token القادم من Google Identity Services

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    user: UserOut


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
    dna_status: str = "uninitialized"
    dna_profile_version: str | None = None
    dna_model_scope: str = "none"
    dna_training_post_count: int = 0
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
    image_urls: list[str] = []
    source_url: str | None = None
    post_count: int = 0
    is_marketed: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator("image_urls", mode="before")
    @classmethod
    def _none_to_list(cls, v):   # الصفوف القديمة قد تحمل NULL
        return v or []


class ContentPlanCreate(BaseModel):
    brand_id: int
    campaign_name: str | None = None
    start_date: datetime | None = None
    days: int = 7
    campaign_goal: str | None = None          # يبقى للتوافق الخلفي
    campaign_goals: list[str] = []            # أهداف متعددة
    product_ids: list[int] = []               # المنتجات المختارة (فارغ = الكل)
    selected_events: list[dict] = []          # المناسبات المختارة ضمن المدة
    include_trends: bool = False              # تضمين التريندات
    selected_trends: list[dict] = []          # التريندات المختارة (سياق الحملة)
    mode: str = "campaign"                    # campaign (الجديدة) | legacy

class ContentPlanOut(ContentPlanCreate):
    id: int; user_id: int; status: str; created_at: datetime
    current_stage: str | None = None
    error_message: str | None = None
    strategy: dict[str, Any] = {}
    campaign_data: dict[str, Any] = {}
    intelligence_summary: dict[str, Any] = {}
    model_config = {"from_attributes": True}

    @field_validator("campaign_goals", "product_ids", "selected_events", "selected_trends",
                     mode="before")
    @classmethod
    def _none_to_list(cls, v):   # الصفوف القديمة قد تحمل NULL
        return v or []

    @field_validator("strategy", "campaign_data", "intelligence_summary", mode="before")
    @classmethod
    def _none_to_plan_dicts(cls, v):
        return v or {}


class PostApprovalUpdate(BaseModel):
    approved: bool

class GeneratedPostOut(BaseModel):
    id: int; content_plan_id: int; product_id: int | None
    post_id: str | None = None
    idea: dict[str, Any] = {}
    design: dict[str, Any] = {}
    day_number: int; post_type: str; post_goal: str
    hook: str; caption: str; cta: str; hashtags: list[str]
    image_prompt: str; image_url: str | None
    status: str; approved: bool; review_notes: str | None
    scheduled_at: datetime | None; created_at: datetime
    candidate_results: list[dict[str, Any]] = []
    selected_candidate: dict[str, Any] = {}
    predesign_score: float | None = None
    multimodal_score: float | None = None
    intelligence_status: str = "not_evaluated"
    evaluation: dict[str, Any] = {}
    dna_profile_version: str | None = None
    dna_model_version: str | None = None
    memory_policy_ids: list[str] = []
    generation_trace_id: str | None = None
    model_config = {"from_attributes": True}

    @field_validator("candidate_results", "memory_policy_ids", mode="before")
    @classmethod
    def _none_to_generated_lists(cls, v):
        return v or []

    @field_validator("idea", "design", "selected_candidate", "evaluation", mode="before")
    @classmethod
    def _none_to_generated_dicts(cls, v):
        return v or {}


class GenerationStatusOut(BaseModel):
    plan_id: int; status: str
    posts_generated: int | None = None
    message: str | None = None
    current_stage: str | None = None
    error_message: str | None = None


class ScheduledPostOut(BaseModel):
    id: int; hook: str | None; caption: str | None; cta: str | None
    hashtags: list[str] = []
    image_url: str | None = None
    scheduled_at: str | None = None
    time_text: str | None = None
    status: str
    created_at: str | None = None


class ScheduledTimeUpdate(BaseModel):
    scheduled_at: datetime   # الوقت الجديد للنشر


class PostPerformanceCreate(BaseModel):
    observation_window: str = "24h"
    actual_success: bool
    reactions: float | None = None
    comments: float | None = None
    shares: float | None = None
    reach: float | None = None
    clicks: float | None = None
    weighted_engagement: float | None = None
    relative_performance_index: float | None = None


class PolicyActivationCreate(BaseModel):
    approved_by: str

    @field_validator("approved_by")
    @classmethod
    def _approved_by_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("approved_by is required")
        return value
