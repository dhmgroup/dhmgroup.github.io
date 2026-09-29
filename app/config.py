from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-insecure-secret-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://dhm:dhm@localhost:5433/dhm"
    base_url: str = "http://localhost:8000"
    secret_key: str = DEV_SECRET_KEY
    timezone: str = "Africa/Lusaka"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False  # implicit TLS, usually port 465
    smtp_starttls: bool = False  # STARTTLS, usually port 587
    smtp_from: str = "DHM Group <no-reply@dhmgroup.net>"

    @model_validator(mode="after")
    def _real_secret_in_production(self):
        if self.env == "production" and self.secret_key == DEV_SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in production")
        return self


settings = Settings()
