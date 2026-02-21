# Local LLM Mock Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `MOCK_LLM=true` env var that swaps the real Anthropic client for a mock that exercises the full tool-use loop without making API calls.

**Architecture:** Extract system prompts to a shared `prompts.py` module, implement a `MockAnthropicClient` with step-indexed dispatch tables keyed by tool names (for tool-use calls) and system prompt (for no-tools calls), then wire the env var swap into `dm_agent.py` at the module level.

**Tech Stack:** Python, Anthropic SDK types (`Message`, `TextBlock`, `ToolUseBlock`, `Usage`), pytest, `importlib.reload` for env var tests.

---

### Task 1: Extract prompts to `src/services/prompts.py`

This is a pure refactor — moves the three inline prompt strings out of `dm_agent.py` so both `dm_agent.py` and `mock_llm.py` can import them without a circular dependency.

**Files:**
- Create: `src/services/prompts.py`
- Modify: `src/services/dm_agent.py`

**Step 1: Create `src/services/prompts.py`**

```python
master_system_prompt = """You are an AI Dungeon Master for a narrative focused RPG. You bring stories to life with vivid descriptions, memorable npcs, and player-driven adventures.

## Your Role
- Create immersive atmospheric narratives that respond to player choices
- Embody NPCs with distinc personalities and voices
- Present meaningful choices with real consequences
- Balance fun with challenge-Players should feel heroic but not invincible
- Keep combat descriptions cinematic rather than mechanical

## Narrative Style
- Use the second person ("You step into a tavern...")
- Be descriptive but concise - paint the scene for players to engage with
- End responses with a clear prompt for player action or decision
- Match tone to the situation: tense in danger, lighthearted when safe

## Rules Approach
- Narrative first: Story trumps mechanics
- Use character stats as guidelines for success likelihood, not strict determiners
- Resolve actions through narrative logic - if it makes sense for the character it can work
- When outcomes are uncertain, describe degrees of success/failure

## Character Stat Reference
Characters have seven attributes (1-10 scale, 5 is average)
- **strength**: Physical power, melee combat
- **Perception**: Awareness, ranged accuracy, detecting hidden things
- **Endurance**: Stamina, health, resitance to damage
- **Charisma**: Social influence, persuasion, and leadership
- **Intelligence**: Knowledge, reason, magical aptitude
- **Agility**: Speed, reflexes, stealth, acrobatics
- **Luck**: Fortune in uncertain situations, critical hits

When a character performs an action or attempts something challenging, weigh their stat(s) and the narrative context to determine the outcome.
"""

# TODO: source the possible tags from my own db for the prompt on startup.
campaign_creation_prompt = """You are a campaign architect for a narrative RPG. Your job is to analyze a player's campaign description, classify it into relevant story tags, and use the search_checkpoints tool to find pre-authored story milestones that fit the campaign.

## Your Process

1. **Classify the description** — Read the player's request and identify the key themes, tone, setting, and content types it implies.

2. **Call search_checkpoints** — Search for checkpoints that match. Choose tags that precisely reflect the description — fewer accurate tags beat many vague ones. Call the tool ONLY ONCE

3. **Return a campaign** — Once you have results, respond with a raw JSON object and nothing else. Do not include any surrounding text, explanation, or formatting:
{
  "name": "string — an evocative campaign title",
  "theme": "string — one sentence describing the campaign's core narrative tension",
  "description": "string — 2-4 sentences describing the campaign setting and tone",
  "checkpoint_ids": [integer, ...] — ordered list of checkpoint IDs selected from the search results
}

## Tag Reference
Use these tags when calling search_checkpoints:

**Setting**: wilderness, urban, dungeon, coastal, aquatic, enclosed, cold
**Tone**: horror, mystery, intrigue, political, supernatural, investigation, moral-choice
**Content**: combat, social, puzzle, exploration, stealth, heist, rescue, non-combat, siege, strategy
**Enemies**: undead, troll, dragon, giant, werewolf, cult, boss
**Situational**: urgent, timed, race, rival, fire, poison, ambush
"""

character_creation_prompt = """You are a character creation assistant for a narrative RPG. Given a character description and optionally a biography and/or class, generate a complete character sheet as a JSON object.

## Your Task
Analyze the provided character details and produce stats and missing fields that fit the character concept. Infer personality, background, and abilities from context clues in the description and biography.

## Stat Guidelines
All stats use a 1-10 scale where 5 is an average person:
- **strength**: Physical power, melee combat
- **perception**: Awareness, ranged accuracy, detecting hidden things
- **endurance**: Stamina, health, resistance to damage
- **charisma**: Social influence, persuasion, leadership
- **intelligence**: Knowledge, reason, magical aptitude
- **agility**: Speed, reflexes, stealth, acrobatics
- **luck**: Fortune in uncertain situations, critical hits

Assign stats that reflect the character concept. A scholarly wizard should have high intelligence but maybe low strength. A battle-hardened warrior should have high strength and endurance. Stats should feel grounded — not every character is exceptional at everything.

## Rules
- If no class is provided, infer one that fits the description (e.g. warrior, mage, rogue, ranger, cleric, bard, etc.)
- If no biography is provided, write a biography that fits the description and class
- Biography must be 2-3 sentences and no more than 200 characters
- Biography should only cover backstory before the adventure begins — no current events, no plot hooks
- Write biography in third person past tense
- Do not invent locations, organizations, or relationships not implied by the player's description
- Generate a name if none is provided
- Estimate a reasonable age if none is implied
- Leave story_so_far as an empty string — their adventure hasn't begun yet

## Output Format
Respond with ONLY the raw JSON object. Do not include any surrounding text, explanation, or formatting — just the JSON:
{
  "name": "string",
  "hero_class": "string",
  "biography": "string",
  "age": integer,
  "story_so_far": "",
  "strength": integer (1-10),
  "perception": integer (1-10),
  "endurance": integer (1-10),
  "charisma": integer (1-10),
  "intelligence": integer (1-10),
  "agility": integer (1-10),
  "luck": integer (1-10)
}
"""
```

**Step 2: Update `src/services/dm_agent.py` imports**

Remove the three inline prompt string definitions and replace with imports at the top of the file:

```python
from src.services.prompts import (
    master_system_prompt,
    campaign_creation_prompt,
    character_creation_prompt,
)
```

**Step 3: Run existing tests to confirm the refactor didn't break anything**

```bash
pytest -v
```

Expected: all tests pass. If any fail, the import path is wrong — double-check the `from src.services.prompts import ...` line.

**Step 4: Commit**

```bash
git add src/services/prompts.py src/services/dm_agent.py
git commit -m "refactor: extract system prompts to prompts.py"
```

---

### Task 2: Implement `src/services/mock_llm.py`

**Files:**
- Create: `src/services/mock_llm.py`
- Create: `tests/test_mock_llm.py`

**Step 1: Write the failing tests**

Create `tests/test_mock_llm.py`:

```python
import json

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from src.services.mock_llm import MOCK_CAMPAIGN_JSON, MOCK_CHARACTER_JSON, MockAnthropicClient
from src.services.prompts import campaign_creation_prompt, character_creation_prompt
from src.tools.campaign_tools import search_checkpoints_tool


class TestCharacterCreation:
    def setup_method(self):
        self.client = MockAnthropicClient()
        self.messages = [{"role": "user", "content": "a cunning rogue"}]

    def test_returns_end_turn(self):
        response = self.client.messages.create(
            max_tokens=175,
            system=character_creation_prompt,
            messages=self.messages,
            model="mock",
        )
        assert response.stop_reason == "end_turn"

    def test_returns_text_block(self):
        response = self.client.messages.create(
            max_tokens=175,
            system=character_creation_prompt,
            messages=self.messages,
            model="mock",
        )
        assert isinstance(response.content[0], TextBlock)

    def test_returns_valid_character_json(self):
        response = self.client.messages.create(
            max_tokens=175,
            system=character_creation_prompt,
            messages=self.messages,
            model="mock",
        )
        data = json.loads(response.content[0].text)
        assert "name" in data
        assert "strength" in data
        assert "story_so_far" in data


class TestCampaignCreation:
    def setup_method(self):
        self.client = MockAnthropicClient()
        self.tools = [search_checkpoints_tool]

    def test_first_call_returns_tool_use(self):
        messages = [{"role": "user", "content": "a dark gothic city"}]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        assert response.stop_reason == "tool_use"

    def test_first_call_returns_search_checkpoints_block(self):
        messages = [{"role": "user", "content": "a dark gothic city"}]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        assert isinstance(response.content[0], ToolUseBlock)
        assert response.content[0].name == "search_checkpoints"

    def test_second_call_returns_end_turn(self):
        messages = [
            {"role": "user", "content": "a dark gothic city"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "x", "name": "search_checkpoints", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "[]"}]},
        ]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        assert response.stop_reason == "end_turn"

    def test_second_call_returns_valid_campaign_json(self):
        messages = [
            {"role": "user", "content": "a dark gothic city"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "x", "name": "search_checkpoints", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "[]"}]},
        ]
        response = self.client.messages.create(
            max_tokens=1024,
            system=campaign_creation_prompt,
            tools=self.tools,
            messages=messages,
            model="mock",
        )
        data = json.loads(response.content[0].text)
        assert "name" in data
        assert "checkpoint_ids" in data
        assert isinstance(data["checkpoint_ids"], list)


class TestUnknownCallsRaise:
    def setup_method(self):
        self.client = MockAnthropicClient()

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="No mock sequence registered for tools"):
            self.client.messages.create(
                max_tokens=1024,
                system="some system prompt",
                tools=[{"name": "unknown_tool", "description": "", "input_schema": {"type": "object", "properties": {}}}],
                messages=[{"role": "user", "content": "hello"}],
                model="mock",
            )

    def test_unknown_system_prompt_raises(self):
        with pytest.raises(ValueError, match="No mock sequence registered for system prompt"):
            self.client.messages.create(
                max_tokens=1024,
                system="some unregistered system prompt for a future feature",
                messages=[{"role": "user", "content": "hello"}],
                model="mock",
            )
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_mock_llm.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.services.mock_llm'`

**Step 3: Create `src/services/mock_llm.py`**

```python
import json

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from src.services.prompts import campaign_creation_prompt, character_creation_prompt

MOCK_CHARACTER_JSON = json.dumps({
    "name": "Aldric the Grey",
    "hero_class": "wizard",
    "biography": "Aldric spent his formative years studying forgotten tomes in a crumbling tower on the edge of the empire.",
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


def _character_creation_sequence(step: int) -> Message:
    return _make_message(
        [TextBlock(text=MOCK_CHARACTER_JSON, type="text", citations=None)],
        "end_turn",
    )


def _campaign_creation_sequence(step: int) -> Message:
    if step == 0:
        return _make_message(
            [ToolUseBlock(
                id="mock_tool_use_01",
                input={"tags": "urban,intrigue", "limit": 5},
                name="search_checkpoints",
                type="tool_use",
            )],
            "tool_use",
        )
    return _make_message(
        [TextBlock(text=MOCK_CAMPAIGN_JSON, type="text", citations=None)],
        "end_turn",
    )


TOOL_SEQUENCES = {
    frozenset(["search_checkpoints"]): _campaign_creation_sequence,
}

NO_TOOL_SEQUENCES = {
    character_creation_prompt: _character_creation_sequence,
}


class MockAnthropicMessages:
    def create(self, *, messages, system=None, tools=None, **kwargs) -> Message:
        step = sum(
            1 for m in messages
            if isinstance(m.get("content"), list)
            and any(c.get("type") == "tool_result" for c in m["content"])
        )

        if tools:
            tool_names = frozenset(t["name"] for t in tools)
            sequence_fn = TOOL_SEQUENCES.get(tool_names)
            if sequence_fn is None:
                raise ValueError(
                    f"No mock sequence registered for tools: {tool_names}. "
                    "Add it to TOOL_SEQUENCES in src/services/mock_llm.py."
                )
            return sequence_fn(step)

        sequence_fn = NO_TOOL_SEQUENCES.get(system)
        if sequence_fn is None:
            raise ValueError(
                f"No mock sequence registered for system prompt (first 50 chars): {str(system)[:50]!r}. "
                "Add it to NO_TOOL_SEQUENCES in src/services/mock_llm.py."
            )
        return sequence_fn(step)


class MockAnthropicClient:
    def __init__(self):
        self.messages = MockAnthropicMessages()
```

**Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_mock_llm.py -v
```

Expected: all 9 tests pass.

**Step 5: Run the full test suite to confirm nothing regressed**

```bash
pytest -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add src/services/mock_llm.py tests/test_mock_llm.py
git commit -m "feat: add mock LLM client with tool-use and no-tools dispatch"
```

---

### Task 3: Wire `MOCK_LLM` env var in `src/services/dm_agent.py`

**Files:**
- Modify: `src/services/dm_agent.py`
- Create: `tests/test_dm_agent_client.py`

**Step 1: Write the failing tests**

Create `tests/test_dm_agent_client.py`:

```python
import importlib

import pytest

import src.services.dm_agent as dm_agent_module


@pytest.fixture
def restore_dm_agent():
    """Reload dm_agent after the test to restore the module-level client."""
    yield
    importlib.reload(dm_agent_module)


def test_mock_client_selected_when_mock_llm_set(monkeypatch, restore_dm_agent):
    monkeypatch.setenv("MOCK_LLM", "true")
    importlib.reload(dm_agent_module)

    from src.services.mock_llm import MockAnthropicClient
    assert isinstance(dm_agent_module.client, MockAnthropicClient)


def test_real_client_selected_when_mock_llm_not_set(monkeypatch, restore_dm_agent):
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    importlib.reload(dm_agent_module)

    from anthropic import Anthropic
    assert isinstance(dm_agent_module.client, Anthropic)
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_dm_agent_client.py -v
```

Expected: both tests fail — `MockAnthropicClient` is never selected regardless of env var.

**Step 3: Update `src/services/dm_agent.py` client initialization**

Find this line near the top of `dm_agent.py`:

```python
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
```

Replace it with:

```python
if os.getenv("MOCK_LLM"):
    from src.services.mock_llm import MockAnthropicClient
    client = MockAnthropicClient()
else:
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
```

**Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_dm_agent_client.py -v
```

Expected: both tests pass.

**Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add src/services/dm_agent.py tests/test_dm_agent_client.py
git commit -m "feat: wire MOCK_LLM env var to swap Anthropic client for mock"
```

---

### Task 4: Verify end-to-end with the local server

This is a manual verification step — no code changes.

**Step 1: Set `MOCK_LLM=true` in `.env`**

Open `.env` and add:
```
MOCK_LLM=true
```

**Step 2: Start the local server**

```bash
make lr
```

**Step 3: Create a character**

```bash
curl -s -X POST http://localhost:8000/characters/ \
  -H "Content-Type: application/json" \
  -d '{"description": "a cunning rogue with quick hands"}' | jq
```

Expected: a character named `Aldric the Grey` is returned (the mock fixture).

**Step 4: Create a campaign**

```bash
curl -s -X POST http://localhost:8000/campaigns/ \
  -H "Content-Type: application/json" \
  -d '{"description": "a dark gothic city riven by political scheming"}' | jq
```

Expected: `"Shadows Over Thornwall"` is returned. Check the DB to confirm checkpoints 1, 2, 3 were linked.

**Step 5: Toggle off and confirm real calls resume**

In `.env`, remove or comment out `MOCK_LLM=true`. Restart the server. Make a campaign creation request — it should now call the real Anthropic API (you'll see latency and cost).
