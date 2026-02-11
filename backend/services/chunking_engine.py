"""智能分块引擎模块"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Chunk:
    """文本块数据类"""
    content: str
    chunk_id: str
    metadata: Dict[str, Any]
    position: int
    parent_document: str

class ChunkingStrategy:
    """分块策略抽象基类"""
    
    def chunk(self, content: str, **kwargs) -> List[Chunk]:
        """执行分块策略"""
        raise NotImplementedError

class FixedSizeChunker(ChunkingStrategy):
    """固定大小分块器"""
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk(self, content: str, **kwargs) -> List[Chunk]:
        """按固定大小分块"""
        chunks = []
        content_length = len(content)
        
        if content_length <= self.chunk_size:
            # 内容小于块大小，直接作为一个块
            chunks.append(Chunk(
                content=content,
                chunk_id=f"chunk_0",
                metadata={"strategy": "fixed_size", "original_length": content_length},
                position=0,
                parent_document=kwargs.get("document_id", "unknown")
            ))
            return chunks
        
        start = 0
        position = 0
        
        while start < content_length:
            # 计算当前块的结束位置
            end = min(start + self.chunk_size, content_length)
            
            # 提取块内容
            chunk_content = content[start:end]
            
            # 创建块
            chunk = Chunk(
                content=chunk_content,
                chunk_id=f"chunk_{position}",
                metadata={
                    "strategy": "fixed_size",
                    "start_pos": start,
                    "end_pos": end,
                    "overlap": self.overlap if start > 0 else 0,
                    "original_length": content_length
                },
                position=position,
                parent_document=kwargs.get("document_id", "unknown")
            )
            
            chunks.append(chunk)
            position += 1
            
            # 计算下一个块的起始位置（考虑重叠）
            start = end - self.overlap if end < content_length else end
        
        return chunks

class SemanticChunker(ChunkingStrategy):
    """语义分块器 - 基于句子和段落边界"""
    
    def __init__(self, max_chunk_size: int = 1500, min_chunk_size: int = 300):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        # 句子分割的正则表达式
        self.sentence_pattern = re.compile(r'[.!?。！？]+')
        # 段落分割的正则表达式
        self.paragraph_pattern = re.compile(r'\n\s*\n')
    
    def chunk(self, content: str, **kwargs) -> List[Chunk]:
        """基于语义的智能分块"""
        chunks = []
        
        # 首先按段落分割
        paragraphs = self._split_paragraphs(content)
        
        current_chunk_content = ""
        current_position = 0
        chunk_index = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # 如果当前块加上段落后超过最大大小
            if len(current_chunk_content) + len(paragraph) > self.max_chunk_size:
                # 如果当前块不为空，保存它
                if current_chunk_content:
                    chunks.append(self._create_chunk(
                        current_chunk_content, chunk_index, kwargs.get("document_id", "unknown")
                    ))
                    chunk_index += 1
                    current_chunk_content = ""
                
                # 如果单个段落就很大，需要进一步分割
                if len(paragraph) > self.max_chunk_size:
                    sub_chunks = self._chunk_large_paragraph(paragraph, chunk_index, kwargs)
                    chunks.extend(sub_chunks)
                    chunk_index += len(sub_chunks)
                else:
                    current_chunk_content = paragraph
            else:
                # 合并到当前块
                if current_chunk_content:
                    current_chunk_content += "\n\n" + paragraph
                else:
                    current_chunk_content = paragraph
        
        # 处理最后一个块
        if current_chunk_content:
            # 如果最后一个块太小，尝试与前面的块合并
            if (len(current_chunk_content) < self.min_chunk_size and chunks and 
                len(chunks[-1].content) + len(current_chunk_content) <= self.max_chunk_size):
                # 合并到最后一个块
                chunks[-1].content += "\n\n" + current_chunk_content
                chunks[-1].metadata["merged"] = True
            else:
                chunks.append(self._create_chunk(
                    current_chunk_content, chunk_index, kwargs.get("document_id", "unknown")
                ))
        
        return chunks
    
    def _split_paragraphs(self, content: str) -> List[str]:
        """分割段落"""
        # 先按双换行分割段落
        paragraphs = self.paragraph_pattern.split(content)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _chunk_large_paragraph(self, paragraph: str, start_index: int, kwargs: Dict) -> List[Chunk]:
        """处理大型段落的进一步分割"""
        chunks = []
        sentences = self._split_sentences(paragraph)
        
        current_chunk_content = ""
        chunk_index = start_index
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 如果当前块加上句子后超过最大大小
            if len(current_chunk_content) + len(sentence) > self.max_chunk_size:
                if current_chunk_content:
                    chunks.append(self._create_chunk(
                        current_chunk_content, chunk_index, kwargs.get("document_id", "unknown")
                    ))
                    chunk_index += 1
                    current_chunk_content = sentence
                else:
                    # 句子本身就很长，强制分割
                    chunks.append(self._create_chunk(
                        sentence[:self.max_chunk_size], chunk_index, kwargs.get("document_id", "unknown")
                    ))
                    chunk_index += 1
                    remaining = sentence[self.max_chunk_size:]
                    if remaining:
                        current_chunk_content = remaining
            else:
                if current_chunk_content:
                    current_chunk_content += " " + sentence
                else:
                    current_chunk_content = sentence
        
        # 处理剩余内容
        if current_chunk_content:
            chunks.append(self._create_chunk(
                current_chunk_content, chunk_index, kwargs.get("document_id", "unknown")
            ))
        
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 使用正则表达式分割句子
        sentences = self.sentence_pattern.split(text)
        # 重新组合句子和分隔符
        result = []
        for i in range(len(sentences) - 1):
            result.append(sentences[i] + '.')
        if sentences[-1]:  # 最后一部分（如果没有以句号结尾）
            result.append(sentences[-1])
        return [s.strip() for s in result if s.strip()]
    
    def _create_chunk(self, content: str, index: int, document_id: str) -> Chunk:
        """创建块对象"""
        return Chunk(
            content=content,
            chunk_id=f"chunk_{index}",
            metadata={
                "strategy": "semantic",
                "chunk_length": len(content),
                "sentence_count": len(self._split_sentences(content)),
                "paragraph_boundaries": self._detect_boundaries(content)
            },
            position=index,
            parent_document=document_id
        )
    
    def _detect_boundaries(self, content: str) -> Dict[str, Any]:
        """检测内容边界特征"""
        return {
            "starts_with_title": bool(re.match(r'^#+\s+\w+', content.strip())),
            "contains_list": bool(re.search(r'^\s*[-*+]\s+|\d+\.\s+', content, re.MULTILINE)),
            "ends_with_sentence": bool(self.sentence_pattern.search(content[-10:])),
            "paragraph_count": len([p for p in content.split('\n\n') if p.strip()])
        }

class HierarchicalChunker(ChunkingStrategy):
    """层次化分块器 - 结合多种策略"""
    
    def __init__(self):
        self.fixed_chunker = FixedSizeChunker(chunk_size=800, overlap=50)
        self.semantic_chunker = SemanticChunker(max_chunk_size=1200, min_chunk_size=400)
    
    def chunk(self, content: str, **kwargs) -> List[Chunk]:
        """层次化分块策略"""
        # 首先尝试语义分块
        semantic_chunks = self.semantic_chunker.chunk(content, **kwargs)
        
        # 检查分块质量
        quality_score = self._evaluate_chunk_quality(semantic_chunks)
        
        if quality_score >= 0.7:  # 语义分块质量较好
            return semantic_chunks
        else:
            # 使用固定大小分块作为备选
            return self.fixed_chunker.chunk(content, **kwargs)
    
    def _evaluate_chunk_quality(self, chunks: List[Chunk]) -> float:
        """评估分块质量"""
        if not chunks:
            return 0.0
        
        scores = []
        
        for chunk in chunks:
            content = chunk.content
            metadata = chunk.metadata
            
            # 长度适中得分
            length_score = self._length_score(len(content))
            
            # 语义完整性得分
            semantic_score = self._semantic_score(content, metadata)
            
            # 边界合理性得分
            boundary_score = self._boundary_score(metadata)
            
            # 综合得分
            chunk_score = (length_score * 0.4 + semantic_score * 0.4 + boundary_score * 0.2)
            scores.append(chunk_score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _length_score(self, length: int) -> float:
        """长度评分"""
        optimal_min, optimal_max = 500, 1500
        if optimal_min <= length <= optimal_max:
            return 1.0
        elif length < optimal_min:
            return length / optimal_min
        else:
            return max(0.1, optimal_max / length)
    
    def _semantic_score(self, content: str, metadata: Dict) -> float:
        """语义完整性评分"""
        score = 0.5  # 基础分
        
        # 检查是否以完整句子结尾
        if metadata.get("ends_with_sentence", False):
            score += 0.3
        
        # 检查段落数量
        paragraph_count = metadata.get("paragraph_count", 0)
        if 1 <= paragraph_count <= 5:
            score += 0.2
        
        return min(1.0, score)
    
    def _boundary_score(self, metadata: Dict) -> float:
        """边界合理性评分"""
        if metadata.get("strategy") == "semantic":
            return 1.0
        return 0.5

class ChunkingEngine:
    """智能分块引擎主类"""
    
    def __init__(self):
        self.strategies = {
            "fixed": FixedSizeChunker(),
            "semantic": SemanticChunker(),
            "hierarchical": HierarchicalChunker()
        }
    
    def chunk_document(self, content: str, strategy: str = "hierarchical", 
                      **kwargs) -> List[Chunk]:
        """对文档内容进行分块"""
        if strategy not in self.strategies:
            raise ValueError(f"不支持的分块策略: {strategy}")
        
        chunker = self.strategies[strategy]
        return chunker.chunk(content, **kwargs)
    
    def chunk_multiple_documents(self, documents: List[Dict[str, Any]], 
                               strategy: str = "hierarchical") -> List[Chunk]:
        """批量处理多个文档"""
        all_chunks = []
        
        for doc in documents:
            content = doc.get("content", "")
            doc_id = doc.get("document_id", "unknown")
            
            if content:
                chunks = self.chunk_document(
                    content, 
                    strategy, 
                    document_id=doc_id
                )
                all_chunks.extend(chunks)
        
        return all_chunks
    
    def get_available_strategies(self) -> List[str]:
        """获取可用的分块策略"""
        return list(self.strategies.keys())
    
    def analyze_content_structure(self, content: str) -> Dict[str, Any]:
        """分析内容结构特征"""
        analysis = {
            "total_length": len(content),
            "character_count": len(content),
            "word_count": len(content.split()),
            "paragraph_count": len([p for p in content.split('\n\n') if p.strip()]),
            "sentence_count": len(re.findall(r'[.!?。！？]', content)),
            "recommended_strategy": "semantic"  # 默认推荐语义分块
        }
        
        # 根据内容特征推荐策略
        if analysis["paragraph_count"] < 3:
            analysis["recommended_strategy"] = "fixed"
        elif analysis["total_length"] > 5000:
            analysis["recommended_strategy"] = "hierarchical"
        
        return analysis

# 导出主要类
__all__ = ['Chunk', 'ChunkingEngine', 'FixedSizeChunker', 'SemanticChunker', 'HierarchicalChunker']