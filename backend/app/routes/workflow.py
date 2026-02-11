from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from models.database import get_db
from services.workflow_service import WorkflowService

router = APIRouter()

class WorkflowRequest(BaseModel):
    workflow_type: str
    input_data: dict

class WorkflowResponse(BaseModel):
    id: int
    workflow_type: str
    status: str
    output_data: dict

@router.post("/execute", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowRequest,
    db: Session = Depends(get_db)
):
    """执行业务工作流"""
    workflow_service = WorkflowService()
    
    try:
        result = await workflow_service.execute_workflow(
            workflow_type=request.workflow_type,
            input_data=request.input_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {str(e)}")

@router.get("/instances")
async def list_workflow_instances(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """列出工作流实例"""
    workflow_service = WorkflowService()
    return await workflow_service.list_instances(skip=skip, limit=limit)

@router.get("/instances/{instance_id}")
async def get_workflow_instance(
    instance_id: int,
    db: Session = Depends(get_db)
):
    """获取工作流实例详情"""
    workflow_service = WorkflowService()
    instance = await workflow_service.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="工作流实例不存在")
    return instance

@router.get("/types")
async def list_workflow_types():
    """列出可用的工作流类型"""
    workflow_service = WorkflowService()
    return await workflow_service.list_available_workflows()