# Dungeon - AI Dungeon Master

A CLI-based D&D game featuring an AI dungeon master powered by Claude, with RAG-based retrieval from the official SRD (System Reference Document) for accurate rulings.

## Project Description

Players create a character, start a campaign, and engage in a text-based D&D adventure with an AI dungeon master. The DM maintains a consistent persona, manages game state, and references official D&D rules through semantic search over the embedded SRD.

### Core Features (v1)

- **Character Creation**: Describe your character in natural language
- **AI Dungeon Master**: Persistent DM persona powered by Claude
- **Rules-Accurate**: RAG retrieval from SRD for spells, monsters, and mechanics
- **Campaign Persistence**: Save and resume campaigns
- **CLI Interface**: Text-based interaction

## Learning Objectives

This project is designed to build applied AI engineering skills through hands-on implementation.

### Primary Skills

| Skill                         | How This Project Teaches It                            |
| ----------------------------- | ------------------------------------------------------ |
| **Python**                    | Full backend implementation                            |
| **FastAPI**                   | REST API development, async patterns                   |
| **LLM Integration**           | Claude API, prompt engineering, persona consistency    |
| **RAG Pipeline**              | Chunking, embeddings, vector search, context injection |
| **Vector Databases**          | pgvector setup, similarity search, embedding storage   |
| **Prompt Engineering**        | System prompts, context management, output parsing     |
| **Context Window Management** | Summarization strategies for long campaigns            |
| **State Management**          | Session persistence, conversation history              |

### Secondary Skills

| Skill          | How This Project Teaches It                |
| -------------- | ------------------------------------------ |
| **PostgreSQL** | Schema design, queries, pgvector extension |
| **Docker**     | Containerizing the application             |
| **Kubernetes** | Production deployment                      |
| **Terraform**  | Infrastructure as code                     |
| **API Design** | RESTful patterns, error handling           |

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL + pgvector
- **ORM**: SQLModel
- **LLM**: Anthropic Claude API
- **Embeddings**: OpenAI text-embedding-3-small
- **CLI**: Typer

See [architecture.md](./docs/architecture.md) for detailed technical design.

## Project Structure

```
dungeon/
└── dungeon-service/          # Python backend service
    ├── src/
    │   ├── api/              # FastAPI routers
    │   ├── services/         # Business logic
    │   │   ├── dm_agent.py   # DM orchestration
    │   │   ├── retrieval.py  # RAG pipeline
    │   │   └── llm.py        # LLM client
    │   ├── models/           # SQLModel schemas
    │   ├── db/               # Database setup
    │   └── cli/              # CLI commands
    ├── scripts/
    │   └── ingest_srd.py     # SRD embedding script
    ├── data/
    │   └── srd/              # SRD markdown files
    ├── tests/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── pyproject.toml
    └── README.md
├── terraform/                # Infrastructure as code (added week 7)
└── k8s/                      # Kubernetes manifests (added week 7)
```

---

## DevOps Milestones

Guidelines for when to introduce infrastructure and CI/CD tooling.

### Docker

| When              | What                                                   | Why                                                                                                                                   |
| ----------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| **End of Week 1** | Create `Dockerfile` and `docker-compose.yml`           | Containerize early so you're always developing against the same environment as production. Includes PostgreSQL + pgvector in compose. |
| **Week 3**        | Update compose with volume mounts for SRD data         | Persist embedded data across container restarts                                                                                       |
| **Week 7**        | Optimize Dockerfile (multi-stage build, smaller image) | Prepare for production deployment                                                                                                     |

### GitHub Actions

| When              | What                                                         | Why                                                                |
| ----------------- | ------------------------------------------------------------ | ------------------------------------------------------------------ |
| **End of Week 1** | Basic CI pipeline: lint (Ruff), type check (mypy), run tests | Catch issues early. Even with no tests yet, the pipeline is ready. |
| **Week 3**        | Add test job that spins up Postgres with pgvector            | Integration tests need the database                                |
| **Week 6**        | Add Docker build step, push to container registry            | Prepare for deployment                                             |
| **Week 7**        | Add deployment workflow (to EKS)                             | Automated production deploys                                       |

### Infrastructure as Code

| When       | What                                                                  | Why                           |
| ---------- | --------------------------------------------------------------------- | ----------------------------- |
| **Week 7** | Terraform for AWS resources (EKS cluster, RDS PostgreSQL, networking) | Production infrastructure     |
| **Week 7** | Kubernetes manifests (Deployment, Service, ConfigMap, Secrets)        | Application deployment config |

---

## Development Roadmap

### Week 1: Foundation

**Goal**: Working development environment with a basic API that can call an LLM.

#### Technical Requirements

- [x] Initialize Python project with `uv` or `Poetry`
- [x] Set up project structure (`src/`, `tests/`, etc.)
- [x] Install dependencies: `fastapi`, `uvicorn`, `anthropic`, `sqlmodel`, `typer`
- [x] Create FastAPI app with health check endpoint (`GET /health`)
- [x] Create LLM service that calls Claude API
- [x] Create single endpoint `POST /chat` that accepts a message and returns LLM response
- [x] Set up environment variables for API keys (`.env` file, `python-dotenv`)
- [x] Create `Dockerfile` and `docker-compose.yml` with PostgreSQL + pgvector
- [ ] Set up GitHub Actions: lint with Ruff, type check with mypy

#### Functional Requirements

- [ ] **FR-1.1**: When I send a POST request to `/chat` with `{"message": "Hello"}`, then I receive a JSON response with the LLM's reply
- [ ] **FR-1.2**: When I run `docker-compose up`, then the API starts and is accessible on `localhost:8000`
- [ ] **FR-1.3**: When I run `docker-compose up`, then PostgreSQL is running and accessible on `localhost:5432`

#### Definition of Done

- API runs locally and in Docker
- Can send a message and get a response from Claude
- CI pipeline runs on push (even if no tests yet)

---

### Week 2: Core DM Loop

**Goal**: The AI behaves like a dungeon master with a consistent persona and remembers conversation history.

#### Technical Requirements

- [ ] Create DM system prompt with persona, tone, and behavioral guidelines
- [ ] Create `Campaign` and `Message` SQLModel models
- [ ] Create database tables and migration setup
- [ ] Implement conversation history storage (save each message exchange)
- [ ] Implement conversation history retrieval (load last N messages for context)
- [ ] Create `POST /campaigns` endpoint to start a new campaign
- [ ] Create `POST /campaigns/{id}/messages` endpoint for gameplay
- [ ] Create `GET /campaigns/{id}` endpoint to view campaign state
- [ ] Inject conversation history into LLM prompt

#### Functional Requirements

- [ ] **FR-2.1**: When I create a new campaign, then I receive a campaign ID and the DM introduces the adventure with a narrative opening
- [ ] **FR-2.2**: When I send "I look around the room", then the DM describes the environment in an immersive, narrative style
- [ ] **FR-2.3**: When I have a 10-message conversation and then ask "what did I do first?", then the DM correctly recalls earlier events
- [ ] **FR-2.4**: When I interact with the DM across multiple requests, then the DM maintains a consistent personality and tone
- [ ] **FR-2.5**: When I make a request without a campaign ID, then I receive a clear error message

#### Definition of Done

- Can have a multi-turn conversation with the DM
- DM remembers what happened earlier in the session
- Conversation is persisted to PostgreSQL
- DM has a distinct, consistent persona

---

### Week 3: RAG Setup

**Goal**: SRD content is chunked, embedded, and stored in the vector database.

#### Technical Requirements

- [ ] Download D&D 5e SRD (Creative Commons version)
- [ ] Parse SRD into logical sections (spells, monsters, rules, classes, etc.)
- [ ] Implement chunking strategy (by section, ~500-1000 tokens per chunk)
- [ ] Add metadata to chunks (source type: spell/monster/rule, name, etc.)
- [ ] Create `srd_embeddings` table with pgvector column
- [ ] Create embedding service that calls OpenAI embeddings API
- [ ] Create ingestion script (`scripts/ingest_srd.py`) that processes all SRD content
- [ ] Run ingestion and verify embeddings are stored
- [ ] Update `docker-compose.yml` with volume for persisted embeddings

#### Functional Requirements

- [ ] **FR-3.1**: When I run the ingestion script, then all SRD content is chunked and embedded without errors
- [ ] **FR-3.2**: When I query the `srd_embeddings` table, then I see chunks with source metadata (e.g., "spell:fireball", "monster:goblin")
- [ ] **FR-3.3**: When I inspect a chunk, then it contains coherent, complete information (not cut off mid-sentence)

#### Definition of Done

- SRD content is parsed and chunked logically
- All chunks are embedded and stored in pgvector
- Can query the database and see embedded content with metadata

---

### Week 4: RAG Integration

**Goal**: Can query the vector database and retrieve relevant SRD content.

#### Technical Requirements

- [ ] Create retrieval service with `search(query: str, top_k: int)` method
- [ ] Implement query embedding (embed the search query)
- [ ] Implement vector similarity search using pgvector (`<->` operator)
- [ ] Implement basic relevance filtering (similarity threshold)
- [ ] Create test endpoint `POST /search` to verify retrieval works
- [ ] Add retrieval metrics/logging (what was retrieved, similarity scores)

#### Functional Requirements

- [ ] **FR-4.1**: When I search for "fireball spell damage", then the fireball spell description is in the top 3 results
- [ ] **FR-4.2**: When I search for "goblin stats", then goblin creature information is returned
- [ ] **FR-4.3**: When I search for "how does grappling work", then the grappling rules are returned
- [ ] **FR-4.4**: When I search for something not in the SRD (e.g., "recipe for pizza"), then I receive low-relevance or no results
- [ ] **FR-4.5**: When I perform a search, then I can see in logs what chunks were retrieved and their similarity scores

#### Definition of Done

- Retrieval service returns relevant SRD content for game-related queries
- Similarity search is working with reasonable accuracy
- Can verify retrieval quality through test endpoint

---

### Week 5: Wire It Together

**Goal**: The DM uses retrieved SRD content to give accurate, rules-based responses.

#### Technical Requirements

- [ ] Integrate retrieval service into DM agent
- [ ] Implement query extraction (determine what to search for based on player input)
- [ ] Inject retrieved context into DM prompt (between system prompt and conversation)
- [ ] Implement context formatting (clear delineation of retrieved rules)
- [ ] Add retrieval trigger logic (not every message needs RAG)
- [ ] Create prompt template that instructs DM how to use retrieved context
- [ ] Test and tune retrieval relevance and prompt integration

#### Functional Requirements

- [ ] **FR-5.1**: When I say "I cast fireball at the goblins", then the DM references the actual fireball damage (8d6) and area of effect (20-foot radius)
- [ ] **FR-5.2**: When I say "I want to grapple the orc", then the DM correctly describes the grappling rules (contested Athletics/Acrobatics check)
- [ ] **FR-5.3**: When I ask "what spells can a level 3 wizard prepare?", then the DM gives accurate information based on SRD
- [ ] **FR-5.4**: When I say "I walk down the hallway", then the DM responds narratively without unnecessary rules retrieval
- [ ] **FR-5.5**: When the DM uses retrieved rules, then the response feels natural and integrated (not robotic rule-quoting)
- [ ] **FR-5.6**: When retrieved context contradicts common misconceptions, then the DM uses the correct SRD rules

#### Definition of Done

- DM responses are accurate to SRD rules when relevant
- RAG is triggered appropriately (not on every message)
- Retrieved context is used naturally in responses
- Can play through combat encounter with accurate mechanics

---

### Week 6: Persistence & Character Creation

**Goal**: Full character creation flow, campaign persistence, and complete CLI.

#### Technical Requirements

- [ ] Create `Character` SQLModel with fields: name, description, class, level, stats (JSON), backstory
- [ ] Create `POST /campaigns/{id}/characters` endpoint
- [ ] Create `GET /campaigns/{id}/characters` endpoint
- [ ] Implement character context injection (DM knows character details)
- [ ] Implement campaign listing `GET /campaigns`
- [ ] Implement campaign resume (load existing campaign with full history)
- [ ] Create CLI commands with Typer:
  - [ ] `dungeon new` - start new campaign
  - [ ] `dungeon play <campaign_id>` - resume campaign
  - [ ] `dungeon list` - list all campaigns
  - [ ] `dungeon character create <campaign_id>` - create character
- [ ] Implement graceful session ending (save state on exit)

#### Functional Requirements

- [ ] **FR-6.1**: When I create a character with "Thorin, a grumpy dwarf fighter with 18 strength", then the DM acknowledges the character and incorporates their personality
- [ ] **FR-6.2**: When I say "I try to lift the boulder" as a character with 18 STR, then the DM factors in my high strength when determining outcome
- [ ] **FR-6.3**: When I cast a spell as a level 3 wizard, then the DM respects my spell slot limitations per SRD
- [ ] **FR-6.4**: When I quit the CLI and later run `dungeon play <id>`, then I resume exactly where I left off with full history
- [ ] **FR-6.5**: When I run `dungeon list`, then I see all my campaigns with their names and last played date
- [ ] **FR-6.6**: When I create multiple characters in a campaign, then the DM tracks each one separately
- [ ] **FR-6.7**: When I type `/quit` during gameplay, then the session is saved and I exit gracefully

#### Definition of Done

- Can create a character and have it affect gameplay
- Can save, quit, and resume a campaign
- CLI provides complete interface for all functionality
- Character stats influence DM responses

---

### Week 7-8: Polish & Deploy

**Goal**: Production-ready deployment on AWS EKS.

#### Technical Requirements

- [ ] Optimize Dockerfile (multi-stage build, non-root user, minimal image)
- [ ] Add production configuration (logging, error handling, health checks)
- [ ] Implement context window management (summarize old messages when context is full)
- [ ] Create Terraform configuration:
  - [ ] VPC and networking
  - [ ] EKS cluster
  - [ ] RDS PostgreSQL with pgvector
  - [ ] Secrets management (AWS Secrets Manager)
- [ ] Create Kubernetes manifests:
  - [ ] Deployment with resource limits
  - [ ] Service (ClusterIP or LoadBalancer)
  - [ ] ConfigMap for non-sensitive config
  - [ ] Secret references for API keys
  - [ ] Horizontal Pod Autoscaler (optional)
- [ ] Set up GitHub Actions deployment workflow
- [ ] Configure production database migration strategy
- [ ] Add monitoring/observability (structured logging, basic metrics)

#### Functional Requirements

- [ ] **FR-7.1**: When the application is deployed to EKS, then it is accessible via a public endpoint
- [ ] **FR-7.2**: When the container crashes, then Kubernetes restarts it automatically
- [ ] **FR-7.3**: When I have a 100+ message campaign, then context is summarized and the DM still remembers key events
- [ ] **FR-7.4**: When API keys are accessed, then they come from AWS Secrets Manager (not environment variables)
- [ ] **FR-7.5**: When I push to `main` branch, then the application is automatically deployed to EKS
- [ ] **FR-7.6**: When the database is unreachable, then the health check fails and the pod is marked unhealthy

#### Definition of Done

- Application running on AWS EKS
- Infrastructure defined in Terraform
- CI/CD pipeline deploys on merge to main
- Long campaigns work without context window errors
- Production-grade logging and error handling

---

## Getting Started

_Setup instructions to be added during Week 1 implementation._

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Anthropic API key
- OpenAI API key (for embeddings)

### Local Development

```bash
# Clone the repository
cd dungeon/dungeon-service

# Install dependencies
uv sync  # or: poetry install

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Start PostgreSQL
docker-compose up -d db

# Run database migrations
# (to be implemented)

# Start the API
uv run uvicorn src.main:app --reload

# Or run everything in Docker
docker-compose up
```

## Resources

- [D&D 5e SRD](https://dnd.wizards.com/resources/systems-reference-document) - Official rules under Creative Commons
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/)
- [Typer](https://typer.tiangolo.com/)

## License

MIT
