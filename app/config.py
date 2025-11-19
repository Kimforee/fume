from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/product_importer"
    database_url_sync: str = "postgresql://user:password@localhost:5432/product_importer"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # Application
    secret_key: str = "your-secret-key-here-change-in-production"
    debug: bool = True
    environment: str = "development"
    
    # API
    api_title: str = "Product Importer API"
    api_version: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

