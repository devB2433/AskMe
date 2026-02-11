"""嵌入编码器模块"""
import numpy as np
from typing import List, Union, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
import torch
from pathlib import Path
import logging

# 配置日志
logger = logging.getLogger(__name__)

class EmbeddingEncoder:
    """文本嵌入编码器"""
    
    # 支持中文的嵌入模型
    DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"  # 中文模型，512维，效果更好
    
    def __init__(self, model_name: str = None):
        """
        初始化嵌入编码器
        
        Args:
            model_name: 预训练模型名称
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.model = None
        self.device = self._get_device()
        self._load_model()
    
    def _get_device(self) -> str:
        """获取计算设备"""
        if torch.cuda.is_available():
            device = "cuda"
            logger.info(f"使用GPU设备: {torch.cuda.get_device_name(0)}")
        elif torch.backends.mps.is_available():
            device = "mps"
            logger.info("使用MPS设备")
        else:
            device = "cpu"
            logger.info("使用CPU设备")
        return device
    
    def _load_model(self):
        """加载预训练模型"""
        try:
            logger.info(f"正在加载嵌入模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"模型加载成功，维度: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        编码单个文本
        
        Args:
            text: 输入文本
            normalize: 是否归一化向量
            
        Returns:
            嵌入向量
        """
        if not text or not text.strip():
            raise ValueError("输入文本不能为空")
        
        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=normalize,
                show_progress_bar=False
            )
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"文本编码失败: {e}")
            raise
    
    def encode_batch(self, texts: List[str], batch_size: int = 32, 
                    normalize: bool = True, show_progress: bool = True) -> np.ndarray:
        """
        批量编码文本
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
            normalize: 是否归一化向量
            show_progress: 是否显示进度条
            
        Returns:
            嵌入向量数组
        """
        if not texts:
            return np.array([])
        
        # 过滤空文本
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            raise ValueError("没有有效的输入文本")
        
        try:
            embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress
            )
            return embeddings.astype(np.float32)
        except Exception as e:
            logger.error(f"批量编码失败: {e}")
            raise
    
    def encode_documents(self, documents: List[Dict[str, Any]], 
                        content_field: str = "content") -> List[Dict[str, Any]]:
        """
        编码文档列表
        
        Args:
            documents: 文档列表
            content_field: 内容字段名
            
        Returns:
            包含嵌入向量的文档列表
        """
        if not documents:
            return []
        
        # 提取文本内容
        texts = [doc.get(content_field, "") for doc in documents]
        
        # 批量编码
        embeddings = self.encode_batch(texts)
        
        # 将嵌入向量添加到文档中
        result_docs = []
        for i, doc in enumerate(documents):
            doc_copy = doc.copy()
            doc_copy["embedding"] = embeddings[i].tolist()  # 转换为列表便于JSON序列化
            doc_copy["embedding_dim"] = len(embeddings[i])
            result_docs.append(doc_copy)
        
        return result_docs
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            余弦相似度 (0-1)
        """
        emb1 = self.encode_single(text1)
        emb2 = self.encode_single(text2)
        return float(np.dot(emb1, emb2))
    
    def batch_similarity(self, texts: List[str]) -> np.ndarray:
        """
        计算文本列表的相似度矩阵
        
        Args:
            texts: 文本列表
            
        Returns:
            相似度矩阵
        """
        embeddings = self.encode_batch(texts)
        # 计算余弦相似度矩阵
        norm_embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        similarity_matrix = np.dot(norm_embeddings, norm_embeddings.T)
        return similarity_matrix
    
    def get_embedding_dimension(self) -> int:
        """获取嵌入维度"""
        return self.model.get_sentence_embedding_dimension()
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "embedding_dimension": self.get_embedding_dimension(),
            "max_sequence_length": self.model.max_seq_length
        }

class MultiModalEncoder:
    """多模态编码器（支持文本和图像）"""
    
    def __init__(self, text_encoder: EmbeddingEncoder):
        """
        初始化多模态编码器
        
        Args:
            text_encoder: 文本编码器实例
        """
        self.text_encoder = text_encoder
        self.image_encoder = None  # 图像编码器将在需要时初始化
    
    def encode_multimodal(self, content: Union[str, List[str]], 
                         content_type: str = "text") -> np.ndarray:
        """
        编码多模态内容
        
        Args:
            content: 内容（文本或图像路径）
            content_type: 内容类型 ("text" 或 "image")
            
        Returns:
            嵌入向量
        """
        if content_type == "text":
            if isinstance(content, str):
                return self.text_encoder.encode_single(content)
            elif isinstance(content, list):
                # 处理文本列表
                texts = [item for item in content if isinstance(item, str)]
                if texts:
                    # 对文本列表进行平均池化
                    embeddings = self.text_encoder.encode_batch(texts)
                    return np.mean(embeddings, axis=0)
                else:
                    raise ValueError("文本列表中没有有效内容")
            else:
                raise ValueError("文本内容必须是字符串或字符串列表")
        
        elif content_type == "image":
            return self._encode_image(content)
        
        else:
            raise ValueError(f"不支持的内容类型: {content_type}")
    
    def _encode_image(self, image_path: str) -> np.ndarray:
        """
        编码图像内容（占位符实现）
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            图像嵌入向量
        """
        # TODO: 实现图像编码功能
        # 这里可以集成CLIP或其他图像编码模型
        logger.warning("图像编码功能尚未实现，返回零向量")
        dim = self.text_encoder.get_embedding_dimension()
        return np.zeros(dim, dtype=np.float32)

class EncoderManager:
    """编码器管理器"""
    
    def __init__(self):
        self.encoders = {}
        self.default_encoder = None
        self._initialize_default_encoder()
    
    def _initialize_default_encoder(self):
        """初始化默认编码器"""
        try:
            self.default_encoder = EmbeddingEncoder()
            self.encoders["default"] = self.default_encoder
            logger.info("默认编码器初始化成功")
        except Exception as e:
            logger.error(f"默认编码器初始化失败: {e}")
            raise
    
    def register_encoder(self, name: str, encoder: EmbeddingEncoder):
        """注册编码器"""
        self.encoders[name] = encoder
        logger.info(f"编码器 '{name}' 注册成功")
    
    def get_encoder(self, name: str = "default") -> EmbeddingEncoder:
        """获取编码器"""
        if name not in self.encoders:
            raise ValueError(f"未找到编码器: {name}")
        return self.encoders[name]
    
    def encode_content(self, content: Union[str, List[str]], 
                      encoder_name: str = "default") -> Union[np.ndarray, List[np.ndarray]]:
        """使用指定编码器编码内容"""
        encoder = self.get_encoder(encoder_name)
        
        if isinstance(content, str):
            return encoder.encode_single(content)
        elif isinstance(content, list):
            return encoder.encode_batch(content)
        else:
            raise ValueError("内容必须是字符串或字符串列表")
    
    def get_available_encoders(self) -> List[str]:
        """获取可用编码器列表"""
        return list(self.encoders.keys())
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        encoders_info = {}
        for name, encoder in self.encoders.items():
            encoders_info[name] = encoder.get_model_info()
        
        return {
            "available_encoders": self.get_available_encoders(),
            "default_encoder": "default",
            "encoders_info": encoders_info
        }

# 导出主要类
__all__ = ['EmbeddingEncoder', 'MultiModalEncoder', 'EncoderManager']