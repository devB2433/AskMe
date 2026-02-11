"""调度器组件模块"""
import asyncio
import heapq
import time
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor
import json

# 导入相关模块
import sys
import os
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_path)

from services.state_manager import StateManager, StateType, StateStatus

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

class ScheduleType(Enum):
    """调度类型枚举"""
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    RECURRING = "recurring"
    CRON = "cron"

@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    name: str
    description: str
    schedule_type: ScheduleType
    priority: TaskPriority
    target_function: str  # 函数标识符
    params: Dict[str, Any]
    scheduled_time: datetime
    created_at: datetime
    status: StateStatus
    retry_count: int
    max_retries: int
    recurrence_pattern: Optional[str]  # cron表达式
    next_run_time: Optional[datetime]
    last_run_time: Optional[datetime]
    metadata: Dict[str, Any]

class TaskQueue:
    """任务队列"""
    
    def __init__(self):
        """初始化任务队列"""
        self.queue = []
        self.lock = threading.RLock()
    
    def push(self, task: ScheduledTask):
        """添加任务到队列"""
        with self.lock:
            # 使用优先级和调度时间作为排序键
            priority_key = (-task.priority.value, task.scheduled_time.timestamp(), task.task_id)
            heapq.heappush(self.queue, (priority_key, task))
    
    def pop(self) -> Optional[ScheduledTask]:
        """从队列取出任务"""
        with self.lock:
            if self.queue:
                _, task = heapq.heappop(self.queue)
                return task
            return None
    
    def peek(self) -> Optional[ScheduledTask]:
        """查看队列头部任务"""
        with self.lock:
            if self.queue:
                _, task = self.queue[0]
                return task
            return None
    
    def remove(self, task_id: str) -> bool:
        """移除指定任务"""
        with self.lock:
            for i, (key, task) in enumerate(self.queue):
                if task.task_id == task_id:
                    self.queue.pop(i)
                    heapq.heapify(self.queue)
                    return True
            return False
    
    def size(self) -> int:
        """获取队列大小"""
        with self.lock:
            return len(self.queue)
    
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return self.size() == 0

class CronParser:
    """Cron表达式解析器"""
    
    def __init__(self):
        """初始化Cron解析器"""
        pass
    
    def parse(self, cron_expression: str) -> Dict[str, Any]:
        """
        解析Cron表达式
        
        Args:
            cron_expression: Cron表达式
            
        Returns:
            解析结果字典
        """
        try:
            parts = cron_expression.split()
            if len(parts) != 5:
                raise ValueError("Cron表达式必须包含5个部分")
            
            return {
                'minute': self._parse_field(parts[0], 0, 59),
                'hour': self._parse_field(parts[1], 0, 23),
                'day_of_month': self._parse_field(parts[2], 1, 31),
                'month': self._parse_field(parts[3], 1, 12),
                'day_of_week': self._parse_field(parts[4], 0, 6)
            }
        except Exception as e:
            logger.error(f"Cron表达式解析失败: {e}")
            raise
    
    def _parse_field(self, field: str, min_val: int, max_val: int) -> List[int]:
        """解析单个字段"""
        if field == '*':
            return list(range(min_val, max_val + 1))
        
        values = []
        for part in field.split(','):
            if '-' in part:
                # 范围表达式
                start, end = part.split('-')
                values.extend(range(int(start), int(end) + 1))
            elif '/' in part:
                # 步长表达式
                base, step = part.split('/')
                if base == '*':
                    base = min_val
                values.extend(range(int(base), max_val + 1, int(step)))
            else:
                # 单个值
                values.append(int(part))
        
        return [v for v in values if min_val <= v <= max_val]
    
    def get_next_run_time(self, cron_expression: str, 
                         start_time: datetime = None) -> Optional[datetime]:
        """
        计算下次运行时间
        
        Args:
            cron_expression: Cron表达式
            start_time: 起始时间
            
        Returns:
            下次运行时间
        """
        if start_time is None:
            start_time = datetime.now()
        
        try:
            cron_fields = self.parse(cron_expression)
            
            # 简化的下次运行时间计算
            # 实际应用中应该使用更精确的算法
            next_time = start_time.replace(second=0, microsecond=0)
            
            # 简单的分钟级调度
            while True:
                if (next_time.minute in cron_fields['minute'] and
                    next_time.hour in cron_fields['hour'] and
                    next_time.day in cron_fields['day_of_month'] and
                    next_time.month in cron_fields['month'] and
                    next_time.weekday() in cron_fields['day_of_week']):
                    if next_time > start_time:
                        return next_time
                next_time += timedelta(minutes=1)
                
                # 防止无限循环
                if next_time > start_time + timedelta(days=365):
                    break
            
            return None
            
        except Exception as e:
            logger.error(f"计算下次运行时间失败: {e}")
            return None

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, state_manager: StateManager = None, max_workers: int = 5):
        """
        初始化任务调度器
        
        Args:
            state_manager: 状态管理器
            max_workers: 最大工作线程数
        """
        self.state_manager = state_manager
        self.max_workers = max_workers
        self.task_queue = TaskQueue()
        self.cron_parser = CronParser()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self.scheduler_thread = None
        self.task_handlers: Dict[str, Callable] = {}
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.lock = threading.RLock()
        
        # 注册内置任务处理器
        self._register_builtin_handlers()
    
    def _register_builtin_handlers(self):
        """注册内置任务处理器"""
        self.task_handlers['health_check'] = self._handle_health_check
        self.task_handlers['cleanup_expired'] = self._handle_cleanup_expired
        self.task_handlers['backup_data'] = self._handle_backup_data
        self.task_handlers['send_notifications'] = self._handle_send_notifications
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("任务调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
        logger.info("任务调度器已停止")
    
    def schedule_task(self, name: str, target_function: str,
                     params: Dict[str, Any] = None,
                     schedule_type: ScheduleType = ScheduleType.IMMEDIATE,
                     priority: TaskPriority = TaskPriority.NORMAL,
                     delay_seconds: int = 0,
                     cron_expression: str = None,
                     max_retries: int = 3,
                     description: str = "") -> str:
        """
        调度任务
        
        Args:
            name: 任务名称
            target_function: 目标函数标识符
            params: 参数
            schedule_type: 调度类型
            priority: 优先级
            delay_seconds: 延迟秒数
            cron_expression: Cron表达式
            max_retries: 最大重试次数
            description: 描述
            
        Returns:
            任务ID
        """
        if params is None:
            params = {}
        
        task_id = f"task_{int(time.time())}_{hash(name) % 10000}"
        scheduled_time = datetime.now() + timedelta(seconds=delay_seconds)
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            description=description,
            schedule_type=schedule_type,
            priority=priority,
            target_function=target_function,
            params=params,
            scheduled_time=scheduled_time,
            created_at=datetime.now(),
            status=StateStatus.PENDING,
            retry_count=0,
            max_retries=max_retries,
            recurrence_pattern=cron_expression,
            next_run_time=None,
            last_run_time=None,
            metadata={}
        )
        
        # 处理周期性任务
        if schedule_type == ScheduleType.RECURRING and cron_expression:
            task.next_run_time = self.cron_parser.get_next_run_time(cron_expression)
        
        with self.lock:
            self.scheduled_tasks[task_id] = task
            self.task_queue.push(task)
            
            # 创建状态记录
            if self.state_manager:
                self.state_manager.create_state(
                    state_type=StateType.TASK,
                    entity_id=task_id,
                    initial_data=asdict(task),
                    tags=['scheduled_task', f'priority_{priority.name.lower()}']
                )
        
        logger.info(f"已调度任务: {name} ({task_id})")
        return task_id
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否取消成功
        """
        with self.lock:
            if task_id in self.scheduled_tasks:
                task = self.scheduled_tasks[task_id]
                task.status = StateStatus.CANCELLED
                
                # 从队列中移除
                self.task_queue.remove(task_id)
                
                # 更新状态
                if self.state_manager:
                    self.state_manager.update_state(
                        f"task_{task_id}",
                        new_status=StateStatus.CANCELLED
                    )
                
                logger.info(f"已取消任务: {task_id}")
                return True
            return False
    
    def get_task_status(self, task_id: str) -> Optional[ScheduledTask]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态
        """
        with self.lock:
            return self.scheduled_tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[ScheduledTask]:
        """获取待处理任务列表"""
        with self.lock:
            return [task for task in self.scheduled_tasks.values() 
                   if task.status == StateStatus.PENDING]
    
    def _scheduler_loop(self):
        """调度器主循环"""
        while self.running:
            try:
                # 检查是否有可执行的任务
                ready_task = self._get_ready_task()
                
                if ready_task:
                    # 在线程池中执行任务
                    self.executor.submit(self._execute_task, ready_task)
                else:
                    # 没有任务时短暂休眠
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"调度器循环异常: {e}")
                time.sleep(1)
    
    def _get_ready_task(self) -> Optional[ScheduledTask]:
        """获取准备执行的任务"""
        current_time = datetime.now()
        
        with self.lock:
            # 检查队列头部任务
            task = self.task_queue.peek()
            if task and task.scheduled_time <= current_time and task.status == StateStatus.PENDING:
                return self.task_queue.pop()
            return None
    
    def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        try:
            task.status = StateStatus.PROCESSING
            task.last_run_time = datetime.now()
            
            # 更新状态
            if self.state_manager:
                self.state_manager.update_state(
                    f"task_{task.task_id}",
                    new_status=StateStatus.PROCESSING
                )
            
            logger.info(f"开始执行任务: {task.name} ({task.task_id})")
            
            # 执行任务处理器
            handler = self.task_handlers.get(task.target_function)
            if handler:
                result = handler(task.params)
                task.status = StateStatus.COMPLETED
                task.metadata['result'] = result
                logger.info(f"任务执行成功: {task.name}")
            else:
                raise ValueError(f"未找到任务处理器: {task.target_function}")
            
            # 处理周期性任务
            if (task.schedule_type == ScheduleType.RECURRING and 
                task.recurrence_pattern and task.next_run_time):
                self._schedule_next_occurrence(task)
            
        except Exception as e:
            task.retry_count += 1
            task.metadata['last_error'] = str(e)
            
            if task.retry_count < task.max_retries:
                task.status = StateStatus.PENDING
                # 延迟重试
                retry_delay = min(60 * (2 ** task.retry_count), 3600)  # 指数退避
                task.scheduled_time = datetime.now() + timedelta(seconds=retry_delay)
                self.task_queue.push(task)
                logger.warning(f"任务执行失败，将在 {retry_delay} 秒后重试: {task.name}")
            else:
                task.status = StateStatus.FAILED
                logger.error(f"任务执行失败，达到最大重试次数: {task.name}, 错误: {e}")
        
        finally:
            # 更新最终状态
            if self.state_manager:
                self.state_manager.update_state(
                    f"task_{task.task_id}",
                    new_status=task.status,
                    new_data=asdict(task)
                )
    
    def _schedule_next_occurrence(self, task: ScheduledTask):
        """安排下一次执行"""
        if task.recurrence_pattern:
            next_time = self.cron_parser.get_next_run_time(
                task.recurrence_pattern, 
                task.scheduled_time
            )
            if next_time:
                task.next_run_time = next_time
                task.scheduled_time = next_time
                task.status = StateStatus.PENDING
                task.retry_count = 0
                self.task_queue.push(task)
                logger.info(f"已安排周期性任务下次执行: {task.name} at {next_time}")
    
    # 内置任务处理器
    def _handle_health_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """健康检查任务处理器"""
        logger.info("执行健康检查任务")
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": ["database", "vector_store", "search_engine"]
        }
    
    def _handle_cleanup_expired(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """清理过期数据任务处理器"""
        logger.info("执行过期数据清理任务")
        # 这里应该调用实际的清理逻辑
        return {
            "cleaned_items": 0,
            "timestamp": datetime.now().isoformat()
        }
    
    def _handle_backup_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """数据备份任务处理器"""
        logger.info("执行数据备份任务")
        # 这里应该调用实际的备份逻辑
        return {
            "backup_path": "/backups/",
            "timestamp": datetime.now().isoformat(),
            "status": "completed"
        }
    
    def _handle_send_notifications(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送通知任务处理器"""
        logger.info("执行通知发送任务")
        # 这里应该调用实际的通知逻辑
        return {
            "notifications_sent": 0,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        with self.lock:
            pending_count = len([t for t in self.scheduled_tasks.values() 
                               if t.status == StateStatus.PENDING])
            processing_count = len([t for t in self.scheduled_tasks.values() 
                                  if t.status == StateStatus.PROCESSING])
            completed_count = len([t for t in self.scheduled_tasks.values() 
                                 if t.status == StateStatus.COMPLETED])
            failed_count = len([t for t in self.scheduled_tasks.values() 
                              if t.status == StateStatus.FAILED])
            
            return {
                "total_tasks": len(self.scheduled_tasks),
                "pending_tasks": pending_count,
                "processing_tasks": processing_count,
                "completed_tasks": completed_count,
                "failed_tasks": failed_count,
                "queue_size": self.task_queue.size(),
                "running": self.running,
                "max_workers": self.max_workers
            }

class WorkflowScheduler:
    """工作流调度器"""
    
    def __init__(self, task_scheduler: TaskScheduler):
        """
        初始化工作流调度器
        
        Args:
            task_scheduler: 任务调度器实例
        """
        self.task_scheduler = task_scheduler
    
    def schedule_workflow(self, workflow_definition: Dict[str, Any],
                         trigger_params: Dict[str, Any] = None,
                         schedule_type: ScheduleType = ScheduleType.IMMEDIATE,
                         priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """
        调度工作流
        
        Args:
            workflow_definition: 工作流定义
            trigger_params: 触发参数
            schedule_type: 调度类型
            priority: 优先级
            
        Returns:
            调度任务ID
        """
        if trigger_params is None:
            trigger_params = {}
        
        # 将工作流定义转换为调度任务
        task_params = {
            "workflow_definition": workflow_definition,
            "trigger_params": trigger_params
        }
        
        task_id = self.task_scheduler.schedule_task(
            name=f"Workflow_{workflow_definition.get('name', 'unnamed')}",
            target_function="execute_workflow",
            params=task_params,
            schedule_type=schedule_type,
            priority=priority,
            description=f"执行工作流: {workflow_definition.get('name', '未命名')}"
        )
        
        return task_id

# 导出主要类
__all__ = ['TaskPriority', 'ScheduleType', 'ScheduledTask', 'TaskQueue', 
           'CronParser', 'TaskScheduler', 'WorkflowScheduler']