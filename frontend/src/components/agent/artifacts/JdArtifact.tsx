// PR-19 S5-13 · JD artifact 渲染器(commit 2 实现)。
import { Typography } from 'antd';
import type { ResultArtifact } from '@/types/agent';

interface JdData {
  title?: string;
  content?: string;
}

export function JdArtifact({ artifact }: { artifact: ResultArtifact }) {
  const d = (artifact.data ?? {}) as JdData;
  return (
    <div data-testid="jd-artifact" style={{ marginTop: 8 }}>
      <Typography.Text strong>JD{artifact.ref_id ? ` · ${artifact.ref_id}` : ''}</Typography.Text>
      {d.title && <Typography.Paragraph style={{ margin: '4px 0 0' }}>{d.title}</Typography.Paragraph>}
      {d.content && (
        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
          {d.content}
        </Typography.Paragraph>
      )}
    </div>
  );
}
