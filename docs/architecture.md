# Architecture

C4 diagrams for the dungeon service, written in Mermaid so they render on GitHub. Update them when containers, external systems, or service boundaries change.

The three C4 levels use Mermaid `flowchart` with C4 colours rather than Mermaid's `C4Context` diagrams. The C4 renderer doesn't route lines around boxes, so its labels overlap and lines cross through shapes. Legend: dark blue = person, blue = our system / containers, light blue = components, grey = external systems. Dashed lines are browser redirects or background work.

## Level 1: System Context

```mermaid
flowchart TB
  player["<b>Player</b><br/><i>[Person]</i><br/>Creates characters and campaigns,<br/>plays text adventures"]
  dungeon["<b>AI Dungeon Master</b><br/><i>[Software System]</i><br/>Web app + API that runs AI-narrated<br/>campaigns with server-side dice checks"]
  discord["<b>Discord</b><br/><i>[External System]</i><br/>OAuth identity provider"]
  anthropic["<b>Anthropic Claude API</b><br/><i>[External System]</i><br/>Characters, campaigns, DM narration,<br/>roll_check tool, memory extraction"]
  voyage["<b>Voyage AI</b><br/><i>[External System]</i><br/>Text embeddings (voyage-3.5)<br/>for memory storage + search"]

  player -- "Plays in browser<br/>[HTTPS]" --> dungeon
  player -. "Signs in" .-> discord
  dungeon -- "OAuth token + profile<br/>[HTTPS]" --> discord
  dungeon -- "Streaming messages + tools<br/>[HTTPS]" --> anthropic
  dungeon -- "Embeds + searches memories<br/>[HTTPS]" --> voyage

  classDef person fill:#08427b,stroke:#052e56,color:#fff
  classDef system fill:#1168bd,stroke:#0b4884,color:#fff
  classDef container fill:#438dd5,stroke:#2e6295,color:#fff
  classDef component fill:#85bbf0,stroke:#5d82a8,color:#0b2340
  classDef external fill:#6b6b6b,stroke:#4d4d4d,color:#fff
  linkStyle default stroke:#707070,stroke-width:2.5px
  class player person
  class dungeon system
  class discord,anthropic,voyage external
```

## Level 2: Containers

```mermaid
flowchart TB
  player["<b>Player</b><br/><i>[Person]</i>"]

  subgraph sys["AI Dungeon Master [Software System]"]
    direction TB
    web["<b>dungeon-web</b><br/><i>[Container: React, Vite, Tailwind]</i><br/>SPA. Handles the Discord redirect,<br/>streams turns, animates dice"]
    api["<b>dungeon-service</b><br/><i>[Container: Python, FastAPI, SQLModel]</i><br/>REST + SSE API: auth, characters,<br/>campaigns, turns, dice checks"]
    db[("<b>PostgreSQL + pgvector</b><br/><i>[Container: Postgres 16]</i><br/>Users, characters, campaigns,<br/>checkpoints, history, memories")]
    flyway["<b>Flyway</b><br/><i>[Container: Docker]</i><br/>Migrations everywhere,<br/>seeds locally"]
  end

  discord["<b>Discord</b><br/><i>[External System]</i>"]
  anthropic["<b>Anthropic Claude API</b><br/><i>[External System]</i>"]
  voyage["<b>Voyage AI</b><br/><i>[External System]</i>"]

  player -- "Uses<br/>[HTTPS]" --> web
  web -. "OAuth authorize redirect" .-> discord
  web -- "JSON + SSE, Bearer JWT<br/>[HTTPS]" --> api
  api -- "Reads/writes<br/>[psycopg2]" --> db
  flyway -- "Migrates<br/>[JDBC]" --> db
  api -- "Token exchange + /users/@me" --> discord
  api -- "Streaming LLM calls + tools" --> anthropic
  api -- "Embeddings" --> voyage

  classDef person fill:#08427b,stroke:#052e56,color:#fff
  classDef system fill:#1168bd,stroke:#0b4884,color:#fff
  classDef container fill:#438dd5,stroke:#2e6295,color:#fff
  classDef component fill:#85bbf0,stroke:#5d82a8,color:#0b2340
  classDef external fill:#6b6b6b,stroke:#4d4d4d,color:#fff
  linkStyle default stroke:#707070,stroke-width:2.5px
  class player person
  class web,api,flyway container
  class db container
  class discord,anthropic,voyage external
  style sys fill:none,stroke:#1168bd,stroke-width:2px,stroke-dasharray:6 4
```

## Level 3: Components (dungeon-service)

The services all read and write Postgres through SQLModel, shown as a single edge from the Services group.

```mermaid
flowchart LR
  web["<b>dungeon-web</b><br/><i>[Container: React SPA]</i>"]

  subgraph svc["dungeon-service [Container]"]
    direction LR
    authR["<b>auth router</b><br/>POST /auth/discord/callback"]
    charR["<b>characters router</b><br/>CRUD, preview, lookups,<br/>turn stream (SSE)<br/><i>JWT via get_current_user</i>"]
    campR["<b>campaigns router</b><br/>Create + list, scoped<br/>to the current user<br/><i>JWT via get_current_user</i>"]
    subgraph services["Services · src/services"]
      direction TB
      authS["<b>auth_service</b><br/>Discord user upsert, JWT"]
      charS["<b>character_service</b><br/>Preview + persistence"]
      turnS["<b>turn_service</b><br/>Context, SSE events,<br/>saves messages"]
      embS["<b>embedding_service</b><br/>Background: extract,<br/>embed, upsert memories"]
      campS["<b>campaign_service</b><br/>Campaign + checkpoints"]
    end
    memS["<b>memory_service</b><br/>Vector search over<br/>campaign memories"]
    dm["<b>dm_agent</b><br/>All Claude calls,<br/>prompts.py system prompts"]
    tools["<b>tools</b><br/>search_checkpoints,<br/>roll_check (d20 + stat)"]
  end

  db[("<b>PostgreSQL + pgvector</b>")]
  discord["<b>Discord</b>"]
  anthropic["<b>Anthropic Claude API</b>"]
  voyage["<b>Voyage AI</b>"]

  web -- "OAuth code" --> authR
  web -- "REST + SSE" --> charR
  web -- "REST" --> campR
  authR --> authS
  authR -- "Token + user fetch" --> discord
  charR --> charS
  charR --> turnS
  charR -. "after each turn" .-> embS
  campR --> campS
  charS -- "create_character" --> dm
  turnS -- "process_turn_stream" --> dm
  turnS -- "retrieve_memories" --> memS
  memS -- "embed query" --> voyage
  memS -- "cosine search" --> db
  embS -- "extract_memories" --> dm
  campS -- "create_campaign" --> dm
  embS -- "embed" --> voyage
  dm -- "runs tool calls" --> tools
  dm -- "Messages API (streaming)" --> anthropic
  services -- "SQLModel" --> db
  tools -- "checkpoint search" --> db

  classDef container fill:#438dd5,stroke:#2e6295,color:#fff
  classDef component fill:#85bbf0,stroke:#5d82a8,color:#0b2340
  classDef external fill:#6b6b6b,stroke:#4d4d4d,color:#fff
  class web,db container
  class authR,charR,campR,authS,charS,campS,turnS,memS,embS,dm,tools component
  class discord,anthropic,voyage external
  style svc fill:none,stroke:#438dd5,stroke-width:2px,stroke-dasharray:6 4
  style services fill:#eef5fc,stroke:#85bbf0
  linkStyle default stroke:#707070,stroke-width:2.5px
```

## Dynamic: Playing a turn

```mermaid
sequenceDiagram
  autonumber
  participant Web as dungeon-web
  participant R as characters router
  participant T as turn_service
  participant DM as dm_agent
  participant C as Claude
  participant Dice as roll_check
  participant DB as Postgres
  participant BG as embedding_service (background)
  participant V as Voyage AI

  Web->>R: POST /characters/{id}/turns/stream {message}
  R->>R: get_current_user + ownership check
  R->>T: load_turn_context()
  T->>DB: character, campaign, active checkpoint, last 10 messages
  T->>V: embed last DM reply + message (query)
  T->>DB: cosine search memory tables (this campaign, top 3 per kind)
  R-->>Web: SSE stream opens
  T-->>Web: event: thinking
  T->>DM: process_turn_stream(turn)
  DM->>C: stream(tools=[roll_check])
  opt outcome is uncertain
    C-->>DM: tool_use roll_check(stat, difficulty, reason)
    DM->>Dice: d20 + stat vs target
    T-->>Web: event: roll
    DM->>C: stream(tool_result, tool_choice=none)
  end
  C-->>DM: narration deltas
  T-->>Web: event: text (repeated)
  T->>DB: save user + assistant messages
  T-->>Web: event: done
  R-)BG: extract_and_store_memories(campaign_id, [player, dm])
```

Rolls are never stored. Memories are written after every turn and searched before the next one; the matches go into the DM's system prompt. If the memory lookup fails, the turn continues without them.

## Dynamic: Creating a campaign

```mermaid
sequenceDiagram
  autonumber
  participant Web as dungeon-web
  participant S as campaign_service
  participant DM as dm_agent
  participant C as Claude
  participant Tool as search_checkpoints
  participant DB as Postgres

  Web->>S: POST /campaigns/ {character_id, description}
  S->>DB: load character, verify owner
  S->>DM: create_campaign()
  loop until stop_reason == end_turn
    DM->>C: messages.create(tools=[search_checkpoints])
    C-->>DM: tool_use(tags)
    DM->>Tool: handle_search_checkpoints(tags)
    Tool->>DB: select checkpoints by tag
    Tool-->>DM: results → tool_result
  end
  C-->>DM: campaign JSON (name, theme, checkpoint_ids, opening_message)
  S->>DB: insert campaign + campaigncheckpoint rows (first "new", rest "locked")
  S->>DB: set character.campaign_id, insert opening message into messagehistory
  S-->>Web: 201 {campaign, opening_message}
```

## Data model

```mermaid
erDiagram
  user ||--o{ character : owns
  campaign ||--o{ character : has
  campaign ||--o{ campaigncheckpoint : "ordered"
  checkpoint ||--o{ campaigncheckpoint : "used in"
  campaign ||--o{ messagehistory : logs
  character ||--o{ messagehistory : sends
  campaign ||--o{ npcmemory : remembers
  campaign ||--o{ locationmemory : remembers
  campaign ||--o{ itemmemory : remembers
  campaign ||--o{ eventmemory : remembers
```
