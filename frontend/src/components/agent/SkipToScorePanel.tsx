// PR-27 · 跳过调研直接评分面板(从 ChatCenter 抽出并补全真实 API 契约)。
// 展开后选择 JD + 候选人简历,点击「立即评分」→ agentApi.skipToScore({jd_id, candidate_ids})。
// 评分任务创建后通过 onTaskCreated 回传 task_id,由上层 TaskStream 接管流式。
import { useEffect, useState } from 'react';
import { Collapse, Select, Button, message } from 'antd';
import { FastForwardOutlined } from '@ant-design/icons';
import { jdApi } from '@/services/jd';
import { resumeApi } from '@/services/resume';
import { agentApi } from '@/services/agent';
import type { Resume } from '@/types';

interface Option {
  value: string;
  label: string;
}

export interface SkipToScorePanelProps {
  onTaskCreated?: (taskId: string) => void;
}

export function SkipToScorePanel({ onTaskCreated }: SkipToScorePanelProps) {
  const [jdId, setJdId] = useState<string | undefined>(undefined);
  const [candidateIds, setCandidateIds] = useState<string[]>([]);
  const [jdOptions, setJdOptions] = useState<Option[]>([]);
  const [resumeOptions, setResumeOptions] = useState<Option[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([jdApi.list(), resumeApi.list()])
      .then(([jdRes, resumeRes]) => {
        if (!active) return;
        const jds = (jdRes?.items ?? []).map(
          (jd: { jd_id: string; title: string }) => ({ value: jd.jd_id, label: jd.title }),
        );
        const resumes = (resumeRes?.items ?? []).map((r: Resume) => ({
          value: r.resume_id,
          label: r.candidate_name ?? r.resume_id,
        }));
        setJdOptions(jds);
        setResumeOptions(resumes);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const handleSkip = async () => {
    if (!jdId || candidateIds.length === 0) return;
    setLoading(true);
    try {
      const res = await agentApi.skipToScore({ jd_id: jdId, candidate_ids: candidateIds });
      message.success('已跳过至评分阶段');
      if (res?.task_id) onTaskCreated?.(res.task_id);
    } catch {
      message.error('跳过失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Collapse
      style={{ marginBottom: 8 }}
      items={[
        {
          key: 'skip',
          label: '跳过计划直接评分',
          children: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Select
                placeholder="选择 JD"
                value={jdId}
                onChange={setJdId}
                options={jdOptions}
                style={{ width: '100%' }}
              />
              <Select
                mode="multiple"
                placeholder="选择候选人简历"
                value={candidateIds}
                onChange={setCandidateIds}
                options={resumeOptions}
                style={{ width: '100%' }}
              />
              <Button
                type="primary"
                icon={<FastForwardOutlined />}
                loading={loading}
                disabled={!jdId || candidateIds.length === 0}
                onClick={handleSkip}
              >
                立即评分
              </Button>
            </div>
          ),
        },
      ]}
    />
  );
}

export default SkipToScorePanel;
