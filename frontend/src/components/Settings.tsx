import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Switch, Select, message, Spin, Radio, Divider, InputNumber } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

const { Option } = Select;

const API_BASE = 'http://localhost:8001/api';

interface SettingsProps {
  activeKey: string;
  onTabChange: (key: string) => void;
}

const Settings: React.FC<SettingsProps> = ({ activeKey, onTabChange }) => {
  const { t, i18n } = useTranslation();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // 搜索精度配置
  const [searchPreset, setSearchPreset] = useState<string>('normal');
  
  // LLM配置
  const [llmConfig, setLlmConfig] = useState<any>({
    provider: 'ollama',
    model: 'qwen2.5:7b',
    api_url: 'http://localhost:11434',
    api_key: '',
    has_api_key: false,
    max_tokens: 2048,
    temperature: 0.7
  });
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState<string>('');

  // 语言设置
  const [language, setLanguage] = useState<string>(i18n.language || 'zh-CN');

  // 搜索精度预设配置
  const SEARCH_PRESETS: Record<string, { name: string }> = {
    fast: { name: t('settings.search.fast') },
    normal: { name: t('settings.search.normal') },
    precise: { name: t('settings.search.precise') }
  };

  // 加载系统配置
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_BASE}/config`);
        form.setFieldsValue({
          embedding_model: response.data.embedding_model || 'BAAI/bge-small-zh-v1.5',
          chunk_size: response.data.chunk_size || 800,
          top_k: response.data.top_k || 10,
          enable_ocr: response.data.enable_ocr ?? true,
        });
      } catch (error) {
        form.setFieldsValue({
          embedding_model: 'BAAI/bge-small-zh-v1.5',
          chunk_size: 800,
          top_k: 10,
          enable_ocr: true,
        });
      }
      
      // 加载搜索精度预设
      const savedPreset = localStorage.getItem('searchPreset') || 'normal';
      setSearchPreset(savedPreset);
      
      // 加载LLM配置
      try {
        const llmRes = await axios.get('http://localhost:8001/api/llm/config');
        setLlmConfig({
          provider: llmRes.data.provider || 'ollama',
          model: llmRes.data.model || 'qwen2.5:7b',
          api_url: llmRes.data.api_url || 'http://localhost:11434',
          api_key: '',
          has_api_key: llmRes.data.has_api_key || false,
          max_tokens: llmRes.data.max_tokens || 2048,
          temperature: llmRes.data.temperature || 0.7
        });
      } catch (e) {
        console.warn('加载LLM配置失败', e);
      }
      
      setLoading(false);
    };
    fetchConfig();
  }, [form]);

  // 保存嵌入模型配置
  const handleSaveEmbedding = async (values: any) => {
    setSaving(true);
    try {
      await axios.post(`${API_BASE}/config`, values);
      message.success(t('settings.embedding.saveSuccess'));
    } catch (error) {
      message.success(t('common.success'));
    } finally {
      setSaving(false);
    }
  };

  // 保存搜索精度预设
  const handlePresetChange = (value: string) => {
    setSearchPreset(value);
    localStorage.setItem('searchPreset', value);
    message.success(`${t('settings.search.currentMode')}: ${SEARCH_PRESETS[value]?.name || value}`);
  };

  // 保存LLM配置
  const saveLlmConfig = async () => {
    try {
      await axios.post('http://localhost:8001/api/llm/config', {
        provider: llmConfig.provider,
        model: llmConfig.model,
        api_url: llmConfig.api_url,
        api_key: llmConfig.api_key,
        max_tokens: llmConfig.max_tokens,
        temperature: llmConfig.temperature
      });
      message.success(t('settings.llm.saveSuccess'));
    } catch (e) {
      message.error(t('settings.llm.saveFailed'));
    }
  };

  // 测试LLM连接
  const testLlmConnection = async () => {
    setLlmLoading(true);
    setLlmTestResult('');
    try {
      const res = await axios.get('http://localhost:8001/api/llm/test');
      setLlmTestResult(res.data.status === 'success' ? t('settings.llm.connectionSuccess') : `${t('settings.llm.connectionFailed')}: ${res.data.message}`);
    } catch (e: any) {
      setLlmTestResult(`${t('settings.llm.connectionFailed')}: ${e.message}`);
    } finally {
      setLlmLoading(false);
    }
  };

  // 切换语言
  const handleLanguageChange = (lang: string) => {
    setLanguage(lang);
    i18n.changeLanguage(lang);
    localStorage.setItem('language', lang);
    message.success(t('settings.language.saveSuccess'));
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin tip={t('common.loading')} />
      </div>
    );
  }

  // 语言设置页面
  const LanguageSettings = () => (
    <div>
      <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid #f0f0f0' }}>
        {t('settings.language.title')}
      </div>
      <Form layout="vertical">
        <Form.Item label={t('settings.language.label')} extra={t('settings.language.hint')}>
          <Radio.Group value={language} onChange={(e) => handleLanguageChange(e.target.value)}>
            <Radio.Button value="zh-CN">{t('settings.language.zhCN')}</Radio.Button>
            <Radio.Button value="en-US">{t('settings.language.enUS')}</Radio.Button>
          </Radio.Group>
        </Form.Item>
      </Form>
    </div>
  );

  // 嵌入模型配置页面
  const EmbeddingSettings = () => (
    <div>
      <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid #f0f0f0' }}>
        {t('settings.embedding.title')}
      </div>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSaveEmbedding}
      >
        <Form.Item
          label={t('settings.embedding.model')}
          name="embedding_model"
          extra={t('settings.embedding.modelHint')}
        >
          <Select>
            <Option value="BAAI/bge-small-zh-v1.5">BAAI/bge-small-zh-v1.5 ({t('settings.embedding.modelZh')})</Option>
            <Option value="sentence-transformers/all-MiniLM-L6-v2">all-MiniLM-L6-v2 ({t('settings.embedding.modelEn')})</Option>
            <Option value="BAAI/bge-base-zh-v1.5">BAAI/bge-base-zh-v1.5 ({t('settings.embedding.modelLarge')})</Option>
          </Select>
        </Form.Item>

        <Form.Item
          label={t('settings.embedding.chunkSize')}
          name="chunk_size"
          extra={t('settings.embedding.chunkSizeHint')}
        >
          <Input type="number" min={200} max={2000} />
        </Form.Item>

        <Form.Item
          label={t('settings.embedding.topK')}
          name="top_k"
          extra={t('settings.embedding.topKHint')}
        >
          <Input type="number" min={1} max={20} />
        </Form.Item>

        <Form.Item
          label={t('settings.embedding.enableOcr')}
          name="enable_ocr"
          valuePropName="checked"
          extra={t('settings.embedding.enableOcrHint')}
        >
          <Switch />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
            {t('common.save')}
          </Button>
        </Form.Item>
      </Form>
    </div>
  );

  // 搜索精度配置页面
  const SearchSettings = () => (
    <div>
      <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid #f0f0f0' }}>
        {t('settings.search.title')}
      </div>
      <Form layout="vertical">
        <Form.Item label={t('settings.search.preset')} extra={t('settings.search.presetHint')}>
          <Radio.Group value={searchPreset} onChange={(e) => handlePresetChange(e.target.value)}>
            <Radio.Button value="fast">{t('settings.search.fast')}</Radio.Button>
            <Radio.Button value="normal">{t('settings.search.normal')}</Radio.Button>
            <Radio.Button value="precise">{t('settings.search.precise')}</Radio.Button>
          </Radio.Group>
        </Form.Item>
        
        <div style={{ padding: 16, background: '#fafafa', borderRadius: 8 }}>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>
            {t('settings.search.currentMode')}: {SEARCH_PRESETS[searchPreset]?.name || searchPreset}
          </div>
          <div style={{ fontSize: 13, color: '#666', lineHeight: 1.8 }}>
            {searchPreset === 'fast' && (
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                <li>{t('settings.search.fastDesc')}</li>
              </ul>
            )}
            {searchPreset === 'normal' && (
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                <li>{t('settings.search.normalDesc')}</li>
              </ul>
            )}
            {searchPreset === 'precise' && (
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                <li>{t('settings.search.preciseDesc')}</li>
              </ul>
            )}
          </div>
        </div>

        <Divider />

        <div style={{ fontSize: 13, color: '#999' }}>
          <strong>{t('settings.search.paramsDesc')}：</strong>
          <ul style={{ marginTop: 8, paddingLeft: 20 }}>
            <li>{t('settings.search.rerankDesc')}</li>
            <li>{t('settings.search.queryEnhanceDesc')}</li>
            <li>{t('settings.search.recallDesc')}</li>
          </ul>
        </div>
      </Form>
    </div>
  );

  // 大模型配置页面
  const LLMSettings = () => (
    <div>
      <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid #f0f0f0' }}>
        {t('settings.llm.title')}
      </div>
      <Form layout="vertical">
        <Form.Item label={t('settings.llm.provider')} extra={t('settings.llm.providerHint')}>
          <Select 
            value={llmConfig.provider} 
            onChange={(v) => {
              const defaults: any = {
                ollama: { api_url: 'http://localhost:11434', model: 'qwen2.5:7b' },
                qwen: { api_url: 'https://dashscope.aliyuncs.com/compatible-mode', model: 'qwen-plus' },
                glm: { api_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4' },
                deepseek: { api_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
                openai: { api_url: 'https://api.openai.com', model: 'gpt-4o-mini' }
              };
              const def = defaults[v] || {};
              setLlmConfig({ ...llmConfig, provider: v, api_url: def.api_url || '', model: def.model || '' });
            }}
            style={{ width: '100%' }}
          >
            <Option value="ollama">{t('settings.llm.providers.ollama')}</Option>
            <Option value="qwen">{t('settings.llm.providers.qwen')}</Option>
            <Option value="glm">{t('settings.llm.providers.glm')}</Option>
            <Option value="deepseek">{t('settings.llm.providers.deepseek')}</Option>
            <Option value="openai">{t('settings.llm.providers.openai')}</Option>
          </Select>
        </Form.Item>

        <Form.Item label={t('settings.llm.model')} extra={t('settings.llm.modelHint')}>
          <Input 
            value={llmConfig.model}
            onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
            placeholder={llmConfig.provider === 'ollama' ? 'qwen2.5:7b' : 'glm-4'}
          />
        </Form.Item>

        <Form.Item label={t('settings.llm.apiUrl')} extra={llmConfig.provider === 'ollama' ? t('settings.llm.apiUrlHintLocal') : t('settings.llm.apiUrlHintCloud')}>
          <Input 
            value={llmConfig.api_url}
            onChange={(e) => setLlmConfig({ ...llmConfig, api_url: e.target.value })}
            placeholder="http://localhost:11434"
          />
        </Form.Item>

        {llmConfig.provider !== 'ollama' && (
          <Form.Item label={t('settings.llm.apiKey')} extra={llmConfig.has_api_key ? t('settings.llm.apiKeyConfigured') : t('settings.llm.apiKeyHint')}>
            <Input.Password 
              value={llmConfig.api_key}
              onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value, has_api_key: !!e.target.value })}
              placeholder={llmConfig.has_api_key ? '•••••••••••••••• (' + t('common.configured') + ')' : 'sk-xxxxxxxxxxxxxxxx'}
              visibilityToggle
            />
          </Form.Item>
        )}

        <div style={{ display: 'flex', gap: 16 }}>
          <Form.Item label={t('settings.llm.maxTokens')} extra={t('settings.llm.maxTokensHint')} style={{ flex: 1 }}>
            <InputNumber 
              value={llmConfig.max_tokens}
              onChange={(v) => setLlmConfig({ ...llmConfig, max_tokens: v || 2048 })}
              min={100}
              max={8192}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label={t('settings.llm.temperature')} extra={t('settings.llm.temperatureHint')} style={{ flex: 1 }}>
            <InputNumber 
              value={llmConfig.temperature}
              onChange={(v) => setLlmConfig({ ...llmConfig, temperature: v || 0.7 })}
              min={0}
              max={1}
              step={0.1}
              style={{ width: '100%' }}
            />
          </Form.Item>
        </div>

        <Form.Item>
          <Button type="primary" onClick={saveLlmConfig} style={{ marginRight: 8 }} icon={<SaveOutlined />}>
            {t('common.save')}
          </Button>
          <Button onClick={testLlmConnection} loading={llmLoading}>
            {t('settings.llm.testConnection')}
          </Button>
          {llmTestResult && (
            <span style={{ marginLeft: 12, color: llmTestResult.includes(t('settings.llm.connectionSuccess')) ? '#52c41a' : '#ff4d4f' }}>
              {llmTestResult}
            </span>
          )}
        </Form.Item>

        <Divider />

        <div style={{ fontSize: 13, color: '#999' }}>
          <strong>{t('settings.llm.usageNote')}：</strong>
          <ul style={{ marginTop: 8, paddingLeft: 20 }}>
            <li>{t('settings.llm.ollamaNote')}</li>
            <li>{t('settings.llm.cloudNote')}</li>
            <li>{t('settings.llm.usageNote2')}</li>
          </ul>
        </div>
      </Form>
    </div>
  );

  // 渲染当前页面
  const renderContent = () => {
    switch (activeKey) {
      case 'embedding':
        return <EmbeddingSettings />;
      case 'search':
        return <SearchSettings />;
      case 'llm':
        return <LLMSettings />;
      case 'language':
        return <LanguageSettings />;
      default:
        return <EmbeddingSettings />;
    }
  };

  return renderContent();
};

export default Settings;
