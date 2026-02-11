"""问答系统上下文管理器模块"""
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ContextType(Enum):
    """上下文类型枚举"""
    USER_QUERY = "user_query"
    SYSTEM_RESPONSE = "system_response"
    DOCUMENT_CONTEXT = "document_context"
    SEARCH_RESULTS = "search_results"
    CONVERSATION_HISTORY = "conversation_history"

@dataclass
class ContextEntry:
    """上下文条目数据类"""
    entry_id: str
    context_type: ContextType
    content: Union[str, Dict[str, Any]]
    timestamp: datetime
    metadata: Dict[str, Any]
    relevance_score: float = 1.0

class ContextWindow:
    """上下文窗口管理器"""
    
    def __init__(self, max_tokens: int = 4000, max_entries: int = 20):
        """
        初始化上下文窗口
        
        Args:
            max_tokens: 最大token数量
            max_entries: 最大条目数量
        """
        self.max_tokens = max_tokens
        self.max_entries = max_entries
        self.entries: List[ContextEntry] = []
        self.token_counter = TokenCounter()
    
    def add_entry(self, entry: ContextEntry) -> bool:
        """
        添加上下文条目
        
        Args:
            entry: 上下文条目
            
        Returns:
            是否成功添加
        """
        # 检查是否超过最大条目限制
        if len(self.entries) >= self.max_entries:
            self._prune_entries()
        
        # 检查token限制
        entry_tokens = self.token_counter.count_tokens(str(entry.content))
        current_tokens = self.get_total_tokens()
        
        if current_tokens + entry_tokens > self.max_tokens:
            self._prune_by_tokens(entry_tokens)
        
        self.entries.append(entry)
        logger.debug(f"添加上下文条目: {entry.entry_id}, 类型: {entry.context_type}")
        return True
    
    def get_relevant_context(self, query: str, max_results: int = 10) -> List[ContextEntry]:
        """
        获取与查询相关的上下文
        
        Args:
            query: 查询字符串
            max_results: 最大返回结果数
            
        Returns:
            相关的上下文条目列表
        """
        # 简单的相关性计算（基于时间接近度和类型匹配）
        relevant_entries = []
        
        for entry in self.entries:
            relevance = self._calculate_relevance(entry, query)
            if relevance > 0.3:  # 相关性阈值
                entry.relevance_score = relevance
                relevant_entries.append(entry)
        
        # 按相关性排序
        relevant_entries.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return relevant_entries[:max_results]
    
    def get_context_by_type(self, context_type: ContextType) -> List[ContextEntry]:
        """根据类型获取上下文条目"""
        return [entry for entry in self.entries if entry.context_type == context_type]
    
    def get_recent_context(self, hours: int = 24) -> List[ContextEntry]:
        """获取最近的上下文条目"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [entry for entry in self.entries if entry.timestamp >= cutoff_time]
    
    def clear_context(self):
        """清空上下文"""
        self.entries.clear()
        logger.info("上下文已清空")
    
    def get_total_tokens(self) -> int:
        """获取总token数"""
        total_tokens = 0
        for entry in self.entries:
            total_tokens += self.token_counter.count_tokens(str(entry.content))
        return total_tokens
    
    def _prune_entries(self):
        """基于条目数量的剪枝"""
        # 移除最旧的条目
        if self.entries:
            removed_entry = self.entries.pop(0)
            logger.debug(f"移除旧条目: {removed_entry.entry_id}")
    
    def _prune_by_tokens(self, required_tokens: int):
        """基于token数量的剪枝"""
        # 按时间顺序移除条目直到满足token要求
        while self.get_total_tokens() + required_tokens > self.max_tokens and self.entries:
            removed_entry = self.entries.pop(0)
            logger.debug(f"因token限制移除条目: {removed_entry.entry_id}")
    
    def _calculate_relevance(self, entry: ContextEntry, query: str) -> float:
        """计算条目与查询的相关性"""
        relevance = 0.0
        
        # 时间相关性（越近越相关）
        time_diff = datetime.now() - entry.timestamp
        hours_diff = time_diff.total_seconds() / 3600
        time_relevance = max(0.0, 1.0 - (hours_diff / 24))  # 24小时内线性衰减
        relevance += time_relevance * 0.3
        
        # 内容相关性
        content_str = str(entry.content).lower()
        query_words = query.lower().split()
        
        matching_words = sum(1 for word in query_words if word in content_str)
        content_relevance = matching_words / len(query_words) if query_words else 0
        relevance += content_relevance * 0.5
        
        # 类型相关性
        type_weights = {
            ContextType.USER_QUERY: 0.8,
            ContextType.SYSTEM_RESPONSE: 0.6,
            ContextType.DOCUMENT_CONTEXT: 0.4,
            ContextType.SEARCH_RESULTS: 0.5,
            ContextType.CONVERSATION_HISTORY: 0.3
        }
        type_relevance = type_weights.get(entry.context_type, 0.1)
        relevance += type_relevance * 0.2
        
        return min(1.0, relevance)

class ContextManager:
    """上下文管理器（简化版本）"""
    
    def __init__(self):
        """初始化上下文管理器"""
        self.conversations = {}
    
    def get_session(self, session_id: str) -> 'ContextWindow':
        """获取会话上下文窗口"""
        if session_id not in self.conversations:
            self.conversations[session_id] = ContextWindow()
        return self.conversations[session_id]
    
    def get_relevant_context(self, session_id: str, query: str, 
                           max_results: int = 10) -> List[ContextEntry]:
        """获取相关上下文"""
        session = self.get_session(session_id)
        return session.get_relevant_context(query, max_results)
    
    def add_context_entry(self, session_id: str, entry: ContextEntry):
        """添加上下文条目"""
        session = self.get_session(session_id)
        session.add_entry(entry)


class ConversationManager:
    """对话管理器"""
    
    def __init__(self, session_timeout: int = 3600):
        """
        初始化对话管理器
        
        Args:
            session_timeout: 会话超时时间（秒）
        """
        self.session_timeout = session_timeout
        self.sessions: Dict[str, ContextWindow] = {}
        self.active_sessions: Dict[str, datetime] = {}
    
    def get_session(self, session_id: str) -> ContextWindow:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ContextWindow()
            logger.info(f"创建新会话: {session_id}")
        
        self.active_sessions[session_id] = datetime.now()
        return self.sessions[session_id]
    
    def add_user_query(self, session_id: str, query: str, metadata: Dict[str, Any] = None) -> str:
        """添加用户查询"""
        if metadata is None:
            metadata = {}
            
        entry_id = f"query_{datetime.now().timestamp()}"
        entry = ContextEntry(
            entry_id=entry_id,
            context_type=ContextType.USER_QUERY,
            content=query,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        session = self.get_session(session_id)
        session.add_entry(entry)
        
        return entry_id
    
    def add_system_response(self, session_id: str, response: str, 
                          related_query_id: str = None, metadata: Dict[str, Any] = None) -> str:
        """添加系统响应"""
        if metadata is None:
            metadata = {}
            
        if related_query_id:
            metadata['related_query'] = related_query_id
            
        entry_id = f"response_{datetime.now().timestamp()}"
        entry = ContextEntry(
            entry_id=entry_id,
            context_type=ContextType.SYSTEM_RESPONSE,
            content=response,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        session = self.get_session(session_id)
        session.add_entry(entry)
        
        return entry_id
    
    def add_document_context(self, session_id: str, document_info: Dict[str, Any],
                           metadata: Dict[str, Any] = None) -> str:
        """添加文档上下文"""
        if metadata is None:
            metadata = {}
            
        entry_id = f"doc_ctx_{datetime.now().timestamp()}"
        entry = ContextEntry(
            entry_id=entry_id,
            context_type=ContextType.DOCUMENT_CONTEXT,
            content=document_info,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        session = self.get_session(session_id)
        session.add_entry(entry)
        
        return entry_id
    
    def get_conversation_history(self, session_id: str, max_turns: int = 10) -> List[Dict[str, Any]]:
        """获取对话历史"""
        session = self.get_session(session_id)
        history_entries = session.get_context_by_type(ContextType.CONVERSATION_HISTORY)
        
        # 获取最新的用户查询和系统响应
        user_queries = session.get_context_by_type(ContextType.USER_QUERY)
        system_responses = session.get_context_by_type(ContextType.SYSTEM_RESPONSE)
        
        # 组合对话历史
        conversation_history = []
        
        # 交替组合查询和响应
        for query in user_queries[-max_turns:]:
            history_item = {
                'role': 'user',
                'content': query.content,
                'timestamp': query.timestamp.isoformat(),
                'metadata': query.metadata
            }
            conversation_history.append(history_item)
            
            # 查找相关的系统响应
            related_responses = [resp for resp in system_responses 
                               if resp.metadata.get('related_query') == query.entry_id]
            for response in related_responses:
                history_item = {
                    'role': 'assistant',
                    'content': response.content,
                    'timestamp': response.timestamp.isoformat(),
                    'metadata': response.metadata
                }
                conversation_history.append(history_item)
        
        # 限制历史长度
        return conversation_history[-(max_turns * 2):]
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, last_active in self.active_sessions.items():
            if (current_time - last_active).total_seconds() > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            del self.active_sessions[session_id]
            logger.info(f"清理过期会话: {session_id}")
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """获取会话信息"""
        if session_id not in self.sessions:
            return {}
        
        session = self.sessions[session_id]
        return {
            'session_id': session_id,
            'entry_count': len(session.entries),
            'total_tokens': session.get_total_tokens(),
            'last_active': self.active_sessions.get(session_id, datetime.now()).isoformat(),
            'context_types': {entry.context_type.value: entry.context_type.value 
                            for entry in session.entries}
        }

class TokenCounter:
    """Token计数器"""
    
    def __init__(self):
        """初始化token计数器"""
        # 简单的字符到token估算（实际应用中应使用更精确的方法）
        self.chars_per_token = 4  # 平均每个token约4个字符
    
    def count_tokens(self, text: str) -> int:
        """
        计算文本的token数量
        
        Args:
            text: 输入文本
            
        Returns:
            估算的token数量
        """
        if not text:
            return 0
        
        # 简单的字符计数方法
        char_count = len(text)
        token_estimate = char_count / self.chars_per_token
        
        # 考虑标点符号和空格的影响
        punctuation_bonus = text.count('.') + text.count(',') + text.count(';') + text.count(':')
        token_estimate += punctuation_bonus * 0.1
        
        return int(token_estimate)
    
    def count_tokens_for_object(self, obj: Any) -> int:
        """计算对象的token数量"""
        return self.count_tokens(json.dumps(obj, ensure_ascii=False))

# 导出主要类
__all__ = ['ContextType', 'ContextEntry', 'ContextWindow', 'ContextManager', 'ConversationManager', 'TokenCounter']