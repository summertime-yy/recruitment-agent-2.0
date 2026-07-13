import React from 'react';
import { FileSearchOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const ResumeWorkspace: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<FileSearchOutlined />}
      title="简历工作台"
      description="上传简历文件（PDF/Word），AI自动解析简历内容，提取候选人信息，进行结构化存储和标签化管理。此模块为Stage 2开发内容。"
    />
  );
};

export default ResumeWorkspace;
