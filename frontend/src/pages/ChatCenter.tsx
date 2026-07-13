import React from 'react';
import { MessageOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const ChatCenter: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<MessageOutlined />}
      title="任务中心 (对话式)"
      description="通过自然语言对话与招聘Agent交互，Agent会根据你的需求分解任务、制定计划并执行。此模块对应Stage 5的Orchestrator + SSE对话能力，将在JD、简历、评分模块完成后实现。"
    />
  );
};

export default ChatCenter;
