import React from 'react';
import { Table, Card } from 'antd';

const DocumentList: React.FC = () => {
  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
  ];

  const data = [];

  return (
    <Card title="文档管理">
      <Table columns={columns} dataSource={data} />
    </Card>
  );
};

export default DocumentList;