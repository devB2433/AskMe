import React, { useState, useEffect } from 'react';
import { Table, Card, Button, Tag, Popconfirm, message, Spin } from 'antd';
import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

const API_BASE = 'http://localhost:8001/api/documents';

const DocumentList: React.FC = () => {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await axios.get(API_BASE);
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error('获取文档列表失败:', error);
      message.error(t('documents.getFailed'));
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
      message.success(t('documents.deleteSuccess'));
      fetchDocuments();
    } catch (error) {
      message.error(t('common.error'));
    }
  };

  const handleReprocess = async (id: string) => {
    try {
      await axios.post(`${API_BASE}/${id}/reprocess`);
      message.info(t('documents.reprocessStart'));
      fetchDocuments();
    } catch (error) {
      message.error(t('common.error'));
    }
  };

  const columns = [
    {
      title: t('documents.filename'),
      dataIndex: 'filename',
      key: 'filename',
    },
    {
      title: t('documents.department'),
      dataIndex: 'team_id',
      key: 'team_id',
      render: (team_id: string) => team_id || '-',
    },
    {
      title: t('documents.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'completed' ? 'green' : 'orange'}>
          {status === 'completed' ? t('documents.completed') : t('documents.processing')}
        </Tag>
      ),
    },
    {
      title: t('documents.chunks'),
      dataIndex: 'chunks_count',
      key: 'chunks_count',
    },
    {
      title: t('documents.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: t('documents.actions'),
      key: 'action',
      render: (_: any, record: any) => (
        <div>
          <Button 
            icon={<ReloadOutlined />} 
            size="small" 
            style={{ marginRight: 8 }}
            onClick={() => handleReprocess(record.document_id)}
            title={t('documents.reprocess')}
          />
          <Popconfirm
            title={t('documents.deleteConfirm')}
            onConfirm={() => handleDelete(record.document_id)}
            okText={t('common.confirm')}
            cancelText={t('common.cancel')}
          >
            <Button icon={<DeleteOutlined />} size="small" danger title={t('documents.delete')} />
          </Popconfirm>
        </div>
      ),
    },
  ];

  return (
    <Card title={t('documents.title')}>
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
