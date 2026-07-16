# 后端测试指南（Stage 4 / S4-05）

## 数据库策略
因 `resumes` 表使用了 PostgreSQL 专有的 `JSONB` 类型，SQLite 无法承载，且项目运行环境
已具备健康的 PostgreSQL 容器，本基线采用 **PLAN S4-05 决策 5 的退化方案**：

- 复用运行中的 PostgreSQL（`recruitment-postgres`）。
- 每个测试通过 `db_session` fixture 在独立连接事务中执行，结束统一 `rollback`，避免污染共享库。
- endpoint 内部的 `session.commit()` 被改写为 `flush`（不真正提交），因此测试间互不干扰。

> 若后续接入 CI，可设置独立 `TEST_DATABASE_URL` 测试库（在 `conftest` 顶部切换 `POSTGRES_DB`）。

## 可用 fixtures
- `client`：基于 `ASGITransport` 的 `httpx.AsyncClient`（不触发 lifespan，不写 DB）。
- `db_session`：事务回滚的 `AsyncSession`（用于直接操作模型）。
- `client_db`：绑定 `db_session` 的 `client`，已 override FastAPI 的 `get_db` 依赖。
- `mock_llm`：打桩 `app.agent.llm_adapter.call_llm_json`，返回固定 JSON（不触发真实 LLM）。

## 工厂函数（`factories.py`）
- `build_jd(**kwargs)` → `JD`
- `build_resume(**kwargs)` → `Resume`（默认 `parse_status="PARSED"`，便于匹配测试）
- `build_skill_execution_log(**kwargs)` → `SkillExecutionLog`

## 运行
```bash
cd backend
uv run pytest -v
```

## 约定
- 文件命名 `test_<module>.py`，用例 `test_<behavior>`，`asyncio_mode=auto`。
- 所有业务测试通过 `AsyncClient` 的 `client` / `client_db` fixture 进行。
- LLM 调用一律用 `mock_llm` 打桩。
