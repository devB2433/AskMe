import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, List, Card, Tag, AutoComplete } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const API_BASE = 'http://localhost:8001/api/search';

interface Department {
  id: string;
  name: string;
}

const SearchInterface: React.FC = () => {
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const { user, token } = useAuth();

  // 处理输入变化，检测部门提示
  const handleInputChange = (value: string) => {
    setQuery(value);
    
    // 检测是否输入了 "/"
    if (value.startsWith('/')) {
      const afterSlash = value.slice(1);
      // 如果 / 后面有内容，提示匹配的部门
      if (afterSlash.length > 0 && !afterSlash.includes(' ')) {
        fetchDepartmentSuggestions(afterSlash);
      } else if (!afterSlash.includes(' ')) {
        // 刚输入 /，显示用户部门
        fetchDepartmentSuggestions('');
      } else {
        setOptions([]);
      }
    } else {
      setOptions([]);
    }
  };

  // 获取部门提示
  const fetchDepartmentSuggestions = async (prefix: string) => {
    try {
      const response = await axios.get('http://localhost:8001/api/users/departments/suggest', {
        params: { q: prefix }
      });
      const departments: Department[] = response.data.departments || [];
      
      setOptions(departments.map(dept => ({
        value: `/${dept.name} `,
        label: dept.name
      })));
    } catch (error) {
      console.error('获取部门提示失败:', error);
      setOptions([]);
    }
  };

  // 选择部门后
  const handleSelect = (value: string) => {
    setQuery(value);
    setOptions([]);
  };

  const handleSearch = async (value: string) => {
    if (!value.trim()) return;
    
    setLoading(true);
    setQuery(value);
    try {
      const headers: any = {};
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      
      const response = await axios.get(API_BASE, {
        params: { q: value, limit: 10 },
        headers
      });
      setSearchResults(response.data.results || []);
    } catch (error) {
      console.error('搜索失败:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Card title="知识检索" style={{ marginBottom: 24 }}>
        <div style={{ marginBottom: 8, color: '#666', fontSize: '13px' }}>
          提示：输入 <code style={{ background: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>/部门名 关键词</code> 可在指定部门知识库中搜索
        </div>
        <AutoComplete
          value={query}
          options={options}
          onSearch={handleInputChange}
          onSelect={handleSelect}
          style={{ width: '100%' }}
        >
          <Input.Search
            placeholder="输入关键词搜索... 或输入 / 选择部门"
            enterButton={<Button type="primary" icon={<SearchOutlined />}>搜索</Button>}
            size="large"
            onSearch={handleSearch}
            loading={loading}
          />
        </AutoComplete>
      </Card>
      
      {searchResults.length > 0 && (
        <Card title={`搜索结果 (${searchResults.length})`}>
          <List
            itemLayout="vertical"
            dataSource={searchResults}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={item.filename}
                  description={
                    <div>
                      {item.matches && item.matches.map((match: string, idx: number) => (
                        <p key={idx} style={{ marginBottom: 8, color: '#333' }}>
                          {match}
                        </p>
                      ))}
                      <div style={{ marginTop: 8 }}>
                        {item.team_id && <Tag color="purple">{item.team_id}</Tag>}
                        <Tag color="blue">相关度: {(item.score * 100).toFixed(1)}%</Tag>
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}
      
      {!loading && searchResults.length === 0 && query && (
        <Card>
          <p style={{ textAlign: 'center', color: '#999' }}>未找到相关结果</p>
        </Card>
      )}
    </div>
  );
};

export default SearchInterface;