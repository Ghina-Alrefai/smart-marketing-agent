from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GOOGLE_API_KEY: str = ""
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    DATABASE_URL: str = "sqlite:///./marketing_os.db"
    UPLOAD_DIR: str = "./uploads"
    SECRET_KEY: str = "change-me-in-production"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-image"
    MAX_UPLOAD_SIZE_MB: int = 10

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
