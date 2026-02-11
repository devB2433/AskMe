from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "postgresql://askme_user:askme_password@localhost:5432/askme"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # 向量数据库配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    
    # 搜索引擎配置
    ELASTICSEARCH_HOST: str = "localhost"
    ELASTICSEARCH_PORT: int = 9200
    
    # 文件存储配置
    UPLOAD_DIR: str = "./uploads"
    PROCESSED_DIR: str = "./processed"
    
    # 模型配置
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    MAX_DOCUMENT_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # OCR配置
    OCR_ENABLED: bool = True
    GLM_OCR_API_URL: Optional[str] = None  # 本地GLM-OCR服务地址
    
    class Config:
        env_file = ".env"

settings = Settings()