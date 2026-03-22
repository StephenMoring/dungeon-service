# Checkpoint Progression Design

**Date**: 2026-03-21
**Status**: Approved

## Overview

Implement checkpoint progression for the AI Dungeon Master game. When a player completes a checkpoint's objective, the system detects this via structured output on the main turn response, surfaces a natural completion moment, allows the player to linger, and advances to the next checkpoint when the player departs — generating a summary and transition narrative in the process.

## Approach

Structured output on `process_turn`. The DM response includes two boolean signals alongside the narrative text. No separate heuristic or classifier call. Completion detection is folded into the LLM call already being made.

## Structured Output Schema

`process_turn` returns a structured object instead of a plain string. The following JSON schema must be passed to `output_config` (same mechanism as `CHARACTER_SCHEMA` in `dm_agent.py`; requires Anthropic SDK >= 0.86.0):

```python
TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {"type": "string"},
        "objective_complete": {"type": "boolean"},
        "player_departing": {"type": "boolean"},
    },
    "required": ["response", "objective_complete", "player_departing"],
    "additionalProperties": False,
}
```

- `response` — the DM's narrative text
- `objective_complete` — model sets this when the checkpoint objective has been fulfilled, based on the `objective` field injected into the system prompt
- `player_departing` — model sets this when the player expresses intent to leave, move on, or continue their journey; only acted on when checkpoint is `pending_completion`

`take_turn` continues to return `str` (the narrative text only). The structured fields are consumed internally and never surfaced to the API caller. `MessageHistory.content` stores the `response` string from the structured output.

## Checkpoint Status Lifecycle

```
locked → new → pending_completion → complete
```

- `locked` — not yet reached
- `new` — currently active; checkpoint context injected into the system prompt
- `pending_completion` — objective met, player chose to linger; checkpoint context still injected into the system prompt; `player_departing` watched each turn
- `complete` — player has departed; summary saved, next checkpoint unlocked

Checkpoint context (`title`, `description`, `setting`, `objective`, `key_npcs`) is injected for both `new` and `pending_completion` statuses. The status only affects which structured output flags are acted upon.

On campaign creation: first checkpoint is `new`, rest are `locked`. When a checkpoint moves to `complete`, the next one flips from `locked` to `new`.

No DB migration required — `status` is plain `TEXT` with no enum constraint.

### Active Checkpoint Query Bug Fix

The current query in `turn_service.take_turn` incorrectly excludes `["campaign", "locked"]` — `"campaign"` is not a valid status and should be `"complete"`. This must be fixed as part of this implementation:

```python
.where(col(CampaignCheckpoint.status).not_in(["complete", "locked"]))
```

This query correctly selects both `new` and `pending_completion` checkpoints as active.

## Turn Flow (`turn_service.take_turn`)

```
1. Load character, campaign, active checkpoint, recent messages (unchanged)

2. Call process_turn → { response, objective_complete, player_departing }

3. If checkpoint is `new` and objective_complete:
   → mark checkpoint as `pending_completion`
   → return response (model naturally writes the completion notice + linger prompt)

4. If checkpoint is `pending_completion` and player_departing:
   → call dm_agent.generate_checkpoint_summary() → save to CampaignCheckpoint.summary
   → mark checkpoint as `complete`
   → find next checkpoint (next lowest `order` where status is `locked`)
   → if next checkpoint exists: flip its status to `new`, call dm_agent.generate_transition_narrative() → return as DM response (original `response` from this turn is discarded)
   → if no next checkpoint (campaign complete): return a campaign-complete message instead of transition narrative; no further advancement attempted

5. Otherwise: return response normally

6. Save player message and DM response (transition narrative or response) to message_history
```

## Campaign Complete State

When the last checkpoint completes and no `locked` checkpoint remains, the campaign is over. The turn flow detects this (no next checkpoint found in step 4) and returns a campaign-complete narrative message — either a hardcoded string or a small LLM call — instead of a transition narrative. No further turns should attempt checkpoint advancement.

Implementing a formal `campaign_complete` flag on `Campaign` is deferred; for MVP, detecting no remaining `locked` checkpoints at advancement time is sufficient.

## New `dm_agent` Functions

### `generate_checkpoint_summary(checkpoint, recent_messages) -> str`

- Summarises what happened at the checkpoint in 2-3 sentences, past tense, third person
- Input: checkpoint `title`, `objective` + the same last 10 messages already loaded for the turn (no additional DB query)
- Output: plain string saved to `CampaignCheckpoint.summary`
- `max_tokens`: 150

### `generate_transition_narrative(current_checkpoint, next_checkpoint, character) -> str`

- Writes a brief atmospheric transition scene moving the character from one location to the next
- Input: both checkpoint `title` and `setting` + character `name` and `hero_class`
- Output: plain string returned as the DM response for the turn
- `max_tokens`: 200

Both functions use `claude-sonnet-4-5-20250929`, no tool use, no `output_config`.

## System Prompt Changes

`build_turn_system_prompt` must be updated to instruct the model on when to set the structured output flags:

- Set `objective_complete: true` when the narrative makes clear the checkpoint's objective has been fulfilled
- Set `player_departing: true` when the player expresses intent to leave, move on, or continue their journey
- When setting `objective_complete`, naturally include a completion beat in the response and offer the player the choice to linger or move on — do not be aggressive about this
- Default both flags to `false`

## What Is Not In Scope

- Model routing (separate model for classifier calls) — deferred
- Keyword heuristic for departure detection — replaced entirely by structured output
- Re-prompting the player after extended lingering — deferred
- Formal `campaign_complete` field on `Campaign` — deferred; detected implicitly at advancement time
