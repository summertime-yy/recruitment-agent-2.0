"""S5-09 · SSE 帧解析 helper（PR-14 阶段 4 填充）。

提供把 SSE 原始文本（以 ``\\n\\n`` 分隔的多个事件块）解析为事件字典列表的工具，
供测试用 ``httpx.AsyncClient.stream()`` 消费 SSE 帧后断言。
"""

from __future__ import annotations

import json
from typing import Any


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """把 SSE 原始文本解析为事件字典列表。

    每个事件字典可能含：``id`` / ``event`` / ``retry`` / ``data``（JSON 解析后的对象，
    解析失败则保留原始字符串）。事件块以空行（``\\n\\n``）分隔。
    """
    events: list[dict[str, Any]] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        ev: dict[str, Any] = {}
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("id:"):
                ev["id"] = line[3:].strip()
            elif line.startswith("event:"):
                ev["event"] = line[6:].strip()
            elif line.startswith("retry:"):
                ev["retry"] = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            joined = "\n".join(data_lines)
            try:
                ev["data"] = json.loads(joined)
            except json.JSONDecodeError:
                ev["data"] = joined
        events.append(ev)
    return events
