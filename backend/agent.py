import os
import json
import logging
import time
from typing import AsyncGenerator, Optional
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

DB_DIR = "./chroma_db"
DATA_DIR = "./lennys-podcast-transcripts/episodes"

bm25_retriever_cache = None

# ---------------------------------------------------------------------------
# LLM Factory with fallback
# ---------------------------------------------------------------------------

def get_llm(provider: str):
    """
    Factory to select the LLM provider. Supports:
      - "anthropic": Anthropic Claude (cloud) — requires ANTHROPIC_API_KEY
      - "openai":    OpenAI GPT-4o (cloud) — requires OPENAI_API_KEY
      - "ollama":    Local Ollama (default for demo)
    
    Raises ValueError with actionable message if required keys are missing.
    """
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key.startswith("sk-ant-your"):
            raise ValueError(
                "ANTHROPIC_API_KEY is not configured. "
                "Set it in your .env file or switch to Local (Ollama) in the UI."
            )
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=api_key,
            max_tokens=4096,
            timeout=120,
        )
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("sk-your"):
            raise ValueError(
                "OPENAI_API_KEY is not configured. "
                "Set it in your .env file or switch to Local (Ollama) in the UI."
            )
        return ChatOpenAI(
            model="gpt-4o",
            openai_api_key=api_key,
            request_timeout=120,
        )
    else:  # Default to local Ollama for the demo
        return ChatOllama(
            model="llama3.1",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            timeout=120,
        )

# ---------------------------------------------------------------------------
# Hybrid Retriever: Dense (ChromaDB) + Sparse (BM25) with RRF
# ---------------------------------------------------------------------------

class CustomEnsembleRetriever(BaseRetriever):
    """Reciprocal Rank Fusion ensemble combining dense + sparse retrieval."""
    retrievers: list[BaseRetriever]
    weights: list[float]
    
    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        doc_lists = [r.invoke(query) for r in self.retrievers]
        
        rrf_score: dict[str, dict] = {}
        for doc_list, weight in zip(doc_lists, self.weights):
            for rank, doc in enumerate(doc_list):
                key = doc.page_content
                if key not in rrf_score:
                    rrf_score[key] = {"score": 0, "doc": doc}
                rrf_score[key]["score"] += weight * (1.0 / (rank + 60))
                
        sorted_docs = sorted(rrf_score.values(), key=lambda x: x["score"], reverse=True)
        return [item["doc"] for item in sorted_docs[:5]]


def get_retriever():
    """Initialize and return the hybrid retriever (ChromaDB + BM25)."""
    global bm25_retriever_cache
    
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    if not os.path.exists(DB_DIR):
        logger.warning("ChromaDB directory does not exist. Retriever unavailable.")
        return None
        
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    chroma_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    
    if bm25_retriever_cache is None and os.path.exists(DATA_DIR):
        try:
            loader = DirectoryLoader(DATA_DIR, glob="**/*.md", loader_cls=TextLoader)
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splits = text_splitter.split_documents(docs)
            bm25_retriever_cache = BM25Retriever.from_documents(splits)
            bm25_retriever_cache.k = 5
            logger.info(f"BM25 retriever initialized with {len(splits)} chunks.")
        except Exception as e:
            logger.error(f"Failed to initialize BM25 retriever: {e}")
            
    if bm25_retriever_cache:
        return CustomEnsembleRetriever(
            retrievers=[bm25_retriever_cache, chroma_retriever],
            weights=[0.3, 0.7]
        )
        
    return chroma_retriever


# ---------------------------------------------------------------------------
# Ship 30 for 30 Skill — Encodes the actual writing framework
# ---------------------------------------------------------------------------

SHIP_30_PRINCIPLES = """
## Ship 30 for 30 Writing Framework

You are encoding the Ship 30 for 30 atomic essay format. Follow these principles strictly:

### Structure: The 1-3-1 Framework
1. **One powerful opening** — Start with a HOOK. Choose one of these hook types:
   - A provocative question ("Why do 90% of startups fail at growth?")
   - A bold contrarian statement ("Most PMs are optimizing the wrong metric.")
   - A surprising statistic or data point from the transcript
   - A relatable "I used to think X, but now I know Y" confession

2. **Three main supporting points** — Each point should:
   - Have its own bold subheading
   - Open with a clear claim grounded in the transcript
   - Support the claim with a specific example, quote, or tactic from the source
   - End with a practical implication the reader can act on
   - Be 200-300 words each

3. **One clear takeaway** — End with:
   - A concise "Bottom Line" or "The Takeaway" section
   - A single actionable sentence the reader can implement today
   - Optionally, a forward-looking question to provoke further thinking

### Formatting Rules (Social-Native)
- Use **bold** selectively for key phrases (not entire sentences)
- Use bullet points for lists of 3+ items
- Keep paragraphs to 2-3 sentences max for skimmability
- Use line breaks generously — white space is your friend
- Include one transitional sentence between each main point
- Total length: approximately 1,250 words

### Grounding Rules
- Every claim MUST be traceable to the provided transcript context
- Attribute insights naturally: "As [speaker] explains on Lenny's Podcast..."
- If the transcript doesn't support a claim, don't make it
"""


@tool
def generate_ship_30_essay(topic: str, context: str) -> str:
    """Creates a Ship 30 for 30 style essay. Only use when the user explicitly asks 
    to 'write an essay', 'Ship 30 for 30', or 'create content'. Do NOT use for 
    regular questions."""
    
    essay_prompt = f"""{SHIP_30_PRINCIPLES}

Now write a Ship 30 for 30 atomic essay on the topic: "{topic}"

Ground your claims using the following context from Lenny's Podcast transcripts:

---
{context}
---

Remember: Follow the 1-3-1 framework exactly. Hook → 3 main points → Takeaway.
Cite specific insights from the transcripts naturally within the text.
Target ~1,250 words. Use Markdown formatting.
"""
    essay_llm = ChatOllama(
        model="llama3.1",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        timeout=180,
    )
    essay_content = essay_llm.invoke(essay_prompt).content
    
    return f"<artifact>\n{essay_content}\n</artifact>"


@tool
def generate_html_artifact(title: str, content: str, style: str = "modern") -> str:
    """Generates a complete, self-contained HTML/CSS document based on the conversation.
    Use when the user asks for an 'HTML page', 'web component', 'landing page', 
    'infographic', or 'visual artifact'."""
    
    html_prompt = f"""Create a complete, self-contained HTML document with inline CSS.
Title: {title}
Content to include: {content}
Style: {style}

Requirements:
- Must be a COMPLETE HTML document (<!DOCTYPE html> ... </html>)
- All CSS must be inline in a <style> tag (no external resources)
- Use modern, clean design with good typography
- Do NOT include any <script> tags (they will be blocked for security)
- Use semantic HTML elements
- Make it visually appealing with colors, spacing, and layout
- Content should be well-structured and readable
"""
    html_llm = ChatOllama(
        model="llama3.1",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        timeout=180,
    )
    html_content = html_llm.invoke(html_prompt).content
    
    # Extract just the HTML if the model wraps it in markdown code fences
    if "```html" in html_content:
        html_content = html_content.split("```html")[1].split("```")[0].strip()
    elif "```" in html_content:
        html_content = html_content.split("```")[1].split("```")[0].strip()
    
    return f"<artifact>\n{html_content}\n</artifact>"


ALL_TOOLS = [generate_ship_30_essay, generate_html_artifact]

# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(context: str, sources: list[str]) -> str:
    """Build the system prompt with retrieved context and source references."""
    source_list = "\n".join([f"  - {s}" for s in sources]) if sources else "  (no sources retrieved)"
    
    return f"""You are the Lenny Growth Assistant, an AI that answers product management and growth questions strictly using the provided context from Lenny's Podcast transcripts.

GROUNDING RULES:
- Answer ONLY based on the provided context below. 
- If the context does not contain enough information to answer, explicitly say: "Based on the available Lenny's Podcast transcripts, I don't have enough information to answer this question fully."
- When referencing insights from the transcripts, naturally cite the source, e.g. "According to a discussion on Lenny's Podcast..." or "As mentioned in [episode topic]..."

SOURCES USED:
{source_list}

TOOL USAGE:
- Use the `generate_ship_30_essay` tool ONLY when the user explicitly asks to "write an essay", "Ship 30 for 30", or "create written content".
- Use the `generate_html_artifact` tool ONLY when the user asks for an "HTML page", "web component", "visual artifact", or "infographic".
- For all other questions, respond directly in conversational text. Do NOT call tools for regular questions.

AT THE VERY END of your response, generate exactly 3 highly relevant follow-up questions the user could ask.
Wrap them strictly in an XML block:
<suggestions>
1. First follow-up question?
2. Second follow-up question?
3. Third follow-up question?
</suggestions>

CONTEXT FROM LENNY'S PODCAST TRANSCRIPTS:
{context}
"""


# ---------------------------------------------------------------------------
# Retrieval helper
# ---------------------------------------------------------------------------

def retrieve_context(query: str) -> tuple[str, list[str]]:
    """Retrieve relevant documents and return (context_str, source_list)."""
    retriever = get_retriever()
    
    if not retriever:
        logger.warning("No retriever available (ChromaDB not initialized).")
        return "", []
    
    start = time.time()
    docs = retriever.invoke(query)
    elapsed = time.time() - start
    
    if not docs:
        logger.warning(f"Retrieval returned 0 results for query in {elapsed:.2f}s.")
        return "", []
    
    logger.info(f"Retrieved {len(docs)} documents in {elapsed:.2f}s.")
    
    context_parts = []
    sources = []
    for d in docs:
        source = d.metadata.get("source", "Unknown episode")
        # Clean up source path for display
        source_display = source.replace("\\", "/").split("/")[-1].replace(".md", "").replace("-", " ").title()
        context_parts.append(f"[Source: {source_display}]\n{d.page_content}")
        if source_display not in sources:
            sources.append(source_display)
    
    context = "\n\n---\n\n".join(context_parts)
    return context, sources


# ---------------------------------------------------------------------------
# Response generation (non-streaming, kept for fallback)
# ---------------------------------------------------------------------------

def generate_response(query: str, chat_history: list, provider: str = "ollama"):
    """Generate a complete (non-streaming) response."""
    try:
        llm = get_llm(provider)
    except ValueError as e:
        return f"⚠️ Configuration Error: {str(e)}"
    
    context, sources = retrieve_context(query)
    system_prompt = build_system_prompt(context, sources)
    
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history:
        messages.append(msg)
    messages.append(HumanMessage(content=query))
    
    try:
        # Conditionally bind tools to prevent local model hallucination
        if _should_bind_tools(query):
            llm_with_tools = llm.bind_tools(ALL_TOOLS)
        else:
            llm_with_tools = llm
            
        response = llm_with_tools.invoke(messages)
        
        if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
            tool_call = response.tool_calls[0]
            tool_fn = _get_tool_by_name(tool_call['name'])
            if tool_fn:
                tool_args = tool_call['args']
                if 'context' not in tool_args or not tool_args['context']:
                    tool_args['context'] = context
                return tool_fn.invoke(tool_args)
                
        return response.content
    except Exception as e:
        logger.error(f"LLM invocation failed with provider={provider}: {e}", exc_info=True)
        return f"⚠️ Error connecting to LLM provider ({provider}): {str(e)}"


# ---------------------------------------------------------------------------
# Response generation (streaming)
# ---------------------------------------------------------------------------

async def generate_response_stream(query: str, chat_history: list, provider: str = "ollama") -> AsyncGenerator[str, None]:
    """Stream the LLM response token-by-token."""
    try:
        llm = get_llm(provider)
    except ValueError as e:
        yield f"⚠️ Configuration Error: {str(e)}"
        return
    
    context, sources = retrieve_context(query)
    system_prompt = build_system_prompt(context, sources)
    
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history:
        messages.append(msg)
    messages.append(HumanMessage(content=query))
    
    try:
        # Conditionally bind tools to prevent local model hallucination
        if _should_bind_tools(query):
            llm_with_tools = llm.bind_tools(ALL_TOOLS)
        else:
            llm_with_tools = llm
        
        is_tool_call = False
        tool_name = ""
        tool_args_str = ""
        
        start = time.time()
        async for chunk in llm_with_tools.astream(messages):
            if chunk.tool_call_chunks:
                is_tool_call = True
                for tc in chunk.tool_call_chunks:
                    if tc.get("name"):
                        tool_name = tc["name"]
                    if tc.get("args"):
                        tool_args_str += tc["args"]
            elif chunk.content and not is_tool_call:
                yield chunk.content
        
        elapsed = time.time() - start
        logger.info(f"LLM stream completed in {elapsed:.2f}s (provider={provider}, tool_call={is_tool_call})")
                
        if is_tool_call:
            async for token in _handle_tool_call_async(tool_name, tool_args_str, context, query, provider):
                yield token
                
    except Exception as e:
        logger.error(f"LLM streaming failure with provider={provider}: {e}", exc_info=True)
        yield f"\n\n⚠️ Error streaming from LLM ({provider}): {str(e)}"


async def _handle_tool_call_async(
    tool_name: str, tool_args_str: str, context: str, query: str, provider: str
) -> AsyncGenerator[str, None]:
    """Execute a tool call detected during streaming, yielding tokens as they arrive."""
    try:
        args = json.loads(tool_args_str)
        if 'context' not in args or not args['context']:
            args['context'] = context
        
        tool_fn = _get_tool_by_name(tool_name)
        if not tool_fn:
            yield f"\n\n⚠️ Unknown tool: {tool_name}"
            return
        
        logger.info(f"Executing tool: {tool_name} with topic={args.get('topic', 'N/A')}")
        
        if tool_name == "generate_ship_30_essay":
            async for token in _stream_essay_async(args, provider):
                yield token
        elif tool_name == "generate_html_artifact":
            async for token in _stream_html_async(args, provider):
                yield token
        else:
            result = tool_fn.invoke(args)
            yield f"\n\n{result}"
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tool args: {e}")
        yield f"\n\n⚠️ Failed to parse tool arguments. Please try again."
    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
        yield f"\n\n⚠️ Error executing {tool_name}: {str(e)}"


async def _stream_essay_async(args: dict, provider: str) -> AsyncGenerator[str, None]:
    """Stream a Ship 30 for 30 essay token-by-token."""
    essay_prompt = f"""{SHIP_30_PRINCIPLES}

Now write a Ship 30 for 30 atomic essay on the topic: "{args.get('topic', 'growth')}"

Ground your claims using the following context from Lenny's Podcast transcripts:

---
{args['context']}
---

Remember: Follow the 1-3-1 framework exactly. Hook → 3 main points → Takeaway.
Cite specific insights from the transcripts naturally within the text.
Target ~1,250 words. Use Markdown formatting.
"""
    yield "\n\n*Generating Ship 30 for 30 Essay...*\n\n<artifact>\n"
    
    llm = get_llm(provider)
    async for chunk in llm.astream(essay_prompt):
        if chunk.content:
            yield chunk.content
    
    yield "\n</artifact>"


async def _stream_html_async(args: dict, provider: str) -> AsyncGenerator[str, None]:
    """Stream an HTML artifact token-by-token."""
    html_prompt = f"""Create a complete, self-contained HTML document with inline CSS.
Title: {args.get('title', 'Artifact')}
Content: {args.get('content', '')}
Style: {args.get('style', 'modern')}

Requirements:
- Complete HTML document (<!DOCTYPE html> to </html>)
- All CSS inline in a <style> tag
- NO <script> tags (blocked for security)
- Modern, clean design with good typography and spacing
- Well-structured and readable
- Output ONLY the raw HTML, no markdown code fences
"""
    yield "\n\n*Generating HTML Artifact...*\n\n<artifact>\n"
    
    llm = get_llm(provider)
    async for chunk in llm.astream(html_prompt):
        if chunk.content:
            yield chunk.content
    
    yield "\n</artifact>"


# ---------------------------------------------------------------------------
# Non-streaming tool helpers (kept for fallback / non-streaming path)
# ---------------------------------------------------------------------------

def from_tool_call_stream(tool_name: str, tool_args_str: str, context: str, query: str, provider: str) -> str:
    """Execute a tool call (synchronous fallback). Used by generate_response()."""
    try:
        args = json.loads(tool_args_str)
        if 'context' not in args or not args['context']:
            args['context'] = context

        tool_fn = _get_tool_by_name(tool_name)
        if not tool_fn:
            return f"\n\n⚠️ Unknown tool: {tool_name}"

        logger.info(f"Executing tool (sync): {tool_name}")
        result = tool_fn.invoke(args)
        return f"\n\n{result}"

    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
        return f"\n\n⚠️ Error executing {tool_name}: {str(e)}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_bind_tools(query: str) -> bool:
    """Determine if tools should be bound based on query keywords.
    This prevents local 8B models from aggressively hallucinating tool calls."""
    keywords = ["essay", "ship 30", "write", "content", "html", "artifact", 
                 "page", "infographic", "component", "landing"]
    return any(kw in query.lower() for kw in keywords)


def _get_tool_by_name(name: str):
    """Look up a tool function by name."""
    tool_map = {
        "generate_ship_30_essay": generate_ship_30_essay,
        "generate_html_artifact": generate_html_artifact,
    }
    return tool_map.get(name)

