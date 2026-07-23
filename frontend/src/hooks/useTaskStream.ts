// PR-18 S5-12 · stage 1 stub.
// Full hook (fetch + ReadableStream SSE parser, reconnect state machine,
// AbortController, heartbeat field) lands in commit 4 (stage 3). Until then it
// throws so the TC-S5-12-1 / TC-S5-12-2 red tests (marked `test.fails`) fail as
// expected.
export function useTaskStream(_opts?: unknown): never {
  throw new Error('not implemented: useTaskStream');
}
