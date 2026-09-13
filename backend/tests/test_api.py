import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, engine
from sqlalchemy.orm import sessionmaker
import models

# Create a test database session
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"

def test_create_session():
    response = client.post("/sessions", json={"title": "Test Chat"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["title"] == "Test Chat"
    
    # Store session id for next test
    pytest.session_id = data["id"]

def test_get_sessions():
    response = client.get("/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any(s["id"] == pytest.session_id for s in data)

# Note: We mock out the actual LLM call in a real CI environment, 
# but for local evaluation this will test the DB routing gracefully.
