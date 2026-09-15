import os
import uuid
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from uuid import UUID

import models
import schemas
from database import engine, get_db, SessionLocal
from agent import generate_response, generate_response_stream
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLAlchemyCache
from watcher import start_watcher

# ---------------------------------------------------------------------------
# Structured Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("lenny.api")

# Create tables if they don't exist
try:
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")
except Exception as e:
    logger.error(f"Failed to initialize database tables: {e}")

# Setup exact-match caching for LLM responses
try:
    set_llm_cache(SQLAlchemyCache(engine=engine))
    logger.info("LLM response cache initialized (SQLAlchemy).")
except Exception as e:
    logger.warning(f"LLM cache initialization failed (non-critical): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start background services on startup."""
    logger.info("Starting Lenny Growth Assistant API...")
    start_watcher()
    yield
    logger.info("Shutting down Lenny Growth Assistant API.")


app = FastAPI(
    title="Lenny Growth Assistant API",
    description="AI-powered conversational assistant grounded in Lenny's Podcast transcripts",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware: Request logging
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    elapsed = (time.time() - start) * 1000
    logger.info(f"[{request_id}] {request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "path": request.url.path,
        }
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint. Returns DB connectivity and system status."""
    # Check database
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"
    
    # Check Ollama
    ollama_status = "unknown"
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=3)
        ollama_status = "connected" if resp.status_code == 200 else "error"
    except Exception:
        ollama_status = "disconnected"
    
    return {
        "status": "ok",
        "database": db_status,
        "ollama": ollama_status,
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------
@app.post("/sessions", response_model=schemas.SessionResponse, tags=["Sessions"])
def create_session(session: schemas.SessionCreate, db: Session = Depends(get_db)):
    """Create a new chat session."""
    db_session = models.Session(title=session.title)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    logger.info(f"Session created: {db_session.id}")
    return db_session


@app.get("/sessions", response_model=List[schemas.SessionResponse], tags=["Sessions"])
def get_sessions(db: Session = Depends(get_db)):
    """List all chat sessions, most recent first."""
    return db.query(models.Session).order_by(models.Session.updated_at.desc()).all()


@app.get("/sessions/{session_id}", response_model=schemas.SessionResponse, tags=["Sessions"])
def get_session(session_id: UUID, db: Session = Depends(get_db)):
    """Get a specific session with its message history."""
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session


@app.delete("/sessions/{session_id}", tags=["Sessions"])
def delete_session(session_id: UUID, db: Session = Depends(get_db)):
    """Delete a chat session and all its messages."""
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(db_session)
    db.commit()
    logger.info(f"Session deleted: {session_id}")
    return {"status": "deleted", "session_id": str(session_id)}


# ---------------------------------------------------------------------------
# Chat endpoint (streaming)
# ---------------------------------------------------------------------------
@app.post("/sessions/{session_id}/chat", tags=["Chat"])
async def chat(session_id: UUID, request: schemas.ChatRequest, db: Session = Depends(get_db)):
    """Send a message and receive a streamed response from the assistant."""
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Auto-title: use first message as session title (truncated to 50 chars)
    existing_msgs = db.query(models.Message).filter(models.Message.session_id == session_id).count()
    if existing_msgs == 0 and db_session.title == "New Chat":
        auto_title = request.message[:50] + ("..." if len(request.message) > 50 else "")
        db_session.title = auto_title
    
    # Save user message
    user_msg = models.Message(session_id=session_id, role="user", content=request.message)
    db.add(user_msg)
    
    # Retrieve history for context
    history = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    langchain_history = []
    for msg in history:
        if msg.role == "user":
            langchain_history.append(HumanMessage(content=msg.content))
        else:
            langchain_history.append(AIMessage(content=msg.content))
            
    # Commit user message before starting stream
    db.commit()
    
    logger.info(f"Chat request: session={session_id}, provider={request.llm_provider}, history_len={len(langchain_history)}")
    
    async def response_streamer():
        full_text = ""
        try:
            async for chunk in generate_response_stream(
                request.message, langchain_history, provider=request.llm_provider
            ):
                full_text += chunk
                yield chunk
        except Exception as stream_e:
            logger.error(f"Streaming error for session {session_id}: {stream_e}", exc_info=True)
            error_msg = f"\n\n⚠️ [System Error: LLM streaming failed. Details: {str(stream_e)}]"
            full_text += error_msg
            yield error_msg
            
        # Save assistant message to DB after stream finishes
        try:
            with SessionLocal() as post_db:
                ai_msg = models.Message(session_id=session_id, role="assistant", content=full_text)
                post_db.add(ai_msg)
                post_db.commit()
                logger.info(f"Assistant message persisted for session {session_id} ({len(full_text)} chars)")
        except Exception as db_e:
            logger.error(f"Failed to persist assistant message: {db_e}", exc_info=True)

    return StreamingResponse(response_streamer(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Feedback endpoint
# ---------------------------------------------------------------------------
@app.post("/messages/{msg_id}/feedback", tags=["Feedback"])
def submit_feedback(msg_id: UUID, request: schemas.FeedbackRequest, db: Session = Depends(get_db)):
    """Submit thumbs-up (+1) or thumbs-down (-1) feedback on a message."""
    msg = db.query(models.Message).filter(models.Message.id == msg_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if request.feedback not in (1, -1):
        raise HTTPException(status_code=422, detail="Feedback must be 1 (thumbs up) or -1 (thumbs down)")
        
    msg.feedback = request.feedback
    db.commit()
    logger.info(f"Feedback recorded: msg={msg_id}, feedback={request.feedback}")
    return {"status": "success", "message_id": str(msg_id), "feedback": request.feedback}


# ---------------------------------------------------------------------------
# Config visibility endpoint
# ---------------------------------------------------------------------------
@app.get("/config", tags=["System"])
def get_config():
    """Returns the current system configuration (non-sensitive)."""
    return {
        "available_providers": [
            {"id": "ollama", "name": "Local (Ollama)", "model": "llama3.1", "type": "local"},
            {"id": "anthropic", "name": "Anthropic Claude", "model": "claude-sonnet-4-20250514", "type": "cloud"},
        ],
        "default_provider": "ollama",
        "embedding_model": "nomic-embed-text",
        "retrieval": "Hybrid (ChromaDB + BM25 RRF)",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
