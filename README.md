# The Lenny Growth Assistant (God-Tier Edition)

A full-stack, AI-powered conversational web application that ingests transcripts from Lenny's Podcast to answer product and growth questions, complete with a dual-pane Artifact Viewer for "Ship 30 for 30" style essays.

## God-Tier Upgrades
This repository includes massive upgrades to both the UI/UX and backend systems:
- **Premium Glassmorphic UI:** A custom-built, modern frontend featuring frosted-glass elements, dynamic radial gradients, interactive starter prompts, and micro-animations.
- **RAG Reciprocal Rank Fusion (RRF):** Utilizes an advanced hybrid ensemble retriever (ChromaDB Vector Search + BM25 Keyword Search) to maximize contextual accuracy.
- **Real-Time Auto-Ingestion:** A background `watchdog` daemon runs inside the FastAPI process, instantly detecting and embedding any new podcast transcripts added to the directory.
- **LLM Caching:** Langchain SQLAlchemy caching eliminates redundant processing and dramatically speeds up repeated queries.
- **Smart Follow-Ups:** The LLM natively generates dynamic, contextual follow-up questions at the end of its response, rendered as interactive pills in the UI.
- **Telemetry & Feedback:** Persistent upvote/downvote buttons let users evaluate responses. Feedback is stored directly in the PostgreSQL `messages` table.
- **Smart Tool Binding:** Intelligent prompt engineering and conditional tool binding prevent aggressive local 8B models (like Llama 3.1) from hallucinating tools when not explicitly requested.

## Architecture & Design
Please see [architecture.md](./architecture.md), [design.md](./design.md), and [PRD.md](./PRD.md) for full documentation on system design, UI/UX decisions, and scoping constraints.

## Prerequisites
- Docker and Docker Compose
- Ollama (installed locally for testing local models)

## Setup & Running locally

1. **Clone the repository.**
2. **Start Ollama** locally and pull the required models:
   ```bash
   ollama pull llama3.1
   ollama pull nomic-embed-text
   ```
3. **Configure Environment:**
   Copy `backend/.env.example` to `backend/.env` and update `ANTHROPIC_API_KEY` if desired.
4. **One-Command Startup:**
   From the root directory, run:
   ```bash
   docker-compose up --build
   ```
   *(Note: The auto-ingestion daemon will automatically pick up and embed the transcripts!)*
5. **Access the App:**
   Open your browser to `http://localhost:5173`.

## Automated Tests
To run backend tests, execute:
```bash
docker-compose exec backend pip install pytest httpx
docker-compose exec backend pytest test_main.py
```

## Troubleshooting & Extending the System
For client engineers taking over this project, here is a quick diagnostic guide:
- **Empty Artifacts / Tool Hallucinations:** The prompt uses conditional binding. If a local model generates empty artifacts, ensure `OLLAMA_BASE_URL` is correct. The system logs model timeouts via `uvicorn` structured logging (check `docker-compose logs backend`).
- **Database Connection Failures:** If `GET /health` returns `disconnected`, ensure the Postgres container is running. FastAPI natively handles unexpected DB disconnects gracefully and logs them via `main.py`.
- **Empty Retrieval Results:** If answers aren't grounded, ChromaDB may not be fully initialized. Check the `backend` logs for `Retrieval returned empty results` warnings. You can manually force an ingestion run via `docker-compose exec backend python ingest.py`.
- **Extending the Application:** 
  - To add more models: Update the `get_llm()` factory in `agent.py`.
  - To add new tools: Define a new `@tool` in `agent.py` and update the conditional binding logic.
  - To add new transcript sources: Just drop `.md` files into `backend/lennys-podcast-transcripts/episodes`. The `watchdog` daemon will automatically detect and embed them without requiring a server restart!
