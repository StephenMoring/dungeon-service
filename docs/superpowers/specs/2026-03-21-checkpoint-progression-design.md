# Checkpoint Progression Design

**Date**: 2026-03-21
**Status**: Approved

## Overview

Implement checkpoint progression for the AI Dungeon Master game. When a player completes a checkpoint's objective, the system detects this via structured output on the main turn response, surfaces a natural completion moment, allows the player to linger, and advances to the next checkpoint when the player departs — generating a summary and transition narrative in the process.

## Approach

Structured output on `process_turn`. The DM response includes two boolean signals alongside the narrative text. No separate heuristic or classifier call. Completion detection is folded into the LLM call already being made.

## Structured Output Schema

`process_turn` returns a structured object instead of a plain string:

```json
{
  "response": "string — the DM's narrative response",
  "objective_complete": false,
  "player_departing": false
}
```

- `objective_complete` — model sets this when it judges the checkpoint objective has been met, based on the checkpoint's `objective` field injected into the system prompt
- `player_departing` — model sets this when it judges the player wants to leave the current location and move on; only acted on when checkpoint is `pending_completion`

## Checkpoint Status Lifecycle

```
locked → new → pending_completion → complete
```

- `locked` — not yet reached
- `new` — currently active; checkpoint context injected into every turn
- `pending_completion` — objective met, player chose to linger; DM continues normally, `player_departing` watched each turn
- `complete` — player has departed; summary saved, next checkpoint unlocked

On campaign creation: first checkpoint is `new`, rest are `locked`. When a checkpoint moves to `complete`, the next one flips from `locked` to `new`.

No DB migration required — `status` is plain `TEXT` with no enum constraint.

## Turn Flow (`turn_service.take_turn`)

```
1. Load character, campaign, active checkpoint, recent messages (unchanged)

2. Call process_turn → { response, objective_complete, player_departing }

3. If checkpoint is `new` and objective_complete:
   → mark checkpoint as `pending_completion`
   → return DM response (model naturally writes the completion notice + linger prompt)

4. If checkpoint is `pending_completion` and player_departing:
   → call dm_agent.generate_checkpoint_summary() → save to CampaignCheckpoint.summary
   → mark checkpoint as `complete`
   → find next checkpoint, flip status from `locked` to `new`
   → call dm_agent.generate_transition_narrative() → return as the DM response for this turn

5. Otherwise: return DM response normally

6. Save both messages to message_history (unchanged)
```

## New `dm_agent` Functions

### `generate_checkpoint_summary(checkpoint, recent_messages) -> str`

- Summarises what happened at the checkpoint in 2-3 sentences, past tense, third person
- Input: checkpoint objective + last N messages
- Output: plain string saved to `CampaignCheckpoint.summary`
- `max_tokens`: ~150

### `generate_transition_narrative(current_checkpoint, next_checkpoint, character) -> str`

- Writes a brief atmospheric transition scene moving the character from one location to the next
- Input: both checkpoint titles/settings + character name/class
- Output: plain string returned as the DM response for the turn
- `max_tokens`: ~200

Both functions use `claude-sonnet-4-5-20250929`, no tool use.

## System Prompt Changes

`build_turn_system_prompt` must be updated to instruct the model on when to set the structured output flags:

- Set `objective_complete: true` when the narrative makes clear the checkpoint's objective has been fulfilled
- Set `player_departing: true` when the player expresses intent to leave, move on, or continue their journey
- When setting `objective_complete`, naturally include a completion beat in the response and offer the player the choice to linger or move on — do not be aggressive about this

## What Is Not In Scope

- Model routing (separate model for classifier calls) — deferred, not needed at MVP
- Keyword heuristic for departure detection — replaced entirely by structured output
- Re-prompting the player after extended lingering — nice to have, deferred
