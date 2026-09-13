import os
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from typing import AsyncGenerator
import json

DB_DIR = "./chroma_db"
DATA_DIR = "./lennys-podcast-transcripts/episodes"

bm25_retriever_cache = None

def get_llm(provider: str):
    if provider == "anthropic":
        return ChatAnthropic(
            model_name="claude-3-5-sonnet-20240620",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    else: # Default to local ollama for the demo
        return ChatOllama(
            model="llama3.1", # Using llama3.1 for native tool calling support
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )

class CustomEnsembleRetriever(BaseRetriever):
    retrievers: list[BaseRetriever]
    weights: list[float]
    
    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        doc_lists = [r.invoke(query) for r in self.retrievers]
        
        # Simple Reciprocal Rank Fusion (RRF)
        rrf_score = {}
        for doc_list, weight in zip(doc_lists, self.weights):
            for rank, doc in enumerate(doc_list):
                # Use page_content as a simple deduplication key
                key = doc.page_content
                if key not in rrf_score:
                    rrf_score[key] = {"score": 0, "doc": doc}
                rrf_score[key]["score"] += weight * (1.0 / (rank + 60))
                
        # Sort by RRF score
        sorted_docs = sorted(rrf_score.values(), key=lambda x: x["score"], reverse=True)
        return [item["doc"] for item in sorted_docs[:3]]

def get_retriever():
    global bm25_retriever_cache
    
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    if not os.path.exists(DB_DIR):
        return None
        
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    chroma_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    if bm25_retriever_cache is None and os.path.exists(DATA_DIR):
        try:
            loader = DirectoryLoader(DATA_DIR, glob="**/*.md", loader_cls=TextLoader)
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splits = text_splitter.split_documents(docs)
            bm25_retriever_cache = BM25Retriever.from_documents(splits)
            bm25_retriever_cache.k = 3
        except Exception as e:
            print(f"Warning: Failed to initialize BM25 retriever: {e}")
            
    if bm25_retriever_cache:
        return CustomEnsembleRetriever(
            retrievers=[bm25_retriever_cache, chroma_retriever],
            weights=[0.3, 0.7]
        )
        
    return chroma_retriever

@tool
def generate_ship_30_essay(topic: str, context: str) -> str:
    """DO NOT USE THIS TOOL UNLESS THE USER EXPLICITLY ASKS TO "WRITE AN ESSAY" OR "SHIP 30 FOR 30".
    If the user is just asking a question, DO NOT use this tool. Answer them normally in plain text.
    Creates a Ship 30 for 30 style essay based on the topic and context."""
    essay_prompt = f"""Write a Ship 30 for 30 essay on the topic: {topic}.
Use the following context from Lenny's Podcast to ground your claims:
{context}

Requirements:
- ~1,250 words
- A strong hook and clear narrative progression
- Skimmable formatting with headings, bullets, and selective bold emphasis
- A specific, useful takeaway
"""
    # For the tool execution, we use a fresh LLM call to guarantee strict formatting
    essay_llm = ChatOllama(model="llama3.1", base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    essay_content = essay_llm.invoke(essay_prompt).content
    
    return f"<artifact>\n{essay_content}\n</artifact>"

def generate_response(query: str, chat_history: list, provider: str = "ollama"):
    llm = get_llm(provider)
    retriever = get_retriever()
    
    context = ""
    if retriever:
        docs = retriever.invoke(query)
        context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')}\n{d.page_content}" for d in docs])
        
    system_prompt = f"""You are the Lenny Growth Assistant. You answer product and growth questions strictly using the provided context from Lenny's Podcast transcripts. 
If the context does not contain the answer, you must state that you don't know based on the available material.
DO NOT cite your sources or mention the transcript file names in your response. Just provide the answer naturally.

AT THE VERY END of your response, you MUST generate exactly 3 highly relevant follow-up questions the user could ask based on this topic. 
Wrap them strictly in an XML block like this:
<suggestions>
1. First follow-up question?
2. Second follow-up question?
3. Third follow-up question?
</suggestions>

Context:
{context}
"""
    
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history:
        messages.append(msg)
    messages.append(HumanMessage(content=query))
    
    try:
        # FIX: Local 8B models aggressively hallucinate tool calls if tools are available.
        # Conditionally bind the essay tool ONLY if the user asks for it.
        if "essay" in query.lower() or "ship 30" in query.lower():
            llm_with_tools = llm.bind_tools([generate_ship_30_essay])
        else:
            llm_with_tools = llm
            
        response = llm_with_tools.invoke(messages)
        
        if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
            tool_call = response.tool_calls[0]
            if tool_call['name'] == 'generate_ship_30_essay':
                tool_args = tool_call['args']
                if 'context' not in tool_args or not tool_args['context']:
                    tool_args['context'] = context
                return generate_ship_30_essay.invoke(tool_args)
                
        return response.content
    except Exception as e:
        return f"Error connecting to LLM provider ({provider}): {str(e)}"

async def generate_response_stream(query: str, chat_history: list, provider: str = "ollama") -> AsyncGenerator[str, None]:
    llm = get_llm(provider)
    retriever = get_retriever()
    
    context = ""
    if retriever:
        docs = retriever.invoke(query)
        context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')}\n{d.page_content}" for d in docs])
        
    system_prompt = f"""You are the Lenny Growth Assistant. You answer product and growth questions strictly using the provided context from Lenny's Podcast transcripts. 
If the context does not contain the answer, you must state that you don't know based on the available material.
DO NOT cite your sources or mention the transcript file names in your response. Just provide the answer naturally.

CRITICAL INSTRUCTIONS:
1. DO NOT use the generate_ship_30_essay tool unless the user explicitly asks you to "write an essay". If they just ask a question, answer it normally in plain text.
2. If you DO use a tool, output ONLY the tool call with NO conversational filler (e.g. do not say "Here is the JSON").

AT THE VERY END of your response, you MUST generate exactly 3 highly relevant follow-up questions the user could ask based on this topic. 
Wrap them strictly in an XML block like this:
<suggestions>
1. First follow-up question?
2. Second follow-up question?
3. Third follow-up question?
</suggestions>

Context:
{context}
"""
    
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history:
        messages.append(msg)
    messages.append(HumanMessage(content=query))
    
    try:
        # FIX: Local 8B models aggressively hallucinate tool calls if tools are available.
        # Conditionally bind the essay tool ONLY if the user asks for it.
        if "essay" in query.lower() or "ship 30" in query.lower():
            llm_with_tools = llm.bind_tools([generate_ship_30_essay])
        else:
            llm_with_tools = llm
        
        is_tool_call = False
        tool_args_str = ""
        
        async for chunk in llm_with_tools.astream(messages):
            if chunk.tool_call_chunks:
                is_tool_call = True
                if chunk.tool_call_chunks[0].get("args"):
                    tool_args_str += chunk.tool_call_chunks[0]["args"]
            elif chunk.content and not is_tool_call:
                yield chunk.content
                
        if is_tool_call:
            try:
                args = json.loads(tool_args_str)
                if 'context' not in args or not args['context']:
                    args['context'] = context
                
                yield "\n\n*Generating Ship 30 for 30 Essay...*\n\n"
                
                essay_prompt = f"""Write a Ship 30 for 30 essay on the topic: {args.get('topic', query)}.
Use the following context from Lenny's Podcast to ground your claims:
{args['context']}

Requirements:
- ~1,250 words
- A strong hook and clear narrative progression
- Skimmable formatting with headings, bullets, and selective bold emphasis
- A specific, useful takeaway
"""
                # Stream the artifact natively
                essay_llm = get_llm(provider)
                yield "<artifact>\n"
                async for essay_chunk in essay_llm.astream(essay_prompt):
                    if essay_chunk.content:
                        yield essay_chunk.content
                yield "\n</artifact>"
                
            except Exception as parse_e:
                yield f"Error executing tool stream: {parse_e}"
                
    except Exception as e:
        yield f"Error streaming from LLM provider ({provider}): {str(e)}"
