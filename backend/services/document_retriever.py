"""文档检索组件模块"""
import numpy as np
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime

# 导入相关模块
import sys
import os
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_path)

from services.embedding_encoder import EncoderManager
from services.vector_search import VectorSearchEngine, SearchResult
from services.context_manager import ContextManager, ContextEntry, ContextType

logger = logging.getLogger(__name__)

class RetrievalStrategy(Enum):
    """检索策略枚举"""
    VECTOR_ONLY = "vector_only"
    KEYWORD_ONLY = "keyword_only"
    HYBRID = "hybrid"
    CONTEXT_AWARE = "context_aware"

@dataclass
class RetrievedDocument:
    """检索到的文档"""
    document_id: str
    chunk_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    retrieval_method: str
    context_relevance: float = 0.0

class DocumentRetriever:
    """文档检索器"""
    
    def __init__(self, vector_engine: VectorSearchEngine, 
                 encoder_manager: EncoderManager,
                 context_manager: ContextManager = None):
        """
        初始化文档检索器
        
        Args:
            vector_engine: 向量搜索引擎
            encoder_manager: 编码器管理器
            context_manager: 上下文管理器（可选）
        """
        self.vector_engine = vector_engine
        self.encoder_manager = encoder_manager
        self.context_manager = context_manager
        self.default_top_k = 10
        self.default_similarity_threshold = 0.5
    
    def retrieve(self, query: str, 
                strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
                top_k: int = None,
                context: Dict[str, Any] = None,
                filters: Dict[str, Any] = None) -> List[RetrievedDocument]:
        """
        检索相关文档
        
        Args:
            query: 查询字符串
            strategy: 检索策略
            top_k: 返回结果数量
            context: 上下文信息
            filters: 过滤条件
            
        Returns:
            检索到的文档列表
        """
        if top_k is None:
            top_k = self.default_top_k
        
        if strategy == RetrievalStrategy.VECTOR_ONLY:
            return self._vector_retrieve(query, top_k, filters)
        elif strategy == RetrievalStrategy.KEYWORD_ONLY:
            return self._keyword_retrieve(query, top_k, filters)
        elif strategy == RetrievalStrategy.HYBRID:
            return self._hybrid_retrieve(query, top_k, filters)
        elif strategy == RetrievalStrategy.CONTEXT_AWARE:
            return self._context_aware_retrieve(query, top_k, context, filters)
        else:
            # 默认使用混合检索
            return self._hybrid_retrieve(query, top_k, filters)
    
    def _vector_retrieve(self, query: str, top_k: int, 
                        filters: Dict[str, Any] = None) -> List[RetrievedDocument]:
        """向量检索"""
        try:
            # 使用向量搜索引擎
            response = self.vector_engine.search(
                query=query,
                top_k=top_k * 2,  # 扩大搜索范围
                filters=filters,
                similarity_threshold=self.default_similarity_threshold
            )
            
            # 转换为检索文档格式
            retrieved_docs = []
            for result in response.results[:top_k]:
                doc = RetrievedDocument(
                    document_id=result.document_id,
                    chunk_id=result.chunk_id,
                    content=result.content,
                    score=result.score,
                    metadata=result.metadata,
                    retrieval_method="vector"
                )
                retrieved_docs.append(doc)
            
            logger.info(f"向量检索返回 {len(retrieved_docs)} 个文档")
            return retrieved_docs
            
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []
    
    def _keyword_retrieve(self, query: str, top_k: int,
                         filters: Dict[str, Any] = None) -> List[RetrievedDocument]:
        """关键词检索"""
        # 这里应该调用关键词搜索引擎
        # 由于关键词搜索模块是占位符实现，返回空列表
        logger.warning("关键词检索功能尚未完全实现")
        return []
    
    def _hybrid_retrieve(self, query: str, top_k: int,
                        filters: Dict[str, Any] = None) -> List[RetrievedDocument]:
        """混合检索"""
        # 获取向量检索结果
        vector_docs = self._vector_retrieve(query, top_k, filters)
        
        # 获取关键词检索结果
        keyword_docs = self._keyword_retrieve(query, top_k, filters)
        
        # 融合结果
        fused_docs = self._fuse_retrieval_results(vector_docs, keyword_docs, top_k)
        
        logger.info(f"混合检索返回 {len(fused_docs)} 个文档")
        return fused_docs
    
    def _context_aware_retrieve(self, query: str, top_k: int,
                              context: Dict[str, Any] = None,
                              filters: Dict[str, Any] = None) -> List[RetrievedDocument]:
        """上下文感知检索"""
        if context is None:
            context = {}
        
        # 基础检索
        base_docs = self._hybrid_retrieve(query, top_k * 2, filters)
        
        # 应用上下文相关性调整
        context_aware_docs = []
        session_id = context.get('session_id')
        
        if session_id and self.context_manager:
            # 获取会话上下文
            session_context = self.context_manager.get_session(session_id)
            relevant_context = session_context.get_relevant_context(query, max_results=5)
            
            # 调整文档相关性分数
            for doc in base_docs:
                context_score = self._calculate_context_relevance(doc, relevant_context)
                doc.context_relevance = context_score
                doc.score = (doc.score + context_score) / 2  # 平均分数
                context_aware_docs.append(doc)
        else:
            context_aware_docs = base_docs
        
        # 按调整后的分数排序
        context_aware_docs.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"上下文感知检索返回 {len(context_aware_docs[:top_k])} 个文档")
        return context_aware_docs[:top_k]
    
    def _fuse_retrieval_results(self, vector_docs: List[RetrievedDocument],
                              keyword_docs: List[RetrievedDocument],
                              top_k: int) -> List[RetrievedDocument]:
        """融合不同来源的检索结果"""
        # 文档去重和分数融合
        doc_dict = {}
        
        # 处理向量检索结果
        for doc in vector_docs:
            doc_key = f"{doc.document_id}_{doc.chunk_id}"
            if doc_key not in doc_dict:
                doc_dict[doc_key] = doc
                doc.score *= 0.7  # 向量检索权重
            else:
                # 如果文档已存在，累加分数
                doc_dict[doc_key].score += doc.score * 0.7
        
        # 处理关键词检索结果
        for doc in keyword_docs:
            doc_key = f"{doc.document_id}_{doc.chunk_id}"
            if doc_key not in doc_dict:
                doc_dict[doc_key] = doc
                doc.score *= 0.3  # 关键词检索权重
            else:
                doc_dict[doc_key].score += doc.score * 0.3
        
        # 转换为列表并排序
        fused_docs = list(doc_dict.values())
        fused_docs.sort(key=lambda x: x.score, reverse=True)
        
        return fused_docs[:top_k]
    
    def _calculate_context_relevance(self, doc: RetrievedDocument, 
                                   context_entries: List[ContextEntry]) -> float:
        """计算文档与上下文的相关性"""
        if not context_entries:
            return 0.0
        
        relevance_scores = []
        
        for entry in context_entries:
            # 基于内容匹配计算相关性
            content_match = self._content_similarity(str(doc.content), str(entry.content))
            
            # 基于时间接近度
            time_diff = datetime.now() - entry.timestamp
            time_relevance = max(0.0, 1.0 - (time_diff.total_seconds() / 3600 / 24))  # 24小时衰减
            
            # 综合相关性
            combined_relevance = (content_match * 0.7 + time_relevance * 0.3)
            relevance_scores.append(combined_relevance)
        
        return sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    
    def _content_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        # 简单的词汇重叠计算
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def get_retrieval_stats(self) -> Dict[str, Any]:
        """获取检索统计信息"""
        return {
            "default_top_k": self.default_top_k,
            "default_similarity_threshold": self.default_similarity_threshold,
            "supported_strategies": [strategy.value for strategy in RetrievalStrategy],
            "context_aware_enabled": self.context_manager is not None
        }

class RAGRetriever:
    """RAG（检索增强生成）检索器"""
    
    def __init__(self, document_retriever: DocumentRetriever):
        """
        初始化RAG检索器
        
        Args:
            document_retriever: 文档检索器
        """
        self.document_retriever = document_retriever
    
    def retrieve_for_qa(self, question: str, 
                       context: Dict[str, Any] = None,
                       max_context_length: int = 2000) -> Dict[str, Any]:
        """
        为问答检索相关文档上下文
        
        Args:
            question: 问题
            context: 上下文信息
            max_context_length: 最大上下文长度
            
        Returns:
            包含检索结果和上下文的字典
        """
        # 使用上下文感知检索
        retrieved_docs = self.document_retriever.retrieve(
            query=question,
            strategy=RetrievalStrategy.CONTEXT_AWARE,
            top_k=5,
            context=context
        )
        
        # 构建上下文字符串
        context_chunks = []
        total_length = 0
        
        for doc in retrieved_docs:
            chunk_content = f"文档[{doc.document_id}]: {doc.content}"
            
            # 检查长度限制
            if total_length + len(chunk_content) > max_context_length:
                break
                
            context_chunks.append(chunk_content)
            total_length += len(chunk_content)
        
        # 构建返回结果
        result = {
            "question": question,
            "context": "\n\n".join(context_chunks),
            "retrieved_documents": [
                {
                    "document_id": doc.document_id,
                    "chunk_id": doc.chunk_id,
                    "score": doc.score,
                    "retrieval_method": doc.retrieval_method
                }
                for doc in retrieved_docs
            ],
            "context_length": total_length,
            "document_count": len(context_chunks)
        }
        
        logger.info(f"RAG检索完成: {len(context_chunks)} 个文档片段, 总长度 {total_length}")
        return result
    
    def expand_query_context(self, question: str, 
                           expansion_terms: int = 3) -> str:
        """
        扩展查询上下文
        
        Args:
            question: 原始问题
            expansion_terms: 扩展词数量
            
        Returns:
            扩展后的问题
        """
        # 这里可以实现查询扩展逻辑
        # 例如：基于同义词、相关概念等扩展查询
        expanded_query = question  # 简单返回原查询
        
        logger.debug(f"查询扩展: '{question}' -> '{expanded_query}'")
        return expanded_query

# 导出主要类
__all__ = ['RetrievalStrategy', 'RetrievedDocument', 'DocumentRetriever', 'RAGRetriever']