from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://dhm:dhm@localhost:5433/dhm"
    base_url: str = "http://localhost:8000"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False  # implicit TLS, usually port 465
    smtp_starttls: bool = False  # STARTTLS, usually port 587
    smtp_from: str = "DHM Group <no-reply@dhmgroup.net>"


settings = Settings()
