from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float,
    Boolean, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    email      = Column(String(255), unique=True, nullable=False, index=True)
    plan       = Column(String(50), default="free")
    created_at = Column(DateTime, default=datetime.utcnow)

    brands   = relationship("Brand",   back_populates="user", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")


class Brand(Base):
    __tablename__ = "brands"
    id                      = Column(Integer, primary_key=True, index=True)
    user_id                 = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand_name              = Column(String(150), nullable=False)
    logo_url                = Column(String(500))        # kept for display only
    template_url            = Column(String(500))        # user-uploaded design template (PNG)
    business_description    = Column(Text)
    tone_of_voice           = Column(String(200))
    content_style           = Column(String(200))
    visual_style            = Column(String(200))
    brand_colors            = Column(JSON, default=list)
    target_audience         = Column(Text)
    language                = Column(String(20), default="ar")
    must_use_words          = Column(JSON, default=list)
    forbidden_words         = Column(JSON, default=list)
    preferred_cta           = Column(String(200))
    preferred_content_types = Column(JSON, default=list)
    # Stable Brand-DNA state. Performance-derived memory is stored separately
    # by Adaptive Memory and never overwrites this profile automatically.
    dna_status              = Column(String(30), default="uninitialized")
    dna_profile             = Column(JSON, default=dict)
    dna_profile_version     = Column(String(120))
    dna_model_scope         = Column(String(30), default="none")
    dna_training_post_count = Column(Integer, default=0)
    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user         = relationship("User",         back_populates="brands")
    examples     = relationship("BrandExample", back_populates="brand", cascade="all, delete-orphan")
    content_plans= relationship("ContentPlan",  back_populates="brand", cascade="all, delete-orphan")


class BrandExample(Base):
    __tablename__ = "brand_examples"
    id           = Column(Integer, primary_key=True, index=True)
    brand_id     = Column(Integer, ForeignKey("brands.id"), nullable=False)
    example_type = Column(String(50))   # post | design
    content      = Column(Text)
    image_url    = Column(String(500))
    created_at   = Column(DateTime, default=datetime.utcnow)

    brand = relationship("Brand", back_populates="examples")


class Product(Base):
    __tablename__ = "products"
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    title       = Column(String(300), nullable=False)
    description = Column(Text)
    price       = Column(Float)
    category    = Column(String(100))
    image_url   = Column(String(500))
    image_urls  = Column(JSON, default=list)       # صور متعددة للمنتج (روابط)
    source_url  = Column(String(500))              # رابط صفحة المنتج الأصلية (اختياري)
    post_count  = Column(Integer, default=0)
    is_marketed = Column(Boolean, default=False)   # هل سُوّق له سابقاً؟
    created_at  = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="products")


class ContentPlan(Base):
    __tablename__ = "content_plans"
    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand_id      = Column(Integer, ForeignKey("brands.id"), nullable=False)
    campaign_name = Column(String(200))
    start_date    = Column(DateTime)
    days          = Column(Integer, default=7)
    campaign_goal = Column(String(200))                    # يبقى للتوافق الخلفي (أول هدف)
    campaign_goals  = Column(JSON, default=list)           # أهداف متعددة للحملة
    product_ids     = Column(JSON, default=list)           # المنتجات المختارة (فارغ = كل المنتجات)
    selected_events = Column(JSON, default=list)           # المناسبات المختارة ضمن مدة الحملة
    include_trends  = Column(Boolean, default=False)       # هل نضمّن التريندات؟
    selected_trends = Column(JSON, default=list)           # التريندات المختارة (سياق الحملة)
    mode            = Column(String(20), default="campaign")  # campaign (المعمارية الجديدة) | legacy
    strategy        = Column(JSON, default=dict)           # مخرَج Strategy Agent المهيكل
    campaign_data   = Column(JSON, default=dict)           # كائن الحملة الموحّد النهائي
    intelligence_summary = Column(JSON, default=dict)      # إصدارات DNA/Memory المستخدمة
    status        = Column(String(50), default="pending")
    current_stage = Column(String(200), nullable=True)      # آخر مرحلة وصل إليها التوليد
    error_message = Column(Text, nullable=True)             # سبب فشل المهمة الخلفية للمستخدم
    created_at    = Column(DateTime, default=datetime.utcnow)

    brand = relationship("Brand",         back_populates="content_plans")
    posts = relationship("GeneratedPost", back_populates="content_plan", cascade="all, delete-orphan")


class GeneratedPost(Base):
    __tablename__ = "generated_posts"
    id              = Column(Integer, primary_key=True, index=True)
    content_plan_id = Column(Integer, ForeignKey("content_plans.id"), nullable=False)
    product_id      = Column(Integer, ForeignKey("products.id"), nullable=True)
    post_id         = Column(String(50))       # المعرّف الأساسي الثابت للبوست (post_001...) عبر كل المراحل
    idea            = Column(JSON, default=dict)  # الفكرة القانونية المشتركة (مصدر الحقيقة الوحيد للبوست)
    design          = Column(JSON, default=dict)  # مخرَج Design Agent المهيكل
    day_number      = Column(Integer)
    post_type       = Column(String(100))
    post_goal       = Column(String(200))
    hook            = Column(Text)
    caption         = Column(Text)
    cta             = Column(Text)
    hashtags        = Column(JSON, default=list)
    image_prompt    = Column(Text)
    image_url       = Column(String(500))
    status          = Column(String(50), default="draft")
    approved        = Column(Boolean, default=False)
    review_notes    = Column(Text)
    scheduled_at    = Column(DateTime, nullable=True)
    # Reproducible intelligence trace for committee/demo and later learning.
    candidate_results   = Column(JSON, default=list)
    selected_candidate  = Column(JSON, default=dict)
    predesign_score     = Column(Float, nullable=True)
    multimodal_score    = Column(Float, nullable=True)
    intelligence_status = Column(String(50), default="not_evaluated")
    evaluation          = Column(JSON, default=dict)
    dna_profile_version = Column(String(120), nullable=True)
    dna_model_version   = Column(String(120), nullable=True)
    memory_policy_ids   = Column(JSON, default=list)
    generation_trace_id = Column(String(120), nullable=True, index=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    content_plan = relationship("ContentPlan",  back_populates="posts")
    product      = relationship("Product")
    performance_snapshots = relationship(
        "PostPerformanceSnapshot", back_populates="generated_post",
        cascade="all, delete-orphan",
    )


class PostPerformanceSnapshot(Base):
    """Observed Facebook/manual metrics after a fixed window.

    These rows are operational audit records. Adaptive Memory stores the
    immutable per-feature Evidence derived from them in its own storage layer.
    """
    __tablename__ = "post_performance_snapshots"
    id                = Column(Integer, primary_key=True, index=True)
    generated_post_id = Column(Integer, ForeignKey("generated_posts.id"), nullable=False)
    observation_window = Column(String(30), default="24h")
    actual_success     = Column(Boolean, nullable=False)
    reactions          = Column(Float, nullable=True)
    comments           = Column(Float, nullable=True)
    shares             = Column(Float, nullable=True)
    reach              = Column(Float, nullable=True)
    clicks             = Column(Float, nullable=True)
    weighted_engagement = Column(Float, nullable=True)
    relative_performance_index = Column(Float, nullable=True)
    memory_parent_event_id = Column(String(160), nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)

    generated_post = relationship("GeneratedPost", back_populates="performance_snapshots")


class ScheduledPost(Base):
    """منشور مجدول للنشر في وقت محدد — يظهر في قسم «المجدولة»."""
    __tablename__ = "scheduled_posts"
    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    generated_post_id = Column(Integer, ForeignKey("generated_posts.id"), nullable=True)  # ربط بمنشور الحملة (للجدولة التلقائية)
    hook         = Column(Text)
    caption      = Column(Text)
    cta          = Column(Text)
    hashtags     = Column(JSON, default=list)
    image_url    = Column(String(500))
    scheduled_at = Column(DateTime, nullable=True)     # الوقت المحلَّل
    time_text    = Column(String(200))                 # النص الأصلي كما كتبه المستخدم
    status       = Column(String(50), default="scheduled")  # scheduled | published | cancelled
    created_at   = Column(DateTime, default=datetime.utcnow)
