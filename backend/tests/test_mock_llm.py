from app.agent import llm_adapter


async def test_mock_llm_fixture_overrides_call(mock_llm) -> None:
    out = await llm_adapter.call_llm_json("sys-prompt", "user-prompt")
    assert out.get("mocked") is True
    assert out.get("user_prompt") == "user-prompt"
