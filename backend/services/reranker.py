"""重排序模块 - 使用Cross-Encoder对召回结果进行精细排序"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class Reranker:
    """Cross-Encoder重排序器"""
    
    DEFAULT_MODEL = "BAAI/bge-reranker-large"  # 中文重排序模型
    
    def __init__(self, model_name: str = None):
        """
        初始化重排序器
        
        Args:
            model_name: 重排序模型名称
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """加载重排序模型"""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch
            
            logger.info(f"正在加载重排序模型: {self.model_name}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.eval()
            
            # 选择设备
            if torch.cuda.is_available():
                self.device = "cuda"
                self.model = self.model.to("cuda")
            else:
                self.device = "cpu"
            
            logger.info(f"重排序模型加载成功，设备: {self.device}")
            
        except Exception as e:
            logger.error(f"加载重排序模型失败: {e}")
            raise
    
    def rerank(
        self, 
        query: str, 
        documents: List[Dict[str, Any]], 
        content_key: str = "content",
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        对文档进行重排序
        
        Args:
            query: 查询文本
            documents: 文档列表，每个文档需包含content字段
            content_key: 内容字段的键名
            top_k: 返回的文档数量
            
        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []
        
        if not query or not query.strip():
            logger.warning("查询为空，返回原始文档")
            return documents[:top_k]
        
        try:
            import torch
            
            # 准备查询-文档对
            pairs = []
            valid_docs = []
            for doc in documents:
                content = doc.get(content_key, "")
                if content and content.strip():
                    pairs.append([query, content[:512]])  # 限制长度
                    valid_docs.append(doc)
            
            if not pairs:
                return documents[:top_k]
            
            # 批量编码
            with torch.no_grad():
                inputs = self.tokenizer(
                    pairs, 
                    padding=True, 
                    truncation=True, 
                    max_length=512,
                    return_tensors="pt"
                )
                
                if self.device == "cuda":
                    inputs = {k: v.to("cuda") for k, v in inputs.items()}
                
                scores = self.model(**inputs).logits.squeeze(-1)
                scores = torch.sigmoid(scores).cpu().numpy()
            
            # 按分数排序
            scored_docs = list(zip(valid_docs, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            # 构建结果
            results = []
            for i, (doc, score) in enumerate(scored_docs[:top_k]):
                result = doc.copy()
                result["rerank_score"] = float(score)
                result["final_score"] = float(score)  # 使用重排序分数作为最终分数
                results.append(result)
            
            logger.info(f"重排序完成: {len(documents)} -> {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return documents[:top_k]
    
    def compute_scores(self, query: str, contents: List[str]) -> List[float]:
        """
        计算查询与文档内容的相关性分数
        
        Args:
            query: 查询文本
            contents: 文档内容列表
            
        Returns:
            相关性分数列表
        """
        if not contents:
            return []
        
        try:
            import torch
            
            pairs = [[query, c[:512]] for c in contents if c and c.strip()]
            
            if not pairs:
                return [0.0] * len(contents)
            
            with torch.no_grad():
                inputs = self.tokenizer(
                    pairs, 
                    padding=True, 
                    truncation=True, 
                    max_length=512,
                    return_tensors="pt"
                )
                
                if self.device == "cuda":
                    inputs = {k: v.to("cuda") for k, v in inputs.items()}
                
                scores = self.model(**inputs).logits.squeeze(-1)
                scores = torch.sigmoid(scores).cpu().numpy()
            
            return [float(s) for s in scores]
            
        except Exception as e:
            logger.error(f"计算分数失败: {e}")
            return [0.0] * len(contents)


class QueryEnhancer:
    """查询增强器"""
    
    def __init__(self, encoder=None):
        """
        初始化查询增强器
        
        Args:
            encoder: 嵌入编码器实例（可选，用于语义扩展）
        """
        self.encoder = encoder
        # 同义词词典（可根据业务扩展）
        self.synonyms = {
            "问题": ["疑问", "难题", "故障"],
            "方法": ["方式", "方案", "办法", "途径"],
            "配置": ["设置", "设定", "参数"],
            "错误": ["异常", "报错", "故障"],
            "文档": ["文件", "资料", "材料"],
            "系统": ["平台", "应用", "软件"],
            "用户": ["使用者", "成员", "人员"],
            "数据": ["信息", "资料", "内容"],
        }
    
    def enhance_query(self, query: str, num_variations: int = 3) -> List[str]:
        """
        生成查询变体
        
        Args:
            query: 原始查询
            num_variations: 变体数量
            
        Returns:
            查询变体列表（包含原始查询）
        """
        variations = [query]  # 始终包含原始查询
        
        # 1. 同义词扩展
        synonym_query = self._synonym_expansion(query)
        if synonym_query and synonym_query != query:
            variations.append(synonym_query)
        
        # 2. 关键词提取（简单实现：提取有意义的词）
        keywords = self._extract_keywords(query)
        if keywords:
            keyword_query = " ".join(keywords)
            if keyword_query != query:
                variations.append(keyword_query)
        
        # 3. 移除停用词
        clean_query = self._remove_stopwords(query)
        if clean_query and clean_query != query:
            variations.append(clean_query)
        
        # 去重并限制数量
        unique_variations = list(dict.fromkeys(variations))
        return unique_variations[:num_variations + 1]
    
    def _synonym_expansion(self, query: str) -> str:
        """同义词扩展"""
        expanded = query
        for word, synonyms in self.synonyms.items():
            if word in query:
                # 使用第一个同义词替换
                expanded = expanded.replace(word, synonyms[0], 1)
                break
        return expanded
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 简单实现：移除常见无意义词
        stopwords = {"的", "是", "在", "有", "和", "了", "与", "对", "这", "那", "如何", "怎么", "什么", "为什么"}
        words = list(query)  # 简单按字符分割
        keywords = [w for w in words if w not in stopwords and len(w.strip()) > 0]
        return keywords[:5]  # 最多5个关键词
    
    def _remove_stopwords(self, query: str) -> str:
        """移除停用词"""
        stopwords = {"的", "是", "在", "有", "和", "了", "与", "对", "这", "那"}
        result = query
        for sw in stopwords:
            result = result.replace(sw, "")
        return result.strip()
    
    def get_multi_query_embeddings(self, query: str, encoder) -> Tuple[List[str], List[np.ndarray]]:
        """
        获取多查询的嵌入向量
        
        Args:
            query: 原始查询
            encoder: 编码器实例
            
        Returns:
            (查询变体列表, 嵌入向量列表)
        """
        variations = self.enhance_query(query)
        embeddings = []
        
        for var in variations:
            try:
                emb = encoder.encode_single(var)
                embeddings.append(emb)
            except Exception as e:
                logger.warning(f"编码查询变体失败: {var}, {e}")
        
        return variations, embeddings


class HybridSearchResult:
    """混合搜索结果融合"""
    
    @staticmethod
    def rrf_fusion(
        vector_results: List[Dict[str, Any]], 
        keyword_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        RRF (Reciprocal Rank Fusion) 融合
        
        Args:
            vector_results: 向量检索结果
            keyword_results: 关键词检索结果
            k: RRF参数，默认60
            
        Returns:
            融合后的结果列表
        """
        # 构建文档ID到分数的映射
        doc_scores = {}
        
        # 处理向量检索结果
        for rank, result in enumerate(vector_results):
            doc_id = result.get("document_id") or result.get("chunk_id")
            if doc_id:
                score = 1.0 / (k + rank + 1)
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"result": result, "score": 0}
                doc_scores[doc_id]["score"] += score
                doc_scores[doc_id]["result"].update(result)
        
        # 处理关键词检索结果
        for rank, result in enumerate(keyword_results):
            doc_id = result.get("document_id") or result.get("chunk_id")
            if doc_id:
                score = 1.0 / (k + rank + 1)
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"result": result, "score": 0}
                doc_scores[doc_id]["score"] += score
        
        # 按融合分数排序
        sorted_results = sorted(
            doc_scores.values(), 
            key=lambda x: x["score"], 
            reverse=True
        )
        
        # 更新最终分数
        for item in sorted_results:
            item["result"]["fusion_score"] = item["score"]
        
        return [item["result"] for item in sorted_results]
    
    @staticmethod
    def weighted_fusion(
        vector_results: List[Dict[str, Any]], 
        keyword_results: List[Dict[str, Any]],
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        加权融合
        
        Args:
            vector_results: 向量检索结果
            keyword_results: 关键词检索结果
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            
        Returns:
            融合后的结果列表
        """
        doc_scores = {}
        
        # 处理向量检索结果
        for result in vector_results:
            doc_id = result.get("document_id") or result.get("chunk_id")
            if doc_id:
                score = result.get("score", 0.5) * vector_weight
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"result": result, "score": 0}
                doc_scores[doc_id]["score"] += score
        
        # 处理关键词检索结果
        for result in keyword_results:
            doc_id = result.get("document_id") or result.get("chunk_id")
            if doc_id:
                score = result.get("score", 0.5) * keyword_weight
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"result": result, "score": 0}
                doc_scores[doc_id]["score"] += score
        
        # 排序
        sorted_results = sorted(
            doc_scores.values(), 
            key=lambda x: x["score"], 
            reverse=True
        )
        
        for item in sorted_results:
            item["result"]["final_score"] = item["score"]
        
        return [item["result"] for item in sorted_results]


# 全局实例（懒加载）
_reranker_instance = None
_query_enhancer_instance = None


def get_reranker() -> Reranker:
    """获取重排序器实例（懒加载）"""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker()
    return _reranker_instance


def get_query_enhancer() -> QueryEnhancer:
    """获取查询增强器实例"""
    global _query_enhancer_instance
    if _query_enhancer_instance is None:
        _query_enhancer_instance = QueryEnhancer()
    return _query_enhancer_instance


# 导出
__all__ = [
    'Reranker', 
    'QueryEnhancer', 
    'HybridSearchResult',
    'get_reranker', 
    'get_query_enhancer'
]
