"""Tests for Historical Memory Intelligence (Part 10 - Hackathon Prototype).

Covers:
1. Unified question with both PostgreSQL metrics and Hindsight memories available.
2. Question where no relevant memories exist in Hindsight (empty recall).
3. Hindsight unavailable or timed out (graceful degradation, PostgreSQL grounding preserved, no 500).
4. Product with insufficient historical data (zero feedback items).
5. Product isolation (records and releases for Product A never contaminate Product B).
6. Evidence and provenance mapping (feedback quotes with UUIDs, themes, and releases).
7. Strict PostgreSQL numerical grounding (all percentages and counts match SQL data).
8. Causal guardrails (no unsupported causal claims; correlation != causation disclaimers).
9. FastAPI HTTP API endpoint POST /api/intelligence/ask via TestClient.
"""

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, List
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.intelligence import get_ai_manager, get_hindsight_client
from app.db.base import Base
from app.db.session import get_db
from app.integrations.hindsight.client import HindsightClient
from app.main import app
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.product_change import ProductChanges
from app.models.theme import Theme
from app.schemas.intelligence import HistoricalIntelligenceRequest
from app.services.historical_intelligence_service import HistoricalIntelligenceService


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with table creation."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_client(db_session: Session):
    """FastAPI TestClient with overridden database session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ai_manager] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_hindsight_client, None)
    app.dependency_overrides.pop(get_ai_manager, None)


# ---------------------------------------------------------------------------
# Mock Transport for Hindsight Client
# ---------------------------------------------------------------------------

class MockHindsightTransport(httpx.AsyncBaseTransport):
    """Simulated Hindsight HTTP transport for intelligence queries."""

    def __init__(self, healthy: bool = True, has_memories: bool = True) -> None:
        self.healthy = healthy
        self.has_memories = has_memories

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not self.healthy:
            raise httpx.ConnectError("Hindsight server unavailable", request=request)

        path = request.url.path

        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})

        if "/memories/recall" in path:
            if not self.has_memories:
                return httpx.Response(200, json={"memories": []})
            return httpx.Response(200, json={
                "memories": [
                    {
                        "id": "hind-mem-101",
                        "content": "Checkout failures surged after mobile OS upgrade.",
                        "context": "theme=checkout",
                    }
                ]
            })

        if "/reflect" in path:
            return httpx.Response(200, json={
                "reasoning": "Historical trajectory shows checkout complaints peaked in October and declined post-hotfix.",
                "memories": [{"id": "hind-mem-101"}],
            })

        return httpx.Response(404, json={"error": "Not Found"})


# ---------------------------------------------------------------------------
# Test Data Seeding Helper
# ---------------------------------------------------------------------------

def seed_product_data(session: Session, product: str = "Mobile App"):
    """Seed comprehensive feedback, classifications, releases, and themes."""
    now = datetime.now(timezone.utc)
    rel_date = now - timedelta(days=10)

    # 1. Product Release
    release = ProductChanges(
        product=product,
        version="v3.2.0",
        feature="Checkout",
        release_description="Fixed payment gateway timeout and button crash",
        release_date=rel_date,
        change_category="hotfix",
    )
    session.add(release)

    # 2. Pre-release feedback (negative)
    fb_pre1 = Feedback(
        product=product,
        source="app_store",
        feedback_text="Checkout button crashes continuously on iOS!",
        timestamp=rel_date - timedelta(days=5),
    )
    fb_pre2 = Feedback(
        product=product,
        source="zendesk",
        feedback_text="Cannot complete payment, order failed.",
        timestamp=rel_date - timedelta(days=3),
    )
    session.add_all([fb_pre1, fb_pre2])
    session.flush()

    clf_pre1 = FeedbackClassification(
        feedback_id=fb_pre1.feedback_id,
        classification_version="1.0.0",
        run_number=1,
        sentiment_score=-0.9,
        confidence_score=0.95,
        overall_sentiment="negative",
        sentiment_intensity="high",
        customer_intent="complaint",
        classified_at=rel_date - timedelta(days=5),
    )
    clf_pre2 = FeedbackClassification(
        feedback_id=fb_pre2.feedback_id,
        classification_version="1.0.0",
        run_number=1,
        sentiment_score=-0.8,
        confidence_score=0.9,
        overall_sentiment="negative",
        sentiment_intensity="high",
        customer_intent="complaint",
        classified_at=rel_date - timedelta(days=3),
    )
    session.add_all([clf_pre1, clf_pre2])

    # 3. Post-release feedback (positive)
    fb_post = Feedback(
        product=product,
        source="csv",
        feedback_text="Checkout works seamlessly now, thank you for fixing it!",
        timestamp=rel_date + timedelta(days=2),
    )
    session.add(fb_post)
    session.flush()

    clf_post = FeedbackClassification(
        feedback_id=fb_post.feedback_id,
        classification_version="1.0.0",
        run_number=1,
        sentiment_score=0.85,
        confidence_score=0.95,
        overall_sentiment="positive",
        sentiment_intensity="high",
        customer_intent="praise",
        classified_at=rel_date + timedelta(days=2),
    )
    session.add(clf_post)

    # 4. Active Theme
    theme = Theme(
        product=product,
        theme_name="Checkout Stability",
        description="Payment flow stability and crash prevention",
        category="bug",
        status="active",
        created_at=rel_date - timedelta(days=20),
    )
    session.add(theme)
    session.commit()
    return release, theme, [fb_pre1, fb_pre2, fb_post]


# ---------------------------------------------------------------------------
# Unit & Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_full_intelligence_workflow_success(db_session: Session):
    """Test unified intelligence query when both PostgreSQL and Hindsight are available."""
    product = "Mobile App"
    release, theme, feedbacks = seed_product_data(db_session, product)

    transport = MockHindsightTransport(healthy=True, has_memories=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)

    question = "Did checkout complaints improve after our latest release?"
    response = await HistoricalIntelligenceService.ask(
        session=db_session,
        product=product,
        question=question,
        hindsight_client=client,
    )

    assert response.product == product
    assert response.question == question
    assert response.hindsight_available is True
    assert response.historical_context is not None
    assert "Historical trajectory shows checkout complaints" in response.historical_context

    # Verify PostgreSQL grounding
    assert response.sql_metrics.total_feedback == 3
    assert response.sql_metrics.positive_percentage == 33.3
    assert response.sql_metrics.negative_percentage == 66.7
    assert response.sql_metrics.pre_post_comparison is not None
    pre_post = response.sql_metrics.pre_post_comparison
    assert pre_post["release_version"] == "v3.2.0"
    assert pre_post["pre_release"]["count"] == 2
    assert pre_post["pre_release"]["negative_count"] == 2
    assert pre_post["post_release"]["count"] == 1
    assert pre_post["post_release"]["negative_count"] == 0

    # Verify Evidence Citations
    assert len(response.evidence.releases) == 1
    assert response.evidence.releases[0].version == "v3.2.0"
    assert len(response.evidence.themes) >= 1
    assert response.evidence.themes[0].theme_name == "Checkout Stability"
    assert len(response.evidence.feedback_quotes) >= 1
    assert len(response.evidence.hindsight_memory_refs) == 1
    assert response.evidence.hindsight_memory_refs[0] == "hind-mem-101"

    # Verify Causal Guardrail
    assert any("correlation" in limit.lower() for limit in response.limitations)


@pytest.mark.anyio
async def test_no_hindsight_memories_found(db_session: Session):
    """Test when Hindsight server is healthy but has no memories matching query."""
    product = "Mobile App"
    seed_product_data(db_session, product)

    transport = MockHindsightTransport(healthy=True, has_memories=False)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)

    response = await HistoricalIntelligenceService.ask(
        session=db_session,
        product=product,
        question="How is user onboarding behaving?",
        hindsight_client=client,
    )

    assert response.hindsight_available is True
    assert response.historical_context is None
    assert response.evidence.hindsight_memory_refs == []
    assert response.sql_metrics.total_feedback == 3


@pytest.mark.anyio
async def test_hindsight_server_offline_graceful_degradation(db_session: Session):
    """Test graceful degradation when Hindsight server is unreachable (no 500, SQL metrics intact)."""
    product = "Mobile App"
    seed_product_data(db_session, product)

    transport = MockHindsightTransport(healthy=False)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)

    response = await HistoricalIntelligenceService.ask(
        session=db_session,
        product=product,
        question="Did checkout improve?",
        hindsight_client=client,
    )

    assert response.hindsight_available is False
    assert response.historical_context is None
    # Grounded PostgreSQL metrics remain fully functional
    assert response.sql_metrics.total_feedback == 3
    assert response.sql_metrics.negative_percentage == 66.7
    # Explicit limitation recorded
    assert any("hindsight" in limit.lower() for limit in response.limitations)


@pytest.mark.anyio
async def test_insufficient_historical_data(db_session: Session):
    """Test product with 0 feedback records returns immediate insufficient data response."""
    product = "Ghost Product"
    client = HindsightClient(base_url=None)

    response = await HistoricalIntelligenceService.ask(
        session=db_session,
        product=product,
        question="Is sentiment positive?",
        hindsight_client=client,
    )

    assert response.product == product
    assert "insufficient" in response.answer.lower()
    assert response.sql_metrics.total_feedback == 0
    assert any("zero" in f.lower() and "feedback" in f.lower() for f in response.key_findings)


@pytest.mark.anyio
async def test_product_isolation(db_session: Session):
    """Ensure data from Product Alpha does not leak into Product Beta."""
    seed_product_data(db_session, "Product Alpha")

    # Add a single feedback for Product Beta
    fb_beta = Feedback(
        product="Product Beta",
        source="csv",
        feedback_text="Beta product has great search.",
        timestamp=datetime.now(timezone.utc),
    )
    db_session.add(fb_beta)
    db_session.commit()

    client = HindsightClient(base_url=None)
    resp_beta = await HistoricalIntelligenceService.ask(
        session=db_session,
        product="Product Beta",
        question="What is the feedback?",
        hindsight_client=client,
    )

    assert resp_beta.product == "Product Beta"
    assert resp_beta.sql_metrics.total_feedback == 1
    # Product Alpha's releases and themes must NOT be in Product Beta's evidence
    assert len(resp_beta.evidence.releases) == 0
    assert len(resp_beta.evidence.themes) == 0


# ---------------------------------------------------------------------------
# API HTTP Endpoint Tests via TestClient
# ---------------------------------------------------------------------------

def test_api_ask_endpoint_success(test_client: TestClient, db_session: Session):
    """Test POST /api/intelligence/ask via FastAPI TestClient."""
    seed_product_data(db_session, "Mobile App")

    transport = MockHindsightTransport(healthy=True, has_memories=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    mock_client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)
    app.dependency_overrides[get_hindsight_client] = lambda: mock_client
    app.dependency_overrides[get_ai_manager] = lambda: None

    payload = {
        "product": "Mobile App",
        "question": "Did checkout complaints improve after our latest release?",
    }
    resp = test_client.post("/api/intelligence/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["product"] == "Mobile App"
    assert "answer" in data
    assert len(data["key_findings"]) >= 1
    assert data["sql_metrics"]["total_feedback"] == 3
    assert data["hindsight_available"] is True
    assert "v3.2.0" in json.dumps(data["evidence"])


def test_api_ask_endpoint_hindsight_offline(test_client: TestClient, db_session: Session):
    """Test POST /api/intelligence/ask when Hindsight is offline."""
    seed_product_data(db_session, "Mobile App")

    transport = MockHindsightTransport(healthy=False)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    mock_client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)
    app.dependency_overrides[get_hindsight_client] = lambda: mock_client
    app.dependency_overrides[get_ai_manager] = lambda: None

    payload = {
        "product": "Mobile App",
        "question": "Are customers still experiencing checkout problems?",
    }
    resp = test_client.post("/api/intelligence/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["hindsight_available"] is False
    assert data["historical_context"] is None
    assert data["sql_metrics"]["total_feedback"] == 3
