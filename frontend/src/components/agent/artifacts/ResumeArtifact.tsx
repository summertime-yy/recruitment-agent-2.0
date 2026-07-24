// PR-19 S5-13 · Resume artifact 渲染器(commit 2 实现)。
import { Typography } from 'antd';
import type { ResultArtifact } from '@/types/agent';

interface ResumeData {
  candidate_name?: string;
  filename?: string;
}

export function ResumeArtifact({ artifact }: { artifact: ResultArtifact }) {
  const d = (artifact.data ?? {}) as ResumeData;
  return (
    <div data-testid="resume-artifact" style={{ marginTop: 8 }}>
      <Typography.Text strong>简历{artifact.ref_id ? ` · ${artifact.ref_id}` : ''}</Typography.Text>
      {d.candidate_name && <Typography.Paragraph style={{ margin: '4px 0 0' }}>{d.candidate_name}</Typography.Paragraph>}
      {d.filename && (
        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
          {d.filename}
        </Typography.Paragraph>
      )}
    </div>
  );
}
