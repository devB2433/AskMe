"""数据库初始化脚本"""
import asyncio
from sqlalchemy import create_engine
from app.config import settings
from models.database import Base

async def init_database():
    """初始化数据库表结构"""
    print("开始初始化数据库...")
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    print("数据库初始化完成!")

if __name__ == "__main__":
    asyncio.run(init_database())