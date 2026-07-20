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
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import Base  # noqa: F401  —— metadata 来源（PR-10 落地后 tables 出现）

# 待 PR-10 实现的 Model（当前导入即红）
from app.models.task import Task  # noqa: F401
from app.models.execution import Execution  # noqa: F401

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
STAGE4_HEAD = "e4c1a2b3d4f5"  # Stage 4 head，新迁移的 down_revision


def _find_tasks_migration() -> tuple[Path | None, str | None]:
    """按 down_revision 定位本迁移脚本（rev 哈希 PR-10 生成，无法预知，故按锚点扫描）。"""
    for f in sorted(VERSIONS_DIR.glob("*.py")):
        if f.name == "__init__.py":
            continue
        src = f.read_text(encoding="utf-8")
        if 'down_revision = "e4c1a2b3d4f5"' in src or "down_revision='e4c1a2b3d4f5'" in src:
            return f, src
    return None, None


@pytest.fixture
async def migrated_conn() -> AsyncConnection:
    """升级到 head 注入 tasks/executions，teardown 仅回退本迁移（回到 Stage4 head），不污染共享库。"""
    settings = get_settings()
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    conn = await engine.connect()
    try:
        yield conn
    finally:
        await conn.close()
        await engine.dispose()
        command.downgrade(cfg, STAGE4_HEAD)


# --- TC-S5-01-1 ---------------------------------------------------------------
def test_tc_s5_01_1_migration_creates_tasks_executions(migrated_conn: AsyncConnection):
    """升级 head 后 tasks / executions 两表存在，且复合索引已建。"""
    inspector = inspect(migrated_conn)
    tables = set(inspector.get_table_names())
    assert "tasks" in tables, "迁移后 tasks 表缺失"
    assert "executions" in tables, "迁移后 executions 表缺失"

    task_indexes = {ix["name"] for ix in inspector.get_indexes("tasks")}
    exec_indexes = {ix["name"] for ix in inspector.get_indexes("executions")}
    assert "idx_tasks_status_created" in task_indexes
    assert "idx_executions_task_created" in exec_indexes


# --- TC-S5-01-2 ---------------------------------------------------------------
def test_tc_s5_01_2_model_id_prefix():
    """Task.task_id 默认 task_ 前缀；Execution.execution_id 默认 exec_ 前缀。"""
    assert Task().task_id.startswith("task_")
    assert Execution().execution_id.startswith("exec_")


# --- TC-S5-01-3 ---------------------------------------------------------------
async def test_tc_s5_01_3_cascade_delete_tasks(db_session):
    """删除 Task → 关联 executions 一并删除（FK ON DELETE CASCADE）。"""
    from sqlalchemy import select

    task = Task(user_message="首条消息")
    db_session.add(task)
    await db_session.flush()

    execution = Execution(task_id=task.task_id, phase="REASON")
    db_session.add(execution)
    await db_session.flush()

    await db_session.delete(task)
    await db_session.flush()

    remaining = (
        await db_session.execute(select(Execution).where(Execution.task_id == task.task_id))
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
