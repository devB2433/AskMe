import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, List, Card, Tag, AutoComplete, Spin, Progress, Checkbox, Alert, Divider, Steps } from 'antd';
import { SearchOutlined, LoadingOutlined, CheckCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const API_BASE = 'http://localhost:8001/api/search';

interface Department {
  id: string;
  name: string;
}

// 搜索阶段定义
type SearchStage = 'idle' | 'vectorizing' | 'recalling' | 'reranking' | 'generating' | 'completed' | 'error';

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
  
  // 搜索阶段状态
  const [searchStage, setSearchStage] = useState<SearchStage>('idle');
  const [stageMessage, setStageMessage] = useState('');
  
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
    setSearchResults([]);
    setSearchStage('vectorizing');
    setStageMessage(t('search.stageVectorizing'));
    
    // 构建SSE URL
    const params = new URLSearchParams({
      q: value,
      limit: '10',
      use_rerank: String(searchConfig.useRerank),
      use_query_enhance: String(searchConfig.useQueryEnhance),
      recall_size: String(searchConfig.recallSize),
      generate_answer: String(generateAnswer)
    });
    
    const sseUrl = `${API_BASE}/stream?${params}`;
    
    // 使用 fetch + ReadableStream 处理 SSE
    try {
      const response = await fetch(sseUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      if (!reader) {
        throw new Error('无法读取响应流');
      }
      
      let buffer = '';
      
      while (true) {
        const { done, value: chunk } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(chunk, { stream: true });
        
        // 解析 SSE 数据
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              // 更新阶段状态
              if (data.stage) {
                setSearchStage(data.stage as SearchStage);
                setStageMessage(data.message || '');
              }
              
              // 完成时设置结果
              if (data.stage === 'completed' && data.data) {
                setSearchResults(data.data.results || []);
                setAiAnswer(data.data.ai_answer || null);
                setSearched(true);
              }
              
              // 错误处理
              if (data.stage === 'error') {
                console.error('搜索错误:', data.message);
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    } catch (error) {
      console.error('Search failed:', error);
      setSearchStage('error');
      setStageMessage(t('search.searchFailed'));
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
    
    // 输入/后立即显示所有部门
    if (!deptQuery) {
      try {
        const response = await axios.get(`http://localhost:8001/api/users/departments`);
        const departments = response.data.departments || [];
        setOptions(departments.map((dept: any) => ({
          value: `/${dept.name} `,
          label: dept.name
        })));
      } catch (error) {
        setOptions([]);
      }
      return;
    }
    
    try {
      const response = await axios.get(`http://localhost:8001/api/users/departments/suggest?q=${deptQuery}`);
      const departments = response.data.departments || [];
      setOptions(departments.map((dept: any) => ({
        value: `/${dept.name || dept} `,
        label: dept.name || dept
      })));
    } catch (error) {
      setOptions([]);
    }
  };

  const handleInputChange = (value: string) => {
    setQuery(value);
    handleDepartmentSearch(value);
  };

  // 获取阶段图标
  const getStageIcon = (stage: SearchStage) => {
    if (stage === 'idle' || stage === 'completed') return null;
    return <SyncOutlined spin style={{ fontSize: 16, marginRight: 8, color: '#1890ff' }} />;
  };

  // 获取阶段进度百分比
  const getStageProgress = () => {
    const stages: SearchStage[] = ['vectorizing', 'recalling', 'reranking', 'generating', 'completed'];
    const currentIndex = stages.indexOf(searchStage);
    if (currentIndex < 0) return 0;
    // 如果不需要重排序或生成，跳过对应阶段
    let progress = 0;
    if (searchStage === 'vectorizing') progress = 20;
    else if (searchStage === 'recalling') progress = 40;
    else if (searchStage === 'reranking') progress = 60;
    else if (searchStage === 'generating') progress = 80;
    else if (searchStage === 'completed') progress = 100;
    return progress;
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
          {/* 进度条 */}
          <div style={{ marginBottom: 24 }}>
            <Progress 
              percent={getStageProgress()} 
              status="active"
              strokeColor="#1890ff"
              trailColor="#f0f0f0"
            />
          </div>
          
          {/* 阶段指示器 */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'center', 
            gap: 32, 
            marginBottom: 24,
            flexWrap: 'wrap'
          }}>
            {/* 向量匹配 */}
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              opacity: ['vectorizing', 'recalling', 'reranking', 'generating', 'completed'].includes(searchStage) ? 1 : 0.4 
            }}>
              {searchStage === 'vectorizing' ? (
                <SyncOutlined spin style={{ fontSize: 16, marginRight: 8, color: '#1890ff' }} />
              ) : ['recalling', 'reranking', 'generating', 'completed'].includes(searchStage) ? (
                <CheckCircleOutlined style={{ fontSize: 16, marginRight: 8, color: '#52c41a' }} />
              ) : (
                <div style={{ width: 16, height: 16, marginRight: 8, borderRadius: '50%', border: '2px solid #d9d9d9' }} />
              )}
              <span style={{ fontSize: 13 }}>{t('search.stageVectorizing')}</span>
            </div>
            
            {/* 结果召回 */}
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              opacity: ['recalling', 'reranking', 'generating', 'completed'].includes(searchStage) ? 1 : 0.4 
            }}>
              {searchStage === 'recalling' ? (
                <SyncOutlined spin style={{ fontSize: 16, marginRight: 8, color: '#1890ff' }} />
              ) : ['reranking', 'generating', 'completed'].includes(searchStage) ? (
                <CheckCircleOutlined style={{ fontSize: 16, marginRight: 8, color: '#52c41a' }} />
              ) : (
                <div style={{ width: 16, height: 16, marginRight: 8, borderRadius: '50%', border: '2px solid #d9d9d9' }} />
              )}
              <span style={{ fontSize: 13 }}>{t('search.stageRecalling')}</span>
            </div>
            
            {/* 重排序（仅当启用时显示） */}
            {searchConfig.useRerank && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                opacity: ['reranking', 'generating', 'completed'].includes(searchStage) ? 1 : 0.4 
              }}>
                {searchStage === 'reranking' ? (
                  <SyncOutlined spin style={{ fontSize: 16, marginRight: 8, color: '#1890ff' }} />
                ) : ['generating', 'completed'].includes(searchStage) ? (
                  <CheckCircleOutlined style={{ fontSize: 16, marginRight: 8, color: '#52c41a' }} />
                ) : (
                  <div style={{ width: 16, height: 16, marginRight: 8, borderRadius: '50%', border: '2px solid #d9d9d9' }} />
                )}
                <span style={{ fontSize: 13 }}>{t('search.stageReranking')}</span>
              </div>
            )}
            
            {/* 推理生成（仅当启用时显示） */}
            {generateAnswer && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                opacity: ['generating', 'completed'].includes(searchStage) ? 1 : 0.4 
              }}>
                {searchStage === 'generating' ? (
                  <SyncOutlined spin style={{ fontSize: 16, marginRight: 8, color: '#1890ff' }} />
                ) : searchStage === 'completed' ? (
                  <CheckCircleOutlined style={{ fontSize: 16, marginRight: 8, color: '#52c41a' }} />
                ) : (
                  <div style={{ width: 16, height: 16, marginRight: 8, borderRadius: '50%', border: '2px solid #d9d9d9' }} />
                )}
                <span style={{ fontSize: 13 }}>{t('search.stageGenerating')}</span>
              </div>
            )}
          </div>
          
          {/* 当前阶段提示 */}
          <div style={{ color: '#666', fontSize: 14, marginBottom: 8 }}>
            {stageMessage}
          </div>
          <div style={{ color: '#999', fontSize: 12 }}>
            {t('search.pleaseWait')}
          </div>
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
