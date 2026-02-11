"""状态管理器 - SQLite版本"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import threading
import logging

from services.database import db

logger = logging.getLogger(__name__)


class StateType(Enum):
    DOCUMENT = "document"
    WORKFLOW = "workflow"
    TASK = "task"


class StateStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StateRecord:
    """状态记录"""
    state_id: str
    state_type: str
    entity_id: str
    status: str
    data: Dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime


class StateManager:
    """状态管理器 - SQLite版本"""
    
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
        logger.info("StateManager初始化完成（SQLite模式）")
    
    def create_state(
        self,
        state_type: StateType,
        entity_id: str,
        initial_data: Dict[str, Any] = None,
        initial_status: StateStatus = StateStatus.PENDING,
        tags: List[str] = None
    ) -> str:
        """
        创建状态记录
        
        Args:
            state_type: 状态类型
            entity_id: 实体ID
            initial_data: 初始数据
            initial_status: 初始状态
            tags: 标签列表
            
        Returns:
            状态ID
        """
        state_id = f"{state_type.value}_{entity_id}"
        now = datetime.now()
        
        # 将data转为JSON字符串存储
        data_json = initial_data or {}
        
        try:
            # 检查是否已存在
            existing = db.fetchone(
                "SELECT state_id FROM states WHERE state_id = ?",
                (state_id,)
            )
            
            if existing:
                # 更新现有记录
                db.execute(
                    """UPDATE states SET status = ?, data = ?, updated_at = ?
                       WHERE state_id = ?""",
                    (initial_status.value, json.dumps(data_json), now, state_id)
                )
            else:
                # 创建新记录
                db.execute(
                    """INSERT INTO states (state_id, state_type, entity_id, status, data, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (state_id, state_type.value, entity_id, initial_status.value, json.dumps(data_json), now, now)
                )
            
            db.conn.commit()
            logger.info(f"创建状态记录: {state_id}")
            return state_id
            
        except Exception as e:
            logger.error(f"创建状态记录失败: {e}")
            raise
    
    def get_state(self, state_id: str) -> Optional[StateRecord]:
        """获取状态记录"""
        row = db.fetchone(
            "SELECT * FROM states WHERE state_id = ?",
            (state_id,)
        )
        if row:
            return StateRecord(
                state_id=row['state_id'],
                state_type=row['state_type'],
                entity_id=row['entity_id'],
                status=row['status'],
                data=json.loads(row['data']) if row['data'] else {},
                version=1,
                created_at=datetime.fromisoformat(row['created_at']) if isinstance(row['created_at'], str) else row['created_at'],
                updated_at=datetime.fromisoformat(row['updated_at']) if isinstance(row['updated_at'], str) else row['updated_at']
            )
        return None
    
    def update_state(
        self,
        state_id: str,
        new_status: StateStatus = None,
        new_data: Dict[str, Any] = None,
        tags: List[str] = None
    ) -> bool:
        """
        更新状态记录
        
        Args:
            state_id: 状态ID
            new_status: 新状态
            new_data: 新数据（会合并到现有数据）
            tags: 标签
            
        Returns:
            是否成功
        """
        try:
            existing = self.get_state(state_id)
            if not existing:
                logger.warning(f"状态记录不存在: {state_id}")
                return False
            
            # 合并数据
            merged_data = existing.data.copy()
            if new_data:
                merged_data.update(new_data)
            
            # 更新
            now = datetime.now()
            status = new_status.value if new_status else existing.status
            
            db.execute(
                """UPDATE states SET status = ?, data = ?, updated_at = ?
                   WHERE state_id = ?""",
                (status, json.dumps(merged_data), now, state_id)
            )
            db.conn.commit()
            
            logger.info(f"更新状态记录: {state_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新状态记录失败: {e}")
            return False
    
    def delete_state(self, state_id: str) -> bool:
        """删除状态记录"""
        try:
            db.execute("DELETE FROM states WHERE state_id = ?", (state_id,))
            db.conn.commit()
            logger.info(f"删除状态记录: {state_id}")
            return True
        except Exception as e:
            logger.error(f"删除状态记录失败: {e}")
            return False
    
    def query_states(
        self,
        state_type: StateType = None,
        entity_id: str = None,
        status: StateStatus = None,
        tags: List[str] = None
    ) -> List[StateRecord]:
        """
        查询状态记录
        
        Args:
            state_type: 状态类型
            entity_id: 实体ID
            status: 状态
            tags: 标签
            
        Returns:
            状态记录列表
        """
        conditions = []
        params = []
        
        if state_type:
            conditions.append("state_type = ?")
            params.append(state_type.value)
        
        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)
        
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM states WHERE {where_clause} ORDER BY created_at DESC"
        
        rows = db.fetchall(sql, tuple(params))
        
        return [
            StateRecord(
                state_id=row['state_id'],
                state_type=row['state_type'],
                entity_id=row['entity_id'],
                status=row['status'],
                data=json.loads(row['data']) if row['data'] else {},
                version=1,
                created_at=datetime.fromisoformat(row['created_at']) if isinstance(row['created_at'], str) else row['created_at'],
                updated_at=datetime.fromisoformat(row['updated_at']) if isinstance(row['updated_at'], str) else row['updated_at']
            )
            for row in rows
        ]
    
    def count_states(self, state_type: StateType = None, status: StateStatus = None) -> int:
        """统计状态记录数量"""
        conditions = []
        params = []
        
        if state_type:
            conditions.append("state_type = ?")
            params.append(state_type.value)
        
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT COUNT(*) as cnt FROM states WHERE {where_clause}"
        
        result = db.fetchone(sql, tuple(params))
        return result['cnt'] if result else 0


# 需要导入json
import json

# 全局实例
state_manager = StateManager()
