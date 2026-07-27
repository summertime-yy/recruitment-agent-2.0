// PR-19 S5-13 · CandidateChat 页面(commit 4)。
import { useCallback, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Button, Input, Space } from 'antd';
import { agentApi } from '@/services/agent';

const CandidateChat: React.FC = () => {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const candidateIds = (params.get('candidates') ?? '').split(',').filter(Boolean);

  const [message, setMessage] = useState('');

  const handleSend = useCallback(async () => {
    const text = message.trim();
    if (!text || candidateIds.length === 0) return;
    await agentApi.chat({ message: text, context: { candidate_ids: candidateIds } });
    setMessage('');
  }, [message, candidateIds]);

  return (
    <div>
      <Space direction="vertical" style={{ width: 400 }}>
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
};

export default CandidateChat;
