import React from 'react';
import { Table, Tag, Button, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { MatchRankingItem } from '@/types';

interface Props {
  items: MatchRankingItem[];
  loading?: boolean;
  onViewDetail: (item: MatchRankingItem) => void;
  onRematch: (item: MatchRankingItem) => void;
}

const MatchRankingTable: React.FC<Props> = ({ items, loading, onViewDetail, onRematch }) => {
  const columns: ColumnsType<MatchRankingItem> = [
    {
      title: '候选人',
      dataIndex: 'candidate_name',
      key: 'candidate_name',
      render: (v: string | null | undefined) => v || '-',
    },
    {
      title: '综合分',
      dataIndex: 'overall_score',
      key: 'overall_score',
      sorter: (a, b) => a.overall_score - b.overall_score,
    },
    {
      title: '技能',
      key: 'skill',
      render: (_, r) => r.dimension_scores.skill_match.score,
    },
    {
      title: '经验',
      key: 'exp',
      render: (_, r) => r.dimension_scores.experience_match.score,
    },
    {
      title: '学历',
      key: 'edu',
      render: (_, r) => r.dimension_scores.education_match.score,
    },
    {
      title: '状态',
      key: 'status',
      render: (_, r) =>
        r.is_stale ? <Tag color="orange">简历已更新</Tag> : <Tag color="green">最新</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_, r) => (
        <Space>
          <Button size="small" onClick={() => onViewDetail(r)}>
            详情
          </Button>
          <Button size="small" type="primary" ghost onClick={() => onRematch(r)}>
            重新匹配
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Table
      rowKey="score_id"
      columns={columns}
      dataSource={items}
      loading={loading}
      pagination={false}
    />
  );
};

export default MatchRankingTable;
