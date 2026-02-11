from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    status = Column(String(50), default="uploaded")  # uploaded, processing, processed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    chunks = relationship("DocumentChunk", back_populates="document")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text)  # 存储向量的JSON字符串
    chunk_metadata = Column(Text)   # 存储元数据的JSON字符串
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联关系
    document = relationship("Document", back_populates="chunks")

class SearchResult(Base):
    __tablename__ = "search_results"
    
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False)
    result_type = Column(String(50), nullable=False)  # keyword, semantic, hybrid
    results = Column(Text)  # 存储搜索结果的JSON字符串
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    input_data = Column(Text)  # 输入数据的JSON字符串
    output_data = Column(Text)  # 输出数据的JSON字符串
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)