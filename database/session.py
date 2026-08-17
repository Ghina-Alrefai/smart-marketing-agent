import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from database.models import Base
from config import settings

logger = logging.getLogger("smartsocial.database")
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=settings.SQL_ECHO,
)


if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
        "intelligence_summary": "JSON", "current_stage": "VARCHAR(200)",
        "error_message": "TEXT",
    },
    "brands": {
        "dna_status": "VARCHAR(30) DEFAULT 'uninitialized'",
        "dna_profile": "JSON", "dna_profile_version": "VARCHAR(120)",
        "dna_model_scope": "VARCHAR(30) DEFAULT 'none'",
        "dna_training_post_count": "INTEGER DEFAULT 0",
    },
    "generated_posts": {
        "post_id": "VARCHAR(50)", "idea": "JSON", "design": "JSON",
        "candidate_results": "JSON", "selected_candidate": "JSON",
        "predesign_score": "FLOAT", "multimodal_score": "FLOAT",
        "intelligence_status": "VARCHAR(50) DEFAULT 'not_evaluated'",
        "evaluation": "JSON", "dna_profile_version": "VARCHAR(120)",
        "dna_model_version": "VARCHAR(120)", "memory_policy_ids": "JSON",
        "generation_trace_id": "VARCHAR(120)",
    },
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
                    logger.info("database.migration_added table=%s column=%s", table, col)


def init_db() -> None:
    """Create all tables, then add any missing columns to existing ones."""
    logger.info("database.initialization_started sqlite=%s", _is_sqlite)
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    logger.info("database.initialization_completed")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for DB sessions."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
