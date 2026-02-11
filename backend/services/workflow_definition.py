"""工作流定义系统模块"""
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class NodeType(Enum):
    """节点类型枚举"""
    START = "start"
    END = "end"
    TASK = "task"
    DECISION = "decision"
    PARALLEL = "parallel"
    MERGE = "merge"
    SUB_WORKFLOW = "sub_workflow"

class TaskType(Enum):
    """任务类型枚举"""
    DOCUMENT_PROCESSING = "document_processing"
    VECTOR_ENCODING = "vector_encoding"
    SEARCH_INDEXING = "search_indexing"
    QA_GENERATION = "qa_generation"
    METADATA_EXTRACTION = "metadata_extraction"
    CUSTOM_SCRIPT = "custom_script"

@dataclass
class Node:
    """工作流节点"""
    node_id: str
    node_type: NodeType
    name: str
    description: str
    config: Dict[str, Any]
    next_nodes: List[str]  # 下一节点ID列表
    conditions: List[Dict[str, Any]]  # 条件列表（用于决策节点）

@dataclass
class Edge:
    """工作流边"""
    edge_id: str
    from_node: str
    to_node: str
    condition: Optional[str] = None
    priority: int = 0

@dataclass
class WorkflowDefinition:
    """工作流定义"""
    workflow_id: str
    name: str
    description: str
    version: str
    nodes: List[Node]
    edges: List[Edge]
    start_node: str
    end_nodes: List[str]
    variables: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class WorkflowParser:
    """工作流解析器"""
    
    def __init__(self):
        """初始化工作流解析器"""
        pass
    
    def parse_from_dict(self, workflow_dict: Dict[str, Any]) -> WorkflowDefinition:
        """
        从字典解析工作流定义
        
        Args:
            workflow_dict: 工作流定义字典
            
        Returns:
            工作流定义对象
        """
        try:
            # 解析节点
            nodes = []
            for node_data in workflow_dict.get('nodes', []):
                node = Node(
                    node_id=node_data['node_id'],
                    node_type=NodeType(node_data['node_type']),
                    name=node_data['name'],
                    description=node_data.get('description', ''),
                    config=node_data.get('config', {}),
                    next_nodes=node_data.get('next_nodes', []),
                    conditions=node_data.get('conditions', [])
                )
                nodes.append(node)
            
            # 解析边
            edges = []
            for edge_data in workflow_dict.get('edges', []):
                edge = Edge(
                    edge_id=edge_data['edge_id'],
                    from_node=edge_data['from_node'],
                    to_node=edge_data['to_node'],
                    condition=edge_data.get('condition'),
                    priority=edge_data.get('priority', 0)
                )
                edges.append(edge)
            
            # 创建工作流定义
            workflow = WorkflowDefinition(
                workflow_id=workflow_dict['workflow_id'],
                name=workflow_dict['name'],
                description=workflow_dict.get('description', ''),
                version=workflow_dict.get('version', '1.0.0'),
                nodes=nodes,
                edges=edges,
                start_node=workflow_dict['start_node'],
                end_nodes=workflow_dict.get('end_nodes', []),
                variables=workflow_dict.get('variables', {}),
                metadata=workflow_dict.get('metadata', {}),
                created_at=datetime.fromisoformat(workflow_dict.get('created_at', datetime.now().isoformat())),
                updated_at=datetime.fromisoformat(workflow_dict.get('updated_at', datetime.now().isoformat()))
            )
            
            logger.info(f"解析工作流定义: {workflow.name} (v{workflow.version})")
            return workflow
            
        except Exception as e:
            logger.error(f"工作流解析失败: {e}")
            raise
    
    def parse_from_json(self, json_string: str) -> WorkflowDefinition:
        """
        从JSON字符串解析工作流定义
        
        Args:
            json_string: JSON字符串
            
        Returns:
            工作流定义对象
        """
        try:
            workflow_dict = json.loads(json_string)
            return self.parse_from_dict(workflow_dict)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise
        except Exception as e:
            logger.error(f"工作流JSON解析失败: {e}")
            raise
    
    def to_dict(self, workflow: WorkflowDefinition) -> Dict[str, Any]:
        """
        将工作流定义转换为字典
        
        Args:
            workflow: 工作流定义对象
            
        Returns:
            工作流字典
        """
        workflow_dict = {
            'workflow_id': workflow.workflow_id,
            'name': workflow.name,
            'description': workflow.description,
            'version': workflow.version,
            'nodes': [
                {
                    'node_id': node.node_id,
                    'node_type': node.node_type.value,
                    'name': node.name,
                    'description': node.description,
                    'config': node.config,
                    'next_nodes': node.next_nodes,
                    'conditions': node.conditions
                }
                for node in workflow.nodes
            ],
            'edges': [
                {
                    'edge_id': edge.edge_id,
                    'from_node': edge.from_node,
                    'to_node': edge.to_node,
                    'condition': edge.condition,
                    'priority': edge.priority
                }
                for edge in workflow.edges
            ],
            'start_node': workflow.start_node,
            'end_nodes': workflow.end_nodes,
            'variables': workflow.variables,
            'metadata': workflow.metadata,
            'created_at': workflow.created_at.isoformat(),
            'updated_at': workflow.updated_at.isoformat()
        }
        
        return workflow_dict
    
    def validate_workflow(self, workflow: WorkflowDefinition) -> List[str]:
        """
        验证工作流定义
        
        Args:
            workflow: 工作流定义对象
            
        Returns:
            验证错误列表
        """
        errors = []
        
        # 检查必需字段
        if not workflow.workflow_id:
            errors.append("工作流ID不能为空")
        
        if not workflow.name:
            errors.append("工作流名称不能为空")
        
        if not workflow.nodes:
            errors.append("工作流必须包含至少一个节点")
        
        # 检查起始节点
        if workflow.start_node not in [node.node_id for node in workflow.nodes]:
            errors.append(f"起始节点 {workflow.start_node} 不存在")
        
        # 检查结束节点
        for end_node in workflow.end_nodes:
            if end_node not in [node.node_id for node in workflow.nodes]:
                errors.append(f"结束节点 {end_node} 不存在")
        
        # 检查节点连接
        node_ids = {node.node_id for node in workflow.nodes}
        for edge in workflow.edges:
            if edge.from_node not in node_ids:
                errors.append(f"边的起始节点 {edge.from_node} 不存在")
            if edge.to_node not in node_ids:
                errors.append(f"边的目标节点 {edge.to_node} 不存在")
        
        # 检查循环引用
        if self._has_cycle(workflow):
            errors.append("工作流存在循环引用")
        
        return errors
    
    def _has_cycle(self, workflow: WorkflowDefinition) -> bool:
        """检查是否存在循环引用"""
        # 构建邻接表
        graph = {node.node_id: [] for node in workflow.nodes}
        for edge in workflow.edges:
            graph[edge.from_node].append(edge.to_node)
        
        # 使用DFS检测环
        visited = set()
        recursion_stack = set()
        
        def dfs(node_id):
            visited.add(node_id)
            recursion_stack.add(node_id)
            
            for neighbor in graph[node_id]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True
            
            recursion_stack.remove(node_id)
            return False
        
        for node_id in graph:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        
        return False

class WorkflowBuilder:
    """工作流构建器"""
    
    def __init__(self):
        """初始化工作流构建器"""
        self.parser = WorkflowParser()
    
    def create_document_processing_workflow(self) -> WorkflowDefinition:
        """创建文档处理工作流"""
        workflow_id = f"doc_process_{uuid.uuid4().hex[:8]}"
        
        # 定义节点
        nodes = [
            Node(
                node_id="start",
                node_type=NodeType.START,
                name="开始",
                description="工作流开始节点",
                config={},
                next_nodes=["validate_doc"],
                conditions=[]
            ),
            Node(
                node_id="validate_doc",
                node_type=NodeType.TASK,
                name="文档验证",
                description="验证文档格式和完整性",
                config={
                    "task_type": TaskType.DOCUMENT_PROCESSING.value,
                    "operation": "validate"
                },
                next_nodes=["process_doc"],
                conditions=[]
            ),
            Node(
                node_id="process_doc",
                node_type=NodeType.TASK,
                name="文档处理",
                description="解析和处理文档内容",
                config={
                    "task_type": TaskType.DOCUMENT_PROCESSING.value,
                    "operation": "process"
                },
                next_nodes=["extract_metadata"],
                conditions=[]
            ),
            Node(
                node_id="extract_metadata",
                node_type=NodeType.TASK,
                name="元数据提取",
                description="提取文档元数据",
                config={
                    "task_type": TaskType.METADATA_EXTRACTION.value
                },
                next_nodes=["encode_vectors"],
                conditions=[]
            ),
            Node(
                node_id="encode_vectors",
                node_type=NodeType.TASK,
                name="向量编码",
                description="将文档内容编码为向量",
                config={
                    "task_type": TaskType.VECTOR_ENCODING.value
                },
                next_nodes=["index_search"],
                conditions=[]
            ),
            Node(
                node_id="index_search",
                node_type=NodeType.TASK,
                name="索引构建",
                description="构建搜索索引",
                config={
                    "task_type": TaskType.SEARCH_INDEXING.value
                },
                next_nodes=["end"],
                conditions=[]
            ),
            Node(
                node_id="end",
                node_type=NodeType.END,
                name="结束",
                description="工作流结束节点",
                config={},
                next_nodes=[],
                conditions=[]
            )
        ]
        
        # 定义边
        edges = [
            Edge(edge_id="e1", from_node="start", to_node="validate_doc"),
            Edge(edge_id="e2", from_node="validate_doc", to_node="process_doc"),
            Edge(edge_id="e3", from_node="process_doc", to_node="extract_metadata"),
            Edge(edge_id="e4", from_node="extract_metadata", to_node="encode_vectors"),
            Edge(edge_id="e5", from_node="encode_vectors", to_node="index_search"),
            Edge(edge_id="e6", from_node="index_search", to_node="end")
        ]
        
        workflow = WorkflowDefinition(
            workflow_id=workflow_id,
            name="文档处理工作流",
            description="完整的文档处理和索引构建流程",
            version="1.0.0",
            nodes=nodes,
            edges=edges,
            start_node="start",
            end_nodes=["end"],
            variables={},
            metadata={
                "category": "document_processing",
                "estimated_duration": "300"  # 预估300秒
            },
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        return workflow
    
    def create_qa_enhancement_workflow(self) -> WorkflowDefinition:
        """创建问答增强工作流"""
        workflow_id = f"qa_enhance_{uuid.uuid4().hex[:8]}"
        
        nodes = [
            Node(
                node_id="start",
                node_type=NodeType.START,
                name="开始",
                description="问答增强流程开始",
                config={},
                next_nodes=["retrieve_docs"],
                conditions=[]
            ),
            Node(
                node_id="retrieve_docs",
                node_type=NodeType.TASK,
                name="文档检索",
                description="检索相关文档",
                config={
                    "task_type": "document_retrieval",
                    "retrieval_strategy": "hybrid"
                },
                next_nodes=["generate_answer"],
                conditions=[]
            ),
            Node(
                node_id="generate_answer",
                node_type=NodeType.TASK,
                name="答案生成",
                description="生成问答答案",
                config={
                    "task_type": TaskType.QA_GENERATION.value,
                    "model": "rule_based"
                },
                next_nodes=["validate_answer"],
                conditions=[]
            ),
            Node(
                node_id="validate_answer",
                node_type=NodeType.TASK,
                name="答案验证",
                description="验证答案质量和准确性",
                config={
                    "task_type": "answer_validation"
                },
                next_nodes=["track_sources"],
                conditions=[]
            ),
            Node(
                node_id="track_sources",
                node_type=NodeType.TASK,
                name="来源跟踪",
                description="跟踪答案来源",
                config={
                    "task_type": "source_tracking"
                },
                next_nodes=["end"],
                conditions=[]
            ),
            Node(
                node_id="end",
                node_type=NodeType.END,
                name="结束",
                description="流程结束",
                config={},
                next_nodes=[],
                conditions=[]
            )
        ]
        
        edges = [
            Edge(edge_id="e1", from_node="start", to_node="retrieve_docs"),
            Edge(edge_id="e2", from_node="retrieve_docs", to_node="generate_answer"),
            Edge(edge_id="e3", from_node="generate_answer", to_node="validate_answer"),
            Edge(edge_id="e4", from_node="validate_answer", to_node="track_sources"),
            Edge(edge_id="e5", from_node="track_sources", to_node="end")
        ]
        
        workflow = WorkflowDefinition(
            workflow_id=workflow_id,
            name="问答增强工作流",
            description="智能问答答案生成和验证流程",
            version="1.0.0",
            nodes=nodes,
            edges=edges,
            start_node="start",
            end_nodes=["end"],
            variables={},
            metadata={
                "category": "qa_enhancement",
                "estimated_duration": "60"
            },
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        return workflow

# 导出主要类
__all__ = ['NodeType', 'TaskType', 'Node', 'Edge', 'WorkflowDefinition', 
           'WorkflowParser', 'WorkflowBuilder']