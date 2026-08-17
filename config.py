from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    GOOGLE_API_KEY: str = ""
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    DATABASE_URL: str = "sqlite:///./marketing_os.db"
    UPLOAD_DIR: str = "./uploads"
    SECRET_KEY: str = "change-me-in-production"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-image"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Brand-DNA + Adaptive Memory integration
    BRAND_DNA_ROOT: str = "."
    ADAPTIVE_MEMORY_DB: str = "./outputs/adaptive_memory/app.db"
    BRAND_DNA_GENERATION_MAX_ATTEMPTS: int = 3
    BRAND_DNA_MIN_CANDIDATE_PROBABILITY: float = 0.50
    BRAND_DNA_MODEL_BRAND_KEYS: str = "al-boraq"
    COLD_START_MIN_TRAINING_POSTS: int = 30
    DEFAULT_SCHEDULE_HOUR: int = 20

    # Application logging. Keep SQL_ECHO disabled unless a local database
    # diagnosis specifically requires raw SQL output.
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"
    LOG_TO_FILE: bool = True
    LOG_MAX_BYTES: int = 5_000_000
    LOG_BACKUP_COUNT: int = 5
    SQL_ECHO: bool = False


settings = Settings()
