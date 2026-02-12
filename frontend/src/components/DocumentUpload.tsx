import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Upload, Button, message, Card, Progress, List, Tag, Space, Modal, Badge, Tooltip } from 'antd';
import { 
  UploadOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined, 
  ClockCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
  SyncOutlined
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

interface TaskProgress {
  stage: string;
  current: number;
  total: number;
  message: string;
  percentage: number;
}

interface Task {
  task_id: string;
  task_type: string;
  filename: string;
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: TaskProgress;
  result?: any;
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface UploadConfig {
  max_batch_size: number;
  max_file_size_mb: number;
  allowed_extensions: string[];
  concurrent_uploads: number;
}

const stageLabels: Record<string, string> = {
  uploading: '上传中',
  parsing: '解析中',
  chunking: '分块中',
  embedding: '向量化中',
  storing: '存储中',
  completed: '已完成'
};

const stageColors: Record<string, string> = {
  uploading: '#1890ff',
  parsing: '#722ed1',
  chunking: '#13c2c2',
  embedding: '#fa8c16',
  storing: '#52c41a',
  completed: '#52c41a'
};

// 判断阶段属于上传还是向量化
const getPhaseInfo = (stage: string) => {
  const uploadStages = ['uploading', 'parsing', 'chunking'];
  const vectorStages = ['embedding', 'storing'];
  
  if (uploadStages.includes(stage)) {
    return { phase: 'upload', label: '文档处理' };
  } else if (vectorStages.includes(stage)) {
    return { phase: 'vector', label: '向量化' };
  }
  return { phase: 'complete', label: '完成' };
};

const DocumentUpload: React.FC = () => {
  const [uploading, setUploading] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [uploadConfig, setUploadConfig] = useState<UploadConfig | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const { token, user } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const pollingRef = useRef<number | null>(null);
  const initializedRef = useRef(false);

  // 获取上传配置
  useEffect(() => {
    fetch('http://localhost:8001/api/documents/config')
      .then(res => res.json())
      .then(data => setUploadConfig(data))
      .catch(err => console.error('获取配置失败:', err));
  }, []);

  // 轮询任务状态
  const pollTasks = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8001/api/documents/tasks');
      const data = await response.json();
      // 合并任务列表，保留本地最新的进度信息
      setTasks(prev => {
        const serverTasks = data.tasks || [];
        const serverTaskIds = new Set(serverTasks.map((t: Task) => t.task_id));
        
        // 过滤掉已不在服务器的任务，同时合并最新的进度
        const mergedTasks = serverTasks.map((serverTask: Task) => {
          const localTask = prev.find(t => t.task_id === serverTask.task_id);
          // 如果本地有更新的进度，优先使用本地（处理中状态）
          if (localTask && localTask.status === 'processing' && serverTask.status !== 'processing') {
            return localTask;
          }
          return serverTask;
        });
        
        return mergedTasks;
      });
    } catch (error) {
      console.error('获取任务列表失败:', error);
    }
  }, []);

  // WebSocket连接
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    const ws = new WebSocket('ws://localhost:8001/ws/tasks');
    
    ws.onopen = () => {
      console.log('WebSocket已连接');
      setWsConnected(true);
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'task_progress') {
          // WebSocket 只更新单个任务，不添加新任务
          setTasks(prev => {
            const taskIndex = prev.findIndex(t => t.task_id === data.data.task_id);
            if (taskIndex >= 0) {
              const newTasks = [...prev];
              newTasks[taskIndex] = data.data;
              return newTasks;
            }
            // 如果任务不存在，可能是新任务，但由轮询来添加
            return prev;
          });
        } else if (data.type === 'ping') {
          ws.send('pong');
        }
      } catch (e) {
        console.error('解析WebSocket消息失败:', e);
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket已断开');
      setWsConnected(false);
      setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };
    
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    // 防止重复初始化
    if (initializedRef.current) return;
    initializedRef.current = true;
    
    connectWebSocket();
    pollTasks();
    pollingRef.current = window.setInterval(pollTasks, 3000);
    
    return () => {
      wsRef.current?.close();
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []); // 空依赖，只在组件挂载时执行一次

  // 批量上传
  const handleBatchUpload = async (files: File[]) => {
    if (!uploadConfig) return;
    
    if (files.length > uploadConfig.max_batch_size) {
      message.error(`最多支持上传${uploadConfig.max_batch_size}个文件`);
      return;
    }
    
    setUploading(true);
    
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    
    try {
      const response = await fetch('http://localhost:8001/api/documents/batch', {
        method: 'POST',
        headers: {
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: formData
      });
      
      const result = await response.json();
      console.log('批量上传结果:', result);
      
      if (result.submitted > 0) {
        message.success(`成功提交${result.submitted}个文档处理任务`);
        pollTasks();
      }
      
      if (result.duplicates > 0) {
        message.warning(`${result.duplicates}个文件已存在，已跳过`);
      }
      
      result.tasks.forEach((t: any) => {
        if (!t.success && !t.duplicate) {
          message.error(`${t.filename}: ${t.error}`);
        }
      });
      
    } catch (error: any) {
      message.error(`上传失败: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  // 获取状态标签
  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待中' },
      queued: { color: 'blue', icon: <ClockCircleOutlined />, text: '队列中' },
      processing: { color: 'processing', icon: <SyncOutlined spin />, text: '处理中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      cancelled: { color: 'warning', icon: <CloseCircleOutlined />, text: '已取消' }
    };
    
    const { color, icon, text } = config[status] || config.pending;
    return <Tag color={color} icon={icon}>{text}</Tag>;
  };

  // 渲染进度条 - 紧凑版本（用于右侧显示）
  const renderCompactProgress = (task: Task) => {
    if (task.status === 'failed') {
      return <span style={{ color: '#ff4d4f', fontSize: 12 }}>{task.error}</span>;
    }
    
    const stage = task.progress?.stage || 'pending';
    const phaseInfo = getPhaseInfo(stage);
    const percentage = task.progress?.percentage || 0;
    
    // 根据状态确定进度
    let uploadPercent = 0;
    let vectorPercent = 0;
    
    if (task.status === 'completed') {
      uploadPercent = 100;
      vectorPercent = 100;
    } else if (task.status === 'processing') {
      if (phaseInfo.phase === 'upload') {
        uploadPercent = percentage;
        vectorPercent = 0;
      } else if (phaseInfo.phase === 'vector') {
        uploadPercent = 100;
        vectorPercent = percentage;
      }
    }
    
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
        <div style={{ width: 120 }}>
          <div style={{ marginBottom: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, color: '#666' }}>文件上传</span>
            {task.status === 'processing' && phaseInfo.phase === 'upload' && (
              <SyncOutlined spin style={{ fontSize: 10, color: '#1890ff', marginLeft: 8 }} />
            )}
          </div>
          <Progress 
            percent={uploadPercent} 
            size="small"
            status={uploadPercent === 100 ? 'success' : (task.status === 'processing' ? 'active' : 'normal')}
            showInfo={false}
            style={{ margin: 0 }}
          />
        </div>
        <div style={{ width: 120 }}>
          <div style={{ marginBottom: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, color: '#666' }}>向量化</span>
            {task.status === 'processing' && phaseInfo.phase === 'vector' && (
              <SyncOutlined spin style={{ fontSize: 10, color: '#fa8c16', marginLeft: 8 }} />
            )}
          </div>
          <Progress 
            percent={vectorPercent}
            size="small"
            status={vectorPercent === 100 ? 'success' : (task.status === 'processing' ? 'active' : 'normal')}
            strokeColor={task.status === 'processing' && phaseInfo.phase === 'vector' ? '#fa8c16' : undefined}
            showInfo={false}
            style={{ margin: 0 }}
          />
        </div>
      </div>
    );
  };

  // 标记已处理的文件，防止重复上传
  const processedFilesRef = useRef<Set<string>>(new Set());

  const uploadProps = {
    name: 'files',
    multiple: true,
    showUploadList: false,
    beforeUpload: () => false,
    onChange: (info: any) => {
      // 当有新文件添加时处理
      const newFiles = info.fileList.filter((f: any) => {
        const uid = f.uid;
        // 只处理未被处理过的文件
        if (!uid || processedFilesRef.current.has(uid)) {
          return false;
        }
        // 标记为已处理
        processedFilesRef.current.add(uid);
        return f.originFileObj;
      });
      
      const files = newFiles.map((f: any) => f.originFileObj).filter(Boolean);
      
      if (files.length > 0) {
        const oversizedFiles = files.filter((f: File) => 
          uploadConfig && f.size > uploadConfig.max_file_size_mb * 1024 * 1024
        );
        
        if (oversizedFiles.length > 0) {
          message.error(`以下文件超过大小限制(${uploadConfig?.max_file_size_mb}MB): ${oversizedFiles.map((f: File) => f.name).join(', ')}`);
          return;
        }
        
        handleBatchUpload(files);
      }
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <Card 
        title={
          <Space>
            <span>文档上传</span>
            <Badge 
              status={wsConnected ? 'success' : 'error'} 
              text={wsConnected ? '实时连接' : '连接断开'}
            />
          </Space>
        }
        extra={
          uploadConfig && (
            <Space>
              <Tag color="blue">最多{uploadConfig.max_batch_size}个文件</Tag>
              <Tag color="green">单文件{uploadConfig.max_file_size_mb}MB</Tag>
            </Space>
          )
        }
      >
        {user && (
          <div style={{ marginBottom: 16, color: '#1890ff' }}>
            上传的文档将归属到: <strong>{user.department}</strong>
          </div>
        )}
        
        <Upload.Dragger {...uploadProps} style={{ marginBottom: 16 }}>
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持批量上传，最多{uploadConfig?.max_batch_size || 20}个文件
          </p>
        </Upload.Dragger>

        {/* 任务队列 */}
        {tasks.length > 0 && (
          <Card 
            title={`任务队列 (${tasks.length})`}
            size="small"
            style={{ marginTop: 16 }}
          >
            <List
              dataSource={tasks}
              renderItem={(task) => (
                <List.Item
                  key={task.task_id}
                  style={{ padding: '12px 0' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', width: '100%', gap: 16 }}>
                    {/* 文件名 - 固定宽度，超长截断 */}
                    <div style={{ width: 300, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span style={{ fontWeight: 500 }}>{task.filename}</span>
                    </div>
                    
                    {/* 状态标签 - 固定宽度，不被遮挡 */}
                    <div style={{ width: 70, flexShrink: 0 }}>
                      {getStatusTag(task.status)}
                    </div>
                    
                    {/* 进度条 */}
                    <div style={{ flexShrink: 0 }}>
                      {renderCompactProgress(task)}
                    </div>
                    
                    {/* 查看详情按钮 */}
                    <div style={{ flexShrink: 0 }}>
                      {task.status === 'completed' && task.result && (
                        <Tooltip title="查看详情">
                          <Button 
                            type="link" 
                            size="small"
                            icon={<EyeOutlined />}
                            onClick={() => {
                              Modal.info({
                                title: '处理结果',
                                content: (
                                  <div>
                                    <p>文档ID: {task.result.document_id}</p>
                                    <p>分块数: {task.result.chunks_count}</p>
                                    <p>向量化: {task.result.vector_stored ? '成功' : '失败'}</p>
                                  </div>
                                )
                              });
                            }}
                          />
                        </Tooltip>
                      )}
                    </div>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        )}
      </Card>
    </div>
  );
};

export default DocumentUpload;
