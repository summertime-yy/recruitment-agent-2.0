// PR-27 · 从 ChatCenter 抽出的复用流式组件。
// 基于真实 useTaskStream({ taskId }) 订阅 SSE;处理 plan 确认/取消,
// 并按需渲染 skip-to-score 面板与输入区,供 ChatCenter 与 CandidateChat 复用。
import { useCallback } from 'react';
import { Layout, Input, Button, Space, Typography } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { useTaskStream } from '@/hooks/useTaskStream';
import { agentApi } from '@/services/agent';
import { StreamStatusBar } from './StreamStatusBar';
import { MessageTimeline } from './MessageTimeline';
import { SkipToScorePanel } from './SkipToScorePanel';

export interface TaskStreamProps {
  taskId: string;
  showSkipToScore?: boolean;
  showInput?: boolean;
  input?: string;
  onInputChange?: (value: string) => void;
  onSend?: (text: string) => void;
  onTaskCreated?: (taskId: string) => void;
}

export function TaskStream({
  taskId,
  showSkipToScore = false,
  showInput = false,
  input = '',
  onInputChange,
  onSend,
  onTaskCreated,
}: TaskStreamProps) {
  const { events, latestByType, status } = useTaskStream({ taskId, autoStart: !!taskId });


  const systemMessage = (latestByType.system?.data as { message?: string } | undefined)?.message;

  const handleConfirm = useCallback(() => {
    void agentApi.executePlan({ task_id: taskId });
  }, [taskId]);
  const handleCancel = useCallback(() => {
    void agentApi.cancelTask(taskId);
  }, [taskId]);

  const isBusy = status === 'connecting' || status === 'streaming';
  const canSend = !!input.trim() && !isBusy;

  return (
    <Layout style={{ height: '100%' }}>
      <Layout.Header
        style={{
          background: '#fff',
          borderBottom: '1px solid #f0f0f0',
          padding: '0 16px',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          AI 助理
        </Typography.Title>
      </Layout.Header>
      <Layout.Content style={{ padding: 16, overflowY: 'auto', background: '#fafafa' }}>
        <StreamStatusBar systemMessage={systemMessage} />
        <MessageTimeline events={events} onPlanConfirm={handleConfirm} onPlanCancel={handleCancel} />
      </Layout.Content>
      {showSkipToScore && <SkipToScorePanel onTaskCreated={onTaskCreated} />}
      {showInput && (
        <div style={{ borderTop: '1px solid #f0f0f0', padding: 12 }}>
          <Input.TextArea
            value={input}
            onChange={(e) => onInputChange?.(e.target.value)}
            placeholder="输入消息..."
            autoSize={{ minRows: 1, maxRows: 3 }}
            onPressEnter={(e) => {
              e.preventDefault();
              if (canSend) onSend?.(input);
            }}
            disabled={isBusy}
            style={{ marginBottom: 8 }}
          />
          <Space>
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={isBusy}
              disabled={!canSend}
              onClick={() => canSend && onSend?.(input)}
            >
              发送
            </Button>
          </Space>
        </div>
      )}
    </Layout>
  );
}

export default TaskStream;
