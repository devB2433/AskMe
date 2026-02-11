#!/bin/bash

# AskMe 项目初始化脚本

echo "🚀 开始初始化 AskMe 知识库项目..."

# 创建必要目录
echo "📁 创建目录结构..."
mkdir -p uploads processed logs volumes

# 启动 Docker 服务
echo "🐳 启动基础设施服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 初始化数据库
echo "🗄️  初始化数据库..."
# python backend/scripts/init_db.py

echo "✅ 项目初始化完成！"
echo "🌐 前端访问地址: http://localhost:5173"
echo "🔧 后端API地址: http://localhost:8000"
echo "📊 Milvus管理界面: http://localhost:9091"
echo "🔍 Elasticsearch: http://localhost:9200"