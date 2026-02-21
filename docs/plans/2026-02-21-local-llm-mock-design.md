# Local LLM Mock Design

## Problem

Every local development iteration makes real API calls to Anthropic, incurring cost and latency. Unit tests already mock the LLM, but running the local server always hits the real API.

## Goal

An env var (`MOCK_LLM=true`) that swaps the real Anthropic client for a mock that exercises the full code path — including the tool-use loop — without making any external calls.

## Files

| File | Change |
|---|---|
| `src/services/prompts.py` | New — all system prompt strings |
| `src/services/mock_llm.py` | New — mock Anthropic client |
| `src/services/dm_agent.py` | Modified — import prompts, swap client on env var |

## Design

### `src/services/prompts.py`

Extracts the three prompt strings currently inline in `dm_agent.py` into a standalone module:

- `master_system_prompt`
- `campaign_creation_prompt`
- `character_creation_prompt`

No logic — pure string constants. Required to avoid a circular import between `dm_agent.py` and `mock_llm.py`.

---

### `src/services/mock_llm.py`

Contains the mock client and all fixture responses.

**Dispatch tables:**

```python
TOOL_SEQUENCES = {
    frozenset(["search_checkpoints"]): _campaign_creation_sequence,
}

NO_TOOL_SEQUENCES = {
    character_creation_prompt: _character_creation_sequence,
}
```

**`MockAnthropicMessages.create()` logic:**

1. Compute `step` — count of `tool_result` messages already in the history
2. If `tools` kwarg present → key on `frozenset(t["name"] for t in tools)` → look up in `TOOL_SEQUENCES` → call sequence at `step`
3. If no tools → key on `system` kwarg → look up in `NO_TOOL_SEQUENCES` → call sequence at `step`
4. Unknown key → raise `ValueError` with a message pointing to the right dict to update

**Sequence functions:**

- `_campaign_creation_sequence(step)`:
  - step 0 → `ToolUseBlock(name="search_checkpoints", input={"tags": "urban,intrigue", "limit": 5})`
  - step 1+ → `TextBlock(MOCK_CAMPAIGN_JSON)` with `stop_reason="end_turn"`

- `_character_creation_sequence(step)`:
  - step 0 → `TextBlock(MOCK_CHARACTER_JSON)` with `stop_reason="end_turn"`

All responses are constructed using real Anthropic SDK types (`Message`, `TextBlock`, `ToolUseBlock`, `Usage`) so the existing logic in `dm_agent.py` and `campaign_service.py` needs no changes.

**`MockAnthropicClient`:** exposes `.messages` as a `MockAnthropicMessages` instance, matching the real `Anthropic` client interface.

---

### `src/services/dm_agent.py`

- Replace inline prompt strings with imports from `prompts.py`
- Swap the module-level client:

```python
if os.getenv("MOCK_LLM"):
    from src.services.mock_llm import MockAnthropicClient
    client = MockAnthropicClient()
else:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
```

No other changes.

---

## Extending the Mock

**New tool workflow (e.g. song generation with a tool):**
1. Add prompt to `prompts.py`
2. Write `_song_generation_sequence(step)` in `mock_llm.py`
3. Add `frozenset(["search_songs"]): _song_generation_sequence` to `TOOL_SEQUENCES`

**New no-tools call (e.g. song generation, prompt-only):**
1. Add prompt to `prompts.py`
2. Write `_song_generation_sequence(step)` in `mock_llm.py`
3. Add `song_generation_prompt: _song_generation_sequence` to `NO_TOOL_SEQUENCES`

**Additional tool in an existing workflow:**
Add steps to the relevant sequence function — step N returns the new `ToolUseBlock`, final step returns the `TextBlock`.

---

## Usage

In `.env`:
```
MOCK_LLM=true    # mock client, no API calls
# MOCK_LLM=     # unset → real Anthropic client
```

Works with `make lr` (local uvicorn) and can be passed into the docker-compose app service environment for `make dr`.
