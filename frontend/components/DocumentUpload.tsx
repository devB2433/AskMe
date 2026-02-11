import React, { useState } from 'react';
import { Upload, Button, message, Card, List } from 'antd';
import { UploadOutlined, FilePdfOutlined, FileWordOutlined, FileTextOutlined } from '@ant-design/icons';
import axios from 'axios';

interface Document {
  id: number;
  filename: string;
  file_size: number;
  status: string;
  created_at: string;
}

const DocumentUpload: React.FC = () => {
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);

  const handleUpload = async (file: any) => {
    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      const response = await axios.post('/api/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      message.success(`${file.name} 上传成功`);
      // 刷新文档列表
      fetchDocuments();
    } catch (error) {
      message.error('上传失败');
      console.error('Upload error:', error);
    } finally {
      setUploading(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get('/api/documents');
      setDocuments(response.data);
    } catch (error) {
      console.error('Fetch documents error:', error);
    }
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf':
        return <FilePdfOutlined style={{ fontSize: '24px', color: '#ff4d4f' }} />;
      case 'doc':
      case 'docx':
        return <FileWordOutlined style={{ fontSize: '24px', color: '#1890ff' }} />;
      default:
        return <FileTextOutlined style={{ fontSize: '24px', color: '#52c41a' }} />;
    }
  };

  React.useEffect(() => {
    fetchDocuments();
  }, []);

  return (
    <div>
      <Card title="文档上传" style={{ marginBottom: 24 }}>
        <Upload
          beforeUpload={handleUpload}
          showUploadList={false}
          accept=".pdf,.doc,.docx,.txt,.md,.jpg,.jpeg,.png"
        >
          <Button icon={<UploadOutlined />} loading={uploading}>
            选择文件上传
          </Button>
        </Upload>
        <p style={{ marginTop: 16, color: '#666' }}>
          支持 PDF、Word、TXT、Markdown、图片等格式
        </p>
      </Card>

      <Card title="已上传文档">
        <List
          dataSource={documents}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                avatar={getFileIcon(item.filename)}
                title={item.filename}
                description={`大小: ${(item.file_size / 1024 / 1024).toFixed(2)} MB | 状态: ${item.status}`}
              />
              <div>{new Date(item.created_at).toLocaleString()}</div>
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
};

export default DocumentUpload;