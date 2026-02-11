"""WebSocket路由 - 实时进度推送"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Header
from services.task_queue import task_queue

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: dict = {}  # user_id -> set of WebSocket
    
    async def connect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """接受连接"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        task_queue.add_ws_connection(websocket)
        logger.info(f"WebSocket连接: {user_id}, 当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, user_id: str = "anonymous"):
        """断开连接"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        task_queue.remove_ws_connection(websocket)
        logger.info(f"WebSocket断开: {user_id}, 当前连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"发送消息失败: {e}")
    
    async def broadcast(self, message: dict, user_id: Optional[str] = None):
        """广播消息"""
        if user_id and user_id in self.active_connections:
            connections = self.active_connections[user_id]
        else:
            connections = [
                ws for conns in self.active_connections.values() for ws in conns
            ]
        
        disconnected = set()
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # 清理断开的连接
        for ws in disconnected:
            for uid, conns in self.active_connections.items():
                conns.discard(ws)


manager = ConnectionManager()


@router.websocket("/ws/tasks")
async def websocket_tasks(websocket: WebSocket):
    """
    任务进度WebSocket端点
    
    连接后可接收实时任务进度更新
    """
    await manager.connect(websocket)
    
    try:
        # 发送初始状态
        await manager.send_personal_message({
            "type": "connected",
            "message": "WebSocket连接成功",
            "queue_status": task_queue.get_queue_status(),
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # 保持连接，接收心跳
        while True:
            try:
                # 接收消息（主要是心跳）
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                
                # 处理心跳
                if data == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                else:
                    # 处理其他消息
                    try:
                        message = json.loads(data)
                        if message.get("type") == "get_status":
                            await manager.send_personal_message({
                                "type": "status",
                                "queue_status": task_queue.get_queue_status(),
                                "tasks": [t.to_dict() for t in task_queue.get_all_tasks()[:20]],
                                "timestamp": datetime.now().isoformat()
                            }, websocket)
                    except json.JSONDecodeError:
                        pass
                        
            except asyncio.TimeoutError:
                # 超时发送心跳检测
                await manager.send_personal_message({
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket异常: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws/tasks/{user_id}")
async def websocket_tasks_user(websocket: WebSocket, user_id: str):
    """
    用户任务进度WebSocket端点
    
    只接收特定用户的任务更新
    """
    await manager.connect(websocket, user_id)
    
    try:
        await manager.send_personal_message({
            "type": "connected",
            "message": f"WebSocket连接成功，用户: {user_id}",
            "queue_status": task_queue.get_queue_status(),
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
            except asyncio.TimeoutError:
                await manager.send_personal_message({
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket异常: {e}")
        manager.disconnect(websocket, user_id)


# 导出管理器
__all__ = ["router", "manager"]
