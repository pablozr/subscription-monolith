from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    API_PORT: int = 8000
    CORS_ALLOW_ORIGINS: str = "http://localhost:4200"

    DB_HOST: str
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    RABBITMQ_HOST: str
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str
    EMAIL_QUEUE_NAME: str = "email-queue"

    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_LOGIN_MAX_REQUESTS: int = 5
    RATE_LIMIT_GOOGLE_LOGIN_MAX_REQUESTS: int = 10
    RATE_LIMIT_FORGET_PASSWORD_MAX_REQUESTS: int = 5
    RATE_LIMIT_VALIDATE_CODE_MAX_REQUESTS: int = 10

    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str
    SMTP_TIMEOUT_SECONDS: int = 15
    SMTP_USE_STARTTLS: bool = True

    GOOGLE_CLIENT_ID: str

    @property
    def cors_allow_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
