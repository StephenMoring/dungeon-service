# Design: Replace MockAnthropicClient with pytest-mock

**Date:** 2026-02-27

## Problem

`src/services/mock_llm.py` is brittle and hard to extend. Its dispatch mechanism — keyed on frozensets of tool names and system prompt string identity, with a step counter — is difficult to follow. Adding any new agent flow requires editing `mock_llm.py` in non-obvious ways.

## Decision

Delete `mock_llm.py` entirely. Use `pytest-mock` to patch `dm_agent.client.messages.create` directly in tests, with a `side_effect` list of canned responses.

## Architecture

- `mock_llm.py` is deleted
- The `MOCK_LLM` env var and `importlib.reload` test pattern are removed
- `dm_agent.py` is unchanged — the module-level client stays; tests patch it in place
- No production code changes required

## Response Helpers

A new `tests/helpers.py` provides lightweight builder functions:

```python
def text_response(text: str) -> Message: ...
def tool_use_response(tool_name: str, tool_input: dict) -> Message: ...
```

These replace `MOCK_CHARACTER_JSON`, `MOCK_CAMPAIGN_JSON`, `_make_message`, and the sequence functions in `mock_llm.py`.

## Test Pattern

**Single-turn (character creation):**
```python
mocker.patch(
    "src.services.dm_agent.client.messages.create",
    return_value=text_response(MOCK_CHARACTER_JSON),
)
```

**Tool-use loop (campaign creation):**
```python
mocker.patch(
    "src.services.dm_agent.client.messages.create",
    side_effect=[
        tool_use_response("search_checkpoints", {"tags": "urban,intrigue", "limit": 5}),
        text_response(MOCK_CAMPAIGN_JSON),
    ],
)
```

The `side_effect` list is consumed call-by-call as `dm_agent.create_campaign` runs its loop, exercising the full tool-use flow end-to-end.

## Tool Argument Assertions

To assert the tool was called with the right arguments, patch `handle_search_checkpoints` separately:

```python
mock_search = mocker.patch(
    "src.services.dm_agent.handle_search_checkpoints",
    return_value=[],
)
# ... run create_campaign ...
mock_search.assert_called_once_with(session=db_session, tags="urban,intrigue", limit=5)
```

## Files Changed

| File | Action |
|------|--------|
| `src/services/mock_llm.py` | Delete |
| `tests/test_mock_llm.py` | Delete |
| `tests/test_dm_agent_client.py` | Delete |
| `tests/helpers.py` | Create (response builder functions) |
| `tests/test_character_service.py` | Update to use pytest-mock |
| `tests/test_campaign_service.py` | Update to use pytest-mock |
| `tests/test_characters.py` | Update if needed |
| `tests/test_campaigns.py` | Update if needed |
| `src/services/dm_agent.py` | Remove MOCK_LLM env var block |
