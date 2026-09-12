import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings

# For demo purposes we use local ChromaDB and Ollama embeddings.
DB_DIR = "./chroma_db"
DATA_DIR = "./data"

def run_ingestion():
    print("Loading documents...")
    loader = DirectoryLoader(DATA_DIR, glob="*.md", loader_cls=TextLoader)
    docs = loader.load()
    
    print(f"Loaded {len(docs)} documents.")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    splits = text_splitter.split_documents(docs)
    
    print(f"Split into {len(splits)} chunks. Creating vector store...")
    
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    
    vectorstore = Chroma.from_documents(
        documents=splits, 
        embedding=embeddings, 
        persist_directory=DB_DIR
    )
    
    print("Ingestion complete. Database persisted to", DB_DIR)

if __name__ == "__main__":
    run_ingestion()
