import React from 'react';
import { TeamOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const CandidateChat: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<TeamOutlined />}
      title="候选人沟通 (Phase 2)"
      description="基于AI的候选人自动沟通机器人，回答常见问题、安排面试时间、发送跟进消息。此为Phase 2规划功能，将在核心模块完成后实现。"
    />
  );
};

export default CandidateChat;
