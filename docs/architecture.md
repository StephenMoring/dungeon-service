# Architecture

## System Overview

A CLI-based D&D dungeon master powered by an LLM with RAG-based rulebook retrieval.
Players describe their character, engage in a chat-based campaign with an AI dungeon master,
and the DM references the official SRD (System Reference Document) for accurate rulings.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                          CLI Client                              │
│                    (Python - Click/Typer)                        │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                          │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │   Campaign     │  │   Character    │  │     Session       │   │
│  │   Router       │  │   Router       │  │     Router        │   │
│  └───────┬────────┘  └───────┬────────┘  └─────────┬─────────┘   │
│          │                   │                     │             │
│          └───────────────────┼─────────────────────┘             │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                     DM Agent Service                      │   │
│  │                                                           │   │
│  │   - Manages conversation state                            │   │
│  │   - Constructs prompts with persona + context             │   │
│  │   - Orchestrates retrieval and LLM calls                  │   │
│  └───────────────────────┬───────────────────────────────────┘   │
│                          │                                       │
│            ┌─────────────┴─────────────┐                         │
│            ▼                           ▼                         │
│  ┌──────────────────┐       ┌────────────────────┐               │
│  │ Retrieval Service│       │    LLM Service     │               │
│  │                  │       │                    │               │
│  │ - Query embedding│       │ - Claude/OpenAI    │               │
│  │ - Vector search  │       │ - Prompt assembly  │               │
│  │ - Context ranking│       │ - Response parsing │               │
│  └────────┬─────────┘       └─────────┬──────────┘               │
│           │                           │                          │
│           │                           ▼                          │
│           │                 ┌────────────────────┐               │
│           │                 │  External LLM API  │               │
│           │                 │ (Anthropic/OpenAI) │               │
│           │                 └────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐       ┌────────────────────┐               │
│  │ Embedding Service│──────▶│ OpenAI Embeddings  │               │
│  └────────┬─────────┘       └────────────────────┘               │
│           │                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────┐
│                   PostgreSQL + pgvector                          │
│                                                                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌────────────────────┐  │
│  │    campaigns    │ │   characters    │ │  message_history   │  │
│  │                 │ │                 │ │                    │  │
│  │ - id            │ │ - id            │ │ - id               │  │
│  │ - name          │ │ - campaign_id   │ │ - campaign_id      │  │
│  │ - created_at    │ │ - name          │ │ - role             │  │
│  │ - summary       │ │ - description   │ │ - content          │  │
│  └─────────────────┘ │ - stats (JSON)  │ │ - timestamp        │  │
│                      └─────────────────┘ └────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                    srd_embeddings                         │   │
│  │                                                           │   │
│  │ - id                                                      │   │
│  │ - chunk_text                                              │   │
│  │ - embedding (vector)                                      │   │
│  │ - source (spells/monsters/rules/etc)                      │   │
│  │ - metadata (JSON)                                         │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Core Application

| Layer          | Technology     | Purpose                             |
| -------------- | -------------- | ----------------------------------- |
| Language       | Python 3.11+   | Primary development language        |
| Web Framework  | FastAPI        | Async API framework                 |
| Database       | PostgreSQL 15+ | Application data and vector storage |
| Vector Storage | pgvector       | Vector similarity search extension  |
| ORM            | SQLModel       | Database models and queries         |
| CLI Framework  | Typer or Click | Command-line interface              |

### AI/ML Components

| Component       | Technology                    | Purpose                       |
| --------------- | ----------------------------- | ----------------------------- |
| LLM             | Anthropic Claude API          | Dungeon master responses      |
| Embeddings      | OpenAI text-embedding-3-small | Document and query embeddings |
| Text Processing | Manual or LangChain splitters | SRD chunking                  |

### Infrastructure

| Component        | Technology     | Purpose                          |
| ---------------- | -------------- | -------------------------------- |
| Containerization | Docker         | Application packaging            |
| Orchestration    | Kubernetes     | Production deployment            |
| IaC              | Terraform      | Infrastructure provisioning      |
| Cloud            | AWS EKS        | Managed Kubernetes               |
| CI/CD            | GitHub Actions | Automated testing and deployment |

### Development Tools

| Tool         | Purpose                |
| ------------ | ---------------------- |
| uv or Poetry | Dependency management  |
| pytest       | Testing                |
| Ruff         | Linting and formatting |
| pre-commit   | Git hooks              |

## Data Flow

### 1. Player Message Flow

```
Player Input
    │
    ▼
FastAPI Endpoint (/campaigns/{id}/message)
    │
    ▼
DM Agent Service
    │
    ├──▶ Retrieve relevant SRD context
    │         │
    │         ▼
    │    Query Embedding (OpenAI)
    │         │
    │         ▼
    │    Vector Search (pgvector)
    │         │
    │         ▼
    │    Ranked Context Chunks
    │
    ├──▶ Build Prompt
    │    - System prompt (DM persona)
    │    - Retrieved SRD context
    │    - Conversation history
    │    - Character info
    │    - Player message
    │
    └──▶ LLM Call (Claude)
              │
              ▼
         DM Response
              │
              ▼
         Save to message_history
              │
              ▼
         Return to Player
```

### 2. SRD Ingestion Flow (One-time Setup)

```
SRD Markdown Files
    │
    ▼
Chunking (by section/logical units)
    │
    ▼
Embedding (OpenAI API)
    │
    ▼
Store in srd_embeddings table
```

## Key Design Decisions

### Why pgvector over a dedicated vector DB?

- Single database to manage
- Simpler infrastructure
- Good enough performance for this scale (thousands of SRD chunks, not millions)
- Transactional consistency with application data

### Why separate Retrieval and LLM services?

- Testable in isolation
- Can swap LLM providers without touching retrieval logic
- Clear separation of concerns

### Why CLI first?

- Faster iteration on core AI logic
- No frontend complexity
- React frontend added later as a separate concern

## Future Extensions (Not in v1)

- Multiplayer support (WebSocket sessions)
- Multiple DM personas/styles
- Campaign branching and world state
- Image generation for scenes
- Voice input/output
