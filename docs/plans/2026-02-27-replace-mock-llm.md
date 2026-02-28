# Replace MockAnthropicClient with pytest-mock Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Delete `mock_llm.py` and replace its custom dispatch infrastructure with standard `pytest-mock` patches in dm_agent tests.

**Architecture:** Add `pytest-mock` to dev deps; create `tests/helpers.py` with two response builder functions; write new `tests/test_dm_agent.py` that patches `client.messages.create` directly; then delete the old mock files.

**Tech Stack:** Python, pytest, pytest-mock, anthropic SDK types

---

### Task 1: Add pytest-mock to dev dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add pytest-mock to the dev group**

Edit `pyproject.toml`, change:
```toml
dev = ["httpx>=0.28.1", "pytest>=9.0.2"]
```
to:
```toml
dev = ["httpx>=0.28.1", "pytest>=9.0.2", "pytest-mock>=3.14.0"]
```

**Step 2: Sync dependencies**

```bash
uv sync
```
Expected: resolves and installs `pytest-mock`.

**Step 3: Verify pytest-mock is available**

```bash
uv run pytest --co -q 2>&1 | head -5
```
Expected: no import errors.

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add pytest-mock to dev dependencies"
```

---

### Task 2: Create `tests/helpers.py` with response builder functions

**Files:**
- Create: `tests/helpers.py`

**Step 1: Write the helpers file**

Create `tests/helpers.py`:

```python
import json

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage


MOCK_CHARACTER_JSON = json.dumps({
    "name": "Aldric the Grey",
    "hero_class": "wizard",
    "biography": "A wizard who studied forgotten tomes in a crumbling tower.",
    "age": 45,
    "story_so_far": "",
    "strength": 3,
    "perception": 7,
    "endurance": 4,
    "charisma": 5,
    "intelligence": 9,
    "agility": 4,
    "luck": 5,
})

MOCK_CAMPAIGN_JSON = json.dumps({
    "name": "Shadows Over Thornwall",
    "theme": "A city teeters on the edge of civil war while something darker stirs beneath the streets.",
    "description": "A gothic urban campaign blending political intrigue with creeping horror.",
    "checkpoint_ids": [1, 2, 3],
})


def _make_message(content: list, stop_reason: str) -> Message:
    return Message(
        id="mock_msg_01",
        content=content,
        model="mock",
        role="assistant",
        stop_reason=stop_reason,
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=0, output_tokens=0),
    )


def text_response(text: str) -> Message:
    """Build a mock end_turn Message with a single TextBlock."""
    return _make_message(
        [TextBlock(text=text, type="text", citations=None)],
        "end_turn",
    )


def tool_use_response(tool_name: str, tool_input: dict) -> Message:
    """Build a mock tool_use Message with a single ToolUseBlock."""
    return _make_message(
        [ToolUseBlock(id="mock_tool_use_01", input=tool_input, name=tool_name, type="tool_use")],
        "tool_use",
    )
```

**Step 2: Verify it imports cleanly**

```bash
uv run python -c "from tests.helpers import text_response, tool_use_response, MOCK_CHARACTER_JSON; print('ok')"
```
Expected: `ok`

**Step 3: Commit**

```bash
git add tests/helpers.py
git commit -m "test: add response builder helpers for dm_agent tests"
```

---

### Task 3: Write `tests/test_dm_agent.py`

**Files:**
- Create: `tests/test_dm_agent.py`

**Step 1: Write the tests**

Create `tests/test_dm_agent.py`:

```python
import json
from unittest.mock import MagicMock

from src.services.dm_agent import create_campaign, create_character
from tests.helpers import (
    MOCK_CAMPAIGN_JSON,
    MOCK_CHARACTER_JSON,
    text_response,
    tool_use_response,
)


class TestCreateCharacter:
    def test_returns_character_json(self, mocker):
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            return_value=text_response(MOCK_CHARACTER_JSON),
        )
        result = create_character("a cunning rogue")
        assert result == MOCK_CHARACTER_JSON

    def test_parsed_response_has_required_fields(self, mocker):
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            return_value=text_response(MOCK_CHARACTER_JSON),
        )
        result = create_character("a cunning rogue")
        data = json.loads(result)
        assert "name" in data
        assert "strength" in data
        assert "story_so_far" in data


class TestCreateCampaign:
    def test_tool_use_loop_returns_campaign_json(self, mocker):
        session = MagicMock()
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            side_effect=[
                tool_use_response("search_checkpoints", {"tags": "urban,intrigue", "limit": 5}),
                text_response(MOCK_CAMPAIGN_JSON),
            ],
        )
        mocker.patch("src.services.dm_agent.handle_search_checkpoints", return_value=[])

        result = create_campaign("a dark gothic city", session)
        assert result == MOCK_CAMPAIGN_JSON

    def test_search_checkpoints_called_with_tool_args(self, mocker):
        session = MagicMock()
        mocker.patch(
            "src.services.dm_agent.client.messages.create",
            side_effect=[
                tool_use_response("search_checkpoints", {"tags": "urban,intrigue", "limit": 5}),
                text_response(MOCK_CAMPAIGN_JSON),
            ],
        )
        mock_search = mocker.patch(
            "src.services.dm_agent.handle_search_checkpoints",
            return_value=[],
        )

        create_campaign("a dark gothic city", session)
        mock_search.assert_called_once_with(session=session, tags="urban,intrigue", limit=5)

    def test_llm_called_twice_for_tool_use_loop(self, mocker):
        session = MagicMock()
        mock_llm = mocker.patch(
            "src.services.dm_agent.client.messages.create",
            side_effect=[
                tool_use_response("search_checkpoints", {"tags": "urban,intrigue", "limit": 5}),
                text_response(MOCK_CAMPAIGN_JSON),
            ],
        )
        mocker.patch("src.services.dm_agent.handle_search_checkpoints", return_value=[])

        create_campaign("a dark gothic city", session)
        assert mock_llm.call_count == 2
```

**Step 2: Run the new tests**

```bash
uv run pytest tests/test_dm_agent.py -v
```
Expected: all 5 tests PASS.

**Step 3: Commit**

```bash
git add tests/test_dm_agent.py
git commit -m "test: add dm_agent tests using pytest-mock"
```

---

### Task 4: Remove `MOCK_LLM` env var block from `dm_agent.py`

**Files:**
- Modify: `src/services/dm_agent.py`

**Step 1: Remove the conditional client selection block**

In `src/services/dm_agent.py`, replace:

```python
if os.getenv("MOCK_LLM"):
    from src.services.mock_llm import MockAnthropicClient
    client = MockAnthropicClient()
else:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
```

with:

```python
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
```

Also remove the `import os` line if it is no longer used (check — `os` is only used for `os.getenv` and `os.environ.get`; the remaining line still uses `os.environ.get`, so keep the import).

**Step 2: Run the full test suite**

```bash
uv run pytest -v
```
Expected: all tests PASS. `test_dm_agent_client.py` tests (which used `importlib.reload` + `MOCK_LLM`) will still run here — they will now fail because `MOCK_LLM` no longer routes to `MockAnthropicClient`. That's expected and fine; they'll be deleted in the next task.

If any _other_ tests fail, investigate before continuing.

**Step 3: Commit**

```bash
git add src/services/dm_agent.py
git commit -m "refactor: remove MOCK_LLM env var client swap from dm_agent"
```

---

### Task 5: Delete old mock files

**Files:**
- Delete: `src/services/mock_llm.py`
- Delete: `tests/test_mock_llm.py`
- Delete: `tests/test_dm_agent_client.py`

**Step 1: Delete the three files**

```bash
rm src/services/mock_llm.py tests/test_mock_llm.py tests/test_dm_agent_client.py
```

**Step 2: Run the full test suite**

```bash
uv run pytest -v
```
Expected: all remaining tests PASS. No references to `mock_llm` should remain.

**Step 3: Verify no stale references**

```bash
grep -r "mock_llm\|MockAnthropicClient\|MOCK_LLM" src/ tests/
```
Expected: no output.

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: delete MockAnthropicClient and replace with pytest-mock"
```
