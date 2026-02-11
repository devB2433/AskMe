"""结果排序和融合算法模块"""
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

from services.vector_search import SearchResult

logger = logging.getLogger(__name__)

class FusionStrategy(Enum):
    """融合策略枚举"""
    RECIPROCAL_RANK = "reciprocal_rank"
    SCORE_FUSION = "score_fusion"
    POSITION_WEIGHTED = "position_weighted"
    LEARNING_TO_RANK = "learning_to_rank"

@dataclass
class RankedResult:
    """排序后的结果"""
    search_result: SearchResult
    final_score: float
    rank_explanation: Dict[str, Any]

class ResultRanker:
    """结果排序器"""
    
    def __init__(self):
        """初始化结果排序器"""
        self.default_weights = {
            'similarity': 0.4,
            'recency': 0.2,
            'popularity': 0.2,
            'quality': 0.2
        }
    
    def rank_results(self, results: List[SearchResult], 
                    weights: Dict[str, float] = None,
                    context: Dict[str, Any] = None) -> List[RankedResult]:
        """
        对搜索结果进行排序
        
        Args:
            results: 搜索结果列表
            weights: 排序权重
            context: 上下文信息
            
        Returns:
            排序后的结果列表
        """
        if not results:
            return []
        
        if weights is None:
            weights = self.default_weights
        
        # 计算每个结果的综合分数
        scored_results = []
        for result in results:
            score_components = self._calculate_score_components(result, context)
            final_score = self._compute_final_score(score_components, weights)
            
            ranked_result = RankedResult(
                search_result=result,
                final_score=final_score,
                rank_explanation=score_components
            )
            scored_results.append(ranked_result)
        
        # 按最终分数排序
        scored_results.sort(key=lambda x: x.final_score, reverse=True)
        
        # 更新排名
        for i, ranked_result in enumerate(scored_results):
            ranked_result.search_result.rank = i + 1
        
        return scored_results
    
    def _calculate_score_components(self, result: SearchResult, 
                                  context: Dict[str, Any] = None) -> Dict[str, float]:
        """计算分数组成部分"""
        components = {}
        
        # 1. 相似度分数（基础分数）
        components['similarity'] = result.score
        
        # 2. 时间新鲜度分数
        components['recency'] = self._calculate_recency_score(result, context)
        
        # 3. 流行度分数
        components['popularity'] = self._calculate_popularity_score(result, context)
        
        # 4. 质量分数
        components['quality'] = self._calculate_quality_score(result, context)
        
        return components
    
    def _calculate_recency_score(self, result: SearchResult, 
                               context: Dict[str, Any] = None) -> float:
        """计算时间新鲜度分数"""
        metadata = result.metadata
        created_at = metadata.get('created_at', 0)
        
        if created_at:
            # 假设created_at是Unix时间戳
            current_time = datetime.now().timestamp()
            age_seconds = current_time - created_at
            
            # 使用指数衰减函数
            # 新文档得分更高，老文档得分递减
            decay_rate = 1e-7  # 调整这个值来控制衰减速度
            recency_score = np.exp(-decay_rate * age_seconds)
            
            return float(recency_score)
        else:
            # 如果没有时间信息，返回中等分数
            return 0.5
    
    def _calculate_popularity_score(self, result: SearchResult, 
                                  context: Dict[str, Any] = None) -> float:
        """计算流行度分数"""
        metadata = result.metadata
        view_count = metadata.get('view_count', 0)
        like_count = metadata.get('like_count', 0)
        share_count = metadata.get('share_count', 0)
        
        # 简单的流行度计算
        popularity = view_count + like_count * 2 + share_count * 3
        
        # 归一化到0-1范围
        if popularity > 0:
            # 使用对数缩放避免极端值
            normalized_popularity = np.log1p(popularity) / 10  # 调整分母控制范围
            return min(1.0, normalized_popularity)
        else:
            return 0.1  # 默认较低分数
    
    def _calculate_quality_score(self, result: SearchResult, 
                               context: Dict[str, Any] = None) -> float:
        """计算质量分数"""
        metadata = result.metadata
        quality_indicators = []
        
        # 内容长度质量
        content_length = len(result.content)
        if content_length > 50:  # 最少50字符
            length_score = min(1.0, content_length / 1000)  # 1000字符为满分
            quality_indicators.append(length_score)
        
        # 语言质量
        language = metadata.get('language', 'unknown')
        if language in ['zh', 'en']:  # 支持的主要语言
            quality_indicators.append(0.8)
        else:
            quality_indicators.append(0.3)
        
        # 内容类型质量
        content_type = metadata.get('content_type', 'general')
        type_weights = {
            'technical': 1.0,
            'academic': 0.9,
            'business': 0.7,
            'general': 0.5
        }
        quality_indicators.append(type_weights.get(content_type, 0.5))
        
        # 可读性质量
        readability = metadata.get('readability_score', 0.5)
        quality_indicators.append(readability)
        
        # 返回平均质量分数
        return sum(quality_indicators) / len(quality_indicators) if quality_indicators else 0.5
    
    def _compute_final_score(self, components: Dict[str, float], 
                           weights: Dict[str, float]) -> float:
        """计算最终综合分数"""
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for component_name, weight in weights.items():
            if component_name in components:
                weighted_sum += components[component_name] * weight
                weight_sum += weight
        
        # 归一化
        if weight_sum > 0:
            return weighted_sum / weight_sum
        else:
            return components.get('similarity', 0.0)

class ResultFusion:
    """结果融合器"""
    
    def __init__(self):
        """初始化结果融合器"""
        pass
    
    def fuse_multiple_sources(self, source_results: Dict[str, List[SearchResult]],
                             strategy: FusionStrategy = FusionStrategy.RECIPROCAL_RANK,
                             weights: Dict[str, float] = None) -> List[SearchResult]:
        """
        融合来自多个来源的结果
        
        Args:
            source_results: 来源结果字典 {source_name: [results]}
            strategy: 融合策略
            weights: 来源权重
            
        Returns:
            融合后的结果列表
        """
        if not source_results:
            return []
        
        if weights is None:
            # 默认平均权重
            weights = {source: 1.0 for source in source_results.keys()}
        
        # 标准化权重
        total_weight = sum(weights.values())
        normalized_weights = {k: v/total_weight for k, v in weights.items()}
        
        if strategy == FusionStrategy.RECIPROCAL_RANK:
            return self._reciprocal_rank_fusion(source_results, normalized_weights)
        elif strategy == FusionStrategy.SCORE_FUSION:
            return self._score_fusion(source_results, normalized_weights)
        elif strategy == FusionStrategy.POSITION_WEIGHTED:
            return self._position_weighted_fusion(source_results, normalized_weights)
        else:
            # 默认使用倒数排名融合
            return self._reciprocal_rank_fusion(source_results, normalized_weights)
    
    def _reciprocal_rank_fusion(self, source_results: Dict[str, List[SearchResult]],
                              weights: Dict[str, float]) -> List[SearchResult]:
        """倒数排名融合算法"""
        # 收集所有唯一文档
        all_documents = {}
        
        for source_name, results in source_results.items():
            weight = weights.get(source_name, 1.0)
            
            for rank, result in enumerate(results, 1):
                doc_key = f"{result.document_id}_{result.chunk_id}"
                
                if doc_key not in all_documents:
                    all_documents[doc_key] = {
                        'result': result,
                        'scores': [],
                        'sources': []
                    }
                
                # 计算倒数排名分数
                reciprocal_rank = 1.0 / rank
                weighted_score = reciprocal_rank * weight
                
                all_documents[doc_key]['scores'].append(weighted_score)
                all_documents[doc_key]['sources'].append(source_name)
        
        # 计算融合分数并排序
        fused_results = []
        for doc_info in all_documents.values():
            # 融合分数：所有来源分数的和
            fusion_score = sum(doc_info['scores'])
            
            # 更新结果的分数和来源信息
            result = doc_info['result']
            result.score = fusion_score
            result.source = '|'.join(doc_info['sources'])  # 多个来源用|分隔
            
            fused_results.append(result)
        
        # 按融合分数排序
        fused_results.sort(key=lambda x: x.score, reverse=True)
        
        # 更新排名
        for i, result in enumerate(fused_results):
            result.rank = i + 1
        
        return fused_results
    
    def _score_fusion(self, source_results: Dict[str, List[SearchResult]],
                     weights: Dict[str, float]) -> List[SearchResult]:
        """分数融合算法"""
        all_documents = {}
        
        for source_name, results in source_results.items():
            weight = weights.get(source_name, 1.0)
            
            for result in results:
                doc_key = f"{result.document_id}_{result.chunk_id}"
                
                if doc_key not in all_documents:
                    # 标准化分数到0-1范围
                    normalized_score = self._normalize_score(result.score, source_name)
                    weighted_score = normalized_score * weight
                    
                    all_documents[doc_key] = {
                        'result': result,
                        'total_score': weighted_score,
                        'source_count': 1,
                        'sources': [source_name]
                    }
                else:
                    # 累加分数
                    normalized_score = self._normalize_score(result.score, source_name)
                    weighted_score = normalized_score * weight
                    
                    all_documents[doc_key]['total_score'] += weighted_score
                    all_documents[doc_key]['source_count'] += 1
                    all_documents[doc_key]['sources'].append(source_name)
        
        # 构建结果列表
        fused_results = []
        for doc_info in all_documents.values():
            result = doc_info['result']
            # 平均分数
            result.score = doc_info['total_score'] / doc_info['source_count']
            result.source = '|'.join(doc_info['sources'])
            fused_results.append(result)
        
        # 排序
        fused_results.sort(key=lambda x: x.score, reverse=True)
        
        # 更新排名
        for i, result in enumerate(fused_results):
            result.rank = i + 1
        
        return fused_results
    
    def _position_weighted_fusion(self, source_results: Dict[str, List[SearchResult]],
                                weights: Dict[str, float]) -> List[SearchResult]:
        """位置加权融合算法"""
        all_documents = {}
        
        for source_name, results in source_results.items():
            weight = weights.get(source_name, 1.0)
            total_results = len(results)
            
            for rank, result in enumerate(results, 1):
                doc_key = f"{result.document_id}_{result.chunk_id}"
                
                # 位置权重：排名越靠前权重越高
                position_weight = (total_results - rank + 1) / total_results
                final_weight = weight * position_weight
                
                if doc_key not in all_documents:
                    all_documents[doc_key] = {
                        'result': result,
                        'weighted_scores': [result.score * final_weight],
                        'sources': [source_name]
                    }
                else:
                    all_documents[doc_key]['weighted_scores'].append(result.score * final_weight)
                    all_documents[doc_key]['sources'].append(source_name)
        
        # 融合结果
        fused_results = []
        for doc_info in all_documents.values():
            result = doc_info['result']
            # 加权分数求和
            result.score = sum(doc_info['weighted_scores'])
            result.source = '|'.join(doc_info['sources'])
            fused_results.append(result)
        
        # 排序和排名
        fused_results.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(fused_results):
            result.rank = i + 1
        
        return fused_results
    
    def _normalize_score(self, score: float, source_name: str) -> float:
        """标准化分数到0-1范围（根据不同来源调整）"""
        # 这里可以根据不同搜索源的特点进行个性化标准化
        # 目前使用简单的min-max标准化
        
        if source_name == 'vector':
            # 向量搜索分数通常在0-1范围
            return max(0.0, min(1.0, score))
        elif source_name == 'keyword':
            # 关键词搜索分数可能需要不同的处理
            return max(0.0, min(1.0, score / 10.0))  # 假设最大分数为10
        else:
            return max(0.0, min(1.0, score))

class DiversityEnhancer:
    """多样性增强器"""
    
    def __init__(self):
        """初始化多样性增强器"""
        pass
    
    def enhance_diversity(self, results: List[SearchResult], 
                         diversity_factor: float = 0.3) -> List[SearchResult]:
        """
        增强结果多样性
        
        Args:
            results: 排序结果
            diversity_factor: 多样性因子 (0-1)
            
        Returns:
            增强多样性的结果列表
        """
        if not results or len(results) <= 1:
            return results
        
        diversified_results = []
        selected_categories = set()
        
        for result in results:
            category = self._get_result_category(result)
            
            # 如果类别已选择，降低分数
            if category in selected_categories:
                result.score *= (1 - diversity_factor)
            else:
                selected_categories.add(category)
            
            diversified_results.append(result)
        
        # 重新排序
        diversified_results.sort(key=lambda x: x.score, reverse=True)
        
        # 更新排名
        for i, result in enumerate(diversified_results):
            result.rank = i + 1
        
        return diversified_results
    
    def _get_result_category(self, result: SearchResult) -> str:
        """获取结果的类别"""
        metadata = result.metadata
        # 可以基于不同类型的信息确定类别
        category = metadata.get('category', 'uncategorized')
        content_type = metadata.get('content_type', 'general')
        return f"{category}_{content_type}"

# 导出主要类
__all__ = ['FusionStrategy', 'RankedResult', 'ResultRanker', 'ResultFusion', 'DiversityEnhancer']