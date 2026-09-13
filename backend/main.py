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
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLAlchemyCache
from contextlib import asynccontextmanager
from watcher import start_watcher

# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)

# Setup exact-match caching for LLM responses
set_llm_cache(SQLAlchemyCache(engine=engine))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background live ingestion watcher
    start_watcher()
    yield
    # Shutdown logic if needed

app = FastAPI(title="Lenny Growth Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": str(exc), "path": request.url.path}
    )

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return {"status": "ok", "database": db_status}

@app.post("/sessions", response_model=schemas.SessionResponse)
def create_session(session: schemas.SessionCreate, db: Session = Depends(get_db)):
    db_session = models.Session(title=session.title)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@app.get("/sessions", response_model=List[schemas.SessionResponse])
def get_sessions(db: Session = Depends(get_db)):
    return db.query(models.Session).order_by(models.Session.updated_at.desc()).all()

@app.get("/sessions/{session_id}", response_model=schemas.SessionResponse)
def get_session(session_id: UUID, db: Session = Depends(get_db)):
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return db_session

@app.post("/sessions/{session_id}/chat")
async def chat(session_id: UUID, request: schemas.ChatRequest, db: Session = Depends(get_db)):
    db_session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Save user message
    user_msg = models.Message(session_id=session_id, role="user", content=request.message)
    db.add(user_msg)
    
    # Retrieve history for context
    history = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.asc()).all()
    langchain_history = []
    for msg in history:
        if msg.role == "user":
            langchain_history.append(HumanMessage(content=msg.content))
        else:
            langchain_history.append(AIMessage(content=msg.content))
            
    # Commit user message immediately so it's saved before the stream starts
    db.commit()
    
    async def response_streamer():
        full_text = ""
        async for chunk in generate_response_stream(request.message, langchain_history, provider=request.llm_provider):
            full_text += chunk
            yield chunk
            
        # Save assistant message to DB after stream finishes
        # Use a fresh DB session because the original one might be closed by FastAPI dependency injection
        with SessionLocal() as post_db:
            ai_msg = models.Message(session_id=session_id, role="assistant", content=full_text)
            post_db.add(ai_msg)
            post_db.commit()

    return StreamingResponse(response_streamer(), media_type="text/event-stream")

@app.post("/messages/{msg_id}/feedback")
def submit_feedback(msg_id: UUID, request: schemas.FeedbackRequest, db: Session = Depends(get_db)):
    msg = db.query(models.Message).filter(models.Message.id == msg_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    msg.feedback = request.feedback
    db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
