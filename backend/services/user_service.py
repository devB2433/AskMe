"""用户服务模块"""
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
import secrets
from pathlib import Path

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

@dataclass
class User:
    """用户数据模型"""
    user_id: str
    username: str
    password_hash: str
    name: str
    department: str  # 用户所属部门
    email: Optional[str] = None
    created_at: datetime = None
    last_login: datetime = None
    is_active: bool = True
    tokens: List[str] = None  # 登录token列表
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.tokens is None:
            self.tokens = []

class UserService:
    """用户服务"""
    
    USER_FILE = Path("data/users.json")
    
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
        self.users: Dict[str, User] = {}
        self.token_to_user: Dict[str, str] = {}  # token -> user_id
        self._load_users()
    
    def _load_users(self):
        """从文件加载用户"""
        try:
            if self.USER_FILE.exists():
                with open(self.USER_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for user_data in data.get('users', []):
                    user = User(
                        user_id=user_data['user_id'],
                        username=user_data['username'],
                        password_hash=user_data['password_hash'],
                        name=user_data['name'],
                        department=user_data['department'],
                        email=user_data.get('email'),
                        created_at=datetime.fromisoformat(user_data['created_at']) if user_data.get('created_at') else None,
                        last_login=datetime.fromisoformat(user_data['last_login']) if user_data.get('last_login') else None,
                        is_active=user_data.get('is_active', True),
                        tokens=user_data.get('tokens', [])
                    )
                    self.users[user.user_id] = user
                    self.users[user.username] = user  # 同时用username做索引
                    # 重建token索引
                    for token in user.tokens:
                        self.token_to_user[token] = user.user_id
                print(f"加载了 {len(self.users) // 2} 个用户")
        except Exception as e:
            print(f"加载用户失败: {e}")
    
    def _save_users(self):
        """保存用户到文件"""
        try:
            self.USER_FILE.parent.mkdir(parents=True, exist_ok=True)
            # 只保存user_id索引的数据
            unique_users = {}
            for key, user in self.users.items():
                if user.user_id not in unique_users:
                    unique_users[user.user_id] = user
            
            data = {
                'users': [{
                    'user_id': user.user_id,
                    'username': user.username,
                    'password_hash': user.password_hash,
                    'name': user.name,
                    'department': user.department,
                    'email': user.email,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'is_active': user.is_active,
                    'tokens': user.tokens
                } for user in unique_users.values()]
            }
            with open(self.USER_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户失败: {e}")
    
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
        if username in self.users:
            return {"success": False, "error": "用户名已存在"}
        
        # 验证部门是否有效
        dept_names = [d['name'] for d in DEFAULT_DEPARTMENTS]
        if department not in dept_names:
            return {"success": False, "error": f"无效的部门，可选部门: {', '.join(dept_names)}"}
        
        # 创建用户
        user_id = f"user_{secrets.token_hex(8)}"
        user = User(
            user_id=user_id,
            username=username,
            password_hash=self._hash_password(password),
            name=name,
            department=department,
            email=email
        )
        
        self.users[user_id] = user
        self.users[username] = user
        
        self._save_users()
        
        return {
            "success": True,
            "user": {
                "user_id": user_id,
                "username": username,
                "name": name,
                "department": department
            }
        }
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            登录结果，包含token
        """
        user = self.users.get(username)
        if not user:
            return {"success": False, "error": "用户名或密码错误"}
        
        if not user.is_active:
            return {"success": False, "error": "账户已被禁用"}
        
        if user.password_hash != self._hash_password(password):
            return {"success": False, "error": "用户名或密码错误"}
        
        # 生成token
        token = secrets.token_urlsafe(32)
        user.tokens.append(token)
        self.token_to_user[token] = user.user_id
        user.last_login = datetime.now()
        
        self._save_users()
        
        return {
            "success": True,
            "token": token,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "name": user.name,
                "department": user.department
            }
        }
    
    def logout(self, token: str) -> bool:
        """用户登出"""
        user_id = self.token_to_user.get(token)
        if not user_id:
            return False
        
        user = self.users.get(user_id)
        if user and token in user.tokens:
            user.tokens.remove(token)
            del self.token_to_user[token]
            self._save_users()
        
        return True
    
    def get_user_by_token(self, token: str) -> Optional[User]:
        """通过token获取用户"""
        user_id = self.token_to_user.get(token)
        if user_id:
            return self.users.get(user_id)
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        return self.users.get(user_id)
    
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
