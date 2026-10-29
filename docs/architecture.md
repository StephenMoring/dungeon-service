# Architecture

C4 diagrams for the dungeon service. They're written in Mermaid and render on GitHub. Update them when containers, external systems, or service boundaries change.

## Level 1: System Context

```mermaid
C4Context
  title System Context: AI Dungeon Master

  Person(player, "Player", "Creates characters and campaigns, plays text adventures")

  System(dungeon, "AI Dungeon Master", "Web app + API that runs AI-narrated campaigns")

  System_Ext(discord, "Discord", "OAuth identity provider")
  System_Ext(anthropic, "Anthropic Claude API", "Generates characters, campaigns, DM narration, memory extraction")
  System_Ext(voyage, "Voyage AI", "Text embeddings (voyage-3.5, 1024 dims)")

  Rel(player, dungeon, "Plays via browser")
  Rel(player, discord, "Signs in with")
  Rel(dungeon, discord, "Exchanges OAuth code, fetches user", "HTTPS")
  Rel(dungeon, anthropic, "Messages API, tool use, structured output", "HTTPS")
  Rel(dungeon, voyage, "Embeds memories", "HTTPS")
```

## Level 2: Containers

```mermaid
C4Container
  title Containers: AI Dungeon Master

  Person(player, "Player")

  System_Boundary(dungeon, "AI Dungeon Master") {
    Container(web, "dungeon-web", "React, Vite, MUI", "SPA served on localhost:3000. Handles the Discord redirect and calls the API with a JWT")
    Container(api, "dungeon-service", "Python, FastAPI, SQLModel", "REST API: auth, characters, campaigns, turns. Runs memory extraction as a background task")
    ContainerDb(db, "PostgreSQL + pgvector", "Postgres 16", "Users, characters, campaigns, checkpoints, message history, vector memory tables")
    Container(flyway, "Flyway", "Docker", "Applies db/migrations (all envs) and db/seeds (local only)")
  }

  System_Ext(discord, "Discord")
  System_Ext(anthropic, "Anthropic Claude API")
  System_Ext(voyage, "Voyage AI")

  Rel(player, web, "Uses", "HTTPS")
  Rel(web, discord, "OAuth authorize redirect")
  Rel(web, api, "JSON/REST, Bearer JWT", "HTTPS")
  Rel(api, db, "Reads/writes", "psycopg2")
  Rel(flyway, db, "Migrates", "JDBC")
  Rel(api, discord, "Token exchange + /users/@me")
  Rel(api, anthropic, "LLM calls")
  Rel(api, voyage, "Embeddings")
```

## Level 3: Components (dungeon-service)

```mermaid
C4Component
  title Components: dungeon-service API

  Container(web, "dungeon-web", "React SPA")
  ContainerDb(db, "PostgreSQL + pgvector")
  System_Ext(discord, "Discord")
  System_Ext(anthropic, "Anthropic Claude API")
  System_Ext(voyage, "Voyage AI")

  Container_Boundary(api, "dungeon-service") {
    Component(authR, "auth router", "src/api/auth.py", "POST /auth/discord/callback")
    Component(charR, "characters router", "src/api/characters.py", "Character CRUD, preview, classes/races, turn stream (SSE)")
    Component(campR, "campaigns router", "src/api/campaigns.py", "Create/list campaigns, campaign characters")
    Component(deps, "get_current_user", "src/api/dependencies.py", "Validates JWT, loads User")

    Component(authS, "auth_service", "Python", "Upserts Discord user, signs/validates JWT")
    Component(charS, "character_service", "Python", "Character preview + persistence, lookups")
    Component(campS, "campaign_service", "Python", "Parses campaign JSON, links checkpoints")
    Component(turnS, "turn_service", "Python", "Turn context, SSE events, persists messages")
    Component(embS, "embedding_service", "BackgroundTask", "Extracts + embeds + upserts memories")

    Component(dm, "dm_agent", "Anthropic SDK", "All Claude calls: create_character, create_campaign, process_turn_stream, extract_memories")
    Component(prompts, "prompts", "Python", "System prompts, build_turn_system_prompt")
    Component(tools, "campaign_tools / dice_tools", "Tool use", "search_checkpoints, roll_check")
  }

  Rel(web, authR, "OAuth code")
  Rel(web, charR, "REST + JWT")
  Rel(web, campR, "REST + JWT")
  Rel(charR, deps, "Depends")
  Rel(campR, deps, "Depends")

  Rel(authR, discord, "Token + user fetch")
  Rel(authR, authS, "Calls")
  Rel(charR, charS, "Calls")
  Rel(charR, turnS, "Calls")
  Rel(charR, embS, "Schedules after turn")
  Rel(campR, campS, "Calls")

  Rel(charS, dm, "create_character")
  Rel(campS, dm, "create_campaign")
  Rel(turnS, dm, "process_turn_stream")
  Rel(embS, dm, "extract_memories")
  Rel(dm, prompts, "Uses")
  Rel(dm, tools, "Executes tool calls")
  Rel(dm, anthropic, "Messages API")
  Rel(embS, voyage, "embed")

  Rel(tools, db, "Query checkpoints by tag")
  Rel(turnS, db, "Load context, save messages")
  Rel(embS, db, "Upsert memory rows")
  Rel(authS, db, "Users")
  Rel(charS, db, "Characters")
  Rel(campS, db, "Campaigns, checkpoints")
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

  Web->>R: POST /characters/{id}/turns/stream {message}
  R->>R: get_current_user + ownership check
  R->>T: load_turn_context()
  T->>DB: character, campaign, active checkpoint, last 10 messages
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

Rolls are never stored. Memories are written after every turn, but nothing reads them back into the turn prompt yet.

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
