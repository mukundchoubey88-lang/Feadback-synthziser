from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_root_endpoint():
    """Verify that the GET / endpoint returns 200 and basic application info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == settings.APP_NAME
    assert data["version"] == "1.0.0"
    assert data["status"] == "online"
    assert data["docs_url"] == "/docs"


def test_health_endpoint():
    """Verify that GET /api/health returns 200 and structured health details."""
    response = client.get(f"{settings.API_V1_PREFIX}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == settings.APP_NAME
    assert data["version"] == "1.0.0"
    assert data["environment"] == settings.APP_ENV

    # Verify dependency structure exists and reports accurately
    dependencies = data["dependencies"]
    assert "database" in dependencies
    assert "gemini" in dependencies
    assert "hindsight" in dependencies

    # Since DATABASE_URL is unset in default test environment, it must not claim connected
    assert dependencies["database"]["status"] in ("not_configured", "not_checked")
    assert dependencies["gemini"]["status"] in ("not_configured", "not_checked")
    assert dependencies["hindsight"]["status"] in ("not_configured", "not_checked")


def test_docs_and_openapi_available():
    """Verify that Swagger docs and OpenAPI schema endpoints are accessible."""
    docs_res = client.get("/docs")
    openapi_res = client.get("/openapi.json")

    assert docs_res.status_code == 200
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert schema["info"]["title"] == "Feedback Intelligence API"
    assert schema["info"]["version"] == "1.0.0"


def test_health_without_database_connection():
    """Verify health endpoint succeeds even when database is unconfigured or unavailable."""
    response = client.get(f"{settings.API_V1_PREFIX}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    # External dependency must not be falsely marked as connected
    assert data["dependencies"]["database"]["status"] != "connected"
