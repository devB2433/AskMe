import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from unstructured.partition.auto import partition
import requests
from PIL import Image
import io
from app.config import settings


@dataclass
class ProcessingConfig:
    """文档处理配置"""
    chunk_size: int = 400  # 减小分块大小，提高检索精度
    chunk_overlap: int = 100  # 增加重叠，提高检索召回率
    enable_metadata: bool = True
    enable_ocr: bool = True
    max_file_size: int = 100 * 1024 * 1024  # 100MB


class FormatHandler(ABC):
    """文档格式处理器抽象基类"""
    
    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """判断是否能处理该文件"""
        pass
    
    @abstractmethod
    def handle(self, file_path: str) -> List[Dict[str, Any]]:
        """处理文件并返回文档元素列表"""
        pass


class PDFHandler(FormatHandler):
    """PDF文档处理器"""
    
    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.pdf'
    
    def handle(self, file_path: str) -> List[Dict[str, Any]]:
        """处理PDF文件"""
        try:
            elements = partition(filename=file_path)
            return self._elements_to_dict(elements)
        except Exception as e:
            print(f"PDF处理失败: {e}")
            return [{"type": "error", "content": f"PDF处理失败: {str(e)}"}]
    
    def _elements_to_dict(self, elements) -> List[Dict[str, Any]]:
        """将unstructured元素转换为字典格式"""
        result = []
        for i, element in enumerate(elements):
            result.append({
                "type": getattr(element, 'category', 'text'),
                "content": str(element),
                "position": i,
                "metadata": {
                    "page_number": getattr(element, 'page_number', None),
                    "coordinates": getattr(element, 'coordinates', None)
                }
            })
        return result


class OfficeHandler(FormatHandler):
    """Office文档处理器 (Word, Excel, PowerPoint)"""
    
    SUPPORTED_EXTENSIONS = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}
    
    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def handle(self, file_path: str) -> List[Dict[str, Any]]:
        """处理Office文档"""
        try:
            elements = partition(filename=file_path)
            return self._elements_to_dict(elements)
        except Exception as e:
            print(f"Office文档处理失败: {e}")
            return [{"type": "error", "content": f"Office文档处理失败: {str(e)}"}]
    
    def _elements_to_dict(self, elements) -> List[Dict[str, Any]]:
        result = []
        for i, element in enumerate(elements):
            result.append({
                "type": getattr(element, 'category', 'text'),
                "content": str(element),
                "position": i,
                "metadata": {
                    "element_type": type(element).__name__,
                    "page_number": getattr(element, 'page_number', None)
                }
            })
        return result


class ImageHandler(FormatHandler):
    """图片处理器 (集成GLM-OCR)"""
    
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def handle(self, file_path: str) -> List[Dict[str, Any]]:
        """处理图片文件"""
        if not settings.OCR_ENABLED:
            return [{
                "type": "image",
                "content": f"[图片文件: {os.path.basename(file_path)}]",
                "position": 0,
                "metadata": {"ocr_enabled": False}
            }]
        
        # 调用GLM-OCR服务
        if settings.GLM_OCR_API_URL:
            try:
                ocr_result = self._call_glm_ocr(file_path)
                if ocr_result:
                    return [{
                        "type": "text",
                        "content": ocr_result.get('text', ''),
                        "position": 0,
                        "metadata": {
                            "ocr_confidence": ocr_result.get('confidence', 0),
                            "ocr_source": "glm-ocr"
                        }
                    }]
            except Exception as e:
                print(f"GLM-OCR调用失败: {e}")
        
        # 如果OCR失败，返回占位符
        return [{
            "type": "image",
            "content": f"[无法OCR处理的图片: {os.path.basename(file_path)}]",
            "position": 0,
            "metadata": {"ocr_failed": True}
        }]
    
    def _call_glm_ocr(self, file_path: str) -> Optional[Dict]:
        """调用GLM-OCR API"""
        try:
            with open(file_path, 'rb') as image_file:
                files = {'image': image_file}
                response = requests.post(settings.GLM_OCR_API_URL, files=files, timeout=30)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"GLM-OCR请求异常: {e}")
        return None


class TextHandler(FormatHandler):
    """文本文件处理器 (txt, md等)"""
    
    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.markdown', '.rst', '.csv'}
    
    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def handle(self, file_path: str) -> List[Dict[str, Any]]:
        """处理文本文件"""
        try:
            # 尝试使用unstructured处理
            elements = partition(filename=file_path)
            if elements:
                return self._elements_to_dict(elements)
            
            # 如果unstructured无法处理，则直接读取文本
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return [{
                "type": "text",
                "content": content,
                "position": 0,
                "metadata": {"source_encoding": "utf-8"}
            }]
        except Exception as e:
            print(f"文本文件处理失败: {e}")
            return [{"type": "error", "content": f"文本文件处理失败: {str(e)}"}]
    
    def _elements_to_dict(self, elements) -> List[Dict[str, Any]]:
        result = []
        for i, element in enumerate(elements):
            result.append({
                "type": getattr(element, 'category', 'text'),
                "content": str(element),
                "position": i,
                "metadata": {"element_type": type(element).__name__}
            })
        return result


class DocumentProcessor:
    """文档处理器 - 处理各种格式的文档"""
    
    def __init__(self):
        # 初始化各种格式处理器
        self.handlers = [
            PDFHandler(),
            OfficeHandler(),
            ImageHandler(),
            TextHandler()
        ]
        
        # 支持的格式映射（用于快速查找）
        self.extension_map = {}
        for handler in self.handlers:
            if hasattr(handler, 'SUPPORTED_EXTENSIONS'):
                for ext in handler.SUPPORTED_EXTENSIONS:
                    self.extension_map[ext] = handler
    
    def process_document(self, file_path: str, filename: str = None) -> List[Dict[str, Any]]:
        """处理单个文档"""
        if not filename:
            filename = os.path.basename(file_path)
            
        file_extension = Path(filename).suffix.lower()
        
        # 查找合适的处理器
        handler = self._find_handler(file_path, file_extension)
        
        if not handler:
            raise ValueError(f"不支持的文件格式: {file_extension}")
        
        # 使用处理器处理文档
        elements = handler.handle(file_path)
        
        # 转换为标准化的文本块
        chunks = self._elements_to_chunks(elements, filename)
        
        return chunks
    
    def _find_handler(self, file_path: str, extension: str) -> Optional[FormatHandler]:
        """根据文件扩展名查找处理器"""
        # 首先检查扩展名映射
        if extension in self.extension_map:
            return self.extension_map[extension]
        
        # 如果没有找到，遍历所有处理器检查can_handle
        for handler in self.handlers:
            if handler.can_handle(file_path):
                return handler
        
        return None
    
    def _elements_to_chunks(self, elements: List[Dict[str, Any]], filename: str) -> List[Dict[str, Any]]:
        """将文档元素转换为文本块"""
        chunks = []
        current_chunk = ""
        chunk_size = 1000  # 字符数限制
        chunk_index = 0
        
        for element in elements:
            content = element.get('content', '')
            element_type = element.get('type', 'unknown')
            metadata = element.get('metadata', {})
            
            # 跳过错误元素
            if element_type == 'error':
                print(f"警告: {content}")
                continue
            
            # 对于大段落，直接分块
            if len(content) > chunk_size and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "metadata": {
                        "source": filename,
                        "element_type": "combined",
                        "chunk_size": len(current_chunk)
                    }
                })
                chunk_index += 1
                current_chunk = content
            elif len(current_chunk) + len(content) > chunk_size and current_chunk:
                # 当前块加上新内容会超限时，保存当前块
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "metadata": {
                        "source": filename,
                        "element_type": "combined",
                        "chunk_size": len(current_chunk)
                    }
                })
                chunk_index += 1
                current_chunk = content
            else:
                # 合并到当前块
                if current_chunk:
                    current_chunk += "\n" + content
                else:
                    current_chunk = content
        
        # 添加最后一个块
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "metadata": {
                    "source": filename,
                    "element_type": "final",
                    "chunk_size": len(current_chunk)
                }
            })
        
        return chunks
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的文件格式列表"""
        formats = set()
        for handler in self.handlers:
            if hasattr(handler, 'SUPPORTED_EXTENSIONS'):
                formats.update(handler.SUPPORTED_EXTENSIONS)
        return sorted(list(formats))
    
    def validate_file(self, file_path: str) -> bool:
        """验证文件是否可以处理"""
        try:
            if not os.path.exists(file_path):
                return False
            
            if not os.path.isfile(file_path):
                return False
            
            extension = Path(file_path).suffix.lower()
            handler = self._find_handler(file_path, extension)
            
            return handler is not None
        
        except Exception:
            return False
    
    async def process_document_async(self, document_id: int):
        """异步处理文档"""
        # 这里应该从数据库获取文档信息
        # 为简化演示，假设已经获取到文档路径
        pass
