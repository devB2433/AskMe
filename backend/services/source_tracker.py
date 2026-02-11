"""来源跟踪功能模块"""
import hashlib
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class SourceType(Enum):
    """来源类型枚举"""
    DOCUMENT = "document"
    CHUNK = "chunk"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"

class CitationStyle(Enum):
    """引用样式枚举"""
    NUMERIC = "numeric"      # [1], [2], [3]
    AUTHOR_YEAR = "author_year"  # (Smith, 2023)
    FULL_CITATION = "full"   # 完整引用信息

@dataclass
class SourceReference:
    """来源引用数据类"""
    source_id: str
    source_type: SourceType
    document_id: str
    chunk_id: str
    content_snippet: str
    page_number: Optional[int]
    section_title: Optional[str]
    confidence_score: float
    relevance_score: float
    citation_format: str
    metadata: Dict[str, Any]

@dataclass
class Citation:
    """引用数据类"""
    citation_id: str
    source_references: List[SourceReference]
    cited_text: str
    citation_style: CitationStyle
    formatted_citation: str
    timestamp: datetime

class SourceTracker:
    """来源跟踪器"""
    
    def __init__(self, citation_style: CitationStyle = CitationStyle.NUMERIC):
        """
        初始化来源跟踪器
        
        Args:
            citation_style: 引用样式
        """
        self.citation_style = citation_style
        self.sources: Dict[str, SourceReference] = {}
        self.citations: List[Citation] = []
        self.citation_counter = 1
    
    def add_source(self, document_id: str, chunk_id: str, 
                  content: str, source_type: SourceType = SourceType.CHUNK,
                  metadata: Dict[str, Any] = None) -> str:
        """
        添加来源
        
        Args:
            document_id: 文档ID
            chunk_id: 块ID
            content: 内容
            source_type: 来源类型
            metadata: 元数据
            
        Returns:
            来源ID
        """
        if metadata is None:
            metadata = {}
        
        # 生成唯一的来源ID
        source_key = f"{document_id}_{chunk_id}"
        source_id = hashlib.md5(source_key.encode()).hexdigest()[:12]
        
        # 创建内容片段
        content_snippet = self._create_content_snippet(content)
        
        # 创建来源引用
        source_ref = SourceReference(
            source_id=source_id,
            source_type=source_type,
            document_id=document_id,
            chunk_id=chunk_id,
            content_snippet=content_snippet,
            page_number=metadata.get('page_number'),
            section_title=metadata.get('section_title'),
            confidence_score=metadata.get('confidence_score', 1.0),
            relevance_score=metadata.get('relevance_score', 1.0),
            citation_format="",  # 将在格式化时填充
            metadata=metadata
        )
        
        self.sources[source_id] = source_ref
        logger.debug(f"添加来源: {source_id} ({document_id})")
        
        return source_id
    
    def create_citation(self, cited_text: str, 
                       source_ids: List[str],
                       citation_style: CitationStyle = None) -> str:
        """
        创建引用
        
        Args:
            cited_text: 被引用的文本
            source_ids: 来源ID列表
            citation_style: 引用样式
            
        Returns:
            引用ID
        """
        if citation_style is None:
            citation_style = self.citation_style
        
        # 获取有效的来源引用
        valid_sources = []
        for source_id in source_ids:
            if source_id in self.sources:
                valid_sources.append(self.sources[source_id])
        
        if not valid_sources:
            logger.warning("没有有效的来源用于创建引用")
            return ""
        
        # 生成引用ID
        citation_id = f"cit_{self.citation_counter}"
        self.citation_counter += 1
        
        # 格式化引用
        formatted_citation = self._format_citation(valid_sources, citation_style)
        
        # 创建引用对象
        citation = Citation(
            citation_id=citation_id,
            source_references=valid_sources,
            cited_text=cited_text,
            citation_style=citation_style,
            formatted_citation=formatted_citation,
            timestamp=datetime.now()
        )
        
        self.citations.append(citation)
        
        # 更新来源的引用格式
        for source in valid_sources:
            source.citation_format = formatted_citation
        
        logger.debug(f"创建引用: {citation_id} (引用 {len(valid_sources)} 个来源)")
        return citation_id
    
    def get_source_by_id(self, source_id: str) -> Optional[SourceReference]:
        """根据ID获取来源"""
        return self.sources.get(source_id)
    
    def get_citation_by_id(self, citation_id: str) -> Optional[Citation]:
        """根据ID获取引用"""
        for citation in self.citations:
            if citation.citation_id == citation_id:
                return citation
        return None
    
    def get_sources_for_document(self, document_id: str) -> List[SourceReference]:
        """获取文档的所有来源"""
        return [source for source in self.sources.values() 
                if source.document_id == document_id]
    
    def get_citations_for_source(self, source_id: str) -> List[Citation]:
        """获取来源的所有引用"""
        return [citation for citation in self.citations 
                if any(src.source_id == source_id for src in citation.source_references)]
    
    def _create_content_snippet(self, content: str, max_length: int = 100) -> str:
        """创建内容片段"""
        if len(content) <= max_length:
            return content
        
        # 截取前半部分和后半部分
        half_length = max_length // 2 - 2  # 减去省略号长度
        start_part = content[:half_length]
        end_part = content[-half_length:] if len(content) > half_length else ""
        
        return f"{start_part}...{end_part}"
    
    def _format_citation(self, sources: List[SourceReference], 
                        style: CitationStyle) -> str:
        """格式化引用"""
        if style == CitationStyle.NUMERIC:
            # 数字引用格式: [1], [2], [3]
            numbers = [str(i + 1) for i in range(len(sources))]
            return f"[{','.join(numbers)}]"
        
        elif style == CitationStyle.AUTHOR_YEAR:
            # 作者年份格式: (Smith, 2023)
            citations = []
            for source in sources:
                author = source.metadata.get('author', 'Unknown')
                year = source.metadata.get('year', 'N.d.')
                citations.append(f"({author}, {year})")
            return "; ".join(citations)
        
        elif style == CitationStyle.FULL_CITATION:
            # 完整引用格式
            full_citations = []
            for i, source in enumerate(sources):
                citation_parts = [
                    f"[{i+1}]",
                    source.document_id,
                    source.section_title or "Untitled Section",
                    f"p.{source.page_number}" if source.page_number else ""
                ]
                full_citations.append(" ".join(filter(None, citation_parts)))
            return "\n".join(full_citations)
        
        else:
            return f"[{len(sources)} sources]"

class CitationFormatter:
    """引用格式化器"""
    
    def __init__(self):
        """初始化引用格式化器"""
        pass
    
    def format_answer_with_citations(self, answer: str, 
                                   citations: List[Citation]) -> str:
        """
        格式化带引用的答案
        
        Args:
            answer: 原始答案
            citations: 引用列表
            
        Returns:
            格式化后的答案
        """
        if not citations:
            return answer
        
        # 按引用ID排序
        sorted_citations = sorted(citations, key=lambda x: x.citation_id)
        
        # 在答案末尾添加引用列表
        formatted_answer = answer
        
        # 添加引用标识
        citation_references = []
        for citation in sorted_citations:
            # 在答案中添加引用标记
            if citation.cited_text in formatted_answer:
                # 简单的文本替换（实际应用中需要更精确的匹配）
                formatted_answer = formatted_answer.replace(
                    citation.cited_text,
                    f"{citation.cited_text}{citation.formatted_citation}"
                )
            
            # 收集引用参考
            for source in citation.source_references:
                ref_text = self._format_source_reference(source)
                citation_references.append(ref_text)
        
        # 添加引用列表
        if citation_references:
            reference_section = "\n\n参考资料:\n" + "\n".join(citation_references)
            formatted_answer += reference_section
        
        return formatted_answer
    
    def _format_source_reference(self, source: SourceReference) -> str:
        """格式化来源参考"""
        parts = [
            f"[{source.source_id[:6]}]",
            f"文档: {source.document_id}",
            f"片段: {source.chunk_id}",
            f"相关性: {source.relevance_score:.2f}"
        ]
        
        if source.page_number:
            parts.append(f"页码: {source.page_number}")
        
        if source.section_title:
            parts.append(f"章节: {source.section_title}")
        
        return " | ".join(parts)

class SourceValidator:
    """来源验证器"""
    
    def __init__(self):
        """初始化来源验证器"""
        pass
    
    def validate_source_accuracy(self, source: SourceReference, 
                               claimed_content: str) -> Dict[str, Any]:
        """
        验证来源准确性
        
        Args:
            source: 来源引用
            claimed_content: 声称的内容
            
        Returns:
            验证结果
        """
        validation_result = {
            "source_id": source.source_id,
            "accuracy_score": 0.0,
            "validation_issues": [],
            "confidence_level": "low"
        }
        
        # 内容匹配验证
        snippet_match = self._calculate_content_match(
            source.content_snippet, claimed_content
        )
        
        if snippet_match < 0.3:
            validation_result["validation_issues"].append("内容匹配度低")
        elif snippet_match < 0.6:
            validation_result["validation_issues"].append("内容部分匹配")
        
        # 置信度验证
        if source.confidence_score < 0.5:
            validation_result["validation_issues"].append("来源置信度较低")
        
        # 相关性验证
        if source.relevance_score < 0.3:
            validation_result["validation_issues"].append("相关性不足")
        
        # 计算综合准确度分数
        accuracy_components = [
            snippet_match,
            source.confidence_score,
            source.relevance_score
        ]
        validation_result["accuracy_score"] = sum(accuracy_components) / len(accuracy_components)
        
        # 确定置信级别
        if validation_result["accuracy_score"] >= 0.8:
            validation_result["confidence_level"] = "high"
        elif validation_result["accuracy_score"] >= 0.6:
            validation_result["confidence_level"] = "medium"
        else:
            validation_result["confidence_level"] = "low"
        
        return validation_result
    
    def _calculate_content_match(self, source_content: str, 
                               claimed_content: str) -> float:
        """计算内容匹配度"""
        # 简单的词汇重叠计算
        source_words = set(source_content.lower().split())
        claimed_words = set(claimed_content.lower().split())
        
        if not source_words or not claimed_words:
            return 0.0
        
        intersection = len(source_words.intersection(claimed_words))
        union = len(source_words.union(claimed_words))
        
        return intersection / union if union > 0 else 0.0
    
    def get_validation_report(self, sources: List[SourceReference], 
                            claimed_contents: List[str]) -> Dict[str, Any]:
        """获取验证报告"""
        if len(sources) != len(claimed_contents):
            raise ValueError("来源数量与声称内容数量不匹配")
        
        validations = []
        overall_accuracy = 0.0
        
        for source, claimed_content in zip(sources, claimed_contents):
            validation = self.validate_source_accuracy(source, claimed_content)
            validations.append(validation)
            overall_accuracy += validation["accuracy_score"]
        
        overall_accuracy /= len(sources) if sources else 1
        
        return {
            "total_sources": len(sources),
            "overall_accuracy": overall_accuracy,
            "validation_details": validations,
            "high_confidence_count": len([v for v in validations if v["confidence_level"] == "high"]),
            "medium_confidence_count": len([v for v in validations if v["confidence_level"] == "medium"]),
            "low_confidence_count": len([v for v in validations if v["confidence_level"] == "low"])
        }

# 导出主要类
__all__ = ['SourceType', 'CitationStyle', 'SourceReference', 'Citation', 
           'SourceTracker', 'CitationFormatter', 'SourceValidator']