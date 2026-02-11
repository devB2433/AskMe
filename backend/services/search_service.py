import numpy as np
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType
from elasticsearch import Elasticsearch
import json
from typing import List, Dict, Any
from app.config import settings

class VectorStore:
    """向量存储管理器"""
    
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.milvus_collection = None
        self.es_client = None
        self._init_connections()
    
    def _init_connections(self):
        """初始化数据库连接"""
        # 连接Milvus
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT
            )
            self._create_milvus_collection()
        except Exception as e:
            print(f"Milvus连接失败: {e}")
        
        # 连接Elasticsearch
        try:
            self.es_client = Elasticsearch([{
                'host': settings.ELASTICSEARCH_HOST,
                'port': settings.ELASTICSEARCH_PORT,
                'scheme': 'http'
            }])
        except Exception as e:
            print(f"Elasticsearch连接失败: {e}")
    
    def _create_milvus_collection(self):
        """创建Milvus集合"""
        collection_name = "document_chunks"
        
        # 检查集合是否已存在
        if collection_name in connections.list_collections():
            self.milvus_collection = Collection(collection_name)
            return
        
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.INT64),
            FieldSchema(name="document_id", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),  # all-MiniLM-L6-v2维度
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535)
        ]
        
        schema = CollectionSchema(fields, description="文档片段向量存储")
        self.milvus_collection = Collection(collection_name, schema)
        
        # 创建索引
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 128}
        }
        self.milvus_collection.create_index("embedding", index_params)
        self.milvus_collection.load()
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> List[int]:
        """添加文档到向量存储"""
        embeddings = []
        contents = []
        chunk_ids = []
        document_ids = []
        
        for doc in documents:
            # 生成向量
            embedding = self.model.encode(doc['content']).tolist()
            embeddings.append(embedding)
            contents.append(doc['content'])
            
            # 提取元数据
            metadata = doc.get('metadata', {})
            chunk_ids.append(metadata.get('chunk_id', 0))
            document_ids.append(metadata.get('document_id', 0))
        
        # 插入到Milvus
        if self.milvus_collection:
            entities = [
                chunk_ids,
                document_ids,
                embeddings,
                contents
            ]
            result = self.milvus_collection.insert(entities)
            self.milvus_collection.flush()
            return result.primary_keys
        
        return []
    
    def similarity_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义相似度搜索"""
        if not self.milvus_collection:
            return []
        
        # 生成查询向量
        query_embedding = self.model.encode(query).tolist()
        
        # 执行搜索
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10}
        }
        
        results = self.milvus_collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["content", "document_id", "chunk_id"]
        )
        
        # 格式化结果
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "id": hit.id,
                    "content": hit.entity.get("content"),
                    "score": 1 / (1 + hit.distance),  # 转换距离为相似度分数
                    "document_id": hit.entity.get("document_id"),
                    "chunk_id": hit.entity.get("chunk_id")
                })
        
        return formatted_results

class SearchService:
    """搜索服务"""
    
    def __init__(self):
        self.vector_store = VectorStore()
    
    async def search(self, query: str, search_type: str = "hybrid", top_k: int = 10, filters: Dict = None) -> List[Dict[str, Any]]:
        """执行搜索"""
        results = []
        
        if search_type in ["semantic", "hybrid"]:
            # 语义搜索
            semantic_results = self.vector_store.similarity_search(query, top_k * 2)
            results.extend(semantic_results)
        
        if search_type in ["keyword", "hybrid"]:
            # 关键词搜索（这里可以集成Elasticsearch）
            pass
        
        # 去重和排序
        unique_results = {}
        for result in results:
            key = f"{result['document_id']}_{result['chunk_id']}"
            if key not in unique_results or result['score'] > unique_results[key]['score']:
                unique_results[key] = result
        
        # 按分数排序并限制数量
        sorted_results = sorted(unique_results.values(), key=lambda x: x['score'], reverse=True)[:top_k]
        return sorted_results
    
    async def save_search_history(self, query: str, search_type: str, results: List[Dict]) -> int:
        """保存搜索历史"""
        # 实现搜索历史保存逻辑
        return 1
    
    async def get_recent_searches(self, limit: int = 10) -> List[Dict]:
        """获取最近搜索"""
        # 实现获取最近搜索逻辑
        return []