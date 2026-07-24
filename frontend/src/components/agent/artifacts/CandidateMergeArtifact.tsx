// PR-19 S5-13 · CandidateMerge artifact 渲染器(commit 2 实现)。
import { Typography } from 'antd';
import type { ResultArtifact } from '@/types/agent';

interface CandidateMergeData {
  merged_count?: number;
  primary_candidate?: string;
}

export function CandidateMergeArtifact({ artifact }: { artifact: ResultArtifact }) {
  const d = (artifact.data ?? {}) as CandidateMergeData;
  return (
    <div data-testid="candidate-merge-artifact" style={{ marginTop: 8 }}>
      <Typography.Text strong>候选人合并{artifact.ref_id ? ` · ${artifact.ref_id}` : ''}</Typography.Text>
      {typeof d.merged_count === 'number' && (
        <Typography.Paragraph style={{ margin: '4px 0 0' }}>合并数量：{d.merged_count}</Typography.Paragraph>
      )}
      {d.primary_candidate && (
        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
          主候选人：{d.primary_candidate}
        </Typography.Paragraph>
      )}
    </div>
  );
}
