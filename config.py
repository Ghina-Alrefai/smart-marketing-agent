from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Secure by default: local/test mode must be explicitly selected (the
    # provided .env.example does so). A missing .env therefore cannot silently
    # start a public server with the development admin password/JWT key.
    APP_ENV: str = "production"
    GOOGLE_API_KEY: str = ""
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    DATABASE_URL: str = "sqlite:///./marketing_os.db"
    UPLOAD_DIR: str = "./uploads"
    SECRET_KEY: str = "change-me-in-production"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-image"
    GEMINI_MAX_OUTPUT_TOKENS: int = 16_384
    LLM_JSON_MAX_ATTEMPTS: int = 3
    MAX_UPLOAD_SIZE_MB: int = 10

    # Brand-DNA + Adaptive Memory integration
    BRAND_DNA_ROOT: str = "."
    ADAPTIVE_MEMORY_DB: str = "./outputs/adaptive_memory/app.db"
    BRAND_DNA_PRELOAD_MODELS: bool = True
    BRAND_DNA_GENERATION_MAX_ATTEMPTS: int = 3
    BRAND_DNA_MIN_CANDIDATE_PROBABILITY: float = 0.50
    BRAND_DNA_MODEL_BRAND_KEYS: str = "al-boraq"
    COLD_START_MIN_TRAINING_POSTS: int = 30
    DEFAULT_SCHEDULE_HOUR: int = 20

    # Evidence-driven lifecycle for learned Adaptive Memory policies.
    POLICY_REVIEW_ENABLED: bool = True
    POLICY_REVIEW_CHECK_INTERVAL_SECONDS: int = 86_400
    POLICY_REVIEW_INTERVAL_DAYS: int = 30
    POLICY_REVIEW_GRACE_DAYS: int = 15
    POLICY_REVIEW_MIN_POSTS: int = 8
    POLICY_REVIEW_DEFERRAL_DAYS: int = 14
    POLICY_REVIEW_MAX_INSUFFICIENT_REVIEWS: int = 2
    POLICY_REVIEW_RENEW_MIN_SUCCESS_RATE: float = 0.60
    POLICY_REVIEW_MODIFY_MIN_SUCCESS_RATE: float = 0.50
    POLICY_REVIEW_EXPIRE_BELOW_SUCCESS_RATE: float = 0.35

    # Application logging. Keep SQL_ECHO disabled unless a local database
    # diagnosis specifically requires raw SQL output.
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"
    LOG_TO_FILE: bool = True
    LOG_MAX_BYTES: int = 5_000_000
    LOG_BACKUP_COUNT: int = 5
    SQL_ECHO: bool = False

    # ── Google Sign-In (OAuth 2.0) ───────────────────────────────────────────
    # القيم الحقيقية تُقرأ من .env — هذه فقط قيم افتراضية آمنة للتطوير.
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── Fixed super-admin account ────────────────────────────────────────────
    ADMIN_EMAIL: str = "admin@gmail.com"
    ADMIN_PASSWORD: str = "admin2026"      # تُهيّأ كـ hash في قاعدة البيانات عند الإقلاع
    ADMIN_NAME: str = "Super Admin"

    # مدة صلاحية رمز الجلسة (بالأيام)
    SESSION_TOKEN_DAYS: int = 30


settings = Settings()
