import logging
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@lru_cache
def get_llm() -> ChatOpenAI:
    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
        raise ValueError("LLM is not configured. Please set LLM_API_KEY and LLM_BASE_URL in environment variables.")
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
        max_retries=0,
    )


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    response_format: dict[str, Any] | None = None,
) -> str:
    llm = get_llm()

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    kwargs: dict[str, Any] = {}
    if settings.LLM_JSON_MODE and response_format and response_format.get("type") == "json_object":
        kwargs["response_format"] = {"type": "json_object"}

    response = await llm.ainvoke(messages, **kwargs)
    return response.content


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    import json
    import re

    content = await call_llm(system_prompt, user_prompt, response_format={"type": "json_object"})

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"LLM response is not valid JSON. Content starts with: {content[:200]}")
