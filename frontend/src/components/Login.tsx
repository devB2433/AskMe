import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Select, message, Card, Tabs } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, TeamOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

interface Department {
  id: string;
  name: string;
  description?: string;
}

const Login: React.FC = () => {
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
      .catch(err => console.error('加载部门列表失败:', err));
  }, []);

  const handleLogin = async (values: any) => {
    setLoading(true);
    try {
      const result = await login(values.username, values.password);
      if (!result.success) {
        message.error(result.error || '登录失败');
      } else {
        message.success('登录成功');
      }
    } catch (err: any) {
      message.error(err.message || '登录失败');
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
        message.success('注册成功，请登录');
        setActiveTab('login');
        form.resetFields();
      } else {
        message.error(result.error || '注册失败');
      }
    } catch (err: any) {
      message.error(err.message || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'login',
      label: '登录',
      children: (
        <Form form={form} onFinish={handleLogin} layout="vertical">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder="请输入用户名" 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password 
              prefix={<LockOutlined />} 
              placeholder="请输入密码" 
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
              登录
            </Button>
          </Form.Item>
        </Form>
      )
    },
    {
      key: 'register',
      label: '注册',
      children: (
        <Form form={form} onFinish={handleRegister} layout="vertical">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder="请输入用户名" 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password 
              prefix={<LockOutlined />} 
              placeholder="请输入密码" 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="name"
            rules={[{ required: true, message: '请输入姓名' }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder="请输入您的姓名" 
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="department"
            rules={[{ required: true, message: '请选择部门' }]}
          >
            <Select 
              placeholder="请选择部门" 
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
              placeholder="请输入邮箱（可选）" 
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
              注册
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
          <h1 style={{ fontSize: 28, marginBottom: 8, color: '#1890ff' }}>AskMe 知识库</h1>
          <p style={{ color: '#666' }}>企业知识管理与智能检索平台</p>
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
