"""用户服务模块 - SQLite版本"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import secrets
import logging

from services.database import db

logger = logging.getLogger(__name__)

# 预定义部门列表
DEFAULT_DEPARTMENTS = [
    {"id": "dev", "name": "研发部", "description": "产品研发团队"},
    {"id": "test", "name": "测试部", "description": "质量保障团队"},
    {"id": "sec", "name": "安全部", "description": "安全团队"},
    {"id": "ops", "name": "运维部", "description": "运维团队"},
    {"id": "product", "name": "产品部", "description": "产品团队"},
    {"id": "hr", "name": "人力资源部", "description": "HR团队"},
    {"id": "finance", "name": "财务部", "description": "财务团队"},
    {"id": "legal", "name": "法务部", "description": "法务团队"},
]


class UserService:
    """用户服务 - SQLite版本"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # 数据库在导入时已初始化
        logger.info("UserService初始化完成（SQLite模式）")
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register(self, username: str, password: str, name: str, department: str, email: str = None) -> Dict[str, Any]:
        """
        用户注册
        
        Args:
            username: 用户名
            password: 密码
            name: 姓名
            department: 部门
            email: 邮箱（可选）
            
        Returns:
            注册结果
        """
        # 检查用户名是否已存在
        existing = db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            return {"success": False, "error": "用户名已存在"}
        
        # 验证部门是否有效
        dept_names = [d['name'] for d in DEFAULT_DEPARTMENTS]
        if department not in dept_names:
            return {"success": False, "error": f"无效的部门，可选部门: {', '.join(dept_names)}"}
        
        # 创建用户
        user_id = f"user_{secrets.token_hex(8)}"
        
        try:
            db.execute(
                """INSERT INTO users (id, username, password_hash, name, department, email, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, self._hash_password(password), name, department, email, datetime.now())
            )
            db.conn.commit()
            
            logger.info(f"用户注册成功: {username}")
            
            return {
                "success": True,
                "user": {
                    "user_id": user_id,
                    "username": username,
                    "name": name,
                    "department": department
                }
            }
        except Exception as e:
            logger.error(f"用户注册失败: {e}")
            return {"success": False, "error": str(e)}
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            登录结果，包含token
        """
        user = db.fetchone(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )
        
        if not user:
            return {"success": False, "error": "用户名或密码错误"}
        
        if not user['is_active']:
            return {"success": False, "error": "账户已被禁用"}
        
        if user['password_hash'] != self._hash_password(password):
            return {"success": False, "error": "用户名或密码错误"}
        
        # 生成token
        token = secrets.token_urlsafe(32)
        
        try:
            # 保存token
            db.execute(
                "INSERT INTO user_tokens (user_id, token, created_at) VALUES (?, ?, ?)",
                (user['id'], token, datetime.now())
            )
            # 更新最后登录时间
            db.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now(), user['id'])
            )
            db.conn.commit()
            
            logger.info(f"用户登录成功: {username}")
            
            return {
                "success": True,
                "token": token,
                "user": {
                    "user_id": user['id'],
                    "username": user['username'],
                    "name": user['name'],
                    "department": user['department']
                }
            }
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return {"success": False, "error": "登录失败"}
    
    def logout(self, token: str) -> bool:
        """用户登出"""
        try:
            db.execute("DELETE FROM user_tokens WHERE token = ?", (token,))
            db.conn.commit()
            return True
        except Exception as e:
            logger.error(f"登出失败: {e}")
            return False
    
    def get_user_by_token(self, token: str) -> Optional[Dict]:
        """通过token获取用户"""
        result = db.fetchone(
            """SELECT u.* FROM users u 
               JOIN user_tokens t ON u.id = t.user_id 
               WHERE t.token = ?""",
            (token,)
        )
        if result:
            return {
                'user_id': result['id'],
                'username': result['username'],
                'name': result['name'],
                'department': result['department'],
                'email': result['email'],
                'is_active': result['is_active']
            }
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """通过ID获取用户"""
        result = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        if result:
            return {
                'user_id': result['id'],
                'username': result['username'],
                'name': result['name'],
                'department': result['department'],
                'email': result['email']
            }
        return None
    
    def get_departments(self) -> List[Dict[str, str]]:
        """获取所有部门列表"""
        return DEFAULT_DEPARTMENTS
    
    def suggest_departments(self, query: str = "") -> List[Dict[str, str]]:
        """
        部门名称提示
        
        Args:
            query: 搜索前缀
            
        Returns:
            匹配的部门列表
        """
        if not query:
            return DEFAULT_DEPARTMENTS
        
        query_lower = query.lower()
        return [
            dept for dept in DEFAULT_DEPARTMENTS
            if query_lower in dept['name'].lower() or query_lower in dept['id'].lower()
        ]


# 全局实例
user_service = UserService()
