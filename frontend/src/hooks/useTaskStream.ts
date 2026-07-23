import { useCallback, useEffect, useRef, useState } from 'react';
import request from '@/utils/request';
import type { SSEEvent, SSEEventType } from '@/types/agent';

// PR-18 S5-12 · SSE 客户端 Hook。
// 选型:fetch + ReadableStream 手写解析器(DECISION Q2 选项 B)。
// 重连状态机:仅「未收到 result/error 终态即关流」才重连(A1 闭合);
// result/error 即终态、弃 data.recoverable(A2 闭合);忽略后端 retry: 字段(B3)。

export type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'closed' | 'error';

export interface UseTaskStreamOptions {
  taskId: string;
  autoStart?: boolean; // 默认 true
  lastEventId?: string; // 首次连接的断点(本 PR 不持久化 · Q3.3 留 PR-19)
  onEvent?: (event: SSEEvent) => void;
  onError?: (err: Error) => void;
}

export interface UseTaskStreamResult {
  events: SSEEvent[]; // 按 id 去重升序(Q3.2)
  lastEventId: string | null;
  status: StreamStatus;
  latestByType: Partial<Record<SSEEventType, SSEEvent>>; // 便捷访问(Q3.1)· system 也进
  lastHeartbeatAt: number | null; // ms 时间戳(A3 新补)
  reconnect: () => void;
  close: () => void;
}

const SSE_EVENT_TYPES: SSEEventType[] = [
  'thinking',
  'plan',
  'tool_call',
  'progress',
  'result',
  'error',
  'warning',
  'system',
];

const RECONNECT_BACKOFF_MS = [3000, 6000, 12000];
const MAX_RETRIES = 3;

function buildStreamUrl(taskId: string): string {
  const base = request.defaults.baseURL || '';
  const path = `/agent/tasks/${taskId}/stream`;
  // 测试环境 base 为绝对地址(http://localhost/api/v1),生产为相对(/api/v1)。
  return base.startsWith('http') ? `${base}${path}` : `${window.location.origin}${base}${path}`;
}

export function useTaskStream(opts: UseTaskStreamOptions): UseTaskStreamResult {
  const { taskId, autoStart = true, lastEventId: initialLastEventId, onEvent, onError } = opts;

  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [lastEventId, setLastEventId] = useState<string | null>(initialLastEventId ?? null);
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [latestByType, setLatestByType] = useState<Partial<Record<SSEEventType, SSEEvent>>>({});
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<number | null>(null);

  const mountedRef = useRef(true);
  const closedRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasReachedTerminalRef = useRef(false);
  const lastEventIdRef = useRef<string | null>(initialLastEventId ?? null);
  const lastHeartbeatAtRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const fallbackSeqRef = useRef(0);
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
    onErrorRef.current = onError;
  }, [onEvent, onError]);

  const handleBlock = useCallback(
    (raw: string) => {
      const lines = raw.split('\n');
      let id: string | undefined;
      let type: string | undefined;
      let dataStr: string | undefined;
      for (const line of lines) {
        if (line.startsWith('id:')) id = line.slice(3).trim();
        else if (line.startsWith('event:')) type = line.slice(6).trim();
        else if (line.startsWith('data:')) dataStr = line.slice(5).trim();
      }
      if (!type) return; // e.g. `retry: 3000` 心跳控制块,忽略(B3)
      if (!SSE_EVENT_TYPES.includes(type as SSEEventType)) {
        // Q14:未知 type → warn + 跳过,不 throw
        console.warn(`useTaskStream: unknown SSE event type: ${type}`);
        return;
      }
      let data: unknown;
      try {
        data = dataStr !== undefined ? JSON.parse(dataStr) : null;
      } catch {
        console.warn(`useTaskStream: failed to parse SSE data for event type ${type}`);
        return;
      }
      const typed = type as SSEEventType;
      const ev: SSEEvent = {
        id: id ?? String(++fallbackSeqRef.current),
        type: typed,
        task_id: taskId,
        step_id: (data as { step_id?: string } | null)?.step_id,
        timestamp: new Date().toISOString(),
        data,
      };
      if (typed === 'result' || typed === 'error') hasReachedTerminalRef.current = true;
      // 始终跟踪 lastEventId,供重连 Last-Event-ID 头(Q3 / TC-S5-12-2)
      lastEventIdRef.current = ev.id;
      setLastEventId(ev.id);
      onEventRef.current?.(ev);
      if (typed === 'system') {
        // Q13:system 不入 events[],但更新 latestByType.system + lastHeartbeatAt
        lastHeartbeatAtRef.current = Date.now();
        setLastHeartbeatAt(lastHeartbeatAtRef.current);
        setLatestByType((prev) => ({ ...prev, system: ev }));
        return;
      }
      setEvents((prev) => {
        const next = prev.filter((e) => e.id !== ev.id);
        next.push(ev);
        next.sort((a, b) => Number(a.id) - Number(b.id));
        return next;
      });
      setLatestByType((prev) => ({ ...prev, [typed]: ev }));
    },
    [taskId],
  );

  const connect = useCallback(() => {
    if (!mountedRef.current || closedRef.current) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    setStatus((prev) => (prev === 'error' ? prev : 'connecting'));

    const url = buildStreamUrl(taskId);
    const headers: Record<string, string> = {};
    if (lastEventIdRef.current) headers['Last-Event-ID'] = lastEventIdRef.current;

    fetch(url, { headers, signal: controller.signal })
      .then((res) => {
        if (!res.ok) {
          const err = new Error(`SSE stream responded ${res.status}`);
          onErrorRef.current?.(err);
          onStreamEndRef.current?.(err);
          return;
        }
        setStatus('streaming');
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        const pump = () => {
          reader
            .read()
            .then(({ done, value }) => {
              if (!mountedRef.current) return;
              if (done) {
                onStreamEndRef.current?.();
                return;
              }
              buffer += decoder.decode(value, { stream: true });
              let idx: number;
              while ((idx = buffer.indexOf('\n\n')) >= 0) {
                const raw = buffer.slice(0, idx);
                buffer = buffer.slice(idx + 2);
                handleBlock(raw);
              }
              pump();
            })
            .catch((err) => {
              if (!mountedRef.current) return;
              onStreamEndRef.current?.(err);
            });
        };
        pump();
      })
      .catch((err) => {
        if (!mountedRef.current) return;
        onStreamEndRef.current?.(err);
      });
  }, [taskId, handleBlock]);

  const onStreamEnd = useCallback((err?: unknown) => {
    if (err) onErrorRef.current?.(err instanceof Error ? err : new Error(String(err)));
    if (!mountedRef.current) return;
    if (closedRef.current) {
      setStatus('closed');
      return;
    }
    if (hasReachedTerminalRef.current) {
      // A2:已收到 result/error 终态 → 关流即 closed,不重连
      setStatus('closed');
      return;
    }
    if (retryCountRef.current >= MAX_RETRIES) {
      setStatus('error');
      return;
    }
    const delay = RECONNECT_BACKOFF_MS[retryCountRef.current] ?? RECONNECT_BACKOFF_MS[RECONNECT_BACKOFF_MS.length - 1];
    retryCountRef.current += 1;
    reconnectTimerRef.current = setTimeout(() => {
      if (mountedRef.current && !closedRef.current) connect();
    }, delay);
  }, [connect]);

  const onStreamEndRef = useRef(onStreamEnd);
  useEffect(() => {
    onStreamEndRef.current = onStreamEnd;
  }, [onStreamEnd]);

  const close = useCallback(() => {
    closedRef.current = true;
    controllerRef.current?.abort();
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    setStatus('closed');
  }, []);

  const reconnect = useCallback(() => {
    closedRef.current = false;
    retryCountRef.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    closedRef.current = false;
    retryCountRef.current = 0;
    hasReachedTerminalRef.current = false;
    if (autoStart) connect();
    return () => {
      mountedRef.current = false;
      closedRef.current = true;
      controllerRef.current?.abort();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [autoStart, connect]);

  return { events, lastEventId, status, latestByType, lastHeartbeatAt, reconnect, close };
}
