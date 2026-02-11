from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from models.database import get_db
from services.search_service import SearchService

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    search_type: str = "hybrid"  # keyword, semantic, hybrid
    top_k: int = 10
    filters: Optional[dict] = None

class SearchResultResponse(BaseModel):
    id: int
    content: str
    score: float
    document_id: int
    document_name: str
    metadata: dict

@router.post("/search", response_model=List[SearchResultResponse])
async def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """搜索文档"""
    search_service = SearchService()
    
    try:
        results = await search_service.search(
            query=request.query,
            search_type=request.search_type,
            top_k=request.top_k,
            filters=request.filters
        )
        
        # 保存搜索历史
        await search_service.save_search_history(
            query=request.query,
            search_type=request.search_type,
            results=results
        )
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@router.get("/recent-searches")
async def get_recent_searches(limit: int = 10, db: Session = Depends(get_db)):
    """获取最近搜索历史"""
    search_service = SearchService()
    return await search_service.get_recent_searches(limit=limit)