"""SQLite数据库模块"""
import sqlite3
import threading
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = Path("data/askme.db")


class Database:
    """SQLite数据库管理类"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._local.connection = sqlite3.connect(
                str(DB_PATH),
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self._local.connection.row_factory = sqlite3.Row
            # 启用外键约束
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection
    
    @property
    def conn(self) -> sqlite3.Connection:
        return self._get_connection()
    
    def _init_db(self):
        """初始化数据库表"""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                email TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # 用户Token表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # 文档状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT,
                team_id TEXT NOT NULL DEFAULT 'default',
                uploaded_by TEXT DEFAULT 'anonymous',
                status TEXT DEFAULT 'pending',
                chunks_count INTEGER DEFAULT 0,
                vector_stored INTEGER DEFAULT 0,
                file_size INTEGER,
                file_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 为team_id创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_documents_team_id ON documents(team_id)
        ''')
        
        # 为filename创建索引（用于去重检查）
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename)
        ''')
        
        # 为file_hash创建索引（用于去重）
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash)
        ''')
        
        # 状态记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS states (
                state_id TEXT PRIMARY KEY,
                state_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 为states表创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_states_type ON states(state_type)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_states_entity ON states(entity_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_states_status ON states(status)
        ''')
        
        conn.commit()
        logger.info(f"数据库初始化完成: {DB_PATH}")
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
    
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL语句"""
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor
    
    def executemany(self, sql: str, params_list: List[tuple]) -> sqlite3.Cursor:
        """批量执行SQL语句"""
        cursor = self.conn.cursor()
        cursor.executemany(sql, params_list)
        return cursor
    
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """查询单条记录"""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict]:
        """查询多条记录"""
        cursor = self.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# 全局数据库实例
db = Database()


def calculate_file_hash(file_path: Path) -> str:
    """计算文件的MD5哈希"""
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def calculate_content_hash(content: bytes) -> str:
    """计算内容的MD5哈希"""
    return hashlib.md5(content).hexdigest()
