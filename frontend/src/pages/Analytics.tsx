import React from 'react';
import { LineChartOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const Analytics: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<LineChartOutlined />}
      title="数据看板"
      description="招聘漏斗分析、各环节转化率统计、JD效果分析、招聘周期追踪、Skill执行成功率监控等数据可视化。"
    />
  );
};

export default Analytics;
