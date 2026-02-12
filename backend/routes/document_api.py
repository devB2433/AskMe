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
from services.config import config
from services.task_queue import task_queue, TaskStage, TaskStatus

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

def get_state_manager():
    """仅获取状态管理器（轻量级，不加载模型）"""
    global state_manager
    if state_manager is None:
        state_manager = StateManager()
    return state_manager

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
                # user可能是字典或对象
                actual_team_id = user.get("department") if isinstance(user, dict) else user.department
                uploaded_by = user.get("username") if isinstance(user, dict) else user.username
        
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
                    "content": c.get("content", "")[:1000],
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


@router.post("/batch", summary="批量上传文档")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    collection_name: str = Form("default_collection"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    enable_metadata: bool = Form(True),
    authorization: Optional[str] = Header(None)
):
    """
    批量上传文档
    
    Args:
        files: 上传的文件列表（最多20个，可通过配置修改）
        collection_name: 集合名称
        chunk_size: 分块大小
        chunk_overlap: 分块重叠
        enable_metadata: 是否启用元数据提取
        authorization: 用户token
        
    Returns:
        批量上传结果，包含任务ID列表
    """
    max_batch_size = config.get("upload.max_batch_size", 20)
    
    if len(files) > max_batch_size:
        raise HTTPException(
            status_code=400, 
            detail=f"批量上传数量超限：最多{max_batch_size}个文件，当前{len(files)}个"
        )
    
    # 获取用户信息
    actual_team_id = "default"
    uploaded_by = "anonymous"
    
    if authorization:
        from services.user_service import user_service
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        user = user_service.get_user_by_token(token)
        if user:
            actual_team_id = user.get("department") if isinstance(user, dict) else user.department
            uploaded_by = user.get("username") if isinstance(user, dict) else user.username
    
    # 注册文档处理任务处理器
    def process_document_task(task):
        """处理文档任务"""
        try:
            processor, milvus, encoder, state_mgr = get_services()
            task_data = task.data
            
            # 更新进度：解析中
            task_queue.update_progress(
                task.task_id, TaskStage.PARSING, 10, 100, "正在解析文档..."
            )
            
            # 处理文档
            chunks = processor.process_document(
                task_data["file_path"], 
                task_data["filename"]
            )
            
            # 更新进度：分块完成
            task_queue.update_progress(
                task.task_id, TaskStage.CHUNKING, 30, 100, 
                f"文档分块完成，共{len(chunks)}个分块"
            )
            
            # 保存解析后的文本内容
            import json
            upload_dir = Path("uploads")
            text_content_path = upload_dir / f"{task_data['document_id']}_content.json"
            with open(text_content_path, "w", encoding="utf-8") as f:
                json.dump({
                    "filename": task_data["filename"],
                    "chunks": chunks,
                    "full_text": "\n".join([c.get("content", "") for c in chunks])
                }, f, ensure_ascii=False, indent=2)
            
            # 更新进度：向量化中
            task_queue.update_progress(
                task.task_id, TaskStage.EMBEDDING, 50, 100, "正在进行向量化..."
            )
            
            # 向量编码和存储
            vector_stored = False
            try:
                chunk_texts = [c.get("content", "") for c in chunks]
                vectors = encoder.encode_batch(chunk_texts)
                
                # 更新进度：存储中
                task_queue.update_progress(
                    task.task_id, TaskStage.STORING, 80, 100, "正在存储向量..."
                )
                
                # 存储到Milvus
                import time
                collection_name_actual = "askme_documents"
                chunk_ids = milvus.insert_vectors(
                    collection_name=collection_name_actual,
                    vectors=vectors,
                    documents=[{
                        "document_id": task_data["document_id"],
                        "team_id": task_data["team_id"],
                        "chunk_id": f"{task_data['document_id']}_{i}",
                        "content": c.get("content", "")[:1000],
                        "metadata": {"chunk_index": i},
                        "created_at": int(time.time())
                    } for i, c in enumerate(chunks)]
                )
                
                # 更新进度：存储完成
                task_queue.update_progress(
                    task.task_id, TaskStage.STORING, 100, 100, "向量存储完成"
                )
                
                logger.info(f"向量化存储完成: {len(chunk_ids)} 个向量")
                vector_stored = True
            except Exception as e:
                logger.warning(f"向量存储失败: {e}")
            
            # 插入文档记录到数据库
            db.execute(
                """INSERT INTO documents 
                   (id, filename, content_type, team_id, uploaded_by, status, chunks_count, vector_stored, file_size, file_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_data["document_id"], 
                    task_data["filename"], 
                    task_data["content_type"],
                    task_data["team_id"], 
                    task_data["uploaded_by"],
                    'completed', 
                    len(chunks), 
                    1 if vector_stored else 0, 
                    task_data["file_size"], 
                    task_data["file_hash"]
                )
            )
            db.conn.commit()
            
            return {
                "document_id": task_data["document_id"],
                "filename": task_data["filename"],
                "chunks_count": len(chunks),
                "vector_stored": vector_stored,
                "team_id": task_data["team_id"]
            }
            
        except Exception as e:
            logger.error(f"任务处理失败: {e}")
            raise
    
    # 注册处理器
    task_queue.register_handler("document_upload", process_document_task)
    
    # 提交任务
    tasks = []
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    
    # 当前批次已处理的哈希（用于检测同批次重复）
    batch_hashes = {}
    
    for file in files:
        try:
            # 读取文件内容并计算哈希
            content = await file.read()
            file_hash = hashlib.md5(content).hexdigest()
            file_size = len(content)
            
            # 重置文件指针
            await file.seek(0)
            
            # 检查当前批次是否已处理过相同文件
            if file_hash in batch_hashes:
                tasks.append({
                    "success": False,
                    "filename": file.filename,
                    "error": f"文件已存在: {batch_hashes[file_hash]}",
                    "duplicate": True
                })
                continue
            
            # 检查文件哈希是否已存在数据库中
            existing_doc = db.fetchone(
                "SELECT id, filename FROM documents WHERE file_hash = ?",
                (file_hash,)
            )
            
            if existing_doc:
                tasks.append({
                    "success": False,
                    "filename": file.filename,
                    "error": f"文件已存在: {existing_doc['filename']}",
                    "duplicate": True
                })
                continue
            
            # 记录当前批次的哈希
            batch_hashes[file_hash] = file.filename
            
            # 生成文档ID
            document_id = f"doc_{uuid.uuid4().hex[:12]}"
            
            # 保存文件
            file_path = upload_dir / f"{document_id}_{file.filename}"
            with open(file_path, "wb") as buffer:
                buffer.write(content)
            
            # 提交任务到队列
            task = task_queue.submit_task(
                task_type="document_upload",
                filename=file.filename,
                data={
                    "document_id": document_id,
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "file_path": str(file_path),
                    "team_id": actual_team_id,
                    "uploaded_by": uploaded_by,
                    "file_size": file_size,
                    "file_hash": file_hash
                }
            )
            
            tasks.append({
                "success": True,
                "filename": file.filename,
                "task_id": task.task_id,
                "document_id": document_id
            })
            
        except Exception as e:
            tasks.append({
                "success": False,
                "filename": file.filename,
                "error": str(e)
            })
    
    return {
        "total": len(files),
        "submitted": sum(1 for t in tasks if t.get("success")),
        "duplicates": sum(1 for t in tasks if t.get("duplicate")),
        "tasks": tasks,
        "queue_status": task_queue.get_queue_status()
    }


@router.get("/tasks", summary="获取任务列表")
async def get_tasks(
    status: Optional[str] = Query(None),
    limit: int = Query(20)
):
    """
    获取任务列表
    
    Args:
        status: 状态过滤
        limit: 返回数量限制
        
    Returns:
        任务列表
    """
    status_enum = None
    if status:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            pass
    
    tasks = task_queue.get_all_tasks(status_enum)
    return {
        "tasks": [t.to_dict() for t in tasks[:limit]],
        "queue_status": task_queue.get_queue_status()
    }


@router.get("/tasks/{task_id}", summary="获取任务详情")
async def get_task(task_id: str):
    """
    获取任务详情
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务详情
    """
    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task.to_dict()


@router.get("/config", summary="获取上传配置")
async def get_upload_config():
    """获取上传相关配置"""
    return {
        "max_batch_size": config.get("upload.max_batch_size"),
        "max_file_size_mb": config.get("upload.max_file_size_mb"),
        "allowed_extensions": config.get("upload.allowed_extensions"),
        "concurrent_uploads": config.get("upload.concurrent_uploads")
    }

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
        state_mgr = get_state_manager()
        
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
        # 从SQLite数据库获取文档列表
        query = "SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params = [limit, offset]
        
        if status:
            query = "SELECT * FROM documents WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = [status, limit, offset]
        
        docs = db.fetchall(query, tuple(params))
        
        # 获取总数
        count_query = "SELECT COUNT(*) as total FROM documents"
        count_params = ()
        if status:
            count_query = "SELECT COUNT(*) as total FROM documents WHERE status = ?"
            count_params = (status,)
        
        total_result = db.fetchone(count_query, count_params)
        total = total_result['total'] if total_result else 0
        
        documents = []
        for doc in docs:
            doc_dict = dict(doc)  # 转换为普通字典
            documents.append({
                "document_id": doc_dict.get('id', ''),
                "status": doc_dict.get('status', 'pending'),
                "filename": doc_dict.get('filename', ''),
                "collection_name": doc_dict.get('collection_name', 'default'),
                "chunks_count": doc_dict.get('chunks_count', 0),
                "team_id": doc_dict.get('team_id', 'default'),
                "uploaded_by": doc_dict.get('uploaded_by', ''),
                "created_at": doc_dict.get('created_at', ''),
                "updated_at": doc_dict.get('updated_at', doc_dict.get('created_at', ''))
            })
        
        return {
            "documents": documents,
            "total": total,
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
        state_mgr = get_state_manager()
        _, milvus, _, _ = get_services()
        
        # 检查文档是否存在
        doc = db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 删除向量数据
        try:
            milvus.delete_vectors_by_document_id("askme_documents", document_id)
            logger.info(f"已删除向量数据: {document_id}")
        except Exception as e:
            logger.warning(f"删除向量数据失败: {e}")
        
        # 删除数据库记录
        db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        db.conn.commit()
        
        # 删除状态记录
        state_mgr.delete_state(f"document_{document_id}")
        
        # 删除上传文件
        upload_dir = Path("uploads")
        for file_path in upload_dir.glob(f"{document_id}_*"):
            if file_path.exists():
                file_path.unlink()
                logger.info(f"已删除文件: {file_path}")
        
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
        processor, milvus, encoder, state_mgr = get_services()
        
        # 检查文档是否存在
        doc = db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        filename = doc.get("filename", "")
        
        # 查找上传文件
        upload_dir = Path("uploads")
        file_path = None
        for uploaded_file in upload_dir.glob(f"{document_id}_*"):
            if uploaded_file.exists() and not uploaded_file.name.endswith("_content.json"):
                file_path = uploaded_file
                break
        
        if not file_path:
            raise HTTPException(status_code=404, detail="原始文件不存在")
        
        # 删除旧向量数据
        try:
            milvus.delete_vectors_by_document_id("askme_documents", document_id)
        except Exception as e:
            logger.warning(f"删除旧向量失败: {e}")
        
        # 重新处理文档
        chunks = processor.process_document(str(file_path), filename)
        
        # 向量化并存储
        if chunks:
            chunk_texts = [c.get("content", "") for c in chunks if c.get("content")]
            if chunk_texts:
                vectors = encoder.encode_batch(chunk_texts)
                import time
                milvus.insert_vectors(
                    collection_name="askme_documents",
                    vectors=vectors,
                    documents=[{
                        "document_id": document_id,
                        "team_id": doc.get("team_id", "default"),
                        "chunk_id": f"{document_id}_{i}",
                        "content": c.get("content", "")[:1000],
                        "metadata": {"chunk_index": i},
                        "created_at": int(time.time())
                    } for i, c in enumerate(chunks)]
                )
        
        # 更新数据库记录
        db.execute(
            "UPDATE documents SET chunks_count = ?, status = 'completed' WHERE id = ?",
            (len(chunks), document_id)
        )
        db.conn.commit()
        
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