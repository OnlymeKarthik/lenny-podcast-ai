import os
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings

DB_DIR = "./chroma_db"

def get_llm(provider: str):
    if provider == "anthropic":
        return ChatAnthropic(
            model_name="claude-3-5-sonnet-20240620",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    else: # Default to local ollama for the demo
        return ChatOllama(
            model="llama3", # Assuming user has llama3 installed, can be parameterized
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )

def get_retriever():
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    # Return None if db doesn't exist yet to handle clean startups gracefully
    if not os.path.exists(DB_DIR):
        return None
        
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    return vectorstore.as_retriever(search_kwargs={"k": 3})

def generate_response(query: str, chat_history: list, provider: str = "ollama"):
    llm = get_llm(provider)
    retriever = get_retriever()
    
    context = ""
    if retriever:
        docs = retriever.invoke(query)
        context = "\n\n".join([d.page_content for d in docs])
        
    system_prompt = f"""You are the Lenny Growth Assistant. You answer product and growth questions strictly using the provided context from Lenny's Podcast transcripts. 
If the context does not contain the answer, you must state that you don't know based on the available material.

Context:
{context}

If the user asks for a 'Ship 30 for 30' essay, output the entire essay wrapped in an <artifact> block formatted with Markdown. It should be ~1,250 words (or as close as you can), have a strong hook, skimmable formatting, and specific takeaways.
"""
    
    messages = [SystemMessage(content=system_prompt)]
    # We could append history here, keeping it simple for the demo
    for msg in chat_history:
        messages.append(msg)
    messages.append(HumanMessage(content=query))
    
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        return f"Error connecting to LLM provider ({provider}): {str(e)}"
