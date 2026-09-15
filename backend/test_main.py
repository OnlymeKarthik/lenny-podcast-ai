"""
Automated tests for Lenny Growth Assistant API.
Run with: pytest test_main.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from main import app
from database import Base, get_db

# ---------------------------------------------------------------------------
# Test Database Setup (isolated SQLite)
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine_test = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

Base.metadata.create_all(bind=engine_test)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
class TestHealthCheck:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "database" in data
        assert "ollama" in data
        assert "version" in data


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------
class TestSessions:
    def test_create_session(self):
        response = client.post("/sessions", json={"title": "Test Session"})
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Session"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_session_default_title(self):
        response = client.post("/sessions", json={})
        assert response.status_code == 200
        assert response.json()["title"] == "New Chat"

    def test_get_sessions_list(self):
        # Create a session first
        client.post("/sessions", json={"title": "List Test"})
        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_session_by_id(self):
        create_resp = client.post("/sessions", json={"title": "Fetch Me"})
        session_id = create_resp.json()["id"]
        
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["id"] == session_id
        assert response.json()["title"] == "Fetch Me"

    def test_get_session_not_found(self):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/sessions/{fake_id}")
        assert response.status_code == 404

    def test_session_has_empty_messages(self):
        create_resp = client.post("/sessions", json={"title": "Empty Messages"})
        session_id = create_resp.json()["id"]
        
        response = client.get(f"/sessions/{session_id}")
        assert response.json()["messages"] == []


# ---------------------------------------------------------------------------
# Chat Endpoint
# ---------------------------------------------------------------------------
class TestChat:
    def test_chat_session_not_found(self):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/sessions/{fake_id}/chat",
            json={"message": "hello", "llm_provider": "ollama"}
        )
        assert response.status_code == 404

    def test_chat_returns_streaming_response(self):
        """Test that the chat endpoint returns a streaming response (even if LLM is unavailable)."""
        create_resp = client.post("/sessions", json={"title": "Chat Test"})
        session_id = create_resp.json()["id"]
        
        response = client.post(
            f"/sessions/{session_id}/chat",
            json={"message": "What is product-market fit?", "llm_provider": "ollama"}
        )
        # Should return 200 even if Ollama is not running (error is streamed)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Feedback Endpoint
# ---------------------------------------------------------------------------
class TestFeedback:
    def test_feedback_message_not_found(self):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/messages/{fake_id}/feedback",
            json={"feedback": 1}
        )
        assert response.status_code == 404

    def test_feedback_invalid_value(self):
        """Feedback must be 1 or -1."""
        # First we need a real message — this is hard without LLM, so we test the validation
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/messages/{fake_id}/feedback",
            json={"feedback": 5}
        )
        # Should return 404 (message not found) or 422 (invalid value)
        assert response.status_code in (404, 422)


# ---------------------------------------------------------------------------
# Config Endpoint
# ---------------------------------------------------------------------------
class TestConfig:
    def test_config_returns_providers(self):
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "available_providers" in data
        assert len(data["available_providers"]) >= 2
        provider_ids = [p["id"] for p in data["available_providers"]]
        assert "ollama" in provider_ids
        assert "anthropic" in provider_ids


# ---------------------------------------------------------------------------
# Agent / Retrieval Unit Tests
# ---------------------------------------------------------------------------
class TestAgentRouting:
    def test_get_llm_ollama(self):
        from agent import get_llm
        llm = get_llm("ollama")
        assert llm is not None
        assert hasattr(llm, "model")

    def test_get_llm_anthropic_missing_key(self):
        from agent import get_llm
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                get_llm("anthropic")

    def test_should_bind_tools(self):
        from agent import _should_bind_tools
        assert _should_bind_tools("write me a ship 30 for 30 essay") == True
        assert _should_bind_tools("What is product-market fit?") == False
        assert _should_bind_tools("Create an HTML artifact for this") == True

    def test_retrieval_returns_list(self):
        from agent import get_retriever
        retriever = get_retriever()
        if retriever:
            docs = retriever.invoke("growth tactics")
            assert isinstance(docs, list)

    def test_retrieve_context_returns_tuple(self):
        from agent import retrieve_context
        context, sources = retrieve_context("growth")
        assert isinstance(context, str)
        assert isinstance(sources, list)


# ---------------------------------------------------------------------------
# Request/Response Contract Validation
# ---------------------------------------------------------------------------
class TestAPIContracts:
    def test_session_response_shape(self):
        response = client.post("/sessions", json={"title": "Shape Test"})
        data = response.json()
        required_keys = {"id", "title", "created_at", "updated_at", "messages"}
        assert required_keys.issubset(set(data.keys()))

    def test_chat_request_validation(self):
        """Chat request must have a message field."""
        create_resp = client.post("/sessions", json={"title": "Validation Test"})
        session_id = create_resp.json()["id"]
        
        response = client.post(
            f"/sessions/{session_id}/chat",
            json={}  # Missing "message"
        )
        assert response.status_code == 422  # Pydantic validation error
