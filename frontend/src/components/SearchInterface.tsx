import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, List, Card, Tag, AutoComplete, Spin, Progress, Checkbox, Alert, Divider } from 'antd';
import { SearchOutlined, LoadingOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const API_BASE = 'http://localhost:8001/api/search';

interface Department {
  id: string;
  name: string;
}

const SearchInterface: React.FC = () => {
  const { t } = useTranslation();
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [searched, setSearched] = useState(false);
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const { user, token } = useAuth();
  
  // 搜索精度预设（从系统设置读取）
  const [searchConfig, setSearchConfig] = useState({
    useRerank: true,
    useQueryEnhance: false,
    recallSize: 15
  });
  const [generateAnswer, setGenerateAnswer] = useState(false);
  const [aiAnswer, setAiAnswer] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  
  // 加载搜索配置
  useEffect(() => {
    const loadConfig = () => {
      const preset = localStorage.getItem('searchPreset') || 'normal';
      const configs: Record<string, any> = {
        fast: { useRerank: false, useQueryEnhance: false, recallSize: 10 },
        normal: { useRerank: true, useQueryEnhance: false, recallSize: 15 },
        precise: { useRerank: true, useQueryEnhance: true, recallSize: 30 }
      };
      setSearchConfig(configs[preset] || configs.normal);
    };
    
    loadConfig();
    
    // 监听storage变化（其他标签页修改设置）
    window.addEventListener('storage', loadConfig);
    return () => window.removeEventListener('storage', loadConfig);
  }, []);

  const handleSearch = async (value: string) => {
    if (!value.trim()) return;
    
    setLoading(true);
    setSearched(false);
    setAiAnswer(null);
    
    try {
      const response = await axios.get(API_BASE, {
        params: { 
          q: value, 
          limit: 10,
          use_rerank: searchConfig.useRerank,
          use_query_enhance: searchConfig.useQueryEnhance,
          recall_size: searchConfig.recallSize,
          generate_answer: generateAnswer
        },
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      
      setSearchResults(response.data.results || []);
      setAiAnswer(response.data.ai_answer || null);
      setSearched(true);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  // 部门搜索处理
  const handleDepartmentSearch = async (value: string) => {
    if (!value.startsWith('/')) {
      setOptions([]);
      return;
    }
    
    const deptQuery = value.substring(1).toLowerCase();
    if (!deptQuery) {
      setOptions([]);
      return;
    }
    
    try {
      const response = await axios.get(`http://localhost:8001/api/users/departments/suggest?q=${deptQuery}`);
      const departments = response.data.departments || [];
      setOptions(departments.map((dept: string) => ({
        value: `/${dept} `,
        label: dept
      })));
    } catch (error) {
      setOptions([]);
    }
  };

  const handleInputChange = (value: string) => {
    setQuery(value);
    handleDepartmentSearch(value);
  };

  return (
    <Card title={t('search.title')}>
      <AutoComplete
        style={{ width: '100%' }}
        options={options}
        value={query}
        onSearch={handleInputChange}
        onSelect={(value) => {
          setQuery(value);
        }}
      >
        <Input.Search
          placeholder={t('search.placeholder')}
          enterButton={t('common.search')}
          size="large"
          loading={loading}
          onSearch={handleSearch}
        />
      </AutoComplete>
      
      <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
        {t('search.hint')}
      </div>
      
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: '#999' }}>{t('search.searchPrecision')}</span>
        <Checkbox 
          checked={generateAnswer} 
          onChange={(e) => setGenerateAnswer(e.target.checked)}
        >
          {t('search.generateAIAnswer')}
        </Checkbox>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
        </div>
      )}

      {!loading && aiAnswer && (
        <Card style={{ marginTop: 16 }}>
          <Alert 
            message={t('search.aiAnswer')} 
            description={<div style={{ whiteSpace: 'pre-wrap' }}>{aiAnswer}</div>}
            type="info"
            showIcon
          />
        </Card>
      )}
      
      {!loading && searchResults.length > 0 && (
        <Card title={`${t('search.relatedDocuments')} (${searchResults.length})`} style={{ marginTop: 16 }}>
          <List
            dataSource={searchResults}
            renderItem={(item: any) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{item.filename}</span>
                      <Tag color="blue">{t('search.score')}: {(item.score * 100).toFixed(1)}%</Tag>
                    </div>
                  }
                  description={
                    <div>
                      {item.matches && item.matches[0] && (
                        <div style={{ color: '#666', marginTop: 4 }}>
                          {item.matches[0].substring(0, 200)}...
                        </div>
                      )}
                      {item.team_id && (
                        <Tag style={{ marginTop: 8 }}>{item.team_id}</Tag>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {!loading && searched && searchResults.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          {t('search.noResults')}
        </div>
      )}
    </Card>
  );
};

export default SearchInterface;
