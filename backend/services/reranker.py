"""重排序模块 - 使用Cross-Encoder对召回结果进行精细排序（优化版）"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging
import threading
import time

logger = logging.getLogger(__name__)

class Reranker:
    """Cross-Encoder重排序器"""
    
    # 使用base模型，速度更快（约3倍），效果也不错
    DEFAULT_MODEL = "BAAI/bge-reranker-base"
    
    def __init__(self, model_name: str = None, lazy_load: bool = True):
        """
        初始化重排序器
        
        Args:
            model_name: 重排序模型名称
            lazy_load: 是否延迟加载模型
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        self._lock = threading.Lock()
        self._loaded = False
        
        if not lazy_load:
            self._ensure_model_loaded()
    
    def _ensure_model_loaded(self):
        """确保模型已加载（线程安全的懒加载）"""
        if self._loaded:
            return
        
        with self._lock:
            if self._loaded:
                return
            
            start_time = time.time()
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
                
                self._loaded = True
                load_time = time.time() - start_time
                logger.info(f"重排序模型加载成功，设备: {self.device}，耗时: {load_time:.2f}秒")
                
            except Exception as e:
                logger.error(f"加载重排序模型失败: {e}")
                raise
    
    def preload(self):
        """预加载模型（启动时调用）"""
        self._ensure_model_loaded()
        return self
    
    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self._loaded
    
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
        
        # 确保模型已加载
        self._ensure_model_loaded()
        
        try:
            import torch
            
            start_time = time.time()
            
            # 准备查询-文档对，缩短内容长度以加速推理
            pairs = []
            valid_docs = []
            for doc in documents:
                content = doc.get(content_key, "")
                if content and content.strip():
                    # 缩短到256字符，加快推理速度
                    pairs.append([query, content[:256]])
                    valid_docs.append(doc)
            
            if not pairs:
                return documents[:top_k]
            
            # 批量编码
            with torch.no_grad():
                inputs = self.tokenizer(
                    pairs, 
                    padding=True, 
                    truncation=True, 
                    max_length=256,  # 缩短以加速
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
                result["final_score"] = float(score)
                results.append(result)
            
            rerank_time = time.time() - start_time
            logger.info(f"重排序完成: {len(documents)} -> {len(results)} 个结果，耗时: {rerank_time:.3f}秒")
            return results
            
        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return documents[:top_k]


class QueryEnhancer:
    """查询增强器"""
    
    def __init__(self, encoder=None):
        """初始化查询增强器"""
        self.encoder = encoder
        # 同义词词典
        self.synonyms = {
            "问题": ["疑问", "难题", "故障"],
            "方法": ["方式", "方案", "办法", "途径"],
            "配置": ["设置", "设定", "参数"],
            "错误": ["异常", "报错", "故障"],
            "文档": ["文件", "资料", "材料"],
            "系统": ["平台", "应用", "软件"],
        }
    
    def enhance_query(self, query: str, num_variations: int = 2) -> List[str]:
        """生成查询变体（减少变体数量以加速）"""
        variations = [query]
        
        # 只做同义词扩展
        synonym_query = self._synonym_expansion(query)
        if synonym_query and synonym_query != query:
            variations.append(synonym_query)
        
        # 移除停用词
        clean_query = self._remove_stopwords(query)
        if clean_query and clean_query != query:
            variations.append(clean_query)
        
        return list(dict.fromkeys(variations))[:num_variations + 1]
    
    def _synonym_expansion(self, query: str) -> str:
        expanded = query
        for word, synonyms in self.synonyms.items():
            if word in query:
                expanded = expanded.replace(word, synonyms[0], 1)
                break
        return expanded
    
    def _remove_stopwords(self, query: str) -> str:
        stopwords = {"的", "是", "在", "有", "和", "了", "与", "对"}
        result = query
        for sw in stopwords:
            result = result.replace(sw, "")
        return result.strip()


class HybridSearchResult:
    """混合搜索结果融合"""
    
    @staticmethod
    def rrf_fusion(
        vector_results: List[Dict[str, Any]], 
        keyword_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """RRF融合"""
        doc_scores = {}
        
        for rank, result in enumerate(vector_results):
            doc_id = result.get("document_id") or result.get("chunk_id")
            if doc_id:
                score = 1.0 / (k + rank + 1)
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"result": result, "score": 0}
                doc_scores[doc_id]["score"] += score
        
        for rank, result in enumerate(keyword_results):
            doc_id = result.get("document_id") or result.get("chunk_id")
            if doc_id:
                score = 1.0 / (k + rank + 1)
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"result": result, "score": 0}
                doc_scores[doc_id]["score"] += score
        
        sorted_results = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
        for item in sorted_results:
            item["result"]["fusion_score"] = item["score"]
        
        return [item["result"] for item in sorted_results]


# 全局实例
_reranker_instance = None
_query_enhancer_instance = None
_reranker_lock = threading.Lock()


def get_reranker() -> Reranker:
    """获取重排序器实例（懒加载）"""
    global _reranker_instance
    if _reranker_instance is None:
        with _reranker_lock:
            if _reranker_instance is None:
                _reranker_instance = Reranker(lazy_load=True)
    return _reranker_instance


def preload_reranker() -> Reranker:
    """预加载重排序器（启动时调用）"""
    global _reranker_instance
    with _reranker_lock:
        if _reranker_instance is None:
            _reranker_instance = Reranker(lazy_load=False)
        else:
            _reranker_instance._ensure_model_loaded()
    return _reranker_instance


def get_query_enhancer() -> QueryEnhancer:
    """获取查询增强器实例"""
    global _query_enhancer_instance
    if _query_enhancer_instance is None:
        _query_enhancer_instance = QueryEnhancer()
    return _query_enhancer_instance


__all__ = [
    'Reranker', 
    'QueryEnhancer', 
    'HybridSearchResult',
    'get_reranker', 
    'get_query_enhancer',
    'preload_reranker'
]
