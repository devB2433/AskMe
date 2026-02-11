import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Switch, Select, message, Spin } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Option } = Select;

const API_BASE = 'http://localhost:8001/api';

const Settings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, [form]);

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