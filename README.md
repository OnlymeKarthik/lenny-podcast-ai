# The Lenny Growth Assistant

A full-stack, AI-powered conversational web application that ingests transcripts from Lenny's Podcast to answer product and growth questions, generate Ship 30 for 30 essays, and render Markdown/HTML artifacts — all grounded in real podcast content.

## Key Features

- **Hybrid RAG (RRF):** Combines dense vector search (ChromaDB) with sparse keyword search (BM25) via Reciprocal Rank Fusion for high-recall retrieval
- **Dual LLM Support:** Toggle between Local (Ollama) and Cloud (Anthropic Claude) with a single click in the UI
- **Ship 30 for 30 Skill:** Dedicated tool encoding the 1-3-1 atomic essay framework (not a generic prompt)
- **Artifact Viewer:** Claude-style split pane rendering for Markdown essays and sandboxed HTML artifacts
- **Live Ingestion:** Background watchdog daemon auto-detects and embeds new transcripts without server restart
- **Source Citations:** Answers cite relevant Lenny's Podcast episodes naturally in the response text
- **Session Persistence:** Full chat history stored in PostgreSQL with independent session context
- **Feedback System:** Thumbs up/down on every assistant response, persisted for quality tracking
- **LLM Caching:** Exact-match response cache via SQLAlchemy eliminates redundant API calls

## Documentation

| Document | Description |
|----------|-------------|
| [PRD.md](./PRD.md) | Product requirements, discovery brief, success metrics, assumptions, risks |
| [architecture.md](./architecture.md) | System architecture, API contracts, DB schema, agent routing, deployment topology |
| [design.md](./design.md) | UI/UX principles, information architecture, responsive behavior, accessibility |

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Ollama** installed locally (for local LLM inference)
  - Ollama needs direct GPU/CPU access, so it runs on the host machine, not in Docker

## Setup & Running Locally

### 1. Clone the repository
```bash
git clone <repo-url>
cd lenny-growth-assistant
```

### 2. Start Ollama and pull required models
```bash
ollama pull llama3.1          # Chat model (~4.7GB)
ollama pull nomic-embed-text  # Embedding model (~274MB)
```

### 3. Configure environment variables
```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` if you want to use a cloud provider:

| Variable | Required? | Description |
|----------|-----------|-------------|
| `DATABASE_URL` | Auto-set by Docker | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | Auto-set by Docker | Ollama API endpoint (`host.docker.internal:11434`) |
| `ANTHROPIC_API_KEY` | Optional | Required only if you toggle to Anthropic Claude in the UI |
| `OPENAI_API_KEY` | Optional | Alternative cloud provider (not shown in UI by default) |
| `LOG_LEVEL` | Optional | `DEBUG`, `INFO` (default), `WARNING`, `ERROR` |

### 4. One-command startup
```bash
docker-compose up --build
```

This starts:
- **PostgreSQL** on port 5432 (with health check)
- **FastAPI backend** on port 8000 (waits for healthy DB)
- **React frontend** on port 5173

The watchdog daemon automatically detects and embeds transcripts on startup.

### 5. Access the app
Open **http://localhost:5173** in your browser.

API documentation (Swagger): **http://localhost:8000/docs**

### 6. Cloud model setup (optional)

**Anthropic Claude:**
1. Get an API key from [console.anthropic.com](https://console.anthropic.com/)
2. Set `ANTHROPIC_API_KEY=sk-ant-...` in `backend/.env`
3. Restart the backend: `docker-compose restart backend`
4. Toggle to "Anthropic Claude" in the UI header

## Running Tests

### Automated tests
```bash
# Run inside the Docker container
docker-compose exec backend pytest test_main.py -v

# Or run locally (requires PostgreSQL and dependencies)
cd backend
pip install -r requirements.txt
pytest test_main.py -v
```

### Manual Test Plan

| # | Scenario | Steps | Expected Result |
|---|----------|-------|-----------------|
| 1 | New chat creation | Click "New Chat" in sidebar | New session appears, empty message feed |
| 2 | Basic RAG query | Ask "What is product-market fit?" | Grounded answer citing Lenny's Podcast episodes |
| 3 | Follow-up question | After Q2, ask "Can you elaborate on that?" | Response uses session context from previous answer |
| 4 | Ship 30 essay | Ask "Write a Ship 30 for 30 essay on growth teams" | Essay appears in Artifact Viewer pane (right side) |
| 5 | Provider toggle | Switch to Anthropic Claude, send a message | Response uses Claude (visible in header toggle state) |
| 6 | No-answer handling | Ask "What did Elon Musk say about Mars?" | System acknowledges insufficient transcript data |
| 7 | Session switching | Create 2 sessions, switch between them | Each session shows its own independent chat history |
| 8 | Feedback | Click thumbs-up on a response | Button highlights; feedback persisted (check `/health`) |
| 9 | Health check | Visit `http://localhost:8000/health` | Returns `{ status: "ok", database: "connected", ... }` |
| 10 | Live ingestion | Add a new `.md` file to `backend/lennys-podcast-transcripts/episodes/` | Backend logs show "Watcher: Detected new/modified transcript" |

## Troubleshooting

### Common Issues

**"Cannot connect to backend" in the UI**
- Verify the backend is running: `docker-compose logs backend`
- Check if port 8000 is accessible: `curl http://localhost:8000/health`

**Empty or irrelevant answers**
- ChromaDB may not be initialized. Check logs: `docker-compose logs backend | grep "Retrieval"`
- Force a manual re-ingestion: `docker-compose exec backend python ingest.py`

**Ollama connection failures**
- Ensure Ollama is running: `ollama list`
- On Windows/Mac, Docker uses `host.docker.internal` to reach host services. If this doesn't resolve, set `OLLAMA_BASE_URL` to your machine's local IP.

**Anthropic Claude errors**
- Verify your key: `docker-compose exec backend python -c "import os; print(os.getenv('ANTHROPIC_API_KEY', 'NOT SET')[:10])"`
- Check for rate limits in logs: `docker-compose logs backend | grep "anthropic"`

**Database connection failures**
- Check Postgres health: `docker-compose ps db`
- Reset the database: `docker-compose down -v && docker-compose up --build`

### Extending the Application

| Task | How |
|------|-----|
| Add a new LLM provider | Update `get_llm()` in `backend/agent.py` with a new provider case |
| Add a new agent tool | Define a `@tool` function in `agent.py`, add it to `ALL_TOOLS`, update `_should_bind_tools()` keywords |
| Add new transcripts | Drop `.md` files into `backend/lennys-podcast-transcripts/episodes/` — the watchdog will auto-embed them |
| Change embedding model | Update `OllamaEmbeddings(model=...)` in `agent.py` and `ingest.py`, then re-run ingestion |
| Add authentication | Integrate FastAPI's security dependencies; add a `users` table to PostgreSQL |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, ReactMarkdown, Lucide Icons, Sonner |
| Backend | FastAPI, SQLAlchemy, LangChain, Pydantic v2 |
| Database | PostgreSQL 15 |
| Vector Store | ChromaDB (local) |
| LLM (Local) | Ollama → Llama 3.1 8B |
| LLM (Cloud) | Anthropic Claude Sonnet |
| Embeddings | nomic-embed-text (via Ollama) |
| Deployment | Docker Compose |
