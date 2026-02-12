import React from 'react';
import { Layout, Menu, Button, Avatar, Dropdown } from 'antd';
import {
  UploadOutlined,
  SearchOutlined,
  FileTextOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  ApiOutlined,
  RobotOutlined
} from '@ant-design/icons';
import DocumentUpload from './components/DocumentUpload';
import SearchInterface from './components/SearchInterface';
import DocumentList from './components/DocumentList';
import Settings from './components/Settings';
import Login from './components/Login';
import { AuthProvider, useAuth } from './contexts/AuthContext';

const { Header, Sider, Content } = Layout;

const AppContent: React.FC = () => {
  const { user, isAuthenticated, logout, isLoading } = useAuth();
  const [activeTab, setActiveTab] = React.useState('search');
  const [settingsTab, setSettingsTab] = React.useState('embedding');

  // 加载中
  if (isLoading) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center' 
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '18px', color: '#666' }}>加载中...</div>
        </div>
      </div>
    );
  }

  // 未登录
  if (!isAuthenticated) {
    return <Login />;
  }

  const menuItems = [
    {
      key: 'search',
      icon: <SearchOutlined />,
      label: '知识检索',
    },
    {
      key: 'upload',
      icon: <UploadOutlined />,
      label: '文档上传',
    },
    {
      key: 'documents',
      icon: <FileTextOutlined />,
      label: '文档管理',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '系统设置',
      children: [
        {
          key: 'settings-embedding',
          icon: <ApiOutlined />,
          label: '嵌入模型配置',
        },
        {
          key: 'settings-search',
          icon: <SearchOutlined />,
          label: '搜索精度配置',
        },
        {
          key: 'settings-llm',
          icon: <RobotOutlined />,
          label: '大模型接入配置',
        },
      ],
    },
  ];

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: logout
    }
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key.startsWith('settings-')) {
      setActiveTab('settings');
      setSettingsTab(key.replace('settings-', ''));
    } else {
      setActiveTab(key);
    }
  };

  // 获取选中的菜单key
  const getSelectedKeys = () => {
    if (activeTab === 'settings') {
      return [`settings-${settingsTab}`];
    }
    return [activeTab];
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'upload':
        return <DocumentUpload />;
      case 'search':
        return <SearchInterface />;
      case 'documents':
        return <DocumentList />;
      case 'settings':
        return <Settings activeKey={settingsTab} onTabChange={setSettingsTab} />;
      default:
        return <SearchInterface />;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#fff', padding: '0 24px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>
          AskMe 知识库系统
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ color: '#666', fontSize: '14px' }}>{user?.department}</span>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />
              <span style={{ color: '#333' }}>{user?.name}</span>
            </div>
          </Dropdown>
        </div>
      </Header>
      <Layout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={getSelectedKeys()}
            defaultOpenKeys={['settings']}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
            onClick={handleMenuClick}
          />
        </Sider>
        <Layout style={{ padding: '24px' }}>
          <Content
            style={{
              padding: 24,
              margin: 0,
              minHeight: 280,
              background: '#fff',
              borderRadius: 8,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
            }}
          >
            {renderContent()}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;