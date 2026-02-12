import React, { useState, useEffect } from 'react';
import { Table, Card, Button, Tag, Popconfirm, message, Spin } from 'antd';
import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import axios from 'axios';

const API_BASE = 'http://localhost:8001/api/documents';

const DocumentList: React.FC = () => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await axios.get(API_BASE);
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error('获取文档列表失败:', error);
      message.error('获取文档列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(`${API_BASE}/${id}`);
      message.success('文档删除成功');
      fetchDocuments();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleReprocess = async (id: string) => {
    try {
      await axios.post(`${API_BASE}/${id}/reprocess`);
      message.info('开始重新处理文档');
      fetchDocuments();
    } catch (error) {
      message.error('重新处理失败');
    }
  };

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
    },
    {
      title: '部门',
      dataIndex: 'team_id',
      key: 'team_id',
      render: (team_id: string) => team_id || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'completed' ? 'green' : 'orange'}>
          {status === 'completed' ? '已完成' : '处理中'}
        </Tag>
      ),
    },
    {
      title: '分块数',
      dataIndex: 'chunks_count',
      key: 'chunks_count',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <div>
          <Button 
            icon={<ReloadOutlined />} 
            size="small" 
            style={{ marginRight: 8 }}
            onClick={() => handleReprocess(record.document_id)}
          >
            重新处理
          </Button>
          <Popconfirm
            title="确定要删除这个文档吗？"
            onConfirm={() => handleDelete(record.document_id)}
            okText="确定"
            cancelText="取消"
          >
            <Button icon={<DeleteOutlined />} size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </div>
      ),
    },
  ];

  return (
    <Card title="文档管理">
      <Table 
        columns={columns} 
        dataSource={documents} 
        rowKey="document_id"
        loading={loading}
      />
    </Card>
  );
};

export default DocumentList;