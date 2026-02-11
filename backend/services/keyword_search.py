"""关键词搜索引擎模块"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import sys
import os
import numpy as np

# 添加项目路径
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_path)

from services.vector_search import SearchResult, SearchResponse

logger = logging.getLogger(__name__)

@dataclass
class KeywordHit:
    """关键词命中结果"""
    document_id: str
    chunk_id: str
    content: str
    keywords_found: List[str]
    keyword_positions: List[int]
    tf_idf_score: float
    metadata: Dict[str, Any]

class SimpleKeywordSearch:
    """简易关键词搜索引擎（占位符实现）"""
    
    def __init__(self):
        """初始化关键词搜索引擎"""
        self.documents_index = {}  # 文档索引
        self.keyword_index = {}    # 关键词倒排索引
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会',
            '着', '没有', '看', '好', '自己', '这', 'that', 'this', 'with', 'for',
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'of', 'is', 'are'
        }
    
    def index_document(self, document_id: str, chunk_id: str, 
                      content: str, metadata: Dict[str, Any] = None):
        """
        索引文档内容
        
        Args:
            document_id: 文档ID
            chunk_id: 块ID
            content: 文档内容
            metadata: 元数据
        """
        if metadata is None:
            metadata = {}
            
        # 提取关键词
        keywords = self._extract_keywords(content)
        
        # 存储文档
        doc_key = f"{document_id}_{chunk_id}"
        self.documents_index[doc_key] = {
            'document_id': document_id,
            'chunk_id': chunk_id,
            'content': content,
            'keywords': keywords,
            'metadata': metadata
        }
        
        # 更新倒排索引
        for keyword in keywords:
            if keyword not in self.keyword_index:
                self.keyword_index[keyword] = []
            self.keyword_index[keyword].append({
                'doc_key': doc_key,
                'positions': self._find_keyword_positions(content, keyword)
            })
    
    def search(self, query: str, top_k: int = 10) -> SearchResponse:
        """
        执行关键词搜索
        
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            
        Returns:
            搜索响应
        """
        # 提取查询关键词
        query_keywords = self._extract_keywords(query)
        
        if not query_keywords:
            return SearchResponse(
                query=query,
                results=[],
                total_hits=0,
                search_time=0,
                search_type="keyword",
                facets={}
            )
        
        # 计算文档相关性分数
        doc_scores = {}
        keyword_matches = {}
        
        for keyword in query_keywords:
            if keyword in self.keyword_index:
                for hit in self.keyword_index[keyword]:
                    doc_key = hit['doc_key']
                    positions = hit['positions']
                    
                    if doc_key not in doc_scores:
                        doc_scores[doc_key] = 0
                        keyword_matches[doc_key] = []
                    
                    # 简单的TF-IDF分数计算
                    tf = len(positions)  # 词频
                    idf = self._calculate_idf(keyword)  # 逆文档频率
                    score = tf * idf
                    
                    doc_scores[doc_key] += score
                    keyword_matches[doc_key].extend([keyword] * len(positions))
        
        # 按分数排序
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 构建结果
        results = []
        for i, (doc_key, score) in enumerate(sorted_docs[:top_k]):
            doc_info = self.documents_index[doc_key]
            result = SearchResult(
                id=i,
                document_id=doc_info['document_id'],
                chunk_id=doc_info['chunk_id'],
                content=doc_info['content'],
                score=float(score),
                metadata=doc_info['metadata'],
                source="keyword",
                rank=i + 1
            )
            results.append(result)
        
        return SearchResponse(
            query=query,
            results=results,
            total_hits=len(sorted_docs),
            search_time=0.01,  # 模拟搜索时间
            search_type="keyword",
            facets=self._build_facets(results)
        )
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        # 移除标点符号
        cleaned_text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        
        # 分词（简单实现）
        words = re.findall(r'[\w\u4e00-\u9fff]+', cleaned_text.lower())
        
        # 过滤停用词和短词
        keywords = [word for word in words 
                   if len(word) > 1 and word not in self.stop_words]
        
        return list(set(keywords))  # 去重
    
    def _find_keyword_positions(self, text: str, keyword: str) -> List[int]:
        """查找关键词在文本中的位置"""
        positions = []
        start = 0
        while True:
            pos = text.find(keyword, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
        return positions
    
    def _calculate_idf(self, keyword: str) -> float:
        """计算逆文档频率"""
        if keyword not in self.keyword_index:
            return 0
        
        # 简化的IDF计算
        doc_freq = len(self.keyword_index[keyword])
        total_docs = len(self.documents_index)
        
        if total_docs == 0 or doc_freq == 0:
            return 0
        
        return np.log(total_docs / doc_freq)
    
    def _build_facets(self, results: List[SearchResult]) -> Dict[str, Any]:
        """构建分面统计"""
        facets = {
            'content_types': {},
            'languages': {},
            'categories': {}
        }
        
        for result in results:
            metadata = result.metadata
            
            # 内容类型
            content_type = metadata.get('content_type', 'unknown')
            facets['content_types'][content_type] = facets['content_types'].get(content_type, 0) + 1
            
            # 语言
            language = metadata.get('language', 'unknown')
            facets['languages'][language] = facets['languages'].get(language, 0) + 1
            
            # 分类
            category = metadata.get('category', 'uncategorized')
            facets['categories'][category] = facets['categories'].get(category, 0) + 1
        
        return facets

class ElasticsearchKeywordSearch:
    """Elasticsearch关键词搜索引擎（完整实现占位符）"""
    
    def __init__(self, host: str = "localhost", port: int = 9200):
        """
        初始化Elasticsearch搜索
        
        Args:
            host: Elasticsearch主机
            port: Elasticsearch端口
        """
        self.host = host
        self.port = port
        self.client = None
        self._connect()
    
    def _connect(self):
        """连接到Elasticsearch"""
        try:
            # 这里应该实际连接到Elasticsearch
            # 由于我们已经有Docker环境，这部分可以后续完善
            logger.info(f"连接到Elasticsearch: {self.host}:{self.port}")
            self.client = "mock_es_client"  # 占位符
        except Exception as e:
            logger.error(f"Elasticsearch连接失败: {e}")
            self.client = None
    
    def search(self, query: str, index_name: str = "documents", 
               top_k: int = 10) -> SearchResponse:
        """
        在Elasticsearch中搜索
        
        Args:
            query: 查询字符串
            index_name: 索引名称
            top_k: 返回结果数量
            
        Returns:
            搜索响应
        """
        # 这里应该实现真正的Elasticsearch搜索逻辑
        logger.warning("Elasticsearch搜索功能尚未完全实现，返回模拟结果")
        
        # 返回模拟结果
        return SearchResponse(
            query=query,
            results=[],
            total_hits=0,
            search_time=0,
            search_type="elasticsearch",
            facets={}
        )

# 导出主要类
__all__ = ['SimpleKeywordSearch', 'ElasticsearchKeywordSearch', 'KeywordHit']