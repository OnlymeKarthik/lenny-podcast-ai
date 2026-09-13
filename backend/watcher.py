import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
import agent

DB_DIR = "./chroma_db"
DATA_DIR = "./lennys-podcast-transcripts/episodes"

class TranscriptHandler(FileSystemEventHandler):
    def process_file(self, file_path):
        if not file_path.endswith('.md'):
            return
            
        print(f"Watcher: Detected new/modified transcript -> {file_path}")
        try:
            loader = TextLoader(file_path)
            docs = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(docs)
            
            embeddings = OllamaEmbeddings(
                model="nomic-embed-text",
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            )
            
            # Append to existing ChromaDB
            vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
            vectorstore.add_documents(splits)
            print(f"Watcher: Successfully embedded {file_path} into ChromaDB.")
            
            # Reset the BM25 cache in the agent so it rebuilds on next request
            agent.bm25_retriever_cache = None
            
        except Exception as e:
            print(f"Watcher Error: Failed to process {file_path}. {e}")

    def on_created(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

def start_watcher():
    if not os.path.exists(DATA_DIR):
        print("Watcher: Data directory does not exist yet. Skipping.")
        return
        
    try:
        event_handler = TranscriptHandler()
        observer = Observer()
        observer.schedule(event_handler, DATA_DIR, recursive=True)
        observer.start()
        print("Watcher: Live ingestion daemon started...")
        
        # Run in a background thread to not block FastAPI
        def run_observer():
            try:
                while True:
                    time.sleep(1)
            except Exception:
                observer.stop()
            observer.join()
            
        thread = threading.Thread(target=run_observer, daemon=True)
        thread.start()
    except Exception as e:
        print(f"Watcher failed to start: {e}")
