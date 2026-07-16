import React from 'react';
import { Drawer, Descriptions, Tag } from 'antd';
import type { MatchScore, MatchRankingItem, DimensionScore } from '@/types';

interface Props {
  open: boolean;
  data: MatchScore | MatchRankingItem | null;
  onClose: () => void;
}

function DimBlock({ title, d }: { title: string; d: DimensionScore }) {
  return (
    <Descriptions title={title} column={1} size="small" bordered style={{ marginBottom: 16 }}>
      <Descriptions.Item label="分数">{d.score}</Descriptions.Item>
      <Descriptions.Item label="说明">{d.rationale}</Descriptions.Item>
      {d.matched && d.matched.length > 0 && (
        <Descriptions.Item label="匹配项">
          {d.matched.map((m, i) => (
            <Tag key={i} color="green">
              {m}
            </Tag>
          ))}
        </Descriptions.Item>
      )}
      {d.missing && d.missing.length > 0 && (
        <Descriptions.Item label="缺失项">
          {d.missing.map((m, i) => (
            <Tag key={i} color="red">
              {m}
            </Tag>
          ))}
        </Descriptions.Item>
      )}
    </Descriptions>
  );
}

const MatchDetailDrawer: React.FC<Props> = ({ open, data, onClose }) => {
  const ds = data?.dimension_scores;
  const candidateName =
    data && 'candidate_name' in data && data.candidate_name ? data.candidate_name : '-';

  return (
    <Drawer title="匹配详情" open={open} onClose={onClose} width={520}>
      {data && ds ? (
        <>
          <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="综合分">{data.overall_score}</Descriptions.Item>
            <Descriptions.Item label="候选人">{candidateName}</Descriptions.Item>
            <Descriptions.Item label="状态">
              {data.is_stale ? '简历已更新' : '最新'}
            </Descriptions.Item>
          </Descriptions>

          <Descriptions title="综合评估" column={1} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item>{ds.overall_reasoning}</Descriptions.Item>
          </Descriptions>

          <DimBlock title="技能匹配" d={ds.skill_match} />
          <DimBlock title="经验匹配" d={ds.experience_match} />
          <DimBlock title="学历匹配" d={ds.education_match} />
        </>
      ) : null}
    </Drawer>
  );
};

export default MatchDetailDrawer;
