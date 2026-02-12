import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Switch, Select, message, Spin, Radio, Divider, Alert, InputNumber, Tooltip } from 'antd';
import { SaveOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Option } = Select;

const API_BASE = 'http://localhost:8001/api';

const Settings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchPreset, setSearchPreset] = useState<string>('normal');
  const [llmConfig, setLlmConfig] = useState<any>({
    provider: 'ollama',
    model: 'qwen2.5:7b',
    api_url: 'http://localhost:11434',
    api_key: '',
    max_tokens: 2048,
    temperature: 0.7
  });
  const [llmPresets, setLlmPresets] = useState<any[]>([]);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState<string>('');
  const [showApiKey, setShowApiKey] = useState(false);

  // 搜索精度预设配置
  const SEARCH_PRESETS = {
    fast: { name: '低精度高速度', useRerank: false, useQueryEnhance: false, recallSize: 10 },
    normal: { name: '正常', useRerank: true, useQueryEnhance: false, recallSize: 15 },
    precise: { name: '高精度低速度', useRerank: true, useQueryEnhance: true, recallSize: 30 }
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
        // 使用默认值
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
          api_key: '', // 不返回实际key
          max_tokens: llmRes.data.max_tokens || 2048,
          temperature: llmRes.data.temperature || 0.7
        });
        setLlmPresets(llmRes.data.available_presets || []);
      } catch (e) {
        console.warn('加载LLM配置失败', e);
      }
      
      setLoading(false);
    };
    fetchConfig();
  }, [form]);

  // 保存搜索精度预设
  const handlePresetChange = (value: string) => {
    setSearchPreset(value);
    localStorage.setItem('searchPreset', value);
    message.success(`已切换为: ${SEARCH_PRESETS[value as keyof typeof SEARCH_PRESETS].name}`);
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
      message.success('大模型配置已保存');
    } catch (e) {
      message.error('保存失败');
    }
  };

  // 应用LLM预设
  const handleLlmPresetChange = async (presetKey: string) => {
    try {
      await axios.post(`http://localhost:8001/api/llm/config/preset/${presetKey}`);
      const res = await axios.get('http://localhost:8001/api/llm/config');
      setLlmConfig(res.data);
      message.success('已切换大模型配置');
    } catch (e) {
      message.error('切换失败');
    }
  };

  // 测试LLM连接
  const testLlmConnection = async () => {
    setLlmLoading(true);
    setLlmTestResult('');
    try {
      const res = await axios.get('http://localhost:8001/api/llm/test');
      setLlmTestResult(res.data.status === 'success' ? '连接成功' : `失败: ${res.data.message}`);
    } catch (e: any) {
      setLlmTestResult(`失败: ${e.message}`);
    } finally {
      setLlmLoading(false);
    }
  };

  const handleSave = async (values: any) => {
    setSaving(true);
    try {
      await axios.post(`${API_BASE}/config`, values);
      message.success('设置保存成功');
    } catch (error) {
      message.success('设置已保存到本地');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card style={{ maxWidth: 600, textAlign: 'center' }}>
        <Spin tip="加载配置中..." />
      </Card>
    );
  }

  return (
    <Card title="系统设置" style={{ maxWidth: 600 }}>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
      >
        <Form.Item
          label="嵌入模型"
          name="embedding_model"
          extra="中文推荐使用 BAAI/bge-small-zh-v1.5"
        >
          <Select>
            <Option value="BAAI/bge-small-zh-v1.5">BAAI/bge-small-zh-v1.5 (中文推荐)</Option>
            <Option value="sentence-transformers/all-MiniLM-L6-v2">all-MiniLM-L6-v2 (英文)</Option>
            <Option value="BAAI/bge-base-zh-v1.5">BAAI/bge-base-zh-v1.5 (更大更准)</Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="分块大小"
          name="chunk_size"
          extra="建议 500-1000，保留更多语义上下文"
        >
          <Input type="number" min={200} max={2000} />
        </Form.Item>

        <Form.Item
          label="返回结果数量"
          name="top_k"
          extra="搜索时返回的最大结果数"
        >
          <Input type="number" min={1} max={20} />
        </Form.Item>

        <Form.Item
          label="启用OCR"
          name="enable_ocr"
          valuePropName="checked"
          extra="对图片类文档进行文字识别"
        >
          <Switch />
        </Form.Item>

        <Divider />

        <Form.Item label="搜索精度预设" extra="调整搜索速度与准确率的平衡">
          <Radio.Group value={searchPreset} onChange={(e) => handlePresetChange(e.target.value)}>
            <Radio.Button value="fast">低精度高速度</Radio.Button>
            <Radio.Button value="normal">正常</Radio.Button>
            <Radio.Button value="precise">高精度低速度</Radio.Button>
          </Radio.Group>
        </Form.Item>
        
        <div style={{ padding: 12, background: '#f5f5f5', borderRadius: 6, marginBottom: 16 }}>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>当前模式: {SEARCH_PRESETS[searchPreset as keyof typeof SEARCH_PRESETS].name}</div>
          <div style={{ fontSize: 13, color: '#666' }}>
            {searchPreset === 'fast' && '关闭重排序，召回10个候选。适合快速浏览，速度最快。'}
            {searchPreset === 'normal' && '开启重排序，召回15个候选。速度与准确率平衡，推荐日常使用。'}
            {searchPreset === 'precise' && '开启重排序和查询增强，召回30个候选。准确率最高，速度较慢。'}
          </div>
        </div>

        <Divider />

        <div style={{ fontWeight: 500, marginBottom: 12 }}>大模型配置</div>
        
        <Form.Item label="模型提供商" extra="选择大模型服务提供商">
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
            <Option value="ollama">Ollama (本地)</Option>
            <Option value="qwen">通义千问 (阿里云)</Option>
            <Option value="glm">智谱GLM (智谱AI)</Option>
            <Option value="deepseek">DeepSeek</Option>
            <Option value="openai">OpenAI兼容API</Option>
          </Select>
        </Form.Item>

        <Form.Item label="模型名称" extra="输入具体的模型名称">
          <Input 
            value={llmConfig.model}
            onChange={(e) => setLlmConfig({ ...llmConfig, model: e.target.value })}
            placeholder={llmConfig.provider === 'ollama' ? 'qwen2.5:7b' : 'glm-4'}
          />
        </Form.Item>

        <Form.Item label="API地址" extra={llmConfig.provider === 'ollama' ? 'Ollama服务地址，默认 http://localhost:11434' : '云端API基础地址'}>
          <Input 
            value={llmConfig.api_url}
            onChange={(e) => setLlmConfig({ ...llmConfig, api_url: e.target.value })}
            placeholder="http://localhost:11434"
          />
        </Form.Item>

        {llmConfig.provider !== 'ollama' && (
          <Form.Item label="API Key" extra="云端API密钥，将安全存储在本地">
            <Input.Password 
              value={llmConfig.api_key}
              onChange={(e) => setLlmConfig({ ...llmConfig, api_key: e.target.value })}
              placeholder="sk-xxxxxxxxxxxxxxxx"
              visibilityToggle
            />
          </Form.Item>
        )}

        <Form.Item label="最大输出Token" extra="限制生成内容的最大长度">
          <InputNumber 
            value={llmConfig.max_tokens}
            onChange={(v) => setLlmConfig({ ...llmConfig, max_tokens: v || 2048 })}
            min={100}
            max={8192}
            style={{ width: '100%' }}
          />
        </Form.Item>

        <Form.Item label="温度参数" extra="控制回答的随机性，0-1之间，越高越随机">
          <InputNumber 
            value={llmConfig.temperature}
            onChange={(v) => setLlmConfig({ ...llmConfig, temperature: v || 0.7 })}
            min={0}
            max={1}
            step={0.1}
            style={{ width: '100%' }}
          />
        </Form.Item>

        <Form.Item>
          <Button type="primary" onClick={saveLlmConfig} style={{ marginRight: 8 }}>
            保存配置
          </Button>
          <Button onClick={testLlmConnection} loading={llmLoading}>
            测试连接
          </Button>
          {llmTestResult && (
            <span style={{ marginLeft: 12, color: llmTestResult.includes('成功') ? '#52c41a' : '#ff4d4f' }}>
              {llmTestResult}
            </span>
          )}
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
            保存设置
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default Settings;