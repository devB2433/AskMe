# AskMe 知识库系统 - 启动指南

## 系统要求
- Docker 和 Docker Compose
- Python 3.10+
- Node.js 16+
- 至少 8GB 内存

## 快速启动

### 1. 克隆项目
```bash
git clone <repository-url>
cd AskMe
```

### 2. 初始化环境
```bash
# Windows 用户
scripts\init.bat

# Linux/Mac 用户
chmod +x scripts/init.sh
./scripts/init.sh
```

### 3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，根据需要调整配置
```

### 4. 安装依赖
```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖
npm install
```

### 5. 启动服务

**启动基础设施（Docker）：**
```bash
docker-compose up -d
```

**启动后端服务：**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**启动前端服务：**
```bash
cd frontend
npm run dev
```

## 访问地址
- **前端界面**: http://localhost:5173
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Milvus管理**: http://localhost:9091
- **Elasticsearch**: http://localhost:9200

## 服务状态检查
```bash
# 检查Docker服务
docker-compose ps

# 检查后端健康状态
curl http://localhost:8000/health

# 检查数据库连接
# (可以通过后端日志确认)
```

## 常见问题

### 1. 端口冲突
如果默认端口被占用，请修改对应服务的端口配置：
- 后端: 修改 `uvicorn` 命令中的 `--port` 参数
- 前端: 修改 `vite.config.ts` 中的 `server.port`
- Docker服务: 修改 `docker-compose.yml` 中的端口映射

### 2. 内存不足
Milvus和Elasticsearch比较消耗内存，建议：
- 分配至少8GB内存给Docker
- 可以临时关闭不需要的服务

### 3. 模型下载慢
首次运行会自动下载嵌入模型，可能需要较长时间：
- 可以预先下载模型文件
- 或配置国内镜像源加速下载

## 开发调试

### 查看日志
```bash
# 查看Docker服务日志
docker-compose logs -f

# 查看后端日志
# 在后端终端查看输出

# 查看前端日志
# 在前端终端查看输出
```

### 重启服务
```bash
# 重启所有Docker服务
docker-compose restart

# 重启特定服务
docker-compose restart milvus-standalone
```

## 停止服务
```bash
# 停止所有服务但保留数据
docker-compose stop

# 停止并删除容器（保留数据卷）
docker-compose down

# 停止并删除所有数据
docker-compose down -v
```