import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Select, message, Card, Tabs } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, TeamOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';

interface Department {
  id: string;
  name: string;
  description?: string;
}

const Login: React.FC = () => {
  const { t } = useTranslation();
  const { login, register } = useAuth();
  const [activeTab, setActiveTab] = useState('login');
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  // 加载部门列表
  useEffect(() => {
    fetch('http://localhost:8001/api/users/departments')
      .then(res => res.json())
      .then(data => {
        if (data.departments) {
          setDepartments(data.departments);
        }
      })
      .catch(err => console.error('Failed to load departments:', err));
  }, []);

  const handleLogin = async (values: any) => {
    setLoading(true);
    try {
      const result = await login(values.username, values.password);
      if (!result.success) {
        message.error(result.error || t('login.loginFailed'));
      } else {
        message.success(t('login.loginSuccess'));
      }
    } catch (err: any) {
      message.error(err.message || t('login.loginFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: any) => {
    setLoading(true);
    try {
      const result = await register({
        username: values.username,
        password: values.password,
        name: values.name,
        department: values.department,
        email: values.email
      });
      if (result.success) {
        message.success(t('login.registerSuccess'));
        setActiveTab('login');
        form.resetFields();
      } else {
        message.error(result.error || t('login.registerFailed'));
      }
    } catch (err: any) {
      message.error(err.message || t('login.registerFailed'));
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'login',
      label: t('login.title'),
      children: (
        <Form form={form} onFinish={handleLogin} layout="vertical">
          <Form.Item
            name="username"
            rules={[{ required: true, message: t('login.username') }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder={t('login.username')} 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: t('login.password') }]}
          >
            <Input.Password 
              prefix={<LockOutlined />} 
              placeholder={t('login.password')} 
              size="large"
            />
          </Form.Item>
          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading} 
              block 
              size="large"
            >
              {t('login.loginBtn')}
            </Button>
          </Form.Item>
        </Form>
      )
    },
    {
      key: 'register',
      label: t('login.register'),
      children: (
        <Form form={form} onFinish={handleRegister} layout="vertical">
          <Form.Item
            name="username"
            rules={[{ required: true, message: t('login.username') }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder={t('login.username')} 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: t('login.password') }]}
          >
            <Input.Password 
              prefix={<LockOutlined />} 
              placeholder={t('login.password')} 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="name"
            rules={[{ required: true, message: t('login.username') }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder={t('login.username')} 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="department"
            rules={[{ required: true, message: t('login.department') }]}
          >
            <Select 
              placeholder={t('login.department')} 
              size="large"
              suffixIcon={<TeamOutlined />}
            >
              {departments.map(dept => (
                <Select.Option key={dept.id} value={dept.name}>
                  {dept.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="email">
            <Input 
              prefix={<MailOutlined />} 
              placeholder={t('login.department')} 
              size="large"
            />
          </Form.Item>
          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading} 
              block 
              size="large"
            >
              {t('login.registerBtn')}
            </Button>
          </Form.Item>
        </Form>
      )
    }
  ];

  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      background: '#f0f2f5'
    }}>
      <Card style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <h1 style={{ fontSize: 28, marginBottom: 8, color: '#1890ff' }}>AskMe</h1>
          <p style={{ color: '#666' }}>{t('header.title')}</p>
        </div>
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab} 
          items={tabItems}
          centered
        />
      </Card>
    </div>
  );
};

export default Login;
