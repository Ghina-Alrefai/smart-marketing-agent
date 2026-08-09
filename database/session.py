from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from database.models import Base
from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},   # SQLite only
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── ترحيل خفيف: يضيف الأعمدة الناقصة لقواعد بيانات قديمة بلا فقدان بيانات ──────
# SQLite يدعم ALTER TABLE ADD COLUMN فقط، فنضيف الأعمدة الجديدة يدوياً إن غابت.
_MIGRATIONS: dict[str, dict[str, str]] = {
    "products":        {"is_marketed": "BOOLEAN DEFAULT 0", "image_urls": "JSON",
                        "source_url": "VARCHAR(500)"},
    "content_plans":   {
        "campaign_goals": "JSON", "product_ids": "JSON", "selected_events": "JSON",
        "include_trends": "BOOLEAN DEFAULT 0", "selected_trends": "JSON",
        "mode": "VARCHAR(20) DEFAULT 'campaign'", "strategy": "JSON", "campaign_data": "JSON",
    },
    "generated_posts": {"post_id": "VARCHAR(50)", "idea": "JSON", "design": "JSON"},
    "scheduled_posts": {"generated_post_id": "INTEGER"},
}


def _run_migrations() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _MIGRATIONS.items():
            if table not in existing_tables:
                continue  # جدول جديد أنشأه create_all بالفعل بكل أعمدته
            have = {c["name"] for c in inspector.get_columns(table)}
            for col, ddl in columns.items():
                if col not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                    print(f"[Migration] +{table}.{col}")


def init_db() -> None:
    """Create all tables, then add any missing columns to existing ones."""
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
