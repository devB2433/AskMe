"""任务队列管理器 - 支持进度追踪和异步处理"""
import asyncio
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Any, Awaitable

from services.config import config
from services.database import db

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"          # 等待中
    QUEUED = "queued"            # 已入队
    PROCESSING = "processing"    # 处理中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消


class TaskStage(str, Enum):
    """任务阶段"""
    UPLOADING = "uploading"      # 上传中
    PARSING = "parsing"          # 解析中
    CHUNKING = "chunking"        # 分块中
    EMBEDDING = "embedding"      # 向量化中
    STORING = "storing"          # 存储中
    COMPLETED = "completed"      # 完成


@dataclass
class TaskProgress:
    """任务进度"""
    stage: TaskStage = TaskStage.UPLOADING
    current: int = 0
    total: int = 100
    message: str = ""
    
    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "percentage": round(self.current / max(self.total, 1) * 100, 1)
        }


@dataclass
class Task:
    """任务"""
    task_id: str
    task_type: str
    filename: str
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    callback: Optional[Callable] = None
    data: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "filename": self.filename,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class TaskQueue:
    """任务队列管理器"""
    
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
        
        self._queue: deque = deque()
        self._tasks: Dict[str, Task] = {}
        self._workers: List[threading.Thread] = []
        self._running = False
        self._max_queue_size = config.get("queue.max_queue_size", 100)
        self._worker_count = config.get("queue.worker_count", 2)
        
        # WebSocket连接管理
        self._ws_connections: set = set()
        
        # 主事件循环引用（用于线程安全广播）
        self._event_loop = None
        
        # 任务处理器注册
        self._handlers: Dict[str, Callable] = {}
        
        # 启动工作线程
        self._start_workers()
        
        logger.info(f"任务队列初始化完成: 工作线程={self._worker_count}")
    
    def set_event_loop(self, loop):
        """设置主事件循环引用"""
        self._event_loop = loop
        logger.debug("事件循环引用已设置")
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.info(f"注册任务处理器: {task_type}")
    
    def add_ws_connection(self, ws):
        """添加WebSocket连接"""
        self._ws_connections.add(ws)
        logger.debug(f"WebSocket连接已添加，当前连接数: {len(self._ws_connections)}")
    
    def remove_ws_connection(self, ws):
        """移除WebSocket连接"""
        self._ws_connections.discard(ws)
        logger.debug(f"WebSocket连接已移除，当前连接数: {len(self._ws_connections)}")
    
    async def broadcast_progress(self, task: Task):
        """广播进度更新"""
        message = {
            "type": "task_progress",
            "data": task.to_dict()
        }
        
        disconnected = set()
        for ws in self._ws_connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"WebSocket发送失败: {e}")
                disconnected.add(ws)
        
        # 清理断开的连接
        self._ws_connections -= disconnected
    
    def submit_task(
        self,
        task_type: str,
        filename: str,
        data: dict,
        callback: Optional[Callable] = None
    ) -> Task:
        """提交任务到队列"""
        if len(self._queue) >= self._max_queue_size:
            raise ValueError(f"队列已满，最大容量: {self._max_queue_size}")
        
        task = Task(
            task_id=f"task_{uuid.uuid4().hex[:12]}",
            task_type=task_type,
            filename=filename,
            status=TaskStatus.QUEUED,
            data=data,
            callback=callback
        )
        
        self._tasks[task.task_id] = task
        self._queue.append(task.task_id)
        
        # 保存到数据库
        self._save_task_to_db(task)
        
        logger.info(f"任务已入队: {task.task_id} - {filename}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """获取所有任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks
    
    def get_queue_status(self) -> dict:
        """获取队列状态"""
        pending = len(self._queue)
        processing = sum(1 for t in self._tasks.values() if t.status == TaskStatus.PROCESSING)
        completed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
        
        return {
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "total": len(self._tasks),
            "max_queue_size": self._max_queue_size
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return False
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        
        # 从队列中移除
        if task_id in self._queue:
            self._queue.remove(task_id)
        
        logger.info(f"任务已取消: {task_id}")
        return True
    
    def update_progress(
        self,
        task_id: str,
        stage: TaskStage,
        current: int,
        total: int,
        message: str = ""
    ):
        """更新任务进度"""
        task = self._tasks.get(task_id)
        if not task:
            return
        
        task.progress.stage = stage
        task.progress.current = current
        task.progress.total = total
        task.progress.message = message
        
        # 更新数据库
        self._update_task_in_db(task)
        
        # 实时广播进度更新（线程安全）
        self._broadcast_task_progress(task)
        
        logger.debug(f"任务进度更新: {task_id} - {stage.value} - {current}/{total}")
    
    def _broadcast_task_progress(self, task: Task):
        """线程安全地广播任务进度"""
        import asyncio
        
        # 使用保存的主事件循环
        if not self._event_loop:
            return
        
        try:
            # 在主事件循环中调度广播
            future = asyncio.run_coroutine_threadsafe(
                self.broadcast_progress(task),
                self._event_loop
            )
            # 不等待结果，立即返回
        except Exception as e:
            logger.warning(f"广播进度失败: {e}")
    
    def _start_workers(self):
        """启动工作线程"""
        self._running = True
        for i in range(self._worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
    
    def _worker_loop(self):
        """工作线程循环"""
        import asyncio
        
        while self._running:
            try:
                if not self._queue:
                    time.sleep(0.5)
                    continue
                
                task_id = self._queue.popleft()
                task = self._tasks.get(task_id)
                
                if not task or task.status == TaskStatus.CANCELLED:
                    continue
                
                # 开始处理
                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now()
                self._update_task_in_db(task)
                
                logger.info(f"开始处理任务: {task_id}")
                
                # 获取处理器
                handler = self._handlers.get(task.task_type)
                if not handler:
                    task.status = TaskStatus.FAILED
                    task.error = f"未找到处理器: {task.task_type}"
                    task.completed_at = datetime.now()
                    self._update_task_in_db(task)
                    continue
                
                # 执行任务
                try:
                    result = handler(task)
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.progress.stage = TaskStage.COMPLETED
                    task.progress.current = 100
                    task.progress.total = 100
                    logger.info(f"任务完成: {task_id}")
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    logger.error(f"任务失败: {task_id} - {e}")
                
                task.completed_at = datetime.now()
                self._update_task_in_db(task)
                
                # 执行回调
                if task.callback:
                    try:
                        task.callback(task)
                    except Exception as e:
                        logger.error(f"回调执行失败: {e}")
                
            except Exception as e:
                logger.error(f"工作线程异常: {e}")
                time.sleep(1)
    
    def _save_task_to_db(self, task: Task):
        """保存任务到数据库"""
        try:
            db.execute(
                """INSERT INTO tasks (id, type, filename, status, progress, data, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.task_id,
                    task.task_type,
                    task.filename,
                    task.status.value,
                    str(task.progress.to_dict()),
                    str(task.data),
                    task.created_at.isoformat()
                )
            )
            db.conn.commit()
        except Exception as e:
            logger.error(f"保存任务到数据库失败: {e}")
    
    def _update_task_in_db(self, task: Task):
        """更新数据库中的任务"""
        try:
            db.execute(
                """UPDATE tasks SET status=?, progress=?, result=?, error=?, 
                   started_at=?, completed_at=? WHERE id=?""",
                (
                    task.status.value,
                    str(task.progress.to_dict()),
                    str(task.result) if task.result else None,
                    task.error,
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.task_id
                )
            )
            db.conn.commit()
        except Exception as e:
            logger.error(f"更新任务失败: {e}")
    
    def shutdown(self):
        """关闭队列"""
        self._running = False
        for worker in self._workers:
            worker.join(timeout=5)
        logger.info("任务队列已关闭")


# 在数据库中创建tasks表
def init_tasks_table():
    """初始化任务表"""
    try:
        cursor = db.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                filename TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress TEXT,
                data TEXT,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type)')
        db.conn.commit()
        logger.info("任务表初始化完成")
    except Exception as e:
        logger.error(f"初始化任务表失败: {e}")


# 全局任务队列实例
task_queue = TaskQueue()
