// PR-18 S5-12 · stage 1 stub.
// Full `agentApi` (5 functions: chat / executePlan / skipToScore / cancelTask /
// getTask) lands in commit 3 (stage 2). Until then every method throws so the
// TC-S5-12-3 red test (marked `test.fails`) fails as expected.
export const agentApi = {
  chat: () => {
    throw new Error('not implemented: agentApi.chat');
  },
  executePlan: () => {
    throw new Error('not implemented: agentApi.executePlan');
  },
  skipToScore: () => {
    throw new Error('not implemented: agentApi.skipToScore');
  },
  cancelTask: () => {
    throw new Error('not implemented: agentApi.cancelTask');
  },
  getTask: () => {
    throw new Error('not implemented: agentApi.getTask');
  },
};
