# AskMe 知识库系统

## 项目概述
这是一个完全本地化的知识库管理系统，支持文档解析、向量化存储、智能检索和业务工作流处理。

## 系统架构
四层架构设计：
1. 展示层：React Web界面
2. 数据处理层：文档解析与预处理
3. 向量化与检索层：Milvus + Elasticsearch
4. 业务工作流层：自定义流程引擎

## 技术栈
- **后端**：Python 3.10+ + FastAPI
- **前端**：React 18 + TypeScript + Ant Design
- **数据库**：PostgreSQL + Redis
- **向量存储**：Milvus
- **搜索引擎**：Elasticsearch
- **文档处理**：unstructured + GLM-OCR
- **嵌入模型**：sentence-transformers

## 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone <repository-url>
cd AskMe

# 安装依赖
pip install -r requirements.txt
npm install
```

### 2. 启动基础设施
```bash
# 启动所有服务
docker-compose up -d

# 检查服务状态
docker-compose ps
```

### 3. 初始化数据库
```bash
# 运行数据库迁移
python backend/scripts/init_db.py
```

### 4. 启动应用
```bash
# 启动后端服务
cd backend
uvicorn app.main:app --reload --port 8000

# 启动前端开发服务器
cd frontend
npm run dev
```

## 目录结构
```
AskMe/
├── backend/           # 后端服务
│   ├── app/          # 主应用代码
│   ├── models/       # 数据模型
│   ├── services/     # 业务服务
│   └── utils/        # 工具函数
├── frontend/         # 前端应用
│   ├── src/         # 源代码
│   ├── public/      # 静态资源
│   └── components/  # 组件库
├── scripts/         # 脚本工具
└── docs/           # 文档
```

## 开发指南
详见 [开发文档](docs/development.md)

## 部署说明
详见 [部署文档](docs/deployment.md)