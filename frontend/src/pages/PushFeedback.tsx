import React from 'react';
import { SendOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const PushFeedback: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<SendOutlined />}
      title="推送反馈"
      description="通过邮件/短信/微信等渠道向候选人推送面试邀请、结果通知，并记录候选人的反馈和回应状态。此模块为Stage 6开发内容。"
    />
  );
};

export default PushFeedback;
