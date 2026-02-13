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
import { useTranslation } from 'react-i18next';
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

const DocumentUpload: React.FC = () => {
  const { t } = useTranslation();
  const [uploading, setUploading] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [uploadConfig, setUploadConfig] = useState<UploadConfig | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const { token, user } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const pollingRef = useRef<number | null>(null);
  const initializedRef = useRef(false);

  // 阶段颜色
  const stageColors: Record<string, string> = {
    uploading: '#1890ff',
    parsing: '#722ed1',
    chunking: '#13c2c2',
    embedding: '#fa8c16',
    storing: '#52c41a',
    completed: '#52c41a'
  };

  // 获取阶段标签
  const getStageLabel = (stage: string) => {
    const labels: Record<string, string> = {
      uploading: t('upload.stageUploading'),
      parsing: t('upload.stageParsing'),
      chunking: t('upload.stageChunking'),
      embedding: t('upload.stageEmbedding'),
      storing: t('upload.stageStoring'),
      completed: t('upload.stageCompleted')
    };
    return labels[stage] || stage;
  };

  // 判断阶段属于上传还是向量化
  const getPhaseInfo = (stage: string) => {
    const uploadStages = ['uploading', 'parsing', 'chunking'];
    const vectorStages = ['embedding', 'storing'];
    
    if (uploadStages.includes(stage)) {
      return { phase: 'upload', label: t('upload.phaseUpload') };
    } else if (vectorStages.includes(stage)) {
      return { phase: 'vector', label: t('upload.phaseVector') };
    }
    return { phase: 'complete', label: t('upload.phaseComplete') };
  };

  // 获取上传配置
  useEffect(() => {
    fetch('http://localhost:8001/api/documents/config')
      .then(res => res.json())
      .then(data => setUploadConfig(data))
      .catch(err => console.error('Failed to load config:', err));
  }, []);

  // 轮询任务状态
  const pollTasks = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8001/api/documents/tasks');
      const data = await response.json();
      setTasks(prev => {
        const serverTasks = data.tasks || [];
        const serverTaskIds = new Set(serverTasks.map((t: Task) => t.task_id));
        
        const mergedTasks = serverTasks.map((serverTask: Task) => {
          const localTask = prev.find(t => t.task_id === serverTask.task_id);
          if (localTask && localTask.status === 'processing' && serverTask.status !== 'processing') {
            return localTask;
          }
          return serverTask;
        });
        
        return mergedTasks;
      });
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
    }
  }, []);

  // WebSocket连接
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    const ws = new WebSocket('ws://localhost:8001/ws/tasks');
    
    ws.onopen = () => {
      console.log('WebSocket connected');
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
            return prev;
          });
        } else if (data.type === 'ping') {
          ws.send('pong');
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setWsConnected(false);
      setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    wsRef.current = ws;
  }, []);

  useEffect(() => {
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
  }, []);

  // 批量上传
  const handleBatchUpload = async (files: File[]) => {
    if (!uploadConfig) return;
    
    if (files.length > uploadConfig.max_batch_size) {
      message.error(t('upload.maxFiles', { count: uploadConfig.max_batch_size }));
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
      
      if (result.submitted > 0) {
        message.success(t('upload.submitSuccess', { count: result.submitted }));
        pollTasks();
      }
      
      if (result.duplicates > 0) {
        message.warning(t('upload.skippedDuplicates', { count: result.duplicates }));
      }
      
      result.tasks.forEach((t: any) => {
        if (!t.success && !t.duplicate) {
          message.error(`${t.filename}: ${t.error}`);
        }
      });
      
    } catch (error: any) {
      message.error(`${t('upload.uploadFailed')}: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  // 获取状态标签
  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: t('upload.statusPending') },
      queued: { color: 'blue', icon: <ClockCircleOutlined />, text: t('upload.statusQueued') },
      processing: { color: 'processing', icon: <SyncOutlined spin />, text: t('upload.statusProcessing') },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: t('upload.statusCompleted') },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: t('upload.statusFailed') },
      cancelled: { color: 'warning', icon: <CloseCircleOutlined />, text: t('upload.statusCancelled') }
    };
    
    const { color, icon, text } = config[status] || config.pending;
    return <Tag color={color} icon={icon}>{text}</Tag>;
  };

  // 渲染进度条
  const renderCompactProgress = (task: Task) => {
    if (task.status === 'failed') {
      return <span style={{ color: '#ff4d4f', fontSize: 12 }}>{task.error}</span>;
    }
    
    const stage = task.progress?.stage || 'pending';
    const phaseInfo = getPhaseInfo(stage);
    const percentage = task.progress?.percentage || 0;
    
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 48 }}>
        <div style={{ width: 140 }}>
          <div style={{ marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, color: '#666' }}>{t('upload.fileUpload')}</span>
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
        <div style={{ width: 140 }}>
          <div style={{ marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, color: '#666' }}>{t('upload.vectorization')}</span>
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

  // 标记已处理的文件
  const processedFilesRef = useRef<Set<string>>(new Set());

  const uploadProps = {
    name: 'files',
    multiple: true,
    showUploadList: false,
    beforeUpload: () => false,
    onChange: (info: any) => {
      const newFiles = info.fileList.filter((f: any) => {
        const uid = f.uid;
        if (!uid || processedFilesRef.current.has(uid)) {
          return false;
        }
        processedFilesRef.current.add(uid);
        return f.originFileObj;
      });
      
      const files = newFiles.map((f: any) => f.originFileObj).filter(Boolean);
      
      if (files.length > 0) {
        const oversizedFiles = files.filter((f: File) => 
          uploadConfig && f.size > uploadConfig.max_file_size_mb * 1024 * 1024
        );
        
        if (oversizedFiles.length > 0) {
          message.error(t('upload.oversizedError', { 
            size: uploadConfig?.max_file_size_mb, 
            files: oversizedFiles.map((f: File) => f.name).join(', ') 
          }));
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
            <span>{t('upload.title')}</span>
            <Badge 
              status={wsConnected ? 'success' : 'error'} 
              text={wsConnected ? t('upload.realtimeConnection') : t('upload.connectionLost')}
            />
          </Space>
        }
        extra={
          uploadConfig && (
            <Space>
              <Tag color="blue">{t('upload.maxFiles', { count: uploadConfig.max_batch_size })}</Tag>
              <Tag color="green">{t('upload.maxFileSize', { size: uploadConfig.max_file_size_mb })}</Tag>
            </Space>
          )
        }
      >
        {user && (
          <div style={{ marginBottom: 16, color: '#1890ff' }}>
            {t('upload.departmentAssign')}: <strong>{user.department}</strong>
          </div>
        )}
        
        <Upload.Dragger {...uploadProps} style={{ marginBottom: 16 }}>
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">{t('upload.dragFile')}</p>
          <p className="ant-upload-hint">
            {t('upload.batchHint', { count: uploadConfig?.max_batch_size || 20 })}
          </p>
        </Upload.Dragger>

        {tasks.length > 0 && (
          <Card 
            title={`${t('upload.taskQueue')} (${tasks.length})`}
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
                  <div style={{ display: 'flex', alignItems: 'center', width: '100%', gap: 24 }}>
                    <div style={{ width: 280, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span style={{ fontWeight: 500 }}>{task.filename}</span>
                    </div>
                    
                    <div style={{ width: 90, flexShrink: 0 }}>
                      {getStatusTag(task.status)}
                    </div>
                    
                    <div style={{ flexShrink: 0 }}>
                      {renderCompactProgress(task)}
                    </div>
                    
                    <div style={{ flexShrink: 0 }}>
                      {task.status === 'completed' && task.result && (
                        <Tooltip title={t('upload.viewDetails')}>
                          <Button 
                            type="link" 
                            size="small"
                            icon={<EyeOutlined />}
                            onClick={() => {
                              Modal.info({
                                title: t('upload.processResult'),
                                content: (
                                  <div>
                                    <p>{t('upload.documentId')}: {task.result.document_id}</p>
                                    <p>{t('upload.chunksCount')}: {task.result.chunks_count}</p>
                                    <p>{t('upload.vectorization')}: {task.result.vector_stored ? t('upload.success') : t('upload.failed')}</p>
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
