"""向量搜索引擎模块"""
import numpy as np
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime
import sys
import os

# 添加项目路径
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_path)

# 使用绝对导入
from services.embedding_encoder import EmbeddingEncoder, EncoderManager
from services.milvus_integration import MilvusClient, VectorStorageManager
from services.query_processor import QueryProcessor, ParsedQuery, QueryType

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """搜索结果数据类"""
    id: Union[int, str]
    document_id: str
    chunk_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    source: str  # 搜索来源 ('vector', 'keyword', 'hybrid')
    rank: int

@dataclass
class SearchResponse:
    """搜索响应数据类"""
    query: str
    results: List[SearchResult]
    total_hits: int
    search_time: float
    search_type: str
    facets: Dict[str, Any]

class SimilarityMetric(Enum):
    """相似度度量枚举"""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"

class VectorSearchEngine:
    """向量搜索引擎"""
    
    def __init__(self, encoder_manager: EncoderManager, 
                 vector_storage: VectorStorageManager,
                 query_processor: QueryProcessor = None):
        """
        初始化向量搜索引擎
        
        Args:
            encoder_manager: 编码器管理器
            vector_storage: 向量存储管理器
            query_processor: 查询处理器（可选）
        """
        self.encoder_manager = encoder_manager
        self.vector_storage = vector_storage
        self.query_processor = query_processor or QueryProcessor()
        
        # 默认搜索参数
        self.default_top_k = 10
        self.default_similarity_threshold = 0.5
        self.default_metric = SimilarityMetric.COSINE
    
    def search(self, query: str, 
               collection_name: str = None,
               top_k: int = None,
               similarity_threshold: float = None,
               filters: Dict[str, Any] = None,
               return_metadata: bool = True) -> SearchResponse:
        """
        执行向量搜索
        
        Args:
            query: 查询字符串
            collection_name: 集合名称
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值
            filters: 过滤条件
            return_metadata: 是否返回元数据
            
        Returns:
            搜索响应对象
        """
        start_time = datetime.now()
        
        if top_k is None:
            top_k = self.default_top_k
        if similarity_threshold is None:
            similarity_threshold = self.default_similarity_threshold
        
        try:
            # 1. 查询处理
            parsed_query, errors = self.query_processor.process_query(query)
            if errors:
                logger.warning(f"查询处理警告: {errors}")
            
            # 2. 文本编码
            query_vector = self._encode_query(query)
            
            # 3. 向量搜索
            raw_results = self.vector_storage.search_similar_documents(
                query_embedding=query_vector,
                top_k=top_k * 2,  # 扩大搜索范围用于后续过滤
                collection_name=collection_name,
                filter_conditions=filters
            )
            
            # 4. 结果过滤和排序
            filtered_results = self._filter_and_rank_results(
                raw_results, 
                similarity_threshold,
                parsed_query
            )
            
            # 5. 截取top_k结果
            final_results = filtered_results[:top_k]
            
            # 6. 格式化结果
            search_results = self._format_results(final_results, "vector")
            
            # 7. 计算搜索时间
            search_time = (datetime.now() - start_time).total_seconds()
            
            return SearchResponse(
                query=query,
                results=search_results,
                total_hits=len(filtered_results),
                search_time=search_time,
                search_type="vector",
                facets=self._extract_facets(final_results)
            )
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            raise
    
    def batch_search(self, queries: List[str], 
                    collection_name: str = None,
                    top_k: int = None) -> List[SearchResponse]:
        """
        批量向量搜索
        
        Args:
            queries: 查询字符串列表
            collection_name: 集合名称
            top_k: 每个查询返回结果数量
            
        Returns:
            搜索响应列表
        """
        results = []
        for query in queries:
            try:
                response = self.search(query, collection_name, top_k)
                results.append(response)
            except Exception as e:
                logger.error(f"批量搜索中单个查询失败: {query}, 错误: {e}")
                # 添加空结果而不是跳过
                results.append(SearchResponse(
                    query=query,
                    results=[],
                    total_hits=0,
                    search_time=0,
                    search_type="vector",
                    facets={}
                ))
        
        return results
    
    def _encode_query(self, query: str) -> List[float]:
        """编码查询文本"""
        try:
            # 使用默认编码器
            encoder = self.encoder_manager.get_encoder("default")
            query_vector = encoder.encode_single(query)
            return query_vector.tolist()
        except Exception as e:
            logger.error(f"查询编码失败: {e}")
            raise
    
    def _filter_and_rank_results(self, raw_results: List[Dict], 
                               similarity_threshold: float,
                               parsed_query: ParsedQuery) -> List[Dict]:
        """过滤和排序搜索结果"""
        filtered_results = []
        
        for result in raw_results:
            # 相似度阈值过滤
            if result.get('score', 0) < similarity_threshold:
                continue
            
            # 应用查询特定的过滤规则
            if self._apply_query_filters(result, parsed_query):
                filtered_results.append(result)
        
        # 按相似度排序
        filtered_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return filtered_results
    
    def _apply_query_filters(self, result: Dict, parsed_query: ParsedQuery) -> bool:
        """应用查询特定过滤规则"""
        metadata = result.get('metadata', {})
        
        # 应用boost因子
        if parsed_query.boost_factors:
            for field, boost in parsed_query.boost_factors.items():
                if field in metadata:
                    result['score'] *= boost
        
        # 应用分页过滤（如果需要）
        # 这里可以根据需要添加更多过滤逻辑
        
        return True
    
    def _format_results(self, results: List[Dict], source: str) -> List[SearchResult]:
        """格式化搜索结果"""
        formatted_results = []
        
        for i, result in enumerate(results):
            search_result = SearchResult(
                id=result.get('id'),
                document_id=result.get('document_id', ''),
                chunk_id=result.get('chunk_id', ''),
                content=result.get('content', ''),
                score=float(result.get('score', 0)),
                metadata=result.get('metadata', {}),
                source=source,
                rank=i + 1
            )
            formatted_results.append(search_result)
        
        return formatted_results
    
    def _extract_facets(self, results: List[Dict]) -> Dict[str, Any]:
        """提取分面信息"""
        facets = {
            'content_types': {},
            'languages': {},
            'categories': {},
            'score_distribution': {}
        }
        
        for result in results:
            metadata = result.get('metadata', {})
            
            # 内容类型分布
            content_type = metadata.get('content_type', 'unknown')
            facets['content_types'][content_type] = facets['content_types'].get(content_type, 0) + 1
            
            # 语言分布
            language = metadata.get('language', 'unknown')
            facets['languages'][language] = facets['languages'].get(language, 0) + 1
            
            # 分类分布
            category = metadata.get('category', 'uncategorized')
            facets['categories'][category] = facets['categories'].get(category, 0) + 1
        
        # 分数分布
        scores = [float(result.get('score', 0)) for result in results]
        if scores:
            facets['score_distribution'] = {
                'min': min(scores),
                'max': max(scores),
                'avg': sum(scores) / len(scores),
                'median': sorted(scores)[len(scores)//2] if scores else 0
            }
        
        return facets

class HybridSearchEngine:
    """混合搜索引擎（向量+关键词）"""
    
    def __init__(self, vector_engine: VectorSearchEngine,
                 keyword_engine: Any = None):  # keyword_engine将在后续实现
        """
        初始化混合搜索引擎
        
        Args:
            vector_engine: 向量搜索引擎
            keyword_engine: 关键词搜索引擎
        """
        self.vector_engine = vector_engine
        self.keyword_engine = keyword_engine
    
    def search(self, query: str,
               collection_name: str = None,
               top_k: int = None,
               vector_weight: float = 0.7,
               keyword_weight: float = 0.3) -> SearchResponse:
        """
        执行混合搜索
        
        Args:
            query: 查询字符串
            collection_name: 集合名称
            top_k: 返回结果数量
            vector_weight: 向量搜索权重
            keyword_weight: 关键词搜索权重
            
        Returns:
            混合搜索响应
        """
        start_time = datetime.now()
        
        if top_k is None:
            top_k = self.vector_engine.default_top_k
        
        try:
            # 1. 向量搜索
            vector_response = self.vector_engine.search(
                query=query,
                collection_name=collection_name,
                top_k=top_k * 2,  # 扩大搜索范围
                similarity_threshold=0.1  # 降低阈值以获得更多候选
            )
            
            # 2. 关键词搜索（如果可用）
            keyword_results = []
            if self.keyword_engine:
                try:
                    keyword_response = self.keyword_engine.search(
                        query=query,
                        collection_name=collection_name,
                        top_k=top_k * 2
                    )
                    keyword_results = keyword_response.results
                except Exception as e:
                    logger.warning(f"关键词搜索失败: {e}")
            
            # 3. 结果融合
            fused_results = self._fuse_results(
                vector_results=vector_response.results,
                keyword_results=keyword_results,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
                top_k=top_k
            )
            
            # 4. 计算总搜索时间
            search_time = (datetime.now() - start_time).total_seconds()
            
            return SearchResponse(
                query=query,
                results=fused_results,
                total_hits=len(fused_results),
                search_time=search_time,
                search_type="hybrid",
                facets=self._combine_facets(vector_response.facets, {})  # TODO: 添加keyword facets
            )
            
        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            raise
    
    def _fuse_results(self, vector_results: List[SearchResult],
                     keyword_results: List[SearchResult],
                     vector_weight: float,
                     keyword_weight: float,
                     top_k: int) -> List[SearchResult]:
        """融合向量和关键词搜索结果"""
        # 结果融合策略：基于排名的位置加权融合
        fused_scores = {}
        result_lookup = {}
        
        # 处理向量搜索结果
        for i, result in enumerate(vector_results):
            doc_key = f"{result.document_id}_{result.chunk_id}"
            vector_score = result.score * vector_weight
            position_score = (len(vector_results) - i) / len(vector_results)  # 位置分数
            fused_scores[doc_key] = vector_score + position_score
            result_lookup[doc_key] = result
        
        # 处理关键词搜索结果
        for i, result in enumerate(keyword_results):
            doc_key = f"{result.document_id}_{result.chunk_id}"
            keyword_score = result.score * keyword_weight
            position_score = (len(keyword_results) - i) / len(keyword_results)
            
            if doc_key in fused_scores:
                # 如果文档已在向量结果中，累加分数
                fused_scores[doc_key] += keyword_score + position_score
            else:
                fused_scores[doc_key] = keyword_score + position_score
                result_lookup[doc_key] = result
        
        # 按融合分数排序
        sorted_docs = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 构建最终结果
        final_results = []
        for i, (doc_key, score) in enumerate(sorted_docs[:top_k]):
            result = result_lookup[doc_key]
            result.score = score  # 更新为融合分数
            result.rank = i + 1
            result.source = "hybrid"
            final_results.append(result)
        
        return final_results
    
    def _combine_facets(self, vector_facets: Dict, keyword_facets: Dict) -> Dict:
        """合并分面信息"""
        combined = vector_facets.copy()
        
        # 合并各类分面统计
        for facet_type in ['content_types', 'languages', 'categories']:
            if facet_type in keyword_facets:
                for key, count in keyword_facets[facet_type].items():
                    if key in combined.get(facet_type, {}):
                        combined[facet_type][key] += count
                    else:
                        combined[facet_type][key] = count
        
        return combined

# 导出主要类
__all__ = ['SearchResult', 'SearchResponse', 'SimilarityMetric', 'VectorSearchEngine', 'HybridSearchEngine']