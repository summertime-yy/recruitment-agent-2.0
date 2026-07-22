"""S5-09 · Agent REST 端点 + SSE HTTP 流（PR-14）。

本文件承载 DECISION §十四 阶段 3/4 的端点实现：
- POST /agent/chat                      → 异步 R-P-R，立即返 {task_id, PLANNING}（Q5 (b1)）
- POST /agent/execute-plan              → 确认执行 plan（Q6 SELECT FOR UPDATE）
- POST /agent/skip-to-score             → 跳过 R-P-R 直接评分（Q7 真 task_id）
- GET  /agent/tasks/{task_id}           → 查询任务状态
- POST /agent/tasks/{task_id}/cancel    → 取消（Q3 补发 SYSTEM("cancelled")）
- GET  /agent/tasks/{task_id}/stream    → SSE 事件流（Q2/Q3/Q4/Q8）

阶段 1（本 commit）：仅建 router 骨架，暂不挂载任何路由。路由与依赖在后续阶段补齐。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["Agent / Orchestrator"])
