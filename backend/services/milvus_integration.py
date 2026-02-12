"""Milvus向量数据库集成模块"""
import numpy as np
from typing import List, Dict, Any, Optional, Union
from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, AnnSearchRequest, RRFRanker, WeightedRanker
)
import logging
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

class MilvusClient:
    """Milvus数据库客户端"""
    
    def __init__(self, host: str = "localhost", port: int = 19530, alias: str = "default"):
        """
        初始化Milvus客户端
        
        Args:
            host: Milvus服务主机
            port: Milvus服务端口
            alias: 连接别名
        """
        self.host = host
        self.port = port
        self.alias = alias
        self.connected = False
        self.collections = {}
        
        self._connect()
    
    def _connect(self):
        """建立Milvus连接"""
        try:
            connections.connect(
                alias=self.alias,
                host=self.host,
                port=self.port
            )
            self.connected = True
            logger.info(f"成功连接到Milvus: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"连接Milvus失败: {e}")
            raise
    
    def disconnect(self):
        """断开连接"""
        try:
            connections.disconnect(self.alias)
            self.connected = False
            logger.info("已断开Milvus连接")
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
    
    def create_collection(self, collection_name: str, dimension: int = 1024, 
                         auto_id: bool = False, description: str = "") -> Collection:
        """
        创建集合
        
        Args:
            collection_name: 集合名称
            dimension: 向量维度
            auto_id: 是否自动生成ID
            description: 集合描述
            
        Returns:
            Collection对象
        """
        if utility.has_collection(collection_name):
            logger.info(f"集合 {collection_name} 已存在，直接返回")
            collection = Collection(collection_name)
            self.collections[collection_name] = collection
            return collection
        
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=auto_id),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="team_id", dtype=DataType.VARCHAR, max_length=256),  # 团队ID
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="created_at", dtype=DataType.INT64),  # Unix timestamp
        ]
        
        # 创建集合模式
        schema = CollectionSchema(fields, description=description)
        
        # 创建集合
        collection = Collection(collection_name, schema)
        
        # 创建索引
        index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 256}  # 提高索引质量
        }
        
        collection.create_index(
            field_name="embedding",
            index_params=index_params
        )
        
        # 加载集合
        collection.load()
        
        self.collections[collection_name] = collection
        logger.info(f"成功创建并加载集合: {collection_name}")
        
        return collection
    
    def drop_collection(self, collection_name: str):
        """删除集合"""
        try:
            if utility.has_collection(collection_name):
                collection = Collection(collection_name)
                collection.drop()
                if collection_name in self.collections:
                    del self.collections[collection_name]
                logger.info(f"成功删除集合: {collection_name}")
            else:
                logger.warning(f"集合不存在: {collection_name}")
        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            raise
    
    def insert_vectors(self, collection_name: str, vectors: List[List[float]], 
                      documents: List[Dict[str, Any]]) -> List[int]:
        """
        插入向量数据
        
        Args:
            collection_name: 集合名称
            vectors: 向量列表
            documents: 文档信息列表
            
        Returns:
            插入的实体ID列表
        """
        if collection_name not in self.collections:
            # 尝试从Milvus获取已存在的集合
            if utility.has_collection(collection_name):
                collection = Collection(collection_name)
                self.collections[collection_name] = collection
            else:
                raise ValueError(f"集合 {collection_name} 不存在")
        
        collection = self.collections[collection_name]
        
        # 准备插入数据
        insert_data = {
            "document_id": [],
            "team_id": [],
            "chunk_id": [],
            "content": [],
            "embedding": [],
            "metadata": [],
            "created_at": []
        }
        
        current_time = int(datetime.now().timestamp())
        
        for i, (vector, doc) in enumerate(zip(vectors, documents)):
            insert_data["document_id"].append(doc.get("document_id", ""))
            insert_data["team_id"].append(doc.get("team_id", "default"))
            insert_data["chunk_id"].append(doc.get("chunk_id", ""))
            insert_data["content"].append(doc.get("content", ""))
            insert_data["embedding"].append(vector)
            insert_data["metadata"].append(doc.get("metadata", {}))
            insert_data["created_at"].append(current_time)
        
        # 批量插入
        try:
            mr = collection.insert([
                insert_data["document_id"],
                insert_data["team_id"],
                insert_data["chunk_id"],
                insert_data["content"],
                insert_data["embedding"],
                insert_data["metadata"],
                insert_data["created_at"]
            ])
            collection.flush()  # 确保数据持久化
            logger.info(f"成功插入 {len(vectors)} 条向量到集合 {collection_name}")
            return mr.primary_keys
        except Exception as e:
            logger.error(f"插入向量失败: {e}")
            raise
    
    def delete_vectors_by_document_id(self, collection_name: str, document_id: str) -> int:
        """
        删除指定文档的所有向量
        
        Args:
            collection_name: 集合名称
            document_id: 文档ID
            
        Returns:
            删除的向量数量
        """
        if collection_name not in self.collections:
            if utility.has_collection(collection_name):
                collection = Collection(collection_name)
                self.collections[collection_name] = collection
            else:
                return 0
        
        collection = self.collections[collection_name]
        
        try:
            # 使用表达式删除
            expr = f'document_id == "{document_id}"'
            result = collection.delete(expr)
            collection.flush()
            deleted_count = result.delete_count if hasattr(result, 'delete_count') else 0
            logger.info(f"删除文档 {document_id} 的 {deleted_count} 条向量")
            return deleted_count
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return 0
    
    def search_vectors(self, collection_name: str, query_vector: List[float], 
                      top_k: int = 10, filter_expr: str = "", 
                      output_fields: List[str] = None) -> List[Dict[str, Any]]:
        """
        向量相似度搜索
        
        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回结果数量
            filter_expr: 过滤表达式
            output_fields: 输出字段列表
            
        Returns:
            搜索结果列表
        """
        if collection_name not in self.collections:
            # 尝试从Milvus获取已存在的集合
            if utility.has_collection(collection_name):
                collection = Collection(collection_name)
                self.collections[collection_name] = collection
            else:
                raise ValueError(f"集合 {collection_name} 不存在")
        
        collection = self.collections[collection_name]
        
        # 默认输出字段
        if output_fields is None:
            output_fields = ["id", "document_id", "team_id", "chunk_id", "content", "metadata", "created_at"]
        
        # 执行搜索
        try:
            search_params = {
                "metric_type": "COSINE",
                "params": {"ef": 256}  # 提高搜索精度
            }
            
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=output_fields,
                consistency_level="Strong"
            )
            
            # 处理搜索结果
            search_results = []
            for hits in results:
                for hit in hits:
                    result = {
                        "id": hit.entity.get("id"),
                        "document_id": hit.entity.get("document_id"),
                        "team_id": hit.entity.get("team_id"),
                        "chunk_id": hit.entity.get("chunk_id"),
                        "content": hit.entity.get("content"),
                        "score": hit.score,
                        "metadata": hit.entity.get("metadata"),
                        "created_at": hit.entity.get("created_at")
                    }
                    search_results.append(result)
            
            logger.info(f"搜索完成，返回 {len(search_results)} 个结果")
            return search_results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            raise
    
    def hybrid_search(self, collection_name: str, 
                     vector_query: List[float],
                     keyword_filter: str = "",
                     top_k: int = 10) -> List[Dict[str, Any]]:
        """
        混合搜索（向量+关键词）
        
        Args:
            collection_name: 集合名称
            vector_query: 向量查询
            keyword_filter: 关键词过滤条件
            top_k: 返回结果数量
            
        Returns:
            混合搜索结果
        """
        if collection_name not in self.collections:
            raise ValueError(f"集合 {collection_name} 不存在")
        
        collection = self.collections[collection_name]
        
        # 向量搜索请求
        vector_search_req = AnnSearchRequest(
            data=[vector_query],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k * 2  # 扩大搜索范围
        )
        
        # 执行混合搜索
        try:
            results = collection.hybrid_search(
                reqs=[vector_search_req],
                rerank=RRFRanker(),
                limit=top_k,
                expr=keyword_filter,
                output_fields=["id", "document_id", "chunk_id", "content", "metadata"]
            )
            
            # 处理结果
            search_results = []
            for hits in results:
                for hit in hits:
                    result = {
                        "id": hit.entity.get("id"),
                        "document_id": hit.entity.get("document_id"),
                        "chunk_id": hit.entity.get("chunk_id"),
                        "content": hit.entity.get("content"),
                        "score": hit.score,
                        "metadata": hit.entity.get("metadata")
                    }
                    search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            raise
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """获取集合信息"""
        if collection_name not in self.collections:
            raise ValueError(f"集合 {collection_name} 不存在")
        
        collection = self.collections[collection_name]
        
        return {
            "name": collection_name,
            "schema": str(collection.schema),
            "num_entities": collection.num_entities,
            "indexes": [index.to_dict() for index in collection.indexes],
            "loaded": True  # 简化处理，假设集合已加载
        }
    
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        try:
            return utility.list_collections()
        except Exception as e:
            logger.error(f"列出集合失败: {e}")
            return []
    
    def delete_entities(self, collection_name: str, ids: List[int]):
        """删除实体"""
        if collection_name not in self.collections:
            raise ValueError(f"集合 {collection_name} 不存在")
        
        collection = self.collections[collection_name]
        
        try:
            expr = f"id in {ids}"
            collection.delete(expr)
            collection.flush()
            logger.info(f"成功删除 {len(ids)} 个实体")
        except Exception as e:
            logger.error(f"删除实体失败: {e}")
            raise

class VectorStorageManager:
    """向量存储管理器"""
    
    def __init__(self, milvus_client: MilvusClient):
        """
        初始化向量存储管理器
        
        Args:
            milvus_client: Milvus客户端实例
        """
        self.milvus_client = milvus_client
        self.default_collection = "documents"
        self._ensure_default_collection()
    
    def _ensure_default_collection(self):
        """确保默认集合存在"""
        try:
            self.milvus_client.create_collection(self.default_collection, dimension=1024)
        except Exception as e:
            logger.info(f"默认集合已存在或创建失败: {e}")
    
    def store_documents(self, documents: List[Dict[str, Any]], 
                       collection_name: str = None) -> List[int]:
        """
        存储文档向量
        
        Args:
            documents: 文档列表，每个文档应包含content和embedding字段
            collection_name: 集合名称
            
        Returns:
            存储的实体ID列表
        """
        if collection_name is None:
            collection_name = self.default_collection
        
        # 提取向量和文档信息
        vectors = []
        doc_infos = []
        
        for doc in documents:
            if "embedding" not in doc:
                raise ValueError("文档必须包含embedding字段")
            
            vectors.append(doc["embedding"])
            doc_info = {
                "document_id": doc.get("document_id", ""),
                "chunk_id": doc.get("chunk_id", ""),
                "content": doc.get("content", ""),
                "metadata": doc.get("metadata", {})
            }
            doc_infos.append(doc_info)
        
        # 存储到Milvus
        return self.milvus_client.insert_vectors(collection_name, vectors, doc_infos)
    
    def search_similar_documents(self, query_embedding: List[float], 
                               top_k: int = 10, 
                               collection_name: str = None,
                               filter_conditions: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            collection_name: 集合名称
            filter_conditions: 过滤条件
            
        Returns:
            相似文档列表
        """
        if collection_name is None:
            collection_name = self.default_collection
        
        # 构建过滤表达式
        filter_expr = ""
        if filter_conditions:
            conditions = []
            for key, value in filter_conditions.items():
                if isinstance(value, str):
                    conditions.append(f'{key} == "{value}"')
                else:
                    conditions.append(f'{key} == {value}')
            filter_expr = " and ".join(conditions)
        
        return self.milvus_client.search_vectors(
            collection_name=collection_name,
            query_vector=query_embedding,
            top_k=top_k,
            filter_expr=filter_expr
        )
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        collections = self.milvus_client.list_collections()
        stats = {
            "total_collections": len(collections),
            "collections": {}
        }
        
        for collection_name in collections:
            try:
                info = self.milvus_client.get_collection_info(collection_name)
                stats["collections"][collection_name] = {
                    "entity_count": info["num_entities"],
                    "loaded": info["loaded"]
                }
            except Exception as e:
                logger.warning(f"获取集合 {collection_name} 信息失败: {e}")
        
        return stats

# 导出主要类
__all__ = ['MilvusClient', 'VectorStorageManager']