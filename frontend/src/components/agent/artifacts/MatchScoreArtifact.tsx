// PR-19 S5-13 · MatchScore artifact 渲染器(commit 2 实现)。
import { Typography } from 'antd';
import type { ResultArtifact } from '@/types/agent';

interface MatchScoreData {
  overall_score?: number;
  candidate_name?: string;
  jd_title?: string;
}

export function MatchScoreArtifact({ artifact }: { artifact: ResultArtifact }) {
  const d = (artifact.data ?? {}) as MatchScoreData;
  return (
    <div data-testid="match-score-artifact" style={{ marginTop: 8 }}>
      <Typography.Text strong>
        匹配分{artifact.ref_id ? ` · ${artifact.ref_id}` : ''}
      </Typography.Text>
      {typeof d.overall_score === 'number' && (
        <Typography.Paragraph style={{ margin: '4px 0 0' }}>总分：{d.overall_score}</Typography.Paragraph>
      )}
      {d.candidate_name && (
        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
          候选人：{d.candidate_name}
        </Typography.Paragraph>
      )}
    </div>
  );
}
