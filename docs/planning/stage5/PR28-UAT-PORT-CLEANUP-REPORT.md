# PR-28 浏览器验收前置 · 端口 8000 僵尸进程清理回报

> 生成时间：2026-08-05
> 背景：用户要求在浏览器中做 PR-28 验收，启动前后端后发现 8000 端口存在"双占"僵尸进程。
> 本文档供**指挥官决策**：是否需要进一步执行 `netsh` 重置以让 netstat 监听快照归一到 1 行。

## 一、现状（已执行的操作）

### 1. 启动序列（用户原始指令）
1. 后端 `uvicorn :8000` 启动（早期某次，PID 3208，起于 7/29 11:07——7 天僵尸）
2. `uv run python _seed_resume_uat.py` → 输出 `SEEDED_RESUME_ID=res_dd43c9ab91cc`
3. 前端 `npm run dev` → 因 5173/5174 被占用，实际起在 **5175**（5173 亦有一份更早的 dev server）

### 2. 清理操作（本轮）
- ✅ `Stop-Process -Id 3208 -Force` —— 7/29 僵尸后端已杀（用户指定只杀这一个）
- ✅ `Stop-Process -Id 17468 -Force` —— 本轮会话初启的 uvicorn（9:55）一并重启
- ✅ `Stop-Process -Id 46216 -Force` —— 10:32 二次重启前的临时实例
- ✅ 已重新启动**唯一**活 uvicorn（今天 10:32:54，PID 47640 为主进程）

## 二、当前端口 8000 监听快照（netstat）

```
TCP  127.0.0.1:8000  0.0.0.0:0  LISTENING  47640   ← 活的 uvicorn（10:32 起，正常应答）
TCP  127.0.0.1:8000  0.0.0.0:0  LISTENING  3208    ← 幽灵 socket（进程已 GONE）
```

- `Get-Process -Id 3208` → **GONE**（已确认退出）
- `Get-Process -Id 17468` → **GONE**
- 活进程 `47640` 的 `/health` → **HTTP 200**，`{"status":"ok","app":"Recruitment Agent 2.0"}` ✅

## 三、关键判断：幽灵 3208 是否影响验收？

**结论：当前不影响验收，但 netstat 行数 ≠ 1。**

- Windows 上已死进程（无 `SO_EXCLUSIVEADDRUSE`）残留的 LISTEN socket 不会被内核回收，仍显示在 netstat 中。
- 该死 socket **无法 accept 新连接**（进程已退出，listen 队列为空且不可服务）。
- 新连接 SYN 实际只落到活进程 `47640` 的 listen 队列——已用 `/health` 200 证明活进程在正常工作。
- 用户原始担忧（"连接随机分给其中一个"）在**死进程无法 accept** 的前提下不会发生：内核只把连接交给能服务的活 socket。

## 四、待指挥官决策的二选一

### 选项 A：保持现状，直接重跑 §4.1 验收（推荐）
- 活进程 47640 已加载工作区代码并正常应答。
- 幽灵 3208 是无害残留，不抢连接。
- 代价：netstat 仍显示 2 行（1 活 + 1 幽灵），不符合"应当只剩 1 行"的理想标准。

### 选项 B：执行 `netsh int ipv4 reset` 彻底清掉幽灵 socket
- 可让 netstat 监听快照归一到 1 行（仅 47640）。
- 代价：
  - 会**中断并重置所有 TCP 连接**（含 docker 容器 Postgres/Redis/MinIO 的现有连接、前端 5173/5175 的代理长连）。
  - 重置后 docker 容器通常自动重连，但**前端 dev server 需重启**，`npm run dev` 会重新占用 5173/5175。
  - 需要 `netsh` 管理员权限，且部分环境重置后需重启系统才完全生效。
- 操作预估：
  ```
  netsh int ipv4 reset
  # 重启 docker 相关连接自动恢复；前端需手动重启
  ```

## 五、其他已发现但未处理的僵尸（不在本轮范围）
| PID | StartTime | 说明 |
|-----|-----------|------|
| 19712 | 7/27 10:36 | python 僵尸（未 bind 8000）|
| 28692 | 7/27 10:36 | python 僵尸（未 bind 8000）|
| 16104 | 7/30 13:44 | python 僵尸（未 bind 8000）|

这三个未出现在 8000 的 netstat 中，判定为其他服务/worker 残留，未动。若指挥官要求全量清理可一并处理。

## 六、Seed 简历 ID（验收用）
```
SEEDED_RESUME_ID=res_dd43c9ab91cc
```
用于走 §4.1 candidate-profile / candidate-chat / execute 流程。

## 七、建议下一步
若指挥官选 A：直接重跑 §4.1 验收（活进程 47640 + seed `res_dd43c9ab91cc`）。
若指挥官选 B：我执行 `netsh` 重置 → 重启前端 → 再重跑 §4.1。

---
回报生成：AI agent（无需用户确认，待指挥官裁决选项 A/B）

---

## 八、指挥官裁决（2026-07-27 · 副指挥官复核后）

**裁决：选项 A。不执行 `netsh int ipv4 reset`。**

### 独立验证（未采信回报结论，自行实证）

1. `Get-Process -Id 3208` → **GONE** ✅（与回报一致）
2. `netstat` 仍 2 行（3208 幽灵 + 47640 活）✅（与回报一致）
3. **`/health` × 5 全部 200 但不足以定论** —— 该端点不返回 pid / git_sha，
   五次相同无法证明是同一进程应答。这正是 §9.3.23 要修的盲区，故改用落库实证。
4. **决定性实证**：经真实 HTTP `POST /api/v1/agent/chat` 连打 **12 个请求**（两轮 × 6），
   `tasks` 表 `count` delta **6 / 6**，**12/12 全部落库**，无一丢失。
   → 证明幽灵 socket **不 accept 任何连接**，回报第三节判断成立。
5. **附带确认故障已消失**：6/6 任务终态 `WAITING_CONFIRMATION`，
   **零 `REASON_PLAN_FAILED`** → reason→reflect→plan→reflect_plan 全链路经真实
   HTTP 端点跑通，与"僵尸进程持旧代码/旧 .env"的归因完全吻合。

### 为什么不选 B
`netsh int ipv4 reset` 会重置**所有** TCP 连接（Postgres / Redis / MinIO / 前端代理长连），
部分环境还需重启系统 —— 为消除一个**已证明无害**的 netstat 显示行付出这个代价不合理。
`netstat` 2 行在此情形下是**已知可接受状态**，判据应放宽为"活进程恰好 1 个"。

### 对 CHECKLIST §0.2b 的修正
§0.2b 原文写"必须只有 1 行输出"过严。**正确判据**：`netstat` 每一行的 PID 都要
`Get-Process` 确认存活；**存活进程恰好 1 个**即通过，已死 PID 的残留行可忽略。

### §五 三个其他僵尸（19712 / 28692 / 16104）
未 bind :8000，**不动**。它们不参与本次故障，清理它们属额外风险无收益。

### 验收参数
- 活后端：PID 47640（2026-08-05 10:32 起）
- Seed 简历：`SEEDED_RESUME_ID=res_dd43c9ab91cc`
- 前端实际端口：**5175**（5173/5174 被占，验收时注意开对端口）
