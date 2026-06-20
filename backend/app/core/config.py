from typing import List, Union, Optional

from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nimbus"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "changethisinproduction"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 # 8 days
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://nimbus:nimbus@db:5432/nimbus_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "nimbus-attachments"
    
    # OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None
    
    # This should be the base URL of your backend (e.g. http://localhost:8100)
    BACKEND_URL: str = "http://localhost:8100"

    # AI Models
    MLX_CHAT_MODEL: str = "mlx-community/gemma-3-4b-it-4bit"
    MLX_FAST_MODEL: str = "mlx-community/Llama-3.2-1B-Instruct-4bit"
    EMBEDDING_MODEL: str = "nomic-ai/nomic-embed-text-v1"

    class Config:

        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()
