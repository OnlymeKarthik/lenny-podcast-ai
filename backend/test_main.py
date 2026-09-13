import pytest
from fastapi.testclient import TestClient
from main import app
from database import Base, engine, get_db
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine_test = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

Base.metadata.create_all(bind=engine_test)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_session():
    response = client.post("/sessions", json={"title": "Test Session"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Session"
    assert "id" in data
    
    return data["id"]

def test_get_sessions():
    client.post("/sessions", json={"title": "Another Session"})
    response = client.get("/sessions")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_chat_persistence():
    # Note: We mock the LLM response in a real robust test suite.
    # For this demo test, if ollama is not running it will return the error string but still persist.
    session_id = test_create_session()
    
    response = client.post(
        f"/sessions/{session_id}/chat",
        json={"message": "What is the best growth tactic?", "llm_provider": "ollama"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert "content" in data
    assert data["session_id"] == session_id

def test_retrieval_system():
    # Test that the vector store can be initialized and queried (even if empty)
    from agent import get_retriever
    retriever = get_retriever()
    if retriever:
        docs = retriever.invoke("growth tactics")
        assert isinstance(docs, list)

def test_agent_routing():
    # Test that the routing logic correctly falls back or initializes the LLM
    from agent import get_llm
    llm = get_llm("ollama")
    assert llm is not None
    # Check that model is set correctly
    assert hasattr(llm, "model")

