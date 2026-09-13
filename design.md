# UI/UX Design Principles: The Lenny Growth Assistant

## 1. Core Principles

- **Premium & Minimalist Aesthetic:** The UI should feel like a modern, high-end SaaS tool (resembling Claude or Linear). We will utilize a sleek dark mode, sophisticated typography (e.g., Inter or Roboto), and subtle borders/shadows to establish trust and quality.
- **Focus on Content:** The layout must prioritize the conversation and the generated artifacts. Unnecessary navigation or clutter should be removed.
- **Clear System State:** Users must always know what the system is doing. We will implement clear loading indicators (e.g., pulsing dots or skeleton loaders) when the Agent is retrieving knowledge or generating a response.

## 2. Information Architecture

The application is structured as a dual-pane layout (on desktop):

1. **Left Sidebar (Optional/Collapsible):** Displays chat history/sessions for quick switching.
2. **Main Chat Pane (Center):** The primary interaction area containing the message feed and the input field.
3. **Artifact Viewer (Right Pane):** Appears dynamically when the assistant generates a structured artifact (Essay, HTML snippet).

## 3. Key Interaction States

- **Empty State:** When a new session begins, display a welcoming message and 3-4 suggested prompts (e.g., "What are some of the best growth tactics for B2B SaaS?") to help users overcome the "blank canvas" problem.
- **Loading/Retrieval State:** When the agent is querying the vector database, show a specific status (e.g., "Searching Lenny's Transcripts...").
- **Streaming State:** Responses from the LLM should stream in smoothly character-by-character to reduce perceived latency, especially critical when using slower local Ollama models.
- **Artifact Detection:** When the LLM outputs a specific tag (e.g., `<artifact>`), the frontend should gracefully split the view and render the content in the right-hand panel.

## 4. Responsive Behavior

- **Desktop ( > 1024px):** Dual-pane layout (Chat on the left, Artifact on the right).
- **Tablet ( 768px - 1024px):** Dual-pane, but the chat pane narrows.
- **Mobile ( < 768px):** Single-pane layout. The Artifact Viewer acts as an overlay or a tabbed view that the user can switch to, ensuring readability on small screens.

## 5. Accessibility Considerations (a11y)

- **Contrast:** Ensure all text passes WCAG AA contrast ratios against the dark background.
- **Keyboard Navigation:** The input field should auto-focus on load. Users should be able to submit messages with `Enter` (and use `Shift+Enter` for new lines).
- **Screen Readers:** Use semantic HTML tags (`<main>`, `<aside>`, `<nav>`) and ARIA labels for buttons (like the sidebar toggle or send button).

## 6. Design Decisions
- **Why Glassmorphism?** To provide a modern, "God-Tier" aesthetic that differentiates the tool from generic internal tools. The frosted glass (`backdrop-filter`) creates a sense of depth.
- **Why hide source citations in text?** Raw markdown filenames clutter the conversational flow. We enforce a clean UI by strictly instructing the LLM to weave answers naturally without robotic citation paths.
- **Why suggestion pills?** To reduce friction. Users often don't know what to ask next; dynamically generated follow-up questions dramatically improve engagement and task completion rates.
