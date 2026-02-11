"""用户API路由"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from pydantic import BaseModel
import logging

from services.user_service import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])

# 请求模型
class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str
    department: str
    email: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# 响应模型
class UserResponse(BaseModel):
    user_id: str
    username: str
    name: str
    department: str

class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[UserResponse] = None
    error: Optional[str] = None

# 认证依赖
async def get_current_user(authorization: Optional[str] = Header(None)):
    """获取当前登录用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    
    # 支持 Bearer token 格式
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    user = user_service.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    
    return user

@router.post("/register", summary="用户注册")
async def register(request: RegisterRequest):
    """
    用户注册
    
    - username: 用户名（唯一）
    - password: 密码
    - name: 姓名
    - department: 部门名称
    - email: 邮箱（可选）
    """
    result = user_service.register(
        username=request.username,
        password=request.password,
        name=request.name,
        department=request.department,
        email=request.email
    )
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return {"success": True, "user": result['user']}

@router.post("/login", summary="用户登录")
async def login(request: LoginRequest):
    """
    用户登录
    
    返回token用于后续API认证
    """
    result = user_service.login(
        username=request.username,
        password=request.password
    )
    
    if not result['success']:
        raise HTTPException(status_code=401, detail=result['error'])
    
    return {
        "success": True,
        "token": result['token'],
        "user": result['user']
    }

@router.post("/logout", summary="用户登出")
async def logout(authorization: Optional[str] = Header(None)):
    """用户登出"""
    if authorization:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        user_service.logout(token)
    return {"success": True}

@router.get("/me", summary="获取当前用户信息")
async def get_me(user = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "name": user.name,
        "department": user.department,
        "email": user.email
    }

@router.get("/departments", summary="获取部门列表")
async def get_departments():
    """获取所有部门列表"""
    return {"departments": user_service.get_departments()}

@router.get("/departments/suggest", summary="部门名称提示")
async def suggest_departments(q: str = ""):
    """
    部门名称提示
    
    - q: 搜索前缀
    """
    return {"departments": user_service.suggest_departments(q)}
