from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

import models
import schemas
from database import engine, get_db
from agent import generate_response
from langchain_core.messages import HumanMessage, AIMessage

# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lenny Growth Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

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

@app.post("/sessions/{session_id}/chat", response_model=schemas.MessageResponse)
def chat(session_id: UUID, request: schemas.ChatRequest, db: Session = Depends(get_db)):
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
            
    # Generate response
    ai_text = generate_response(request.message, langchain_history, provider=request.llm_provider)
    
    # Save assistant message
    ai_msg = models.Message(session_id=session_id, role="assistant", content=ai_text)
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    
    return ai_msg

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
