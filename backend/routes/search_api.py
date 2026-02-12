"""搜索API路由 - 增强版（多路召回+重排序+查询增强）"""
from fastapi import APIRouter, Query, HTTPException, Header
from typing import List, Optional, Dict, Any
import logging
import os
from pathlib import Path
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from services.state_manager import StateManager, StateType, StateStatus
from services.embedding_encoder import EmbeddingEncoder
from services.milvus_integration import MilvusClient
from services.database import db
from services.reranker import get_reranker, get_query_enhancer, QueryEnhancer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# 全局状态管理器
state_manager = None
embedding_encoder = None
milvus_client = None
reranker = None
query_enhancer = None

# 线程池用于并行处理
executor = ThreadPoolExecutor(max_workers=4)

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

def get_reranker_instance():
    global reranker
    if reranker is None:
        try:
            reranker = get_reranker()
        except Exception as e:
            logger.warning(f"重排序器加载失败，将跳过重排序: {e}")
    return reranker

def get_query_enhancer_instance():
    global query_enhancer
    if query_enhancer is None:
        query_enhancer = get_query_enhancer()
    return query_enhancer


@router.get("/", summary="搜索文档（增强版）")
async def search_documents(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, description="返回结果数量"),
    team: str = Query(None, description="团队/部门过滤"),
    use_rerank: bool = Query(True, description="是否使用重排序"),
    use_query_enhance: bool = Query(False, description="是否使用查询增强"),
    recall_size: int = Query(15, description="召回数量（重排序前）"),
    authorization: Optional[str] = Header(None)
):
    """
    增强版搜索文档内容
    
    优化特性：
    1. 查询增强：生成查询变体，提高召回率
    2. 多路召回：扩大召回数量
    3. 重排序：使用Cross-Encoder精细排序
    4. 自动部门过滤
    
    支持搜索语法：
    - "/部门名 关键词" : 仅在指定部门的知识库中搜索
    - "关键词" : 在用户有权限的所有部门搜索
    """
    try:
        state_mgr = get_state_manager()
        
        # 解析搜索语法
        actual_team = team
        actual_query = q
        
        if not actual_team and q.startswith("/"):
            parts = q.split(None, 1)
            if len(parts) >= 1:
                parsed_team = parts[0][1:]
                actual_query = parts[1] if len(parts) > 1 else ""
                
                from services.user_service import user_service
                departments = user_service.get_departments()
                matched_dept = None
                for dept in departments:
                    if dept == parsed_team or parsed_team in dept:
                        matched_dept = dept
                        break
                
                actual_team = matched_dept or parsed_team
                logger.info(f"解析搜索语法: parsed={parsed_team}, matched={actual_team}, query={actual_query}")
        
        # 获取用户信息
        user_department = None
        if authorization:
            from services.user_service import user_service
            token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
            user = user_service.get_user_by_token(token)
            if user:
                user_department = user.get("department") if isinstance(user, dict) else user.department
        
        # 构建过滤条件
        filter_expr = None
        search_team = actual_team or user_department
        if search_team:
            filter_expr = f'team_id == "{search_team}"'
            logger.info(f"应用team_id过滤: {filter_expr}")
        
        # ========== 核心搜索逻辑 ==========
        all_candidates = []
        
        try:
            encoder = get_embedding_encoder()
            milvus = get_milvus_client()
            
            # 查询增强
            queries = [actual_query]
            if use_query_enhance and actual_query.strip():
                enhancer = get_query_enhancer_instance()
                enhanced_queries = enhancer.enhance_query(actual_query, num_variations=2)
                queries = enhanced_queries
                logger.info(f"查询增强: {actual_query} -> {queries}")
            
            # 多路召回
            seen_chunk_ids = set()
            
            for query_text in queries:
                if not query_text.strip():
                    continue
                    
                # 向量化
                query_vector = encoder.encode_single(query_text).tolist()
                
                # 搜索 - 扩大召回数量
                search_results = milvus.search_vectors(
                    collection_name="askme_documents",
                    query_vector=query_vector,
                    top_k=recall_size,
                    filter_expr=filter_expr,
                    output_fields=["document_id", "team_id", "chunk_id", "content", "metadata"]
                )
                
                # 收集候选结果（去重）
                for result in search_results:
                    chunk_id = result.get("chunk_id")
                    if chunk_id and chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        all_candidates.append(result)
            
            logger.info(f"多路召回完成: {len(all_candidates)} 个候选")
            
            # 如果没有结果，返回空
            if not all_candidates:
                return {
                    "query": q,
                    "total": 0,
                    "results": [],
                    "search_type": "vector",
                    "enhanced": True
                }
            
            # ========== 重排序 ==========
            reranker_instance = get_reranker_instance()
            
            if use_rerank and reranker_instance and len(all_candidates) > 0:
                # 使用重排序模型
                reranked_results = reranker_instance.rerank(
                    query=actual_query,
                    documents=all_candidates,
                    content_key="content",
                    top_k=limit
                )
                final_candidates = reranked_results
                search_type = "vector_reranked"
                logger.info(f"重排序完成: {len(final_candidates)} 个结果")
            else:
                # 按原始分数排序
                all_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
                final_candidates = all_candidates[:limit]
                search_type = "vector"
            
            # ========== 构建返回结果 ==========
            results = []
            seen_docs = set()
            
            for candidate in final_candidates:
                doc_id = candidate.get("document_id")
                
                if doc_id and doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    
                    # 获取文档信息
                    doc_record = db.fetchone(
                        "SELECT filename, created_at FROM documents WHERE id = ?",
                        (doc_id,)
                    )
                    
                    # 获取分数
                    final_score = candidate.get("rerank_score") or candidate.get("score", 0.9)
                    
                    if doc_record:
                        results.append({
                            "document_id": doc_id,
                            "filename": doc_record["filename"],
                            "score": round(final_score, 4),
                            "matches": [candidate.get("content", "")[:500]],
                            "created_at": doc_record["created_at"],
                            "search_type": search_type,
                            "chunk_id": candidate.get("chunk_id")
                        })
                    else:
                        results.append({
                            "document_id": doc_id,
                            "filename": "Unknown",
                            "score": round(final_score, 4),
                            "matches": [candidate.get("content", "")[:500]],
                            "created_at": "",
                            "search_type": search_type,
                            "chunk_id": candidate.get("chunk_id")
                        })
            
            # 按分数排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            logger.info(f"搜索完成: query={actual_query}, candidates={len(all_candidates)}, results={len(results)}")
            
            return {
                "query": q,
                "actual_query": actual_query,
                "total": len(results),
                "results": results[:limit],
                "search_type": search_type,
                "enhanced": use_rerank or use_query_enhance,
                "recall_count": len(all_candidates),
                "query_variations": queries if use_query_enhance else None
            }
            
        except Exception as e:
            logger.warning(f"向量搜索失败，降级为文本搜索: {e}")
            # 降级到文本搜索
            return await _text_search_fallback(q, limit, state_mgr)
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


async def _text_search_fallback(q: str, limit: int, state_mgr) -> Dict[str, Any]:
    """文本搜索降级方案"""
    results = []
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
    
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
    
    return {
        "query": q,
        "total": len(results),
        "results": results,
        "search_type": "text",
        "enhanced": False
    }


@router.get("/suggestions", summary="获取搜索建议")
async def get_search_suggestions(
    q: str = Query(..., description="搜索关键词前缀"),
    limit: int = Query(5, description="返回建议数量")
):
    """获取搜索建议"""
    return {
        "query": q,
        "suggestions": []
    }


@router.get("/config", summary="获取搜索配置")
async def get_search_config():
    """获取当前搜索配置"""
    return {
        "rerank_enabled": True,
        "query_enhance_enabled": True,
        "default_recall_size": 30,
        "default_limit": 10,
        "rerank_model": "BAAI/bge-reranker-large",
        "embedding_model": "BAAI/bge-large-zh-v1.5"
    }
