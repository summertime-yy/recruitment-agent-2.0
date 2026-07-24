// PR-19 S5-13 · CandidateProfile artifact 渲染器(commit 2 实现)。
import { Typography } from 'antd';
import type { ResultArtifact } from '@/types/agent';

interface CandidateProfileData {
  candidate_name?: string;
  summary?: string;
}

export function CandidateProfileArtifact({ artifact }: { artifact: ResultArtifact }) {
  const d = (artifact.data ?? {}) as CandidateProfileData;
  return (
    <div data-testid="candidate-profile-artifact" style={{ marginTop: 8 }}>
      <Typography.Text strong>候选人画像{artifact.ref_id ? ` · ${artifact.ref_id}` : ''}</Typography.Text>
      {d.candidate_name && <Typography.Paragraph style={{ margin: '4px 0 0' }}>{d.candidate_name}</Typography.Paragraph>}
      {d.summary && (
        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
          {d.summary}
        </Typography.Paragraph>
      )}
    </div>
  );
}
