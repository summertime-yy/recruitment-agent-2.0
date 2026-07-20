"""S5-01 · tasks / executions 数据层 TDD 测试骨架（PR-10 交付物，当前为「红」态）。

归属 PR：PR-10（TASKS-STAGE5.md S5-01）
TDD 约定：先写测试（红）再实现（绿）。本文件导入的模块/字段在 PR-10 落地前不存在，
`uv run pytest backend/tests/test_stage5_s5_01_data_layer.py` 当前应整文件收集失败（红）。
PR-10 实现「迁移 + Task/Execution Model + app/models/__init__ 导出」后转绿。

覆盖用例：
- TC-S5-01-1  migration_creates_tasks_executions（升级 head 后两表+复合索引存在）
- TC-S5-01-2  model_id_prefix（task_ / exec_ 前缀默认）
- TC-S5-01-3  cascade_delete_tasks（删 Task 级联删 executions）
- TC-S5-01-4  composite_index_exists（idx_tasks_status_created / idx_executions_task_created 在元数据）
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import Base  # noqa: F401  —— metadata 来源（PR-10 落地后 tables 出现）

# 待 PR-10 实现的 Model（当前导入即红）
from app.models.task import Task  # noqa: F401
from app.models.execution import Execution  # noqa: F401

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _make_alembic_cfg() -> Config:
    settings = get_settings()
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _current_head(sync_url: str) -> str | None:
    """读取共享 dev 库当前所处 alembic head（同步引擎，避免 event loop 冲突）。"""
    with create_engine(sync_url).connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


@pytest.fixture(scope="module")
def _migrated_schema() -> None:
    """模块级同步 fixture：进入前记录 head，upgrade 到 head 后 yield，teardown 恢复至进入前 head。

    - **同步** def（非 async）→ 规避 `alembic.command.upgrade` 内部 `asyncio.run` 与运行中事件循环冲突。
    - **相对进入前 head 回退**：不硬编码 Stage4 revision，避免未来 Stage 5 后续迁移落地后误伤。
    - **模块级 scope**：4 个用例共用同一次 upgrade/downgrade，减少 DDL 开销。
    """
    cfg = _make_alembic_cfg()
    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")

    pre_head = _current_head(sync_url)
    command.upgrade(cfg, "head")
    try:
        yield
    finally:
        # 若共享库进入前已在 head（如后续 PR merge 后），downgrade 至同一 head 是 no-op；
        # 否则恢复到 pre_head，绝不误删本测试未创建的迁移。
        command.downgrade(cfg, pre_head or "base")


@pytest_asyncio.fixture
async def migrated_session(_migrated_schema) -> AsyncSession:
    """基于模块 fixture 已建好的 schema，开一个独立 async session（不复用 conftest.db_session）。

    独立 engine + NullPool + 事务 rollback → 每个用例数据隔离，schema 由 _migrated_schema 统一管理。
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


# --- TC-S5-01-1 ---------------------------------------------------------------
def test_tc_s5_01_1_migration_creates_tasks_executions(_migrated_schema):
    """升级 head 后 tasks / executions 两表存在，且复合索引已建。"""
    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "tasks" in tables, "迁移后 tasks 表缺失"
        assert "executions" in tables, "迁移后 executions 表缺失"

        task_indexes = {ix["name"] for ix in inspector.get_indexes("tasks")}
        exec_indexes = {ix["name"] for ix in inspector.get_indexes("executions")}
        assert "idx_tasks_status_created" in task_indexes
        assert "idx_executions_task_created" in exec_indexes
    finally:
        engine.dispose()


# --- TC-S5-01-2 ---------------------------------------------------------------
def test_tc_s5_01_2_model_id_prefix():
    """Task.task_id 默认 task_ 前缀；Execution.execution_id 默认 exec_ 前缀。"""
    assert Task().task_id.startswith("task_")
    assert Execution().execution_id.startswith("exec_")


# --- TC-S5-01-3 ---------------------------------------------------------------
async def test_tc_s5_01_3_cascade_delete_tasks(migrated_session: AsyncSession):
    """删除 Task → 关联 executions 一并删除（FK ON DELETE CASCADE）。"""
    from sqlalchemy import select

    task = Task(user_message="首条消息")
    migrated_session.add(task)
    await migrated_session.flush()

    execution = Execution(task_id=task.task_id, phase="REASON")
    migrated_session.add(execution)
    await migrated_session.flush()

    await migrated_session.delete(task)
    await migrated_session.flush()

    remaining = (
        await migrated_session.execute(select(Execution).where(Execution.task_id == task.task_id))
    ).scalars().all()
    assert len(remaining) == 0, "删除 Task 后 executions 未级联删除"


# --- TC-S5-01-4 ---------------------------------------------------------------
def test_tc_s5_01_4_composite_index_exists():
    """复合索引定义在 metadata 中（idx_tasks_status_created / idx_executions_task_created）。"""
    tasks_table = Base.metadata.tables["tasks"]
    execs_table = Base.metadata.tables["executions"]

    task_idx = {ix.name: ix for ix in tasks_table.indexes}
    assert "idx_tasks_status_created" in task_idx, "tasks 复合索引缺失"

    exec_idx = {ix.name: ix for ix in execs_table.indexes}
    assert "idx_executions_task_created" in exec_idx, "executions 复合索引缺失"
