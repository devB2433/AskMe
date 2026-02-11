"""状态管理器模块"""
import json
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime, timedelta
import threading
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

class StateType(Enum):
    """状态类型枚举"""
    WORKFLOW = "workflow"
    TASK = "task"
    DOCUMENT = "document"
    SEARCH = "search"
    SYSTEM = "system"

class StateStatus(Enum):
    """状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class StateRecord:
    """状态记录"""
    state_id: str
    state_type: StateType
    entity_id: str
    status: StateStatus
    data: Dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    tags: List[str]

class StateMachine:
    """状态机"""
    
    def __init__(self):
        """初始化状态机"""
        # 定义状态转换规则
        self.transitions = {
            StateType.WORKFLOW: {
                StateStatus.PENDING: [StateStatus.ACTIVE, StateStatus.CANCELLED],
                StateStatus.ACTIVE: [StateStatus.PROCESSING, StateStatus.COMPLETED, StateStatus.FAILED, StateStatus.CANCELLED],
                StateStatus.PROCESSING: [StateStatus.COMPLETED, StateStatus.FAILED, StateStatus.CANCELLED],
                StateStatus.COMPLETED: [],
                StateStatus.FAILED: [StateStatus.PENDING],
                StateStatus.CANCELLED: []
            },
            StateType.TASK: {
                StateStatus.PENDING: [StateStatus.ACTIVE, StateStatus.CANCELLED],
                StateStatus.ACTIVE: [StateStatus.PROCESSING, StateStatus.COMPLETED, StateStatus.FAILED, StateStatus.CANCELLED],
                StateStatus.PROCESSING: [StateStatus.COMPLETED, StateStatus.FAILED, StateStatus.CANCELLED],
                StateStatus.COMPLETED: [],
                StateStatus.FAILED: [StateStatus.PENDING],
                StateStatus.CANCELLED: []
            },
            StateType.DOCUMENT: {
                StateStatus.PENDING: [StateStatus.ACTIVE, StateStatus.PROCESSING],
                StateStatus.ACTIVE: [StateStatus.PROCESSING, StateStatus.COMPLETED, StateStatus.FAILED],
                StateStatus.PROCESSING: [StateStatus.COMPLETED, StateStatus.FAILED],
                StateStatus.COMPLETED: [],
                StateStatus.FAILED: [StateStatus.PENDING]
            }
        }
    
    def can_transition(self, state_type: StateType, from_status: StateStatus, 
                      to_status: StateStatus) -> bool:
        """
        检查是否可以进行状态转换
        
        Args:
            state_type: 状态类型
            from_status: 当前状态
            to_status: 目标状态
            
        Returns:
            是否允许转换
        """
        if state_type not in self.transitions:
            return False
        
        allowed_transitions = self.transitions[state_type].get(from_status, [])
        return to_status in allowed_transitions
    
    def get_allowed_transitions(self, state_type: StateType, 
                              current_status: StateStatus) -> List[StateStatus]:
        """
        获取允许的状态转换
        
        Args:
            state_type: 状态类型
            current_status: 当前状态
            
        Returns:
            允许转换的状态列表
        """
        if state_type not in self.transitions:
            return []
        
        return self.transitions[state_type].get(current_status, [])

class StateStore:
    """状态存储"""
    
    _instance = None
    _lock = threading.Lock()
    STATE_FILE = Path("data/state_store.json")
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化状态存储"""
        if self._initialized:
            return
        self._initialized = True
        self.states: Dict[str, StateRecord] = {}
        self.lock = threading.RLock()
        self.indexes = {
            'type': defaultdict(set),      # state_type -> state_ids
            'entity': defaultdict(set),    # entity_id -> state_ids
            'status': defaultdict(set),    # status -> state_ids
            'tag': defaultdict(set)        # tag -> state_ids
        }
        # 从文件加载状态
        self._load_from_file()
    
    def _load_from_file(self):
        """从文件加载状态"""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for state_data in data.get('states', []):
                    record = StateRecord(
                        state_id=state_data['state_id'],
                        state_type=StateType(state_data['state_type']),
                        entity_id=state_data['entity_id'],
                        status=StateStatus(state_data['status']),
                        data=state_data['data'],
                        version=state_data['version'],
                        created_at=datetime.fromisoformat(state_data['created_at']),
                        updated_at=datetime.fromisoformat(state_data['updated_at']),
                        expires_at=datetime.fromisoformat(state_data['expires_at']) if state_data.get('expires_at') else None,
                        tags=state_data.get('tags', [])
                    )
                    self.states[record.state_id] = record
                    self._add_to_indexes(record)
                logger.info(f"从文件加载了 {len(self.states)} 条状态记录")
        except Exception as e:
            logger.warning(f"加载状态文件失败: {e}")
    
    def _save_to_file(self):
        """保存状态到文件"""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {'states': []}
            for record in self.states.values():
                data['states'].append({
                    'state_id': record.state_id,
                    'state_type': record.state_type.value,
                    'entity_id': record.entity_id,
                    'status': record.status.value,
                    'data': record.data,
                    'version': record.version,
                    'created_at': record.created_at.isoformat(),
                    'updated_at': record.updated_at.isoformat(),
                    'expires_at': record.expires_at.isoformat() if record.expires_at else None,
                    'tags': record.tags
                })
            with open(self.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存状态文件失败: {e}")
    
    def save_state(self, state_record: StateRecord) -> bool:
        """
        保存状态记录
        
        Args:
            state_record: 状态记录
            
        Returns:
            是否保存成功
        """
        with self.lock:
            try:
                # 更新索引
                old_record = self.states.get(state_record.state_id)
                if old_record:
                    self._remove_from_indexes(old_record)
                
                self.states[state_record.state_id] = state_record
                self._add_to_indexes(state_record)
                
                # 持久化到文件
                self._save_to_file()
                
                logger.debug(f"保存状态记录: {state_record.state_id}")
                return True
                
            except Exception as e:
                logger.error(f"保存状态记录失败: {e}")
                return False
    
    def get_state(self, state_id: str) -> Optional[StateRecord]:
        """
        获取状态记录
        
        Args:
            state_id: 状态ID
            
        Returns:
            状态记录
        """
        with self.lock:
            return self.states.get(state_id)
    
    def delete_state(self, state_id: str) -> bool:
        """
        删除状态记录
        
        Args:
            state_id: 状态ID
            
        Returns:
            是否删除成功
        """
        with self.lock:
            try:
                if state_id in self.states:
                    record = self.states[state_id]
                    self._remove_from_indexes(record)
                    del self.states[state_id]
                    # 持久化到文件
                    self._save_to_file()
                    logger.debug(f"删除状态记录: {state_id}")
                    return True
                return False
                
            except Exception as e:
                logger.error(f"删除状态记录失败: {e}")
                return False
    
    def query_states(self, state_type: StateType = None, 
                    status: StateStatus = None,
                    entity_id: str = None,
                    tags: List[str] = None) -> List[StateRecord]:
        """
        查询状态记录
        
        Args:
            state_type: 状态类型
            status: 状态
            entity_id: 实体ID
            tags: 标签列表
            
        Returns:
            符合条件的状态记录列表
        """
        with self.lock:
            # 获取候选集合
            candidate_ids = set(self.states.keys())
            
            # 应用过滤条件
            if state_type:
                type_ids = self.indexes['type'].get(state_type, set())
                candidate_ids &= type_ids
            
            if status:
                status_ids = self.indexes['status'].get(status, set())
                candidate_ids &= status_ids
            
            if entity_id:
                entity_ids = self.indexes['entity'].get(entity_id, set())
                candidate_ids &= entity_ids
            
            if tags:
                tag_ids = set()
                for tag in tags:
                    tag_ids |= self.indexes['tag'].get(tag, set())
                candidate_ids &= tag_ids
            
            # 返回结果
            return [self.states[state_id] for state_id in candidate_ids]
    
    def _add_to_indexes(self, record: StateRecord):
        """添加到索引"""
        self.indexes['type'][record.state_type].add(record.state_id)
        self.indexes['entity'][record.entity_id].add(record.state_id)
        self.indexes['status'][record.status].add(record.state_id)
        for tag in record.tags:
            self.indexes['tag'][tag].add(record.state_id)
    
    def _remove_from_indexes(self, record: StateRecord):
        """从索引中移除"""
        self.indexes['type'][record.state_type].discard(record.state_id)
        self.indexes['entity'][record.entity_id].discard(record.state_id)
        self.indexes['status'][record.status].discard(record.state_id)
        for tag in record.tags:
            self.indexes['tag'][tag].discard(record.state_id)

class StateManager:
    """状态管理器"""
    
    def __init__(self, state_store: StateStore = None, 
                 state_machine: StateMachine = None):
        """
        初始化状态管理器
        
        Args:
            state_store: 状态存储
            state_machine: 状态机
        """
        self.state_store = state_store or StateStore()
        self.state_machine = state_machine or StateMachine()
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)
    
    def create_state(self, state_type: StateType, entity_id: str,
                    initial_data: Dict[str, Any] = None,
                    initial_status: StateStatus = StateStatus.PENDING,
                    expires_in: int = None,
                    tags: List[str] = None) -> str:
        """
        创建状态记录
        
        Args:
            state_type: 状态类型
            entity_id: 实体ID
            initial_data: 初始数据
            initial_status: 初始状态
            expires_in: 过期时间（秒）
            tags: 标签列表
            
        Returns:
            状态ID
        """
        if initial_data is None:
            initial_data = {}
        if tags is None:
            tags = []
        
        state_id = f"{state_type.value}_{entity_id}_{int(datetime.now().timestamp())}"
        
        expires_at = None
        if expires_in:
            expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        state_record = StateRecord(
            state_id=state_id,
            state_type=state_type,
            entity_id=entity_id,
            status=initial_status,
            data=initial_data,
            version=1,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            expires_at=expires_at,
            tags=tags
        )
        
        if self.state_store.save_state(state_record):
            self._notify_listeners('created', state_record)
            logger.info(f"创建状态记录: {state_id}")
            return state_id
        else:
            raise RuntimeError("创建状态记录失败")
    
    def update_state(self, state_id: str, new_status: StateStatus = None,
                    new_data: Dict[str, Any] = None,
                    increment_version: bool = True) -> bool:
        """
        更新状态记录
        
        Args:
            state_id: 状态ID
            new_status: 新状态
            new_data: 新数据
            increment_version: 是否增加版本号
            
        Returns:
            是否更新成功
        """
        state_record = self.state_store.get_state(state_id)
        if not state_record:
            logger.warning(f"状态记录不存在: {state_id}")
            return False
        
        # 检查状态转换合法性
        if new_status and not self.state_machine.can_transition(
            state_record.state_type, state_record.status, new_status):
            logger.warning(f"非法状态转换: {state_record.status} -> {new_status}")
            return False
        
        # 更新记录
        old_record = StateRecord(**asdict(state_record))
        
        if new_status:
            state_record.status = new_status
        
        if new_data:
            state_record.data.update(new_data)
        
        if increment_version:
            state_record.version += 1
        
        state_record.updated_at = datetime.now()
        
        if self.state_store.save_state(state_record):
            self._notify_listeners('updated', state_record, old_record)
            logger.info(f"更新状态记录: {state_id}")
            return True
        else:
            return False
    
    def get_state(self, state_id: str) -> Optional[StateRecord]:
        """获取状态记录"""
        return self.state_store.get_state(state_id)
    
    def delete_state(self, state_id: str) -> bool:
        """删除状态记录"""
        state_record = self.state_store.get_state(state_id)
        if state_record:
            if self.state_store.delete_state(state_id):
                self._notify_listeners('deleted', state_record)
                logger.info(f"删除状态记录: {state_id}")
                return True
        return False
    
    def query_states(self, **kwargs) -> List[StateRecord]:
        """查询状态记录"""
        return self.state_store.query_states(**kwargs)
    
    def get_entity_states(self, entity_id: str) -> List[StateRecord]:
        """获取实体的所有状态记录"""
        return self.query_states(entity_id=entity_id)
    
    def get_active_states(self, state_type: StateType = None) -> List[StateRecord]:
        """获取活跃状态记录"""
        return self.query_states(
            state_type=state_type,
            status=StateStatus.ACTIVE
        )
    
    def add_listener(self, event_type: str, callback: Callable):
        """
        添加状态变更监听器
        
        Args:
            event_type: 事件类型 ('created', 'updated', 'deleted')
            callback: 回调函数
        """
        self.listeners[event_type].append(callback)
    
    def remove_listener(self, event_type: str, callback: Callable):
        """
        移除状态变更监听器
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        if callback in self.listeners[event_type]:
            self.listeners[event_type].remove(callback)
    
    def _notify_listeners(self, event_type: str, new_record: StateRecord, 
                         old_record: StateRecord = None):
        """通知监听器"""
        for callback in self.listeners[event_type]:
            try:
                if event_type == 'updated' and old_record:
                    callback(event_type, new_record, old_record)
                else:
                    callback(event_type, new_record)
            except Exception as e:
                logger.error(f"监听器执行失败: {e}")

class StateMonitor:
    """状态监控器"""
    
    def __init__(self, state_manager: StateManager):
        """
        初始化状态监控器
        
        Args:
            state_manager: 状态管理器
        """
        self.state_manager = state_manager
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self, interval: int = 60):
        """
        开始监控
        
        Args:
            interval: 监控间隔（秒）
        """
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("状态监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("状态监控已停止")
    
    def _monitor_loop(self, interval: int):
        """监控循环"""
        while self.monitoring:
            try:
                self._check_expired_states()
                self._check_stale_states()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
    
    def _check_expired_states(self):
        """检查过期状态"""
        now = datetime.now()
        expired_states = []
        
        # 查询所有状态记录
        all_states = self.state_manager.query_states()
        
        for state_record in all_states:
            if (state_record.expires_at and 
                state_record.expires_at < now and
                state_record.status != StateStatus.EXPIRED):
                expired_states.append(state_record.state_id)
        
        # 更新过期状态
        for state_id in expired_states:
            self.state_manager.update_state(
                state_id,
                new_status=StateStatus.EXPIRED
            )
        
        if expired_states:
            logger.info(f"处理了 {len(expired_states)} 个过期状态")
    
    def _check_stale_states(self):
        """检查陈旧状态"""
        stale_threshold = datetime.now() - timedelta(hours=24)
        stale_states = []
        
        processing_states = self.state_manager.query_states(
            status=StateStatus.PROCESSING
        )
        
        for state_record in processing_states:
            if state_record.updated_at < stale_threshold:
                stale_states.append(state_record.state_id)
        
        # 将陈旧的处理状态标记为失败
        for state_id in stale_states:
            self.state_manager.update_state(
                state_id,
                new_status=StateStatus.FAILED,
                new_data={"failure_reason": "处理超时"}
            )
        
        if stale_states:
            logger.warning(f"发现 {len(stale_states)} 个陈旧状态")

# 导出主要类
__all__ = ['StateType', 'StateStatus', 'StateRecord', 'StateMachine', 
           'StateStore', 'StateManager', 'StateMonitor']