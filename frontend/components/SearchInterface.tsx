import React from 'react';
import { Input, Button, Card, List } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

const SearchInterface: React.FC = () => {
  return (
    <div>
      <Card title="知识检索">
        <Input.Search
          placeholder="请输入搜索关键词..."
          enterButton={<Button icon={<SearchOutlined />}>搜索</Button>}
          size="large"
          style={{ marginBottom: 24 }}
        />
        
        <Card title="搜索结果" style={{ marginTop: 24 }}>
          <p>暂无搜索结果</p>
        </Card>
      </Card>
    </div>
  );
};

export default SearchInterface;