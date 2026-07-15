import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError, validate

logger = logging.getLogger(__name__)


class SkillStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    FALLBACK = "FALLBACK"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


COMPLIANCE_FORBIDDEN_KEYWORDS = {
    "gender": ["性别不限(男)", "仅限男性", "仅限女性", "男生优先", "女生优先", "男优先", "女优先"],
    "age": ["年龄不限(35岁以下)", "35岁以下", "30岁以下", "25岁以下", "岁以下优先"],
    "marriage": ["已婚优先", "未婚优先", "已育优先"],
}


@dataclass
class SkillMetadata:
    skill_id: str
    skill_name: str
    version: str
    description: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 2


@dataclass
class SkillResult:
    success: bool
    output: dict[str, Any] | None = None
    error_message: str | None = None
    execution_time_ms: int = 0
    validation_score: float = 0.0
    validation_errors: list[str] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.SUCCESS


class BaseSkill:
    skill_id: str = ""
    skill_name: str = ""
    version: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    max_retries: int = 2

    def __init__(self, skill_dir: Path | None = None):
        self.skill_dir = skill_dir
        self.metadata: SkillMetadata | None = None
        self._system_prompt: str = ""
        self._user_prompt_template: str = ""
        self._examples: list[dict[str, Any]] = []
        self._tool_chain: list[dict[str, Any]] = []

        if skill_dir and skill_dir.exists():
            self._load_from_directory(skill_dir)
        else:
            self._load_embedded()

    def _load_from_directory(self, skill_dir: Path) -> None:
        skill_yaml_path = skill_dir / "skill.yaml"
        if skill_yaml_path.exists():
            with open(skill_yaml_path, encoding="utf-8") as f:
                skill_def = yaml.safe_load(f)
            self.skill_id = skill_def["skill_id"]
            self.skill_name = skill_def["skill_name"]
            self.version = skill_def["version"]
            self.description = skill_def.get("description", "")
            self.input_schema = skill_def.get("input_schema", {})
            self.output_schema = skill_def.get("output_schema", {})
            self.max_retries = skill_def.get("max_retries", 2)
            self.metadata = SkillMetadata(
                skill_id=self.skill_id,
                skill_name=self.skill_name,
                version=self.version,
                description=self.description,
                input_schema=self.input_schema,
                output_schema=self.output_schema,
                max_retries=self.max_retries,
            )

        system_prompt_path = skill_dir / "prompt.md"
        if system_prompt_path.exists():
            with open(system_prompt_path, encoding="utf-8") as f:
                content = f.read()
            parts = content.split("---USER_TEMPLATE---")
            self._system_prompt = parts[0].strip()
            if len(parts) > 1:
                self._user_prompt_template = parts[1].strip()

        examples_path = skill_dir / "examples.yaml"
        if examples_path.exists():
            with open(examples_path, encoding="utf-8") as f:
                examples_data = yaml.safe_load(f)
            self._examples = examples_data.get("examples", [])

    def _load_embedded(self) -> None:
        pass

    def get_system_prompt(self) -> str:
        examples_text = ""
        if self._examples:
            examples_text = "\n\n## Few-shot Examples\n\n"
            for i, ex in enumerate(self._examples, 1):
                examples_text += f"### Example {i}\n"
                examples_text += f"Input:\n```json\n{json.dumps(ex.get('input', {}), ensure_ascii=False, indent=2)}\n```\n\n"
                examples_text += f"Output:\n```json\n{json.dumps(ex.get('output', {}), ensure_ascii=False, indent=2)}\n```\n\n"

        required_fields = self.output_schema.get("required", []) if self.output_schema else []
        properties = self.output_schema.get("properties", {}) if self.output_schema else {}
        schema_hint = ""
        if required_fields:
            field_desc_parts = []
            for f in required_fields:
                prop = properties.get(f, {})
                desc = prop.get("description", "")
                type_info = prop.get("type", "")
                if type_info == "array":
                    items = prop.get("items", {})
                    item_props = items.get("properties", {})
                    sub_fields = [k for k in item_props.keys()]
                    if sub_fields:
                        field_desc_parts.append(f"{f}(数组，每项包含: {', '.join(sub_fields)})")
                    else:
                        field_desc_parts.append(f"{f}(数组)")
                else:
                    field_desc_parts.append(f"{f}({desc[:30] if desc else type_info})")
            schema_hint = f"\n\n## 必填输出字段: {', '.join(required_fields)}\n{chr(10).join('- ' + p for p in field_desc_parts)}\n只输出JSON对象。"

        return self._system_prompt + examples_text + schema_hint

    def render_user_prompt(self, input_params: dict[str, Any]) -> str:
        from jinja2 import Template

        template = Template(self._user_prompt_template)
        return template.render(**input_params)

    def validate_input(self, input_params: dict[str, Any]) -> tuple[bool, list[str]]:
        if not self.input_schema:
            return True, []
        try:
            validate(instance=input_params, schema=self.input_schema)
            return True, []
        except ValidationError as e:
            return False, [e.message]

    def validate_output(self, output: dict[str, Any]) -> tuple[bool, list[str], float]:
        if not self.output_schema:
            return True, [], 1.0
        errors = []
        required_fields = self.output_schema.get("required", [])
        properties = self.output_schema.get("properties", {})

        for field in required_fields:
            if field not in output or output[field] is None:
                errors.append(f"Missing required field: {field}")
            elif isinstance(output[field], str):
                pass
            elif isinstance(output[field], list):
                if field in ("responsibilities", "requirements", "required_skills") and len(output[field]) == 0:
                    errors.append(f"Required list field is empty: {field}")

        try:
            validate(instance=output, schema=self.output_schema)
        except ValidationError as e:
            errors.append(e.message)

        total_required = len(required_fields)
        filled = sum(
            1 for f in required_fields if f in output and output[f] is not None
        )
        score = filled / total_required if total_required > 0 else 1.0

        return len(errors) == 0, errors, score

    def compliance_check(self, output: dict[str, Any]) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        all_text_parts = []

        def collect_text(obj: Any) -> None:
            if isinstance(obj, str):
                all_text_parts.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    collect_text(v)
            elif isinstance(obj, list):
                for item in obj:
                    collect_text(item)

        collect_text(output)
        full_text = " ".join(all_text_parts)

        for category, keywords in COMPLIANCE_FORBIDDEN_KEYWORDS.items():
            for kw in keywords:
                if kw in full_text:
                    issues.append({"category": category, "keyword": kw, "message": f"发现违规词: {kw}"})

        return {"passed": len(issues) == 0, "issues": issues}

    async def execute(self, input_params: dict[str, Any]) -> SkillResult:
        import time

        from app.agent.llm_adapter import call_llm_json

        start_time = time.time()
        input_valid, input_errors = self.validate_input(input_params)
        if not input_valid:
            return SkillResult(
                success=False,
                error_message=f"Input validation failed: {'; '.join(input_errors)}",
                status=ExecutionStatus.FAILED,
            )

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                system_prompt = self.get_system_prompt()
                user_prompt = self.render_user_prompt(input_params)

                output = await call_llm_json(system_prompt, user_prompt)

                output_valid, validation_errors, validation_score = self.validate_output(output)
                compliance = self.compliance_check(output)

                execution_time = int((time.time() - start_time) * 1000)

                if output_valid and compliance["passed"]:
                    return SkillResult(
                        success=True,
                        output=output,
                        execution_time_ms=execution_time,
                        validation_score=validation_score,
                        status=ExecutionStatus.SUCCESS,
                    )
                else:
                    all_errors = validation_errors + [
                        f"合规问题: {i['message']}" for i in compliance.get("issues", [])
                    ]
                    last_error = "; ".join(all_errors)
                    if attempt < self.max_retries:
                        logger.warning(f"Skill {self.skill_id} attempt {attempt + 1} failed: {last_error}, retrying...")
                        continue

            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    logger.warning(f"Skill {self.skill_id} attempt {attempt + 1} error: {e}, retrying...")
                    continue

        execution_time = int((time.time() - start_time) * 1000)
        return SkillResult(
            success=False,
            error_message=last_error or "Max retries exceeded",
            execution_time_ms=execution_time,
            validation_errors=[last_error] if last_error else [],
            status=ExecutionStatus.FAILED,
        )
