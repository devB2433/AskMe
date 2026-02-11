# AskMe 项目结构说明

## 整体架构
```
AskMe/
├── backend/                # 后端服务 (Python + FastAPI)
│   ├── app/               # 主应用目录
│   │   ├── main.py       # 应用入口点
│   │   ├── config.py     # 配置管理
│   │   └── routes/       # API路由
│   │       ├── documents.py  # 文档管理API
│   │       ├── search.py     # 搜索API
│   │       └── workflow.py   # 工作流API
│   ├── models/            # 数据模型
│   │   ├── database.py   # 数据库连接
│   │   └── models.py     # ORM模型定义
│   ├── services/          # 业务服务层
│   │   ├── document_processor.py  # 文档处理服务
│   │   ├── search_service.py      # 搜索服务
│   │   └── workflow_service.py    # 工作流服务
│   ├── utils/             # 工具函数
│   └── scripts/           # 脚本工具
│       └── init_db.py    # 数据库初始化脚本
├── frontend/              # 前端应用 (React + TypeScript)
│   ├── src/              # 源代码
│   │   ├── main.tsx      # 应用入口
│   │   ├── App.tsx       # 主应用组件
│   │   └── index.css     # 全局样式
│   ├── components/        # React组件
│   │   ├── DocumentUpload.tsx     # 文档上传组件
│   │   ├── SearchInterface.tsx    # 搜索界面组件
│   │   ├── DocumentList.tsx       # 文档列表组件
│   │   └── Settings.tsx           # 设置组件
│   ├── public/            # 静态资源
│   ├── vite.config.ts    # Vite配置
│   └── tsconfig.json     # TypeScript配置
├── scripts/               # 项目脚本
│   ├── init.sh           # Linux初始化脚本
│   ├── init.bat          # Windows初始化脚本
│   └── check_env.py      # 环境检查脚本
├── docker-compose.yml     # Docker编排文件
├── requirements.txt       # Python依赖
├── package.json          # Node.js依赖
├── .env.example          # 环境变量模板
├── README.md             # 项目说明
└── STARTUP.md            # 启动指南
```

## 四层架构详解

### 1. 展示层 (前端)
- **技术栈**: React 18 + TypeScript + Ant Design
- **主要功能**:
  - 文档上传界面
  - 搜索交互界面
  - 文档管理面板
  - 系统设置页面
- **特点**: 响应式设计，支持多端访问

### 2. 数据处理层
- **核心技术**: unstructured + GLM-OCR
- **处理能力**:
  - PDF、Word、PPT、Excel等办公文档
  - TXT、Markdown等文本文件
  - JPG、PNG等图片文件（通过OCR）
- **输出格式**: 结构化文本块，便于后续处理

### 3. 向量化与检索层
- **向量存储**: Milvus（Zilliz开源版）
- **嵌入模型**: sentence-transformers/all-MiniLM-L6-v2
- **搜索引擎**: Elasticsearch（关键词搜索）
- **检索策略**: 混合搜索（语义+关键词）

### 4. 业务工作流层
- **工作流类型**:
  - 文档问答（document_qa）
  - 知识抽取（knowledge_extraction）
  - 文档摘要（summarization）
  - 多轮对话（multi_turn_chat）
- **执行引擎**: 自研轻量级工作流引擎

## 核心服务说明

### DocumentProcessor (文档处理器)
负责将各种格式的文档转换为结构化文本：
- 支持40+种文档格式
- 自动分块处理大文档
- 集成GLM-OCR处理图片文字
- 保持原文档结构信息

### SearchService (搜索服务)
提供多种搜索能力：
- 语义搜索：基于向量相似度
- 关键词搜索：基于倒排索引
- 混合搜索：结合两种搜索方式
- 搜索历史记录和统计

### WorkflowService (工作流服务)
管理不同场景的业务流程：
- 可扩展的工作流框架
- 异步任务执行
- 状态跟踪和监控
- 错误处理和重试机制

## 数据流向
```
用户上传文档 → 文档处理器 → 文本分块 → 向量编码 → Milvus存储
     ↓
用户发起搜索 → 搜索服务 → 向量检索 + 关键词检索 → 结果融合 → 返回用户
     ↓
用户选择工作流 → 工作流引擎 → 调用相关服务 → 生成结果 → 返回用户
```

## 部署架构
- **容器化**: 所有服务通过Docker部署
- **服务发现**: Docker Compose管理服务间通信
- **数据持久化**: 各服务使用独立的数据卷
- **负载均衡**: 前后端分离，可独立扩展