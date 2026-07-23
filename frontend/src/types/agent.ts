// PR-18 S5-12 · stage 1 placeholder.
// Full type definitions (SSEEvent / SSEEventType / Plan / PlanStep / TaskStatus /
// AgentChat* / ResultArtifact / ArtifactType) land in commit 2 (stage 2).
// Kept minimal so red-test skeletons can import the module without runtime errors:
// test files import these names as `import type { ... }`, which esbuild erases, so
// the missing exports are harmless at runtime during the red phase.
export type _Pr18AgentTypesPlaceholder = never;
