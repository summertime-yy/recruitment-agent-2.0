import React from 'react';
import { SettingOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const Settings: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<SettingOutlined />}
      title="系统设置"
      description="LLM模型配置（API Key、模型选择、温度参数）、Skill管理（注册/启用/禁用技能）、面试邮件模板、合规规则配置、用户权限管理。"
    />
  );
};

export default Settings;
