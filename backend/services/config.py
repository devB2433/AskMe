"""AskMe 配置管理"""
import os
from pathlib import Path
from typing import Optional
import json

# 配置文件路径
CONFIG_FILE = Path(__file__).parent.parent / "config.json"


class Config:
    """配置管理类"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """加载配置"""
        # 默认配置
        self._config = {
            # 文档上传配置
            "upload": {
                "max_batch_size": 20,          # 最大批量上传数量
                "max_file_size_mb": 100,        # 单文件最大大小(MB)
                "allowed_extensions": [
                    ".pdf", ".docx", ".doc", ".txt", ".md",
                    ".xlsx", ".xls", ".pptx", ".ppt",
                    ".png", ".jpg", ".jpeg", ".bmp"
                ],
                "concurrent_uploads": 3         # 并发上传数量
            },
            
            # 文档处理配置
            "processing": {
                "chunk_size": 500,              # 分块大小
                "chunk_overlap": 50,            # 分块重叠
                "enable_ocr": True,             # 启用OCR
                "ocr_timeout": 60               # OCR超时时间(秒)
            },
            
            # 向量化配置
            "vector": {
                "embedding_model": "BAAI/bge-small-zh-v1.5",
                "embedding_dimension": 512,
                "batch_size": 32                # 向量化批处理大小
            },
            
            # 队列配置
            "queue": {
                "max_queue_size": 100,          # 最大队列长度
                "worker_count": 2,              # 工作线程数
                "task_timeout": 300             # 任务超时时间(秒)
            },
            
            # 搜索配置
            "search": {
                "default_limit": 10,
                "max_limit": 100,
                "min_score": 0.3                # 最低相似度阈值
            },
            
            # 服务配置
            "server": {
                "host": "0.0.0.0",
                "port": 8001,
                "cors_origins": ["http://localhost:5173", "http://127.0.0.1:5173"]
            }
        }
        
        # 从文件加载配置（如果存在）
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    self._deep_merge(self._config, file_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        # 从环境变量覆盖
        self._load_from_env()
    
    def _deep_merge(self, base: dict, override: dict):
        """深度合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 上传配置
        if os.getenv("ASKME_MAX_BATCH_SIZE"):
            self._config["upload"]["max_batch_size"] = int(os.getenv("ASKME_MAX_BATCH_SIZE"))
        if os.getenv("ASKME_MAX_FILE_SIZE"):
            self._config["upload"]["max_file_size_mb"] = int(os.getenv("ASKME_MAX_FILE_SIZE"))
        
        # 处理配置
        if os.getenv("ASKME_CHUNK_SIZE"):
            self._config["processing"]["chunk_size"] = int(os.getenv("ASKME_CHUNK_SIZE"))
        
        # 队列配置
        if os.getenv("ASKME_WORKER_COUNT"):
            self._config["queue"]["worker_count"] = int(os.getenv("ASKME_WORKER_COUNT"))
        
        # 服务配置
        if os.getenv("ASKME_PORT"):
            self._config["server"]["port"] = int(os.getenv("ASKME_PORT"))
    
    def get(self, key: str, default=None):
        """获取配置项（支持点号分隔的路径）"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_all(self) -> dict:
        """获取所有配置"""
        return self._config.copy()
    
    def save(self):
        """保存配置到文件"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)


# 全局配置实例
config = Config()
