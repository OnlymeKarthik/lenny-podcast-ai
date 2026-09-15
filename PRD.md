# Product Requirements Document (PRD): The Lenny Growth Assistant

## 1. Discovery Brief

### 1.1 User and Problem
**Primary User:** Product Managers, Growth Marketers, and Content Creators on the Product & Growth team.
**Job to be Done (JTBD):** Users need to quickly find actionable insights, growth tactics, and product management frameworks from Lenny's Podcast transcripts, and convert these insights into reusable, structured written content.
**Pain Point:** Reading through hundreds of hours of raw podcast transcripts is time-consuming. Users currently lack a reliable, easy-to-use tool to query this specific knowledge base and generate formatted, shareable artifacts (like essays or UI snippets) without needing to be prompt engineers or understand LLM infrastructure.

### 1.2 Success Metrics
- **Task Completion Rate:** The percentage of sessions where a user successfully generates and views an artifact (e.g., a "Ship 30 for 30" essay).
- **Time to Insight:** Reduction in the time taken to find a specific growth tactic compared to manual searching (qualitative feedback).
- **System Reliability:** 95%+ uptime for the local deployment during the evaluator's test, handling model timeouts and empty retrievals gracefully.

### 1.3 Assumptions
- The primary transcript repository is static for the duration of this demo (no real-time syncing required, a one-time ingestion is sufficient).
- Users will run the application locally using Docker and Ollama for evaluation purposes, meaning resource constraints (RAM/CPU) for the local LLM must be considered.
- The "Artifact Viewer" only needs to support Markdown and self-contained HTML/CSS. No complex JavaScript execution is required or permitted for security reasons.

### 1.4 Scope Choices
**Included:**
- RAG pipeline utilizing a local vector store (ChromaDB) with hybrid retrieval (dense + BM25 sparse via Reciprocal Rank Fusion).
- Dual LLM support (Anthropic Claude as cloud provider, Ollama as local provider) with a visible UI toggle.
- A structured "Ship 30 for 30" writing skill encoding the 1-3-1 atomic essay framework (not a generic prompt).
- An HTML artifact generation tool for visual content like infographics and landing pages.
- Secure HTML rendering in the frontend using a fully sandboxed iframe (`sandbox=""` — no scripts, no same-origin).
- Source citations in every grounded answer, naturally referencing the relevant podcast episode.

**Excluded (and Why):**
- **Authentication/Authorization:** Excluded to simplify the evaluator's setup experience. The focus is on the AI application layer, not user management.
- **Real-time Web Search:** The knowledge base is strictly limited to the provided transcripts to ensure high-fidelity grounding and prevent hallucination.
- **Complex Agentic Loops (e.g., executing arbitrary code):** The agent's tools are restricted to RAG retrieval and structured content generation to reduce the risk of infinite loops and latency.

### 1.5 Risks and Trade-offs
- **Risk: Local LLM Latency and Quality.** Local models (Llama 3.1 8B via Ollama) may be slow or struggle with complex system prompts compared to Claude Sonnet.
  - *Trade-off:* Prompts are optimized for clarity. The UI shows a typing indicator during generation. Users can toggle to Anthropic Claude for higher quality.
- **Risk: Hallucination.** The LLM might invent product advice not found in the transcripts.
  - *Trade-off:* Strict system prompts require the model to cite sources naturally and explicitly state when the transcript material doesn't support an answer. Conditional tool binding prevents false tool invocations on regular questions.
- **Risk: Unsafe Artifact Rendering (XSS).** Generating HTML opens vectors for Cross-Site Scripting.
  - *Trade-off:* The Artifact Viewer uses `<iframe sandbox="">` (the strictest sandbox — no scripts, no forms, no same-origin access). Markdown is rendered via `react-markdown` which never uses `dangerouslySetInnerHTML`.
- **Risk: Data Leakage.** API keys could be exposed in committed code.
  - *Trade-off:* All secrets are loaded from environment variables. `.env` files are `.gitignore`d. The `.env.example` contains only placeholder values.
- **Risk: Provider Unavailability.** Ollama may be down or Anthropic API key may be missing.
  - *Trade-off:* The `get_llm()` factory validates key presence before connection and returns actionable error messages. Errors are streamed to the chat gracefully rather than crashing the server.

## 2. Core Flows
1. **Chat Initiation:** User opens the web app, which creates a new session in PostgreSQL.
2. **Knowledge Retrieval:** User asks a growth question. The backend chunks the query, retrieves relevant transcript sections from the vector store, and passes them to the agent.
3. **Artifact Generation:** User requests a "Ship 30 for 30" essay. The agent invokes the specific formatting skill and returns the essay wrapped in an artifact block.
4. **Artifact Rendering:** The frontend detects the artifact block and renders the Markdown/HTML in the side panel.

## 3. Acceptance Criteria
- **AC1 (RAG Retrieval):** The system must successfully query ChromaDB and inject relevant podcast transcripts into the LLM context.
- **AC2 (Source Grounding):** Every answer must naturally cite or identify the relevant Lenny's Podcast transcript/episode used.
- **AC3 (Tool Calling):** The system must successfully execute the `generate_ship_30_essay` tool when explicitly requested, rendering the output as an artifact.
- **AC4 (HTML Artifacts):** The system must generate complete HTML/CSS documents when requested, rendered securely in the Artifact Viewer.
- **AC5 (Hallucination Prevention):** The system must NOT attempt to execute tools on standard queries (enforced via conditional tool binding).
- **AC6 (UI/UX):** The frontend must elegantly handle loading states (typing indicator) and stream the LLM response without double-rendering message bubbles.
- **AC7 (Graceful Failure):** Missing API keys, unavailable Ollama, and empty retrieval results must produce helpful error messages, not crashes.

## 4. Implementation Plan (Executed)
- **Phase 1 (Foundation):** Set up Docker Compose, FastAPI, and Postgres schema (`sessions`, `messages`).
- **Phase 2 (Knowledge Base):** Implement Langchain Document Loaders and Recursive splitters to ingest the transcripts into ChromaDB.
- **Phase 3 (Agentic Core):** Build the FastAPI endpoints (`/sessions`, `/chat`) and the Langchain agent to route queries to Ollama (Llama 3.1).
- **Phase 4 (UI & Artifacts):** Develop the React frontend with a split-pane layout to render streaming text and isolated Artifacts.
- **Phase 5 (God-Tier Polish):** Implement Reciprocal Rank Fusion (RRF), Live Ingestion Daemons, Telemetry (upvotes/downvotes), dynamic suggestions, and a premium glassmorphic UI.
