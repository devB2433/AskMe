"""搜索API路由"""
from fastapi import APIRouter, Query, HTTPException, Header
from typing import List, Optional, Dict, Any
import logging
import os
from pathlib import Path
import json

from services.state_manager import StateManager, StateType, StateStatus
from services.embedding_encoder import EmbeddingEncoder
from services.milvus_integration import MilvusClient
from services.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# 全局状态管理器
state_manager = None
embedding_encoder = None
milvus_client = None

def get_state_manager():
    global state_manager
    if state_manager is None:
        state_manager = StateManager()
    return state_manager

def get_embedding_encoder():
    global embedding_encoder
    if embedding_encoder is None:
        embedding_encoder = EmbeddingEncoder()
    return embedding_encoder

def get_milvus_client():
    global milvus_client
    if milvus_client is None:
        milvus_client = MilvusClient()
    return milvus_client

@router.get("/", summary="搜索文档")
async def search_documents(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, description="返回结果数量"),
    team: str = Query(None, description="团队/部门过滤"),
    authorization: Optional[str] = Header(None)
):
    """
    搜索文档内容
    
    支持搜索语法：
    - "/部门名 关键词" : 仅在指定部门的知识库中搜索
    - "关键词" : 在用户有权限的所有部门搜索
    
    Args:
        q: 搜索关键词（支持 /部门名 前缀语法）
        limit: 返回结果数量
        team: 团队/部门过滤（可选，优先于语法解析）
        authorization: 用户token
        
    Returns:
        搜索结果列表
    """
    try:
        state_mgr = get_state_manager()
        results = []
        
        # 解析搜索语法
        actual_team = team
        actual_query = q
        
        if not actual_team and q.startswith("/"):
            # 解析 /部门名 关键词 格式
            parts = q.split(None, 1)
            if len(parts) >= 1:
                actual_team = parts[0][1:]  # 去掉开头的 /
                actual_query = parts[1] if len(parts) > 1 else ""
                logger.info(f"解析搜索语法: team={actual_team}, query={actual_query}")
        
        # 获取用户信息
        user_department = None
        if authorization:
            from services.user_service import user_service
            token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
            user = user_service.get_user_by_token(token)
            if user:
                # user可能是字典或对象
                user_department = user.get("department") if isinstance(user, dict) else user.department
        
        # 验证部门权限
        if actual_team:
            # 如果指定了部门，验证用户是否有权限
            if user_department and actual_team != user_department:
                logger.warning(f"用户 {user_department} 无权访问 {actual_team} 的知识库")
                # 可以选择返回空结果或错误
                # 这里暂时允许，后续可加权限控制
        
        # 尝试向量搜索
        try:
            encoder = get_embedding_encoder()
            milvus = get_milvus_client()
            
            # 对查询进行向量化
            query_vector = encoder.encode_single(actual_query).tolist()
            
            # 构建过滤条件
            filter_expr = None
            if actual_team:
                filter_expr = f'team_id == "{actual_team}"'
                logger.info(f"应用team_id过滤: {filter_expr}")
            
            # 在Milvus中搜索相似向量
            search_results = milvus.search_vectors(
                collection_name="askme_documents",
                query_vector=query_vector,
                top_k=limit,
                filter_expr=filter_expr,
                output_fields=["document_id", "team_id", "chunk_id", "content", "metadata"]
            )
            
            # 处理搜索结果
            seen_docs = set()
            logger.info(f"处理 {len(search_results)} 个搜索结果")
            for result in search_results:
                doc_id = result.get("document_id")
                logger.info(f"结果 doc_id={doc_id}, score={result.get('score')}")
                if doc_id and doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    # 从SQLite数据库获取文档信息
                    doc_record = db.fetchone(
                        "SELECT filename, created_at FROM documents WHERE id = ?",
                        (doc_id,)
                    )
                    if doc_record:
                        results.append({
                            "document_id": doc_id,
                            "filename": doc_record["filename"],
                            "score": result.get("score", 0.9),
                            "matches": [result.get("content", "")[:300]],
                            "created_at": doc_record["created_at"],
                            "search_type": "vector"
                        })
                    else:
                        # 如果数据库查不到，尝试从状态管理器获取
                        doc_states = state_mgr.query_states(entity_id=doc_id)
                        if doc_states:
                            doc_state = doc_states[0]
                            results.append({
                                "document_id": doc_id,
                                "filename": doc_state.data.get("filename", "Unknown"),
                                "score": result.get("score", 0.9),
                                "matches": [result.get("content", "")[:300]],
                                "created_at": doc_state.created_at.isoformat() if hasattr(doc_state.created_at, 'isoformat') else str(doc_state.created_at),
                                "search_type": "vector"
                            })
                        else:
                            # 如果都查不到，直接返回向量结果
                            results.append({
                                "document_id": doc_id,
                                "filename": "Unknown",
                                "score": result.get("score", 0.9),
                                "matches": [result.get("content", "")[:300]],
                                "created_at": "",
                                "search_type": "vector"
                            })
            
            if results:
                logger.info(f"向量搜索返回 {len(results)} 个结果")
                return {
                    "query": q,
                    "total": len(results),
                    "results": results[:limit],
                    "search_type": "vector"
                }
        except Exception as e:
            logger.warning(f"向量搜索失败，降级为文本搜索: {e}")
        
        # 降级：文本搜索 - 从SQLite获取已完成的文档
        completed_docs = db.fetchall(
            "SELECT id, filename, created_at FROM documents WHERE status = 'completed'"
        )
        query_lower = q.lower()
        upload_dir = Path("uploads")
        
        for doc_record in completed_docs:
            doc_id = doc_record["id"]
            filename = doc_record["filename"]
            
            content_file = upload_dir / f"{doc_id}_content.json"
            if content_file.exists():
                try:
                    with open(content_file, "r", encoding="utf-8") as f:
                        content_data = json.load(f)
                    
                    full_text = content_data.get("full_text", "")
                    chunks = content_data.get("chunks", [])
                    
                    if query_lower in full_text.lower():
                        matches = []
                        for chunk in chunks:
                            chunk_content = chunk.get("content", "")
                            if query_lower in chunk_content.lower():
                                matches.append(chunk_content[:300] + "..." if len(chunk_content) > 300 else chunk_content)
                                if len(matches) >= 3:
                                    break
                        
                        if matches:
                            results.append({
                                "document_id": doc_id,
                                "filename": filename,
                                "score": 0.95,
                                "matches": matches,
                                "created_at": doc_record["created_at"],
                                "search_type": "text"
                            })
                except Exception as e:
                    logger.warning(f"读取内容文件失败 {content_file}: {e}")
        
        # 按相关度排序并限制数量
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
        
        return {
            "query": q,
            "total": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@router.get("/suggestions", summary="获取搜索建议")
async def get_search_suggestions(
    q: str = Query(..., description="搜索关键词前缀"),
    limit: int = Query(5, description="返回建议数量")
):
    """
    获取搜索建议
    
    Args:
        q: 搜索关键词前缀
        limit: 返回建议数量
        
    Returns:
        搜索建议列表
    """
    # 简化实现：返回空列表
    return {
        "query": q,
        "suggestions": []
    }
