"""任务执行器模块"""
import asyncio
import traceback
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future

# 导入相关模块
import sys
import os
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_path)

from services.workflow_definition import WorkflowDefinition, Node, NodeType, TaskType

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionMode(Enum):
    """执行模式枚举"""
    SYNC = "sync"
    ASYNC = "async"
    THREAD_POOL = "thread_pool"

@dataclass
class TaskExecution:
    """任务执行实例"""
    execution_id: str
    workflow_id: str
    node_id: str
    task_type: str
    status: TaskStatus
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_message: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration: Optional[float]
    retry_count: int
    max_retries: int

@dataclass
class ExecutionContext:
    """执行上下文"""
    execution_id: str
    workflow_id: str
    current_node: str
    variables: Dict[str, Any]
    history: List[TaskExecution]
    metadata: Dict[str, Any]

class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, max_workers: int = 10, execution_mode: ExecutionMode = ExecutionMode.THREAD_POOL):
        """
        初始化任务执行器
        
        Args:
            max_workers: 最大工作线程数
            execution_mode: 执行模式
        """
        self.max_workers = max_workers
        self.execution_mode = execution_mode
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.running_executions: Dict[str, TaskExecution] = {}
        self.task_handlers: Dict[str, Callable] = {}
        
        # 注册内置任务处理器
        self._register_builtin_handlers()
    
    def _register_builtin_handlers(self):
        """注册内置任务处理器"""
        self.task_handlers[TaskType.DOCUMENT_PROCESSING.value] = self._handle_document_processing
        self.task_handlers[TaskType.VECTOR_ENCODING.value] = self._handle_vector_encoding
        self.task_handlers[TaskType.SEARCH_INDEXING.value] = self._handle_search_indexing
        self.task_handlers[TaskType.QA_GENERATION.value] = self._handle_qa_generation
        self.task_handlers[TaskType.METADATA_EXTRACTION.value] = self._handle_metadata_extraction
        self.task_handlers[TaskType.CUSTOM_SCRIPT.value] = self._handle_custom_script
    
    async def execute_workflow(self, workflow: WorkflowDefinition, 
                             input_data: Dict[str, Any] = None,
                             execution_id: str = None) -> ExecutionContext:
        """
        执行工作流
        
        Args:
            workflow: 工作流定义
            input_data: 输入数据
            execution_id: 执行ID
            
        Returns:
            执行上下文
        """
        if input_data is None:
            input_data = {}
        
        if execution_id is None:
            execution_id = f"exec_{int(time.time())}"
        
        # 创建执行上下文
        context = ExecutionContext(
            execution_id=execution_id,
            workflow_id=workflow.workflow_id,
            current_node=workflow.start_node,
            variables=input_data.copy(),
            history=[],
            metadata={
                "workflow_name": workflow.name,
                "workflow_version": workflow.version,
                "start_time": datetime.now().isoformat()
            }
        )
        
        logger.info(f"开始执行工作流: {workflow.name} (执行ID: {execution_id})")
        
        try:
            # 执行工作流
            await self._execute_workflow_nodes(workflow, context)
            
            # 更新元数据
            context.metadata["end_time"] = datetime.now().isoformat()
            context.metadata["status"] = "completed"
            
            logger.info(f"工作流执行完成: {workflow.name}")
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            context.metadata["end_time"] = datetime.now().isoformat()
            context.metadata["status"] = "failed"
            context.metadata["error"] = str(e)
            raise
        
        return context
    
    async def _execute_workflow_nodes(self, workflow: WorkflowDefinition, 
                                    context: ExecutionContext):
        """执行工作流节点"""
        current_node_id = context.current_node
        visited_nodes = set()
        
        while current_node_id and current_node_id not in visited_nodes:
            visited_nodes.add(current_node_id)
            
            # 查找当前节点
            current_node = None
            for node in workflow.nodes:
                if node.node_id == current_node_id:
                    current_node = node
                    break
            
            if not current_node:
                raise ValueError(f"找不到节点: {current_node_id}")
            
            # 执行节点任务
            if current_node.node_type == NodeType.TASK:
                await self._execute_task_node(current_node, context, workflow)
            elif current_node.node_type == NodeType.DECISION:
                current_node_id = await self._execute_decision_node(current_node, context)
                continue
            elif current_node.node_type == NodeType.END:
                logger.info("到达结束节点，工作流执行完成")
                break
            
            # 获取下一个节点
            current_node_id = self._get_next_node(current_node, context, workflow)
    
    async def _execute_task_node(self, node: Node, context: ExecutionContext, 
                               workflow: WorkflowDefinition):
        """执行任务节点"""
        execution = TaskExecution(
            execution_id=f"{context.execution_id}_{node.node_id}",
            workflow_id=context.workflow_id,
            node_id=node.node_id,
            task_type=node.config.get('task_type', 'unknown'),
            status=TaskStatus.PENDING,
            input_data=context.variables.copy(),
            output_data={},
            error_message=None,
            start_time=None,
            end_time=None,
            duration=None,
            retry_count=0,
            max_retries=node.config.get('max_retries', 3)
        )
        
        self.running_executions[execution.execution_id] = execution
        
        try:
            execution.status = TaskStatus.RUNNING
            execution.start_time = datetime.now()
            
            logger.info(f"执行任务节点: {node.name} ({node.node_id})")
            
            # 根据执行模式执行任务
            if self.execution_mode == ExecutionMode.ASYNC:
                result = await self._execute_task_async(node, execution)
            elif self.execution_mode == ExecutionMode.THREAD_POOL:
                result = await self._execute_task_thread_pool(node, execution)
            else:  # SYNC
                result = self._execute_task_sync(node, execution)
            
            execution.output_data = result
            execution.status = TaskStatus.COMPLETED
            execution.end_time = datetime.now()
            execution.duration = (execution.end_time - execution.start_time).total_seconds()
            
            # 更新上下文变量
            context.variables.update(result)
            logger.info(f"任务节点执行成功: {node.name}")
            
        except Exception as e:
            execution.status = TaskStatus.FAILED
            execution.error_message = str(e)
            execution.end_time = datetime.now()
            execution.duration = (execution.end_time - execution.start_time).total_seconds() if execution.start_time else 0
            
            logger.error(f"任务节点执行失败: {node.name}, 错误: {e}")
            raise
        finally:
            context.history.append(execution)
            if execution.execution_id in self.running_executions:
                del self.running_executions[execution.execution_id]
    
    async def _execute_task_async(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """异步执行任务"""
        handler = self.task_handlers.get(execution.task_type)
        if not handler:
            raise ValueError(f"未找到任务处理器: {execution.task_type}")
        
        # 如果处理器是异步的，直接await
        if asyncio.iscoroutinefunction(handler):
            return await handler(node, execution)
        else:
            # 如果是同步处理器，在执行器中运行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, handler, node, execution)
    
    async def _execute_task_thread_pool(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """在线程池中执行任务"""
        handler = self.task_handlers.get(execution.task_type)
        if not handler:
            raise ValueError(f"未找到任务处理器: {execution.task_type}")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, handler, node, execution)
    
    def _execute_task_sync(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """同步执行任务"""
        handler = self.task_handlers.get(execution.task_type)
        if not handler:
            raise ValueError(f"未找到任务处理器: {execution.task_type}")
        
        return handler(node, execution)
    
    async def _execute_decision_node(self, node: Node, context: ExecutionContext) -> str:
        """执行决策节点"""
        logger.info(f"执行决策节点: {node.name}")
        
        # 简单的条件判断逻辑
        conditions = node.conditions
        for condition in conditions:
            expression = condition.get('expression')
            next_node = condition.get('next_node')
            
            if self._evaluate_condition(expression, context.variables):
                logger.info(f"条件满足，转向节点: {next_node}")
                return next_node
        
        # 如果没有条件满足，使用默认下一个节点
        if node.next_nodes:
            return node.next_nodes[0]
        
        raise ValueError(f"决策节点 {node.name} 没有可转向的节点")
    
    def _evaluate_condition(self, expression: str, variables: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        # 简单的条件评估实现
        try:
            # 替换变量
            for var_name, var_value in variables.items():
                if isinstance(var_value, str):
                    expression = expression.replace(f"${var_name}", f"'{var_value}'")
                else:
                    expression = expression.replace(f"${var_name}", str(var_value))
            
            # 简单的安全eval（实际应用中应使用更安全的表达式解析器）
            result = eval(expression, {"__builtins__": {}}, {})
            return bool(result)
        except Exception as e:
            logger.warning(f"条件评估失败: {expression}, 错误: {e}")
            return False
    
    def _get_next_node(self, current_node: Node, context: ExecutionContext, 
                      workflow: WorkflowDefinition) -> Optional[str]:
        """获取下一个节点"""
        if current_node.next_nodes:
            return current_node.next_nodes[0]
        return None
    
    # 内置任务处理器实现
    def _handle_document_processing(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """处理文档处理任务"""
        operation = node.config.get('operation', 'process')
        input_data = execution.input_data
        
        logger.info(f"执行文档处理操作: {operation}")
        
        # 模拟文档处理逻辑
        result = {
            "operation": operation,
            "processed_documents": input_data.get('documents', []),
            "processing_time": time.time(),
            "status": "success"
        }
        
        # 模拟处理时间
        time.sleep(1)
        
        return result
    
    def _handle_vector_encoding(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """处理向量编码任务"""
        input_data = execution.input_data
        
        logger.info("执行向量编码任务")
        
        result = {
            "encoded_vectors": len(input_data.get('documents', [])),
            "encoding_model": "sentence-transformers",
            "encoding_time": time.time(),
            "status": "success"
        }
        
        time.sleep(0.5)
        
        return result
    
    def _handle_search_indexing(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """处理搜索索引任务"""
        input_data = execution.input_data
        
        logger.info("执行搜索索引构建")
        
        result = {
            "indexed_documents": len(input_data.get('documents', [])),
            "index_type": "milvus_hnsw",
            "indexing_time": time.time(),
            "status": "success"
        }
        
        time.sleep(0.3)
        
        return result
    
    def _handle_qa_generation(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """处理问答生成任务"""
        input_data = execution.input_data
        
        logger.info("执行问答生成任务")
        
        result = {
            "generated_answers": 1,
            "question": input_data.get('question', ''),
            "answer": "这是模拟生成的答案",
            "confidence": 0.85,
            "generation_time": time.time(),
            "status": "success"
        }
        
        time.sleep(0.2)
        
        return result
    
    def _handle_metadata_extraction(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """处理元数据提取任务"""
        input_data = execution.input_data
        
        logger.info("执行元数据提取任务")
        
        result = {
            "extracted_metadata": {
                "document_count": len(input_data.get('documents', [])),
                "extraction_time": time.time()
            },
            "status": "success"
        }
        
        time.sleep(0.1)
        
        return result
    
    def _handle_custom_script(self, node: Node, execution: TaskExecution) -> Dict[str, Any]:
        """处理自定义脚本任务"""
        script_content = node.config.get('script', '')
        
        logger.info("执行自定义脚本任务")
        
        result = {
            "script_output": f"执行脚本: {script_content[:50]}...",
            "execution_time": time.time(),
            "status": "success"
        }
        
        time.sleep(0.1)
        
        return result
    
    def get_execution_status(self, execution_id: str) -> Optional[TaskExecution]:
        """获取执行状态"""
        return self.running_executions.get(execution_id)
    
    def cancel_execution(self, execution_id: str) -> bool:
        """取消执行"""
        if execution_id in self.running_executions:
            execution = self.running_executions[execution_id]
            execution.status = TaskStatus.CANCELLED
            execution.end_time = datetime.now()
            logger.info(f"已取消执行: {execution_id}")
            return True
        return False
    
    def get_running_executions(self) -> List[TaskExecution]:
        """获取正在运行的执行"""
        return list(self.running_executions.values())

class WorkflowExecutor:
    """工作流执行器（高层接口）"""
    
    def __init__(self, task_executor: TaskExecutor):
        """
        初始化工作流执行器
        
        Args:
            task_executor: 任务执行器实例
        """
        self.task_executor = task_executor
    
    async def run_workflow(self, workflow: WorkflowDefinition, 
                          input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行工作流
        
        Args:
            workflow: 工作流定义
            input_data: 输入数据
            
        Returns:
            执行结果
        """
        try:
            context = await self.task_executor.execute_workflow(workflow, input_data)
            
            return {
                "execution_id": context.execution_id,
                "workflow_id": context.workflow_id,
                "status": context.metadata.get("status", "unknown"),
                "start_time": context.metadata.get("start_time"),
                "end_time": context.metadata.get("end_time"),
                "variables": context.variables,
                "history": [
                    {
                        "node_id": exec_record.node_id,
                        "task_type": exec_record.task_type,
                        "status": exec_record.status.value,
                        "duration": exec_record.duration,
                        "error": exec_record.error_message
                    }
                    for exec_record in context.history
                ]
            }
            
        except Exception as e:
            logger.error(f"工作流运行失败: {e}")
            raise

# 导出主要类
__all__ = ['TaskStatus', 'ExecutionMode', 'TaskExecution', 'ExecutionContext', 
           'TaskExecutor', 'WorkflowExecutor']