import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Upload, Button, message, Card, Progress, List, Tag, Space, Modal, Badge, Tooltip, Row, Col, Spin } from 'antd';
import { 
  UploadOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined, 
  ClockCircleOutlined,
  LoadingOutlined,
  FileTextOutlined,
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
      setTasks(data.tasks || []);
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
          setTasks(prev => {
            const taskIndex = prev.findIndex(t => t.task_id === data.data.task_id);
            if (taskIndex >= 0) {
              const newTasks = [...prev];
              newTasks[taskIndex] = data.data;
              return newTasks;
            }
            return [data.data, ...prev];
          });
        } else if (data.type === 'status') {
          setTasks(data.tasks || []);
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
    connectWebSocket();
    pollTasks();
    pollingRef.current = window.setInterval(pollTasks, 3000);
    
    return () => {
      wsRef.current?.close();
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [connectWebSocket, pollTasks]);

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

  // 渲染进度条
  const renderProgress = (task: Task) => {
    if (task.status === 'completed') {
      return (
        <Row gutter={16}>
          <Col span={12}>
            <div style={{ marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: '#666' }}>文档处理</span>
            </div>
            <Progress percent={100} size="small" status="success" />
          </Col>
          <Col span={12}>
            <div style={{ marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: '#666' }}>向量化</span>
            </div>
            <Progress percent={100} size="small" status="success" />
          </Col>
        </Row>
      );
    }
    
    if (task.status === 'failed') {
      return <span style={{ color: '#ff4d4f' }}>{task.error}</span>;
    }
    
    if (task.status === 'processing') {
      const stage = task.progress.stage;
      const phaseInfo = getPhaseInfo(stage);
      const percentage = task.progress.percentage;
      
      return (
        <Row gutter={16}>
          <Col span={12}>
            <div style={{ marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: '#666' }}>
                文档处理
                {phaseInfo.phase === 'upload' && (
                  <SyncOutlined spin style={{ marginLeft: 8, color: '#1890ff' }} />
                )}
              </span>
            </div>
            <Progress 
              percent={phaseInfo.phase === 'upload' ? percentage : 100} 
              size="small"
              status={phaseInfo.phase === 'upload' ? 'active' : 'success'}
            />
          </Col>
          <Col span={12}>
            <div style={{ marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: '#666' }}>
                向量化
                {phaseInfo.phase === 'vector' && (
                  <SyncOutlined spin style={{ marginLeft: 8, color: '#fa8c16' }} />
                )}
              </span>
            </div>
            <Progress 
              percent={phaseInfo.phase === 'vector' ? percentage : (phaseInfo.phase === 'complete' ? 100 : 0)} 
              size="small"
              status={phaseInfo.phase === 'vector' ? 'active' : (phaseInfo.phase === 'complete' ? 'success' : 'normal')}
              strokeColor={phaseInfo.phase === 'vector' ? '#fa8c16' : undefined}
            />
          </Col>
        </Row>
      );
    }
    
    // pending/queued 状态
    return (
      <Row gutter={16}>
        <Col span={12}>
          <div style={{ marginBottom: 4 }}>
            <span style={{ fontSize: 12, color: '#666' }}>文档处理</span>
          </div>
          <Progress percent={0} size="small" />
        </Col>
        <Col span={12}>
          <div style={{ marginBottom: 4 }}>
            <span style={{ fontSize: 12, color: '#666' }}>向量化</span>
          </div>
          <Progress percent={0} size="small" />
        </Col>
      </Row>
    );
  };

  const uploadProps = {
    name: 'files',
    multiple: true,
    showUploadList: false,
    beforeUpload: () => false,
    onChange: (info: any) => {
      if (info.fileList.length > 0) {
        const files = info.fileList.map((f: any) => f.originFileObj).filter(Boolean);
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
                  style={{ alignItems: 'flex-start' }}
                  actions={[
                    task.status === 'completed' && task.result && (
                      <Tooltip title="查看详情" key="view">
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
                    )
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <div style={{ width: 40, textAlign: 'center' }}>
                        {task.status === 'processing' ? (
                          <Spin indicator={<LoadingOutlined style={{ fontSize: 24, color: '#1890ff' }} spin />} />
                        ) : (
                          <FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />
                        )}
                      </div>
                    }
                    title={
                      <Space>
                        <span>{task.filename}</span>
                        {getStatusTag(task.status)}
                      </Space>
                    }
                    description={renderProgress(task)}
                  />
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
