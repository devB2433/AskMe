from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routes import documents, search, workflow

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    print("Starting AskMe backend service...")
    yield
    # 关闭时执行
    print("Shutting down AskMe backend service...")

app = FastAPI(
    title="AskMe Knowledge Base API",
    description="本地化知识库管理系统API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["workflow"])

@app.get("/")
async def root():
    return {"message": "AskMe Knowledge Base API", "version": "0.1.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}