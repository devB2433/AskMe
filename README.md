# AskMe 知识库系统

一个完全本地化的企业知识库管理系统，支持文档解析、向量化存储、语义检索和部门级权限控制。

## 功能特性

- **文档管理**：支持 PDF、Word、Excel、PPT 等多种格式文档上传
- **批量上传**：支持多文件同时上传，实时显示处理进度
- **语义搜索**：基于向量相似度的智能检索，支持中文语义理解
- **部门隔离**：按部门隔离知识库，支持部门级搜索语法
- **用户认证**：本地用户管理，支持部门归属

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Ant Design |
| 后端 | Python 3.10 + FastAPI |
| 数据库 | SQLite |
| 向量存储 | Milvus 2.4 |
| 嵌入模型 | BAAI/bge-large-zh-v1.5 (1024维) |
| 文档解析 | unstructured |

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/devB2433/AskMe.git
cd AskMe

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
```

### 2. 启动基础设施

```bash
# 启动 Milvus 向量数据库
docker-compose up -d
```

### 3. 启动应用

```bash
# 启动后端服务 (端口 8001)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8001

# 启动前端服务 (端口 5173)
cd frontend
npm run dev
```

### 4. 访问系统

打开浏览器访问 http://localhost:5173

## 搜索语法

| 语法 | 说明 |
|------|------|
| `关键词` | 在当前用户部门的知识库中搜索 |
| `/部门名 关键词` | 在指定部门的知识库中搜索 |

示例：
- `安全规范` - 搜索本部门的安全规范相关文档
- `/研发部 API设计` - 搜索研发部的API设计相关文档

## 目录结构

```
AskMe/
├── backend/
│   ├── main.py              # 应用入口
│   ├── routes/              # API路由
│   │   ├── document_api.py  # 文档上传、管理
│   │   ├── search_api.py    # 搜索接口
│   │   ├── user_api.py      # 用户认证
│   │   └── websocket_api.py # 实时推送
│   ├── services/            # 业务服务
│   │   ├── embedding_encoder.py  # 向量编码
│   │   ├── milvus_integration.py # 向量存储
│   │   ├── document_processor.py # 文档解析
│   │   └── task_queue.py         # 任务队列
│   └── data/                # 数据存储
├── frontend/
│   └── src/
│       └── components/      # React组件
│           ├── Login.tsx          # 登录页
│           ├── SearchInterface.tsx # 搜索页
│           ├── DocumentUpload.tsx  # 文档上传
│           └── DocumentList.tsx    # 文档管理
├── docker-compose.yml       # Milvus服务配置
└── requirements.txt         # Python依赖
```

## 配置说明

### 分块配置
- 分块大小：400 字符
- 分块重叠：100 字符

### 向量索引
- 索引类型：HNSW
- 相似度度量：COSINE
- 搜索精度(ef)：256

## 开发

```bash
# 运行后端开发服务器
cd backend
uvicorn main:app --reload --port 8001

# 运行前端开发服务器
cd frontend
npm run dev
```

## 许可证

MIT License