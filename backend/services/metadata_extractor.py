"""元数据提取器模块"""
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import mimetypes
from dataclasses import dataclass

@dataclass
class DocumentMetadata:
    """文档元数据数据类"""
    # 基础信息
    filename: str
    file_size: int
    file_type: str
    mime_type: str
    
    # 时间信息
    created_time: datetime
    modified_time: datetime
    
    # 内容统计
    character_count: int
    word_count: int
    line_count: int
    paragraph_count: int
    
    # 技术信息
    encoding: str
    checksum: str
    
    # 分析信息
    language: str
    content_type: str
    readability_score: float
    complexity_score: float
    
    # 自定义元数据
    custom_metadata: Dict[str, Any]

class MetadataExtractor:
    """文档元数据提取器"""
    
    def __init__(self):
        # 注册文件类型对应的MIME类型
        mimetypes.init()
        
        # 语言检测支持的语言
        self.supported_languages = ['zh', 'en', 'ja', 'ko']
        
        # 内容类型分类
        self.content_types = {
            'technical': ['技术', '开发', '编程', '代码', 'algorithm', 'programming'],
            'business': ['商业', '市场', '销售', 'finance', 'business'],
            'academic': ['学术', '研究', '论文', 'research', 'study'],
            'general': ['一般', '通用', '日常', 'general', 'daily']
        }
    
    def extract_metadata(self, file_path: str, content: str = None) -> DocumentMetadata:
        """提取文档元数据"""
        path = Path(file_path)
        
        # 获取文件基础信息
        stat = path.stat()
        filename = path.name
        file_size = stat.st_size
        file_type = path.suffix.lower()
        mime_type = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        
        # 获取时间信息
        created_time = datetime.fromtimestamp(stat.st_ctime)
        modified_time = datetime.fromtimestamp(stat.st_mtime)
        
        # 如果提供了内容，进行详细分析
        if content is not None:
            content_stats = self._analyze_content(content)
        else:
            # 读取文件内容进行分析
            content = self._read_file_content(file_path)
            content_stats = self._analyze_content(content) if content else {
                'character_count': 0,
                'word_count': 0,
                'line_count': 0,
                'paragraph_count': 0,
                'language': 'unknown',
                'content_type': 'unknown',
                'readability_score': 0.0,
                'complexity_score': 0.0
            }
        
        # 计算文件校验和
        checksum = self._calculate_checksum(file_path)
        
        # 确定编码
        encoding = self._detect_encoding(file_path)
        
        return DocumentMetadata(
            filename=filename,
            file_size=file_size,
            file_type=file_type,
            mime_type=mime_type,
            created_time=created_time,
            modified_time=modified_time,
            character_count=content_stats['character_count'],
            word_count=content_stats['word_count'],
            line_count=content_stats['line_count'],
            paragraph_count=content_stats['paragraph_count'],
            encoding=encoding,
            checksum=checksum,
            language=content_stats['language'],
            content_type=content_stats['content_type'],
            readability_score=content_stats['readability_score'],
            complexity_score=content_stats['complexity_score'],
            custom_metadata={}
        )
    
    def _read_file_content(self, file_path: str) -> Optional[str]:
        """读取文件内容"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                return None
        
        return None
    
    def _analyze_content(self, content: str) -> Dict[str, Any]:
        """分析内容特征"""
        # 基础统计
        character_count = len(content)
        word_count = len(content.split())
        line_count = len(content.splitlines())
        paragraph_count = len([p for p in content.split('\n\n') if p.strip()])
        
        # 语言检测
        language = self._detect_language(content)
        
        # 内容类型分类
        content_type = self._classify_content_type(content)
        
        # 可读性评分
        readability_score = self._calculate_readability(content)
        
        # 复杂度评分
        complexity_score = self._calculate_complexity(content)
        
        return {
            'character_count': character_count,
            'word_count': word_count,
            'line_count': line_count,
            'paragraph_count': paragraph_count,
            'language': language,
            'content_type': content_type,
            'readability_score': readability_score,
            'complexity_score': complexity_score
        }
    
    def _detect_language(self, content: str) -> str:
        """检测内容语言"""
        # 简单的语言检测逻辑
        chinese_chars = len([c for c in content if '\u4e00' <= c <= '\u9fff'])
        english_chars = len([c for c in content if c.isalpha() and ord(c) < 128])
        japanese_chars = len([c for c in content if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff'])
        
        total_chars = chinese_chars + english_chars + japanese_chars
        
        if total_chars == 0:
            return 'unknown'
        
        if chinese_chars / total_chars > 0.5:
            return 'zh'
        elif english_chars / total_chars > 0.5:
            return 'en'
        elif japanese_chars / total_chars > 0.3:
            return 'ja'
        else:
            return 'mixed'
    
    def _classify_content_type(self, content: str) -> str:
        """分类内容类型"""
        content_lower = content.lower()
        
        # 检查关键词匹配
        for content_type, keywords in self.content_types.items():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    return content_type
        
        return 'general'
    
    def _calculate_readability(self, content: str) -> float:
        """计算可读性评分 (0-1)"""
        if not content:
            return 0.0
        
        # 简单的可读性计算
        sentences = len([s for s in content.replace('。', '.').replace('！', '!').replace('？', '?').split('.') if s.strip()])
        words = len(content.split())
        syllables = self._count_syllables(content)
        
        # 中文使用字符复杂度，英文使用音节复杂度
        if self._detect_language(content) == 'zh':
            # 中文可读性基于字符复杂度
            avg_word_length = sum(len(word) for word in content.split()) / max(1, len(content.split()))
            readability = max(0.0, min(1.0, 1.0 - (avg_word_length - 2) / 10))
        else:
            # 英文可读性公式 (简化版 Flesch Reading Ease)
            if sentences > 0 and words > 0:
                score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
                readability = max(0.0, min(1.0, score / 100))
            else:
                readability = 0.5
        
        return readability
    
    def _calculate_complexity(self, content: str) -> float:
        """计算内容复杂度评分 (0-1)"""
        if not content:
            return 0.0
        
        # 复杂度因素
        factors = []
        
        # 词汇多样性
        words = content.split()
        unique_words = len(set(words))
        vocabulary_ratio = unique_words / max(1, len(words))
        factors.append(vocabulary_ratio)
        
        # 句子长度变化
        sentences = [s.strip() for s in content.replace('。', '.').split('.') if s.strip()]
        if sentences:
            avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
            length_variance = sum((len(s.split()) - avg_length) ** 2 for s in sentences) / len(sentences)
            complexity_factor = min(1.0, length_variance / 100)
            factors.append(complexity_factor)
        
        # 特殊字符比例
        special_chars = len([c for c in content if not c.isalnum() and not c.isspace()])
        special_ratio = special_chars / max(1, len(content))
        factors.append(min(1.0, special_ratio * 5))
        
        return sum(factors) / len(factors) if factors else 0.5
    
    def _count_syllables(self, content: str) -> int:
        """计算音节数（英文）"""
        # 简化的音节计算
        vowels = "aeiouAEIOU"
        count = 0
        prev_was_vowel = False
        
        for char in content:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                count += 1
            prev_was_vowel = is_vowel
        
        return max(1, count)
    
    def _calculate_checksum(self, file_path: str) -> str:
        """计算文件SHA256校验和"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return "unable_to_calculate"
    
    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        # 尝试常见的编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1000)  # 读取部分文件测试
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                break
        
        return 'unknown'
    
    def extract_custom_metadata(self, file_path: str, custom_extractors: List[callable] = None) -> Dict[str, Any]:
        """提取自定义元数据"""
        custom_metadata = {}
        
        if custom_extractors:
            for extractor in custom_extractors:
                try:
                    result = extractor(file_path)
                    if isinstance(result, dict):
                        custom_metadata.update(result)
                except Exception as e:
                    print(f"自定义元数据提取器执行失败: {e}")
        
        return custom_metadata
    
    def batch_extract_metadata(self, file_paths: List[str]) -> List[DocumentMetadata]:
        """批量提取元数据"""
        results = []
        
        for file_path in file_paths:
            try:
                metadata = self.extract_metadata(file_path)
                results.append(metadata)
            except Exception as e:
                print(f"提取 {file_path} 的元数据失败: {e}")
        
        return results
    
    def get_file_statistics(self, file_paths: List[str]) -> Dict[str, Any]:
        """获取文件集合统计信息"""
        if not file_paths:
            return {}
        
        metadata_list = self.batch_extract_metadata(file_paths)
        
        stats = {
            'total_files': len(metadata_list),
            'total_size': sum(m.file_size for m in metadata_list),
            'file_types': {},
            'languages': {},
            'content_types': {},
            'average_readability': sum(m.readability_score for m in metadata_list) / len(metadata_list),
            'average_complexity': sum(m.complexity_score for m in metadata_list) / len(metadata_list)
        }
        
        # 统计文件类型分布
        for metadata in metadata_list:
            file_type = metadata.file_type
            stats['file_types'][file_type] = stats['file_types'].get(file_type, 0) + 1
            
            language = metadata.language
            stats['languages'][language] = stats['languages'].get(language, 0) + 1
            
            content_type = metadata.content_type
            stats['content_types'][content_type] = stats['content_types'].get(content_type, 0) + 1
        
        return stats

# 导出主要类
__all__ = ['DocumentMetadata', 'MetadataExtractor']