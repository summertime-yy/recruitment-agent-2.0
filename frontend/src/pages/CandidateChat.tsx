// PR-27 · 候选人对话 / 画像页活化。
// 接 URL ?candidates=a,b → 复用 <TaskStream /> 渲染流式;无 candidates 时引导去简历库。
import { useCallback, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button, Empty, Input, Space } from 'antd';
import { agentApi } from '@/services/agent';
import { TaskStream } from '@/components/agent/TaskStream';

export default function CandidateChat() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(location.search);
  const candidateIds = (params.get('candidates') ?? '').split(',').filter(Boolean);

  const [message, setMessage] = useState('');
  const [taskId, setTaskId] = useState<string | null>(null);

  const handleSend = useCallback(async () => {
    const text = message.trim();
    if (!text || candidateIds.length === 0) return;
    const res = await agentApi.chat({ message: text, context: { candidate_ids: candidateIds } });
    setTaskId(res.task_id);
    setMessage('');
  }, [message, candidateIds]);

  if (candidateIds.length === 0) {
    return (
      <div style={{ padding: 16 }}>
        <Empty description="请先在候选人列表选择要对话的候选人">
          <Button type="primary" onClick={() => navigate('/resumes')}>
            去候选人列表选择
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, maxWidth: 720 }}>
      {taskId && <TaskStream key={taskId} taskId={taskId} showSkipToScore={false} />}
      <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
        <Input.TextArea
          placeholder="输入消息..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={3}
        />
        <Button type="primary" onClick={handleSend}>
          发送
        </Button>
      </Space>
    </div>
  );
}
