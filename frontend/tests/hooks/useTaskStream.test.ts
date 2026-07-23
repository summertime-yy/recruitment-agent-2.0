import { describe, test } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import request from '@/utils/request';
import { useTaskStream } from '@/hooks/useTaskStream';
import type { SSEEventType } from '@/types/agent';

const base = request.defaults.baseURL || '';
const streamUrl = (taskId: string) => `${base}/agent/tasks/${taskId}/stream`;

function makeStream(events: Array<{ id: string; type: string; data: unknown }>) {
  const text = events
    .map((e) => `id: ${e.id}\nevent: ${e.type}\ndata: ${JSON.stringify(e.data)}\n\n`)
    .join('');
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
  return new HttpResponse(stream, { headers: { 'content-type': 'text/event-stream' } });
}

describe('useTaskStream (S5-12)', () => {
  test.fails('TC-S5-12-1 parses all 8 SSE event types and routes system heartbeat', async () => {
    const frames = [
      { id: '1', type: 'thinking', data: { content: 'thinking...' } },
      { id: '2', type: 'plan', data: { task_id: 't1', steps: [] } },
      { id: '3', type: 'tool_call', data: { step_id: 's1', tool_name: 'search_resumes', params: {} } },
      { id: '4', type: 'progress', data: { step_id: 's1', progress: 0.5, message: 'working' } },
      {
        id: '5',
        type: 'result',
        data: {
          content: 'done',
          artifacts: [{ step_id: 's1', tool_name: 'search_resumes', type: 'resume', data: {} }],
        },
      },
      { id: '6', type: 'error', data: { code: 'E1', message: 'boom' } },
      { id: '7', type: 'warning', data: { message: 'careful' } },
      { id: '8', type: 'system', data: { message: 'heartbeat' } },
    ];
    server.use(http.get(streamUrl('t1'), () => makeStream(frames)));

    const { result } = renderHook(() => useTaskStream({ taskId: 't1' }));
    await waitFor(() => expect(result.current.events.length).toBe(7));

    const byType = (t: SSEEventType) => result.current.events.find((e) => e.type === t);
    expect(byType('thinking')?.data).toMatchObject({ content: 'thinking...' });
    expect(byType('plan')?.data).toMatchObject({ task_id: 't1' });
    expect(byType('tool_call')?.data).toMatchObject({ tool_name: 'search_resumes' });
    expect(byType('progress')?.data).toMatchObject({ progress: 0.5 });
    expect(byType('result')?.data).toMatchObject({ content: 'done' });
    expect(byType('error')?.data).toMatchObject({ code: 'E1' });
    expect(byType('warning')?.data).toMatchObject({ message: 'careful' });

    expect(result.current.events.find((e) => e.type === 'system')).toBeUndefined();
    expect(result.current.latestByType.system?.type).toBe('system');
    expect(typeof result.current.lastHeartbeatAt).toBe('number');
    expect(result.current.lastEventId).toBe('8');
    expect(result.current.status).toBe('closed');
  });

  test.fails(
    'TC-S5-12-2 reconnects with Last-Event-ID header after a non-terminal disconnect',
    async () => {
      let callCount = 0;
      const lastEventIds: Array<string | null> = [];
      server.use(
        http.get(streamUrl('t1'), ({ request }) => {
          callCount += 1;
          if (callCount === 1) {
            return makeStream([
              { id: '1', type: 'thinking', data: { content: 'a' } },
              { id: '2', type: 'progress', data: { step_id: 's1', progress: 0.4, message: 'm' } },
            ]);
          }
          lastEventIds.push(request.headers.get('last-event-id'));
          return makeStream([
            { id: '3', type: 'progress', data: { step_id: 's1', progress: 0.8, message: 'm2' } },
            { id: '4', type: 'result', data: { content: 'done' } },
          ]);
        }),
      );

      const { result } = renderHook(() => useTaskStream({ taskId: 't1' }));
      await waitFor(() => expect(result.current.status).toBe('closed'));
      await waitFor(() => expect(result.current.events.length).toBe(4));
      expect(callCount).toBe(2);
      expect(lastEventIds[0]).toBe('2');
      expect(result.current.lastEventId).toBe('4');
    },
  );
});
