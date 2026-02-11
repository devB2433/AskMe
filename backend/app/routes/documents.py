from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os
from pathlib import Path

from app.config import settings
from models.database import get_db
from models.models import Document
from services.document_processor import DocumentProcessor

router = APIRouter()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传文档"""
    # 验证文件大小
    if file.size > settings.MAX_DOCUMENT_SIZE:
        raise HTTPException(status_code=400, detail="文件过大")
    
    # 创建上传目录
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)
    
    # 保存文件
    file_path = upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # 创建文档记录
    db_document = Document(
        filename=file.filename,
        file_path=str(file_path),
        file_size=file.size,
        mime_type=file.content_type or "application/octet-stream"
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    # 异步处理文档
    processor = DocumentProcessor()
    await processor.process_document_async(db_document.id)
    
    return {"message": "文档上传成功", "document_id": db_document.id}

@router.get("/{document_id}")
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """获取文档信息"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document

@router.get("/")
async def list_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """列出所有文档"""
    documents = db.query(Document).offset(skip).limit(limit).all()
    return documents

@router.delete("/{document_id}")
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """删除文档"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 删除物理文件
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    # 删除数据库记录
    db.delete(document)
    db.commit()
    
    return {"message": "文档删除成功"}