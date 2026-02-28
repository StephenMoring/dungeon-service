# Gameplay Loop Implementation Plan

## Overview

Implement a turn-based gameplay loop where a player exchanges messages with an AI DM across a campaign's sequence of checkpoints. Context is maintained via a rolling message window and compressed checkpoint summaries. Checkpoint completion is detected automatically by the DM after each turn.

Single-player design: each character is a unique playthrough of one campaign. No `game_session` table — the character implicitly represents the session. Current checkpoint is derived from `CampaignCheckpoint.status` (first `active` one).

---

## Database: New Table

### `session_message`
- `id` (PK)
- `character_id` (FK → character)
- `role` (str: `user` / `assistant`)
- `content` (str)
- `created_at` (datetime)

No other schema changes. `CampaignCheckpoint.status` and `CampaignCheckpoint.summary` are already present and used. First checkpoint's status is set to `active` when a campaign is created.

---

## New API Endpoints

### `POST /characters/{character_id}/turn`
Submit a player message and receive a DM response.

- Input: `{ message: str }`
- Returns: `{ response: str }`
- Internally: assembles context, calls DM, checks completion, maybe advances checkpoint

---

## Turn Endpoint Flow

```
1. Load character (stats, biography, campaign_id)
2. Load campaign checkpoints ordered by `order`:
     - completed: use summary field only
     - current (first with status == "active"): full checkpoint data
     - next (order == current.order + 1): full checkpoint data (DM's hidden goal)
3. Load last 15 session_messages for this character_id
4. Build system prompt (see below)
5. Call LLM → get DM response text
6. Persist player message + DM response to session_message
7. Run checkpoint completion check (see below)
8. Return DM response
```

---

## System Prompt Structure

```
You are a Dungeon Master running a D&D 5e campaign.

CHARACTER:
[name, class, stats, biography]

STORY SO FAR:
[one paragraph per completed checkpoint summary, in order]

CURRENT SITUATION:
[current checkpoint: title, setting, objective, key_npcs, description]

YOUR SECRET GOAL:
The player should eventually reach: [next checkpoint title + description].
Do not reveal this directly. Weave in plot hooks and encounters that
naturally lead them there. Give the player full agency.

RULES: Respond only as the DM. Keep responses under 3 paragraphs.
```

If there is no next checkpoint (player is on the final checkpoint), omit the secret goal section.

---

## Checkpoint Completion Check (Option A)

After each DM response, run a second lightweight LLM call to classify whether the current checkpoint has been completed.

**Classifier prompt:**

```
Checkpoint objective: [checkpoint.objective]

Recent exchange:
[last 3-4 messages from session_message]

Has the player meaningfully completed or arrived at this checkpoint objective?
Reply with only: YES or NO
```

- Use `max_tokens=5` to keep this call cheap and fast
- If YES:
  1. Call LLM to generate a 2-3 sentence summary of what happened at this checkpoint (use last 15 messages + checkpoint description as context)
  2. Store summary in `CampaignCheckpoint.summary`, set status to `completed`
  3. Set next `CampaignCheckpoint` status to `active`
  4. Trim `session_message` rows for this character: keep only the last 5 (the rest are now captured in the summary)
  5. If no next checkpoint exists, the campaign is complete

---

## Nudge Fallback

If the player has exchanged more than 20 turns on a checkpoint without completing it, append to the system prompt:

```
URGENT: The player has been in this situation for a long time.
Actively steer them toward the objective. Introduce a compelling
reason they must act now.
```

Track turn count by querying `session_message` count for this character since the current checkpoint became `active`.

---

## New Services

### `turn_service.py`
- `get_context(character_id, db)` → bundle: character, checkpoint summaries, current checkpoint, next checkpoint, recent messages
- `persist_messages(character_id, player_msg, dm_response, db)`
- `advance_checkpoint(character_id, current_checkpoint, summary, db)`
- `trim_messages(character_id, keep_last_n, db)`
- `run_turn(character_id, player_message, db)` → `str` (DM response)

### `dm_agent.py` additions
- `run_turn(context_bundle, player_message)` → `str`
- `check_checkpoint_completion(checkpoint_objective, recent_messages)` → `bool`
- `summarize_checkpoint(checkpoint, recent_messages)` → `str`

---

## Build Order

1. Flyway migration: add `session_message` table
2. SQLModel model for `session_message`
3. `POST /characters/{character_id}/turn` endpoint + `turn_service.get_context` + `turn_service.persist_messages`
4. `dm_agent.run_turn` + wire into turn endpoint — rolling window only, no checkpoint detection yet
5. Play test: verify context assembly and message persistence work
6. Add `dm_agent.check_checkpoint_completion` + wiring in `turn_service`
7. Add `dm_agent.summarize_checkpoint` + `turn_service.advance_checkpoint`
8. Add nudge fallback
