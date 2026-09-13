import os
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma

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

@tool
def generate_ship_30_essay(topic: str, context: str) -> str:
    """Creates a Ship 30 for 30 style essay based on the topic and context.
    Call this tool ONLY when the user explicitly asks to write a Ship 30 for 30 essay or similar formatted output."""
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
    essay_llm = ChatOllama(model="llama3", base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
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
When answering, you MUST cite or clearly identify the specific transcript/source you used based on the 'Source' metadata provided in the context.

Context:
{context}
"""
    
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history:
        messages.append(msg)
    messages.append(HumanMessage(content=query))
    
    try:
        # Bind the Ship 30 for 30 tool to the LLM
        llm_with_tools = llm.bind_tools([generate_ship_30_essay])
        response = llm_with_tools.invoke(messages)
        
        # Check if the LLM decided to invoke the tool
        if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
            tool_call = response.tool_calls[0]
            if tool_call['name'] == 'generate_ship_30_essay':
                # Execute the tool and return the explicitly generated artifact
                tool_args = tool_call['args']
                # Ensure context is provided to the tool if the LLM omitted it
                if 'context' not in tool_args or not tool_args['context']:
                    tool_args['context'] = context
                return generate_ship_30_essay.invoke(tool_args)
                
        return response.content
    except Exception as e:
        return f"Error connecting to LLM provider ({provider}): {str(e)}"
