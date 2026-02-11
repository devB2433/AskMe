import React from 'react';
import { Card, Form, Input, Switch, Button } from 'antd';

const Settings: React.FC = () => {
  return (
    <Card title="系统设置">
      <Form layout="vertical">
        <Form.Item label="OCR功能">
          <Switch defaultChecked />
          <span style={{ marginLeft: 8 }}>启用OCR文字识别</span>
        </Form.Item>
        
        <Form.Item label="最大文件大小">
          <Input defaultValue="50MB" />
        </Form.Item>
        
        <Form.Item>
          <Button type="primary">保存设置</Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default Settings;