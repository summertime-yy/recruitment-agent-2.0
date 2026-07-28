"""Generate the ``ArtifactType`` union in frontend/src/types/agent.ts.

Rule: union = sorted(_ARTIFACT_TYPE_MAP.values()) + 'generic'
('generic' is the engine.py fallback for unknown tool_name and is NOT a map
 value, so it is appended explicitly.)

Pure stdlib (ast + re + pathlib + sys). Does NOT import any app package, so it
runs cleanly in any environment (incl. CI without backend deps installed).

Output is written with ``newline="\n"`` + ``encoding="utf-8"`` (no BOM) to avoid
 Windows CRLF churn. The generated region is delimited by markers so we only
 ever touch that region — never the rest of agent.ts.

Idempotent: running it repeatedly produces byte-identical output.
"""

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # backend/scripts -> repo root
ENGINE = REPO_ROOT / "backend" / "app" / "agent" / "orchestrator" / "engine.py"
AGENT_TS = REPO_ROOT / "frontend" / "src" / "types" / "agent.ts"
MARK_START = "// <auto-gen-artifacttype-start>"
MARK_END = "// <auto-gen-artifacttype-end>"


def extract_map_values() -> list[str]:
    """Parse ``_ARTIFACT_TYPE_MAP`` as a dict literal and return its string values."""
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        # 兼容 `x = {...}` (Assign) 与 `x: dict[...] = {...}` (AnnAssign，带类型注解)
        targets = None
        value = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "_ARTIFACT_TYPE_MAP":
                if not isinstance(value, ast.Dict):
                    sys.exit("_ARTIFACT_TYPE_MAP 不是字典字面量")
                values: list[str] = []
                for v in value.values:
                    if not isinstance(v, ast.Constant) or not isinstance(v.value, str):
                        sys.exit(f"_ARTIFACT_TYPE_MAP value 非字符串字面量: {ast.dump(v)}")
                    values.append(v.value)
                return values
    sys.exit("未找到 _ARTIFACT_TYPE_MAP")


def build_union(values: list[str]) -> str:
    all_types = sorted(set(values) | {"generic"})
    return " | ".join(f"'{t}'" for t in all_types)


def main() -> None:
    values = extract_map_values()
    union = build_union(values)
    content = AGENT_TS.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.DOTALL)
    if not pattern.search(content):
        sys.exit(f"marker 缺失于 {AGENT_TS}: {MARK_START} / {MARK_END}")

    replacement = (
        f"{MARK_START} — DO NOT EDIT. Run: uv run python backend/scripts/gen_artifact_types.py\n"
        f"export type ArtifactType = {union};\n"
        f"{MARK_END}"
    )
    new_content = pattern.sub(replacement, content)
    AGENT_TS.write_text(new_content, encoding="utf-8", newline="\n")
    print(f"OK · {AGENT_TS} · union = {union}")


if __name__ == "__main__":
    main()
