"""Application configuration using pydantic-settings"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "Medical KG QA System"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # API Keys
    openai_api_key: str = ""
    gemini_api_key: str = ""
    siliconflow_api_key: str = ""  # 硅基流动 API Key

    # LLM Provider: "openai", "gemini", "siliconflow", or "mock"
    llm_provider: str = "siliconflow"

    # SiliconFlow 配置
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = "deepseek-ai/DeepSeek-V3"  # 或 deepseek-ai/DeepSeek-R1

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "medical_docs"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/medical_kg"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000", "http://localhost:5173"]

    # Logging
    log_level: str = "INFO"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
