import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, List, Card, Tag, AutoComplete, Spin, Progress, Switch, Slider, Collapse } from 'antd';
import { SearchOutlined, LoadingOutlined, SettingOutlined } from '@ant-design/icons';
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
  const [searched, setSearched] = useState(false);
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const { user, token } = useAuth();
  
  // 搜索参数状态
  const [useRerank, setUseRerank] = useState(true);
  const [useQueryEnhance, setUseQueryEnhance] = useState(false);
  const [recallSize, setRecallSize] = useState(15);

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
    setSearched(false);
    setQuery(value);
    try {
      const headers: any = {};
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      
      const response = await axios.get(API_BASE, {
        params: { 
          q: value, 
          limit: 10,
          use_rerank: useRerank,
          use_query_enhance: useQueryEnhance,
          recall_size: recallSize
        },
        headers
      });
      setSearchResults(response.data.results || []);
      setSearched(true);
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
        
        {/* 高级搜索选项 */}
        <Collapse 
          ghost 
          style={{ marginTop: 12 }}
          items={[{
            key: '1',
            label: <span><SettingOutlined /> 高级选项</span>,
            children: (
              <div style={{ padding: '8px 0' }}>
                <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>重排序（提高准确率）</span>
                  <Switch checked={useRerank} onChange={setUseRerank} />
                </div>
                <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>查询增强（提高召回率）</span>
                  <Switch checked={useQueryEnhance} onChange={setUseQueryEnhance} />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
                    <span>召回数量</span>
                    <span style={{ color: '#666' }}>{recallSize} 个</span>
                  </div>
                  <Slider 
                    min={5} 
                    max={50} 
                    value={recallSize} 
                    onChange={setRecallSize}
                    marks={{ 5: '5', 15: '15', 30: '30', 50: '50' }}
                  />
                </div>
              </div>
            )
          }]}
        />
      </Card>
      
      {/* 搜索中进度条 */}
      {loading && (
        <Card style={{ marginTop: 16 }}>
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} />
            <div style={{ marginTop: 16, color: '#666' }}>
              正在搜索...
            </div>
            <Progress 
              percent={100} 
              status="active" 
              showInfo={false}
              style={{ maxWidth: 300, margin: '16px auto 0' }}
            />
          </div>
        </Card>
      )}
      
      {!loading && searchResults.length > 0 && (
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
      
      {!loading && searched && searchResults.length === 0 && (
        <Card style={{ marginTop: 16 }}>
          <p style={{ textAlign: 'center', color: '#999' }}>未找到相关结果</p>
        </Card>
      )}
    </div>
  );
};

export default SearchInterface;