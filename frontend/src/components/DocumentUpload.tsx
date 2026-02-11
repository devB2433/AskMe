import React, { useState } from 'react';
import { Upload, Button, message, Card } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

const DocumentUpload: React.FC = () => {
  const [uploading, setUploading] = useState(false);
  const { token, user } = useAuth();

  const props = {
    name: 'file',
    action: 'http://localhost:8001/api/documents/upload',
    headers: {
      authorization: token ? `Bearer ${token}` : '',
    },
    onChange(info: any) {
      if (info.file.status === 'uploading') {
        setUploading(true);
      }
      if (info.file.status === 'done') {
        message.success(`${info.file.name} 上传成功`);
        setUploading(false);
      } else if (info.file.status === 'error') {
        message.error(`${info.file.name} 上传失败`);
        setUploading(false);
      }
    },
  };

  return (
    <Card title="文档上传" style={{ maxWidth: 600, margin: '0 auto' }}>
      {user && (
        <div style={{ marginBottom: 16, color: '#1890ff' }}>
          上传的文档将归属到: <strong>{user.department}</strong>
        </div>
      )}
      <Upload {...props}>
        <Button icon={<UploadOutlined />} loading={uploading}>
          选择文件上传
        </Button>
      </Upload>
      <div style={{ marginTop: 16, color: '#666' }}>
        <p>支持格式：PDF、Word、Excel、PPT、图片等</p>
        <p>文件将自动进行解析和向量化处理</p>
      </div>
    </Card>
  );
};

export default DocumentUpload;