"""文档管理API路由"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query, Header
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import uuid
import os
from pathlib import Path
import hashlib

# 导入服务层
from services.document_processor import DocumentProcessor, ProcessingConfig
from services.milvus_integration import MilvusClient
from services.embedding_encoder import EmbeddingEncoder
from services.state_manager import StateManager, StateType, StateStatus
from services.database import db

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/documents", tags=["documents"])

# 全局服务实例（实际应用中应该使用依赖注入）
document_processor = None
milvus_client = None
embedding_encoder = None
state_manager = None

def get_services():
    """获取服务实例"""
    global document_processor, milvus_client, embedding_encoder, state_manager
    
    if document_processor is None:
        document_processor = DocumentProcessor()
    
    if milvus_client is None:
        milvus_client = MilvusClient()
    
    if embedding_encoder is None:
        embedding_encoder = EmbeddingEncoder()
    
    if state_manager is None:
        state_manager = StateManager()
    
    return document_processor, milvus_client, embedding_encoder, state_manager

@router.post("/upload", summary="上传文档")
async def upload_document(
    file: UploadFile = File(...),
    collection_name: str = Form("default_collection"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    enable_metadata: bool = Form(True),
    team_id: str = Form(None),
    authorization: Optional[str] = Header(None)
):
    """
    上传并处理文档
    
    Args:
        file: 上传的文件
        collection_name: 集合名称
        chunk_size: 分块大小
        chunk_overlap: 分块重叠
        enable_metadata: 是否启用元数据提取
        team_id: 团队/部门ID（可选，登录后自动从用户信息获取）
        authorization: 用户token（可选）
        
    Returns:
        上传结果
    """
    try:
        processor, milvus_client, encoder, state_mgr = get_services()
        
        # 获取用户信息和team_id
        actual_team_id = team_id or "default"
        uploaded_by = "anonymous"
        
        if authorization:
            from services.user_service import user_service
            token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
            user = user_service.get_user_by_token(token)
            if user:
                actual_team_id = user.department
                uploaded_by = user.username
        
        # 读取文件内容并计算哈希
        content = await file.read()
        file_hash = hashlib.md5(content).hexdigest()
        file_size = len(content)
        
        # 重置文件指针
        await file.seek(0)
        
        # 检查文件哈希是否已存在（去重）
        existing_doc = db.fetchone(
            "SELECT id, filename FROM documents WHERE file_hash = ?",
            (file_hash,)
        )
        
        if existing_doc:
            logger.info(f"检测到重复文件（哈希相同）: {file.filename} -> 已存在 {existing_doc['filename']}")
            return {
                "success": False,
                "error": f"文件已存在: {existing_doc['filename']}",
                "duplicate": True,
                "existing_id": existing_doc['id']
            }
        
        # 检查是否存在同名文件（不同内容），存在则先删除旧的
        existing_same_name = db.fetchone(
            "SELECT id FROM documents WHERE filename = ?",
            (file.filename,)
        )
        
        if existing_same_name:
            old_doc_id = existing_same_name['id']
            logger.info(f"检测到同名文件，删除旧文档: {file.filename} (ID: {old_doc_id})")
            
            # 删除数据库记录
            db.execute("DELETE FROM documents WHERE id = ?", (old_doc_id,))
            
            # 删除状态记录
            state_mgr.delete_state(f"document_{old_doc_id}")
            
            # 删除向量数据
            try:
                milvus.delete_vectors_by_document_id("askme_documents", old_doc_id)
            except Exception as e:
                logger.warning(f"删除旧向量数据失败: {e}")
            
            # 删除文件
            upload_dir = Path("uploads")
            for old_file in upload_dir.glob(f"{old_doc_id}_*"):
                old_file.unlink()
                logger.info(f"删除旧文件: {old_file}")
            
            db.conn.commit()
        
        # 生成文档ID
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # 创建状态记录
        state_id = state_mgr.create_state(
            state_type=StateType.DOCUMENT,
            entity_id=document_id,
            initial_data={
                "filename": file.filename,
                "content_type": file.content_type,
                "collection_name": collection_name,
                "upload_time": datetime.now().isoformat(),
                "team_id": actual_team_id,
                "uploaded_by": uploaded_by
            },
            tags=["upload", "processing"]
        )
        
        # 保存上传文件
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / f"{document_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 更新状态为处理中
        state_mgr.update_state(state_id, new_status=StateStatus.PROCESSING)
        
        # 处理文档
        chunks = processor.process_document(str(file_path), file.filename)
        
        # 保存解析后的文本内容（用于搜索）
        import json
        text_content_path = upload_dir / f"{document_id}_content.json"
        with open(text_content_path, "w", encoding="utf-8") as f:
            json.dump({
                "filename": file.filename,
                "chunks": chunks,
                "full_text": "\n".join([c.get("content", "") for c in chunks])
            }, f, ensure_ascii=False, indent=2)
        
        # 向量编码和存储到Milvus
        try:
            encoder = embedding_encoder or EmbeddingEncoder()
            milvus = milvus_client or MilvusClient()
            
            # 创建集合（如果不存在）
            collection_name = "askme_documents"
            collection = milvus.create_collection(
                collection_name=collection_name,
                dimension=512,  # bge-small-zh-v1.5 模型维度
                auto_id=True,
                description="AskMe文档向量存储"
            )
            
            # 对每个chunk进行向量编码
            chunk_texts = [c.get("content", "") for c in chunks]
            vectors = encoder.encode_batch(chunk_texts)
            
            # 存储到Milvus
            chunk_ids = milvus.insert_vectors(
                collection_name=collection_name,
                vectors=vectors,
                documents=[{
                    "document_id": document_id,
                    "team_id": actual_team_id,
                    "chunk_id": f"{document_id}_{i}",
                    "content": c.get("content", "")[:500],
                    "metadata": {"chunk_index": i}
                } for i, c in enumerate(chunks)]
            )
            
            logger.info(f"向量化存储完成: {len(chunk_ids)} 个向量")
            vector_stored = True
        except Exception as e:
            logger.warning(f"向量存储失败（降级为纯文本搜索）: {e}")
            vector_stored = False
        
        # 更新状态记录
        state_mgr.update_state(
            state_id,
            new_status=StateStatus.COMPLETED,
            new_data={
                "processing_result": {
                    "chunks_count": len(chunks),
                    "metadata_extracted": True,
                    "vector_stored": vector_stored
                }
            }
        )
        
        # 插入文档记录到数据库
        db.execute(
            """INSERT INTO documents 
               (id, filename, content_type, team_id, uploaded_by, status, chunks_count, vector_stored, file_size, file_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (document_id, file.filename, file.content_type, actual_team_id, uploaded_by, 
             'completed', len(chunks), 1 if vector_stored else 0, file_size, file_hash)
        )
        db.conn.commit()
        
        logger.info(f"文档上传处理完成: {file.filename}")
        
        return {
            "document_id": document_id,
            "filename": file.filename,
            "chunks_count": len(chunks),
            "collection_name": collection_name,
            "processing_time": 0,
            "status": "completed",
            "vector_stored": vector_stored,
            "team_id": actual_team_id,
            "message": "文档已成功上传、处理和向量化存储" if vector_stored else "文档已处理，向量存储失败（可使用文本搜索）"
        }
        
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        
        # 更新错误状态
        if 'state_id' in locals():
            state_mgr.update_state(
                state_id,
                new_status=StateStatus.FAILED,
                new_data={"error": str(e)}
            )
        
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@router.get("/{document_id}", summary="获取文档信息")
async def get_document(document_id: str):
    """
    获取文档详细信息
    
    Args:
        document_id: 文档ID
        
    Returns:
        文档信息
    """
    try:
        _, _, _, state_mgr = get_services()
        
        # 查询文档状态
        states = state_mgr.query_states(
            entity_id=document_id,
            state_type=StateType.DOCUMENT
        )
        
        if not states:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        state = states[0]
        
        # 简化：返回基本文档信息
        return {
            "document_id": document_id,
            "status": state.status.value,
            "state_data": state.data,
            "vector_info": {"status": "not_implemented"},
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "message": "向量存储功能待完善"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档信息失败: {str(e)}")

@router.get("/", summary="列出文档")
async def list_documents(
    collection_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0)
):
    """
    列出文档列表
    
    Args:
        collection_name: 集合名称过滤
        status: 状态过滤
        limit: 限制数量
        offset: 偏移量
        
    Returns:
        文档列表
    """
    try:
        _, _, _, state_mgr = get_services()
        
        # 查询文档状态
        states = state_mgr.query_states(state_type=StateType.DOCUMENT)
        
        # 应用偏移和限制
        filtered_states = states[offset:offset + limit]
        
        documents = []
        for state in filtered_states:
            processing_result = state.data.get("processing_result", {})
            documents.append({
                "document_id": state.entity_id,
                "status": state.status.value,
                "filename": state.data.get("filename", "Unknown"),
                "collection_name": state.data.get("collection_name", "default"),
                "chunks_count": processing_result.get("chunks_count", 0),
                "created_at": state.created_at.isoformat(),
                "updated_at": state.updated_at.isoformat()
            })
        
        return {
            "documents": documents,
            "total": len(states),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"列出文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"列出文档失败: {str(e)}")

@router.delete("/{document_id}", summary="删除文档")
async def delete_document(document_id: str):
    """
    删除文档
    
    Args:
        document_id: 文档ID
        
    Returns:
        删除结果
    """
    try:
        _, _, _, state_mgr = get_services()
        
        # 检查文档是否存在
        states = state_mgr.query_states(
            entity_id=document_id,
            state_type=StateType.DOCUMENT
        )
        
        if not states:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 删除状态记录
        state_mgr.delete_state(f"document_{document_id}")
        
        # 删除上传文件
        upload_files = Path("uploads").glob(f"{document_id}_*")
        for file_path in upload_files:
            if file_path.exists():
                file_path.unlink()
        
        logger.info(f"文档删除成功: {document_id}")
        
        return {
            "document_id": document_id,
            "status": "deleted",
            "message": "文档已成功删除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")

@router.post("/{document_id}/reprocess", summary="重新处理文档")
async def reprocess_document(document_id: str, config: Optional[Dict[str, Any]] = None):
    """
    重新处理文档
    
    Args:
        document_id: 文档ID
        config: 处理配置
        
    Returns:
        重新处理结果
    """
    try:
        processor, _, _, state_mgr = get_services()
        
        # 检查文档是否存在
        states = state_mgr.query_states(
            entity_id=document_id,
            state_type=StateType.DOCUMENT
        )
        
        if not states:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        state = states[0]
        filename = state.data.get("filename", "")
        
        # 更新状态为处理中
        state_mgr.update_state(
            f"document_{document_id}",
            new_status=StateStatus.PROCESSING
        )
        
        # 查找上传文件
        upload_dir = Path("uploads")
        file_path = None
        for uploaded_file in upload_dir.glob(f"{document_id}_*"):
            if uploaded_file.exists():
                file_path = uploaded_file
                break
        
        if not file_path:
            raise HTTPException(status_code=404, detail="原始文件不存在")
        
        # 重新处理文档
        chunks = processor.process_document(str(file_path), filename)
        
        # 更新最终状态
        state_mgr.update_state(
            f"document_{document_id}",
            new_status=StateStatus.COMPLETED,
            new_data={
                "reprocessing_result": {
                    "chunks_count": len(chunks)
                }
            }
        )
        
        logger.info(f"文档重新处理完成: {document_id}")
        
        return {
            "document_id": document_id,
            "filename": filename,
            "chunks_count": len(chunks),
            "status": "completed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新处理文档失败: {e}")
        
        # 更新错误状态
        state_mgr.update_state(
            f"document_{document_id}",
            new_status=StateStatus.FAILED,
            new_data={"error": str(e)}
        )
        
        raise HTTPException(status_code=500, detail=f"重新处理文档失败: {str(e)}")

@router.get("/{document_id}/chunks", summary="获取文档分块")
async def get_document_chunks(
    document_id: str,
    limit: int = Query(100),
    offset: int = Query(0)
):
    """
    获取文档分块内容
    
    Args:
        document_id: 文档ID
        limit: 限制数量
        offset: 偏移量
        
    Returns:
        文档分块列表
    """
    try:
        return {
            "document_id": document_id,
            "chunks": [],
            "count": 0,
            "message": "分块获取功能待完善"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档分块失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档分块失败: {str(e)}")