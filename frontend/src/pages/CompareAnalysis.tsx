import React from 'react';
import { SwapOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const CompareAnalysis: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<SwapOutlined />}
      title="对比分析 (Phase 2)"
      description="多候选人横向对比、多个JD的招聘效果对比、不同渠道来源效果对比。此为Phase 2规划功能，将在核心模块完成后实现。"
    />
  );
};

export default CompareAnalysis;
