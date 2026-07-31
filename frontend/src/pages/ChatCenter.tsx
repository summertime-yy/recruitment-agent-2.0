// PR-19 S5-13 · 招聘助手主对话页。
// PR-27 · 抽 TaskStream 组件复用:本页只负责持有 taskId + 输入,流式渲染交给 <TaskStream />。
import { useCallback, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Layout } from 'antd';
import { agentApi } from '@/services/agent';
import { TaskStream } from '@/components/agent/TaskStream';

export default function ChatCenter() {
  const { jdId, resumeId } = useParams();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [input, setInput] = useState('');

  const handleSend = useCallback(
    async (text: string) => {
      const res = await agentApi.chat({
        message: text,
        context: { jd_id: jdId ?? '', resume_id: resumeId ?? '' },
      });
      setTaskId(res.task_id);
      setInput('');
    },
    [jdId, resumeId],
  );

  return (
    <Layout style={{ height: '100%' }}>
      <TaskStream
        key={taskId ?? 'empty'}
        taskId={taskId ?? ''}
        showSkipToScore
        showInput
        input={input}
        onInputChange={setInput}
        onSend={handleSend}
        onTaskCreated={setTaskId}
      />
    </Layout>
  );
}
