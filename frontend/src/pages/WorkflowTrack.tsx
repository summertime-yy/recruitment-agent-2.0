import React from 'react';
import { BranchesOutlined } from '@ant-design/icons';
import PlaceholderPage from '@/components/PlaceholderPage';

const WorkflowTrack: React.FC = () => {
  return (
    <PlaceholderPage
      icon={<BranchesOutlined />}
      title="流程跟踪 (Phase 2)"
      description="可视化招聘工作流，查看每个候选人的招聘进度和状态流转，瓶颈识别。此为Phase 2规划功能，将在核心模块完成后实现。"
    />
  );
};

export default WorkflowTrack;
