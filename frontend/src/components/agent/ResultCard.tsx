// PR-19 S5-13 · 结果卡片(commit 2 实现 · 含 artifact switch/never 断言)。
import { Fragment } from 'react';
import { Typography } from 'antd';
import type { SSEEvent, ResultData, ResultArtifact } from '@/types/agent';
import { CardContainer } from './CardContainer';
import {
  JdArtifact,
  ResumeArtifact,
  MatchScoreArtifact,
  CandidateMergeArtifact,
  CandidateProfileArtifact,
  GenericArtifact,
} from './artifacts';

function renderArtifact(artifact: ResultArtifact) {
  switch (artifact.type) {
    case 'jd':
      return <JdArtifact artifact={artifact} />;
    case 'resume':
      return <ResumeArtifact artifact={artifact} />;
    case 'match_score':
      return <MatchScoreArtifact artifact={artifact} />;
    case 'candidate_merge':
      return <CandidateMergeArtifact artifact={artifact} />;
    case 'candidate_profile':
      return <CandidateProfileArtifact artifact={artifact} />;
    case 'generic':
      return <GenericArtifact artifact={artifact} />;
    default: {
      const _exhaustive: never = artifact.type;
      void _exhaustive;
      return <GenericArtifact artifact={artifact} />;
    }
  }
}

export function ResultCard({ event }: { event: SSEEvent<ResultData> }) {
  const { content, artifacts } = event.data;
  return (
    <CardContainer title="结果" testId="result-card">
      <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{content}</Typography.Paragraph>
      {artifacts?.map((a, i) => (
        <Fragment key={i}>{renderArtifact(a)}</Fragment>
      ))}
    </CardContainer>
  );
}
