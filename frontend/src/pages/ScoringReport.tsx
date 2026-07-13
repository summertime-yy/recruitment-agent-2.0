import React from 'react';
import { BarChartOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const ScoringReport: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<BarChartOutlined />}
      title="评分报告"
      description="根据JD要求自动对候选人进行多维度评分匹配，生成详细的匹配报告和排名，帮助HR快速筛选最合适的候选人。此模块为Stage 4开发内容（依赖Stage 2简历模块）。"
    />
  );
};

export default ScoringReport;
