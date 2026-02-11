"""环境验证脚本"""
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print(f"项目根目录: {project_root}")

try:
    from app.config import settings
    print("✓ 配置模块加载成功")
    print(f"数据库URL: {settings.DATABASE_URL}")
except Exception as e:
    print(f"✗ 配置模块加载失败: {e}")

try:
    from models.database import engine
    print("✓ 数据库连接模块加载成功")
except Exception as e:
    print(f"✗ 数据库连接模块加载失败: {e}")

try:
    from services.document_processor import DocumentProcessor
    print("✓ 文档处理模块加载成功")
except Exception as e:
    print(f"✗ 文档处理模块加载失败: {e}")

try:
    from services.search_service import SearchService
    print("✓ 搜索服务模块加载成功")
except Exception as e:
    print(f"✗ 搜索服务模块加载失败: {e}")

try:
    from services.workflow_service import WorkflowService
    print("✓ 工作流服务模块加载成功")
except Exception as e:
    print(f"✗ 工作流服务模块加载失败: {e}")

print("\n=== 环境验证完成 ===")