// PR-19 S5-13 · SSE mock helper(从 PR-18 useTaskStream.test 范式抽取)。
// 导出 makeSseHandler(url, frames) 与 SSEFrame;复用 msw v2 http.get + ReadableStream。
import { http, HttpResponse } from 'msw';
import request from '@/utils/request';

export interface SSEFrame {
  id: string;
  event: string;
  data: unknown;
}

export function sseStreamUrl(taskId: string): string {
  const base = request.defaults.baseURL || '';
  return `${base}/agent/tasks/${taskId}/stream`;
}

export function makeSseHandler(url: string, frames: SSEFrame[]) {
  return http.get(url, () => {
    const text = frames
      .map((f) => `id: ${f.id}\nevent: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`)
      .join('');
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(text));
        controller.close();
      },
    });
    return new HttpResponse(stream, { headers: { 'content-type': 'text/event-stream' } });
  });
}
