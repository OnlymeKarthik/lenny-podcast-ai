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
- RAG pipeline utilizing a local vector store (e.g., FAISS or ChromaDB) for simple, dependency-free setup.
- Dual LLM support (Cloud provider like Anthropic, and Local via Ollama).
- A specific "Ship 30 for 30" agentic skill that adheres to strict formatting constraints.
- Secure HTML rendering in the frontend using a sandboxed iframe.

**Excluded (and Why):**
- **Authentication/Authorization:** Excluded to simplify the evaluator's setup experience. The focus is on the AI application layer, not user management.
- **Real-time Web Search:** The knowledge base is strictly limited to the provided transcripts to ensure high-fidelity grounding and prevent hallucination.
- **Complex Agentic Loops (e.g., executing arbitrary code):** The agent's tools are restricted to RAG retrieval and structured content generation to reduce the risk of infinite loops and latency.

### 1.5 Risks and Trade-offs
- **Risk: Local LLM Latency and Quality.** Local models (e.g., via Ollama) may be slow or struggle with complex system prompts compared to Claude 3.5 Sonnet.
  - *Trade-off:* We will optimize prompts to be clear and concise. The system will clearly indicate when it's generating to manage user expectations regarding latency.
- **Risk: Hallucination.** The LLM might invent product advice not found in the transcripts.
  - *Trade-off:* We will implement strict system prompts requiring the model to cite sources and explicitly state if the transcript does not contain the answer.
- **Risk: Unsafe Artifact Rendering (XSS).** Generating HTML opens vectors for Cross-Site Scripting.
  - *Trade-off:* We will use a sandboxed `iframe` with `sandbox="allow-scripts"` disabled by default, ensuring generated HTML can only render styling and structure, not execute malicious JS.

## 2. Core Flows
1. **Chat Initiation:** User opens the web app, which creates a new session in PostgreSQL.
2. **Knowledge Retrieval:** User asks a growth question. The backend chunks the query, retrieves relevant transcript sections from the vector store, and passes them to the agent.
3. **Artifact Generation:** User requests a "Ship 30 for 30" essay. The agent invokes the specific formatting skill and returns the essay wrapped in an artifact block.
4. **Artifact Rendering:** The frontend detects the artifact block and renders the Markdown/HTML in the side panel.
