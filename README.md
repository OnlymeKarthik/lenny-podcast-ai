# The Lenny Growth Assistant

A full-stack, AI-powered conversational web application that ingests transcripts from Lenny's Podcast to answer product and growth questions, complete with a dual-pane Artifact Viewer for "Ship 30 for 30" style essays.

## Architecture & Design
Please see [architecture.md](./architecture.md), [design.md](./design.md), and [PRD.md](./PRD.md) for full documentation on system design, UI/UX decisions, and scoping constraints.

## Prerequisites
- Docker and Docker Compose
- Ollama (installed locally for testing local models)
- An Anthropic API Key (optional, if testing cloud provider)

## Setup & Running locally

1. **Clone the repository.**
2. **Start Ollama** locally and pull a model (e.g., `llama3` and `nomic-embed-text`):
   ```bash
   ollama pull llama3
   ollama pull nomic-embed-text
   ```
3. **Configure Environment:**
   Copy `backend/.env.example` to `backend/.env` and update `ANTHROPIC_API_KEY` if desired.
4. **One-Command Startup:**
   From the root directory, run:
   ```bash
   docker-compose up --build
   ```
5. **Data Ingestion (First run only):**
   In a new terminal, run the ingestion script to embed the dummy transcripts:
   ```bash
   docker-compose exec backend python ingest.py
   ```

6. **Access the App:**
   Open your browser to `http://localhost:5173`.

## Manual Test Plan (UI)
1. **Empty State:** Verify the app loads a blank chat.
2. **Create Session:** Type a message and hit enter. Verify a session is created in the sidebar.
3. **Artifact Generation:** Ask the assistant to "Write a Ship 30 for 30 essay on activation". Wait for the `<artifact>` block to trigger the right-side pane.
4. **LLM Toggle:** Switch the provider at the top from Ollama to Claude and send another message.

## Automated Tests
To run backend tests, execute:
```bash
docker-compose exec backend pip install pytest httpx
docker-compose exec backend pytest test_main.py
```
# lenny-podcast-ai
# lenny-podcast-ai
