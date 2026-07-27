import React, { useCallback, useEffect, useState } from 'react';
import { Button, Collapse, Input, Select, Space } from 'antd';
import { useTaskStream } from '@/hooks/useTaskStream';
import { agentApi } from '@/services/agent';
import { jdApi } from '@/services/jd';
import { resumeApi } from '@/services/resume';
import { StreamStatusBar } from '@/components/agent/StreamStatusBar';
import { MessageTimeline } from '@/components/agent/MessageTimeline';
import type { JD, Resume } from '@/types';

// PR-19 S5-13 · ChatCenter 对话式任务中心。
// 结构:SkipToScorePanel(可折叠) + 任务流(StreamStatusBar + MessageTimeline) + 消息输入框。

function TaskStream({ taskId }: { taskId: string }) {
  const { events, latestByType } = useTaskStream({ taskId });
  const systemMessage = latestByType.system?.data?.message;

  const handleConfirm = useCallback(() => {
    void agentApi.executePlan({ task_id: taskId });
  }, [taskId]);

  const handleCancel = useCallback(() => {
    void agentApi.cancelTask(taskId);
  }, [taskId]);

  return (
    <>
      <StreamStatusBar systemMessage={systemMessage} />
      <MessageTimeline events={events} onPlanConfirm={handleConfirm} onPlanCancel={handleCancel} />
    </>
  );
}

function SkipToScorePanel({
  onScore,
}: {
  onScore: (jdId: string, candidateIds: string[]) => void;
}) {
  const [jds, setJds] = useState<JD[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [jdId, setJdId] = useState<string>();
  const [candidateIds, setCandidateIds] = useState<string[]>([]);

  useEffect(() => {
    void jdApi.list().then((r) => setJds(r.items));
    void resumeApi.list().then((r) => setResumes(r.items));
  }, []);

  return (
    <Collapse style={{ marginBottom: 16 }}>
      <Collapse.Panel header="跳过计划直接评分" key="skip">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Select
            placeholder="选择 JD"
            value={jdId}
            onChange={setJdId}
            options={jds.map((j) => ({ label: j.title, value: j.jd_id }))}
            style={{ width: 280 }}
          />
          <Select
            mode="multiple"
            placeholder="选择候选人简历"
            value={candidateIds}
            onChange={setCandidateIds}
            options={resumes.map((r) => ({ label: r.candidate_name ?? r.resume_id, value: r.resume_id }))}
            style={{ width: 280 }}
          />
          <Button
            type="primary"
            disabled={!jdId || candidateIds.length === 0}
            onClick={() => jdId && onScore(jdId, candidateIds)}
          >
            立即评分
          </Button>
        </Space>
      </Collapse.Panel>
    </Collapse>
  );
}

const ChatCenter: React.FC = () => {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [message, setMessage] = useState('');

  const handleSend = useCallback(async () => {
    const text = message.trim();
    if (!text) return;
    const res = await agentApi.chat({ message: text });
    setTaskId(res.task_id);
    setMessage('');
  }, [message]);

  const handleScore = useCallback(async (jdId: string, candidateIds: string[]) => {
    const res = await agentApi.skipToScore({ jd_id: jdId, candidate_ids: candidateIds });
    setTaskId(res.task_id);
  }, []);

  return (
    <div style={{ padding: 16, maxWidth: 720 }}>
      <SkipToScorePanel onScore={handleScore} />
      {taskId && <TaskStream key={taskId} taskId={taskId} />}
      <div style={{ marginTop: 16 }}>
        <Input.TextArea
          placeholder="输入消息..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          autoSize={{ minRows: 2, maxRows: 6 }}
        />
        <Button type="primary" style={{ marginTop: 8 }} onClick={() => void handleSend()}>
          发送
        </Button>
      </div>
    </div>
  );
};

export default ChatCenter;
