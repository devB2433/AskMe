"""FastAPI主应用"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
import json
from pathlib import Path

# 导入路由模块
from routes.document_api import router as document_router
from routes.search_api import router as search_router
from routes.user_api import router as user_router
from routes.websocket_api import router as websocket_router
from services.embedding_encoder import EmbeddingEncoder
from services.milvus_integration import MilvusClient
from services.state_manager import StateManager, StateType, StateStatus
from services.task_queue import init_tasks_table

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def rebuild_vector_index():
    """重建向量索引"""
    try:
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return 0
        
        # 查找所有内容文件
        content_files = list(upload_dir.glob("*_content.json"))
        if not content_files:
            return 0
        
        logger.info(f"发现 {len(content_files)} 个文档需要重建索引")
        
        encoder = EmbeddingEncoder()
        milvus = MilvusClient()
        state_mgr = StateManager()
        
        # 创建集合 - 使用encoder的维度
        collection_name = "askme_documents"
        collection = milvus.create_collection(
            collection_name=collection_name,
            dimension=encoder.model.get_sentence_embedding_dimension(),
            auto_id=True,
            description="AskMe文档向量存储"
        )
        
        # 按文件名去重，只保留最新的
        seen_filenames = {}
        for content_file in content_files:
            try:
                with open(content_file, "r", encoding="utf-8") as f:
                    content_data = json.load(f)
                filename = content_data.get("filename", "")
                if filename and filename not in seen_filenames:
                    seen_filenames[filename] = content_file
            except:
                pass
        
        logger.info(f"去重后 {len(seen_filenames)} 个唯一文档")
        
        rebuilt_count = 0
        for filename, content_file in seen_filenames.items():
            try:
                # 提取document_id
                doc_id = content_file.stem.replace("_content", "")
                
                with open(content_file, "r", encoding="utf-8") as f:
                    content_data = json.load(f)
                
                chunks = content_data.get("chunks", [])
                
                if not chunks:
                    continue
                
                # 向量编码
                chunk_texts = [c.get("content", "") for c in chunks if c.get("content")]
                if not chunk_texts:
                    continue
                
                vectors = encoder.encode_batch(chunk_texts)
                
                # 存储到Milvus
                milvus.insert_vectors(
                    collection_name=collection_name,
                    vectors=vectors,
                    documents=[{
                        "document_id": doc_id,
                        "chunk_id": f"{doc_id}_{i}",
                        "content": c[:500],
                        "metadata": {"chunk_index": i}
                    } for i, c in enumerate(chunk_texts)]
                )
                
                # 恢复或更新状态记录
                existing_states = state_mgr.query_states(entity_id=doc_id)
                if existing_states:
                    # 更新已有状态的分块数
                    state_mgr.update_state(
                        existing_states[0].state_id,
                        new_data={
                            "processing_result": {
                                "chunks_count": len(chunk_texts),
                                "vector_stored": True
                            }
                        }
                    )
                else:
                    state_mgr.create_state(
                        state_type=StateType.DOCUMENT,
                        entity_id=doc_id,
                        initial_data={
                            "filename": filename,
                            "processing_result": {
                                "chunks_count": len(chunk_texts),
                                "vector_stored": True
                            }
                        },
                        initial_status=StateStatus.COMPLETED
                    )
                
                rebuilt_count += 1
                logger.info(f"重建索引: {filename}")
                
            except Exception as e:
                logger.warning(f"重建索引失败 {content_file}: {e}")
        
        return rebuilt_count
        
    except Exception as e:
        logger.error(f"重建索引失败: {e}")
        return 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("启动AskMe知识库系统...")
    
    # 保存事件循环引用到任务队列
    import asyncio
    from services.task_queue import task_queue
    task_queue.set_event_loop(asyncio.get_running_loop())
    
    # 初始化服务
    try:
        # 检查向量索引是否存在，不存在则重建
        milvus = MilvusClient()
        collection_name = "askme_documents"
        
        from pymilvus import utility
        if not utility.has_collection(collection_name):
            logger.info("向量索引不存在，开始重建...")
            rebuilt = rebuild_vector_index()
            logger.info(f"重建完成，共 {rebuilt} 个文档")
        else:
            logger.info("向量索引已存在")
        
        # 初始化任务队列表
        init_tasks_table()
        
        logger.info("服务初始化完成")
    except Exception as e:
        logger.error(f"服务初始化失败: {e}")
        raise
    
    yield
    
    # 关闭时执行
    logger.info("关闭AskMe知识库系统...")
    # 清理资源

# 创建FastAPI应用
app = FastAPI(
    title="AskMe 知识库系统 API",
    description="基于RAG的智能文档问答系统API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(document_router)
app.include_router(search_router)
app.include_router(user_router)
app.include_router(websocket_router)

@app.get("/", summary="API根路径")
async def root():
    """API根路径"""
    return {
        "message": "欢迎使用AskMe知识库系统API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

@app.get("/health", summary="健康检查")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": "2026-02-11T10:00:00Z",
        "services": {
            "database": "connected",
            "vector_store": "ready",
            "document_processor": "available"
        }
    }

@app.get("/api/info", summary="API信息")
async def api_info():
    """获取API信息"""
    return {
        "title": "AskMe 知识库系统 API",
        "version": "1.0.0",
        "description": "基于RAG的智能文档问答系统",
        "endpoints": {
            "documents": "/api/documents",
            "search": "/api/search",
            "qa": "/api/qa",
            "workflows": "/api/workflows"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }

# 系统配置存储
SYSTEM_CONFIG = {
    "embedding_model": "BAAI/bge-large-zh-v1.5",
    "chunk_size": 400,
    "chunk_overlap": 100,
    "top_k": 10,
    "search_ef": 256,
    "content_store_length": 1000,
    "enable_ocr": True
}

@app.get("/api/config", summary="获取系统配置")
async def get_config():
    """获取系统配置"""
    return SYSTEM_CONFIG

@app.post("/api/config", summary="保存系统配置")
async def save_config(config: dict):
    """保存系统配置"""
    global SYSTEM_CONFIG
    SYSTEM_CONFIG.update(config)
    return {"success": True, "config": SYSTEM_CONFIG}

# 错误处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}")
    return HTTPException(status_code=500, detail=str(exc))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )