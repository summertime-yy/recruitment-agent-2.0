// PR-19 S5-13 · Generic artifact 渲染器(commit 2 实现 · never 兜底)。
import { Typography } from 'antd';
import type { ResultArtifact } from '@/types/agent';

export function GenericArtifact({ artifact }: { artifact: ResultArtifact }) {
  return (
    <div data-testid="generic-artifact" style={{ marginTop: 8 }}>
      <Typography.Text strong>{artifact.tool_name || '产物'}</Typography.Text>
      {artifact.ref_id && (
        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
          ref_id：{artifact.ref_id}
        </Typography.Paragraph>
      )}
    </div>
  );
}
