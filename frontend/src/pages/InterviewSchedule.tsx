import React from 'react';
import { CalendarOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const InterviewSchedule: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<CalendarOutlined />}
      title="面试安排 (Phase 2)"
      description="面试日程管理、面试官分配、会议室预约、自动提醒、面试评价表收集。此为Phase 2规划功能，将在核心模块完成后实现。"
    />
  );
};

export default InterviewSchedule;
