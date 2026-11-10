"""Comprehensive tests for Hindsight Persistent Memory Integration (Part 9).

Covers:
1. HindsightClient operations (health_check, ensure_bank, retain, recall, reflect).
2. Deterministic and isolated memory bank ID derivation.
3. Selective PostgreSQL curation (5 memory types: feedback, theme, snapshot, release, insight).
4. Deduplication via MemoryMetadata (re-sync skips already retained records).
5. Dry-run simulation (counts candidates without persistence).
6. Recall with local PostgreSQL provenance enrichment.
7. Reflect with separation of concerns and mandatory analytical disclaimer.
8. Graceful degradation when Hindsight server is offline or unconfigured (no uncaught 500s).
9. Full FastAPI HTTP API routes tested via TestClient.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.memory import get_hindsight_client
from app.db.base import Base
from app.db.session import get_db
from app.integrations.hindsight.client import HindsightClient
from app.main import app
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.insight import Insight
from app.models.memory import MemoryMetadata
from app.models.product_change import ProductChanges
from app.models.theme import Theme, ThemeSnapshot
from app.services import hindsight_service


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
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_hindsight_client, None)


# ---------------------------------------------------------------------------
# Mock Transport for Hindsight HTTP Client
# ---------------------------------------------------------------------------

class MockHindsightTransport(httpx.AsyncBaseTransport):
    """Simulated Hindsight REST API HTTP transport."""

    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy
        self.retained_items: List[Dict[str, Any]] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not self.healthy:
            raise httpx.ConnectError("Connection refused to Hindsight", request=request)

        path = request.url.path

        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})

        if path.endswith("/banks") and request.method == "POST":
            return httpx.Response(201, json={"status": "created"})

        if "/memories/recall" in path:
            body = json.loads(request.content.decode("utf-8"))
            query = body.get("query", "")
            return httpx.Response(200, json={
                "memories": [
                    {
                        "id": "hind-mem-001",
                        "content": f"Historical memory relevant to '{query}'",
                        "context": "feature=checkout",
                    }
                ]
            })

        if "/reflect" in path:
            body = json.loads(request.content.decode("utf-8"))
            query = body.get("query", "")
            return httpx.Response(200, json={
                "reasoning": f"Synthesized historical trend analysis for: {query}",
                "memories": [
                    {
                        "id": "hind-mem-001",
                        "content": "Historical memory citation",
                    }
                ]
            })

        if "/memories" in path and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            mem_id = f"hind-mem-{uuid.uuid4().hex[:8]}"
            self.retained_items.append({"id": mem_id, **body})
            return httpx.Response(201, json={"id": mem_id, "status": "stored"})

        return httpx.Response(404, json={"error": "Not Found"})


# ---------------------------------------------------------------------------
# Unit Tests: Bank ID & Client
# ---------------------------------------------------------------------------

def test_bank_id_derivation():
    """Verify deterministic, isolated, URL-safe bank ID generation."""
    bank1 = hindsight_service.get_bank_id_for_product("Mobile App")
    bank2 = hindsight_service.get_bank_id_for_product("mobile-app")
    bank3 = hindsight_service.get_bank_id_for_product("Web Dashboard")

    assert bank1 == bank2  # normalized
    assert bank1 != bank3
    assert bank1.startswith("bank-mobile-app-")
    assert all(c.isalnum() or c in "-_" for c in bank1)


@pytest.mark.anyio
async def test_unconfigured_client():
    """Unconfigured client handles calls gracefully without network errors."""
    client = HindsightClient(base_url=None)
    assert not client.is_configured
    assert await client.health_check() is False
    assert await client.ensure_bank("bank-test") is False
    assert await client.retain("bank-test", "content") is None

    recall = await client.recall("bank-test", "query")
    assert recall["success"] is False
    assert recall["memories"] == []

    reflect = await client.reflect("bank-test", "query")
    assert reflect["success"] is False
    assert reflect["reasoning"] is None


@pytest.mark.anyio
async def test_configured_client_operations():
    """Configured client with mock transport succeeds on REST endpoints."""
    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(
        base_url="http://mock-hindsight:8888",
        api_key="secret-key",
        async_client=async_client,
    )

    assert client.is_configured
    assert await client.health_check() is True
    assert await client.ensure_bank("bank-test") is True

    mem_id = await client.retain("bank-test", "High battery usage reported", "app_version=2.1")
    assert mem_id is not None
    assert mem_id.startswith("hind-mem-")

    recall = await client.recall("bank-test", "battery issue")
    assert recall["success"] is True
    assert len(recall["memories"]) == 1
    assert recall["memories"][0]["id"] == "hind-mem-001"

    reflect = await client.reflect("bank-test", "Why did battery complaints increase?")
    assert reflect["success"] is True
    assert "battery complaints" in reflect["reasoning"]


@pytest.mark.anyio
async def test_client_server_down_degradation():
    """Client handles server downtime gracefully without unhandled exceptions."""
    transport = MockHindsightTransport(healthy=False)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(
        base_url="http://mock-hindsight:8888",
        async_client=async_client,
    )

    assert await client.health_check() is False
    assert await client.ensure_bank("bank-test") is False
    assert await client.retain("bank-test", "test content") is None

    recall = await client.recall("bank-test", "query")
    assert recall["success"] is False
    assert "unreachable" in recall["error"].lower()

    reflect = await client.reflect("bank-test", "query")
    assert reflect["success"] is False
    assert "unreachable" in reflect["error"].lower()


# ---------------------------------------------------------------------------
# Integration Tests: Selective Curation, Deduplication, and Provenance
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sync_curation_deduplication_and_dry_run(db_session: Session):
    """Test curation across all 5 memory types, deduplication, and dry-run."""
    product = "Mobile App"
    now = datetime.now(timezone.utc)

    # 1. Feedback + Classification
    # Fb 1: High signal negative complaint (should be curated)
    fb1 = Feedback(
        product=product,
        source="csv",
        feedback_text="Checkout button crashes continuously!",
        timestamp=now,
    )
    db_session.add(fb1)
    db_session.flush()
    clf1 = FeedbackClassification(
        feedback_id=fb1.feedback_id,
        classification_version="v1.0",
        run_number=1,
        sentiment_score=-0.85,
        confidence_score=0.95,
        overall_sentiment="negative",
        sentiment_intensity="high",
        customer_intent="complaint",
        classified_at=now,
    )
    db_session.add(clf1)

    # Fb 2: Low signal neutral comment (should be skipped by curation)
    fb2 = Feedback(
        product=product,
        source="csv",
        feedback_text="Everything is okay.",
        timestamp=now,
    )
    db_session.add(fb2)
    db_session.flush()
    clf2 = FeedbackClassification(
        feedback_id=fb2.feedback_id,
        classification_version="v1.0",
        run_number=1,
        sentiment_score=0.05,
        confidence_score=0.6,
        overall_sentiment="neutral",
        sentiment_intensity="low",
        customer_intent="other",
        classified_at=now,
    )
    db_session.add(clf2)

    # Fb 3: Soft-deleted feedback (should be skipped)
    fb3 = Feedback(
        product=product,
        source="csv",
        feedback_text="Soft deleted feedback",
        timestamp=now,
        deleted_at=now,
    )
    db_session.add(fb3)
    db_session.flush()

    # 2. Theme
    th = Theme(
        product=product,
        theme_name="Checkout Failures",
        description="Failures during checkout process",
        category="bug",
        status="active",
        created_at=now,
    )
    db_session.add(th)
    db_session.flush()

    # 3. ThemeSnapshot
    snap = ThemeSnapshot(
        theme_id=th.theme_id,
        period_start=now,
        period_end=now,
        feedback_count=10,
        positive_count=1,
        negative_count=9,
        neutral_count=0,
        sentiment_average=-0.8,
    )
    db_session.add(snap)

    # 4. ProductChanges
    rel = ProductChanges(
        product=product,
        version="v2.4.0",
        feature="Checkout",
        release_description="Redesigned payment flow",
        release_date=now,
        change_category="feature_launch",
    )
    db_session.add(rel)

    # 5. Insight
    ins = Insight(
        title="Payment gateway dropoff",
        summary="High dropoff during payment gateway redirect",
        recommendation="Fix timeout threshold in checkout client",
        confidence_score=0.9,
        status="active",
        created_at=now,
    )
    db_session.add(ins)
    db_session.commit()

    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)

    # Step A: Dry Run
    dry_resp = await hindsight_service.sync_product_memories(
        session=db_session,
        product=product,
        client=client,
        dry_run=True,
    )
    assert dry_resp.dry_run is True
    assert dry_resp.synced_count == 5  # fb1, th, snap, rel, ins
    assert dry_resp.details["customer_feedback"] == 1
    assert dry_resp.details["theme_trajectory"] == 1
    assert dry_resp.details["temporal_shift"] == 1
    assert dry_resp.details["product_release"] == 1
    assert dry_resp.details["synthesized_insight"] == 1

    # Verify no records written to MemoryMetadata in dry-run
    db_count = db_session.scalar(select(MemoryMetadata).where(MemoryMetadata.bank_id == dry_resp.bank_id))
    assert db_count is None

    # Step B: Live Sync
    sync_resp = await hindsight_service.sync_product_memories(
        session=db_session,
        product=product,
        client=client,
        dry_run=False,
    )
    assert sync_resp.dry_run is False
    assert sync_resp.synced_count == 5
    assert sync_resp.skipped_count == 0
    assert sync_resp.failed_count == 0

    # Verify MemoryMetadata records in DB
    records = db_session.scalars(select(MemoryMetadata).where(MemoryMetadata.bank_id == sync_resp.bank_id)).all()
    assert len(records) == 5
    types = {r.memory_type for r in records}
    assert types == {
        "customer_feedback",
        "theme_trajectory",
        "temporal_shift",
        "product_release",
        "synthesized_insight",
    }

    # Step C: Re-sync to verify deduplication
    resync_resp = await hindsight_service.sync_product_memories(
        session=db_session,
        product=product,
        client=client,
        dry_run=False,
    )
    assert resync_resp.synced_count == 0
    assert resync_resp.skipped_count == 5  # all 5 skipped!


@pytest.mark.anyio
async def test_recall_with_provenance_enrichment(db_session: Session):
    """Test that recalled memories are enriched with PostgreSQL provenance."""
    product = "Web Dashboard"
    bank_id = hindsight_service.get_bank_id_for_product(product)

    # Seed MemoryMetadata matching mock recall ID 'hind-mem-001'
    meta = MemoryMetadata(
        bank_id=bank_id,
        hindsight_memory_id="hind-mem-001",
        memory_type="customer_feedback",
        source_entity_type="feedback",
        source_reference="feedback:00000000-0000-0000-0000-000000000001",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(meta)
    db_session.commit()

    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)

    recall_resp = await hindsight_service.recall_memories(
        session=db_session,
        product=product,
        query="checkout problem",
        limit=5,
        client=client,
    )

    assert recall_resp.available is True
    assert len(recall_resp.memories) == 1
    recalled = recall_resp.memories[0]
    assert recalled.hindsight_memory_id == "hind-mem-001"
    assert recalled.memory_id == meta.memory_id
    assert recalled.source_reference == "feedback:00000000-0000-0000-0000-000000000001"
    assert recalled.source_entity_type == "feedback"
    assert recalled.memory_type == "customer_feedback"


@pytest.mark.anyio
async def test_reflect_with_disclaimer_and_provenance(db_session: Session):
    """Test that reflect returns synthesized reasoning and analytical disclaimer."""
    product = "Mobile App"
    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)

    reflect_resp = await hindsight_service.reflect_on_memories(
        session=db_session,
        product=product,
        query="How have customer complaints shifted over the last two versions?",
        client=client,
    )

    assert reflect_resp.available is True
    assert reflect_resp.reasoning is not None
    assert "Synthesized historical trend analysis" in reflect_resp.reasoning
    assert len(reflect_resp.supporting_memories) == 1
    # Check mandatory disclaimer
    assert "derived authoritatively from PostgreSQL" in reflect_resp.disclaimer


# ---------------------------------------------------------------------------
# API Routes Tests via TestClient
# ---------------------------------------------------------------------------

def test_api_status_endpoint(test_client: TestClient, db_session: Session):
    """Test GET /api/memory/status endpoint."""
    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    mock_client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)

    app.dependency_overrides[get_hindsight_client] = lambda: mock_client

    resp = test_client.get("/api/memory/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["available"] is True
    assert data["total_synced_memories"] == 0
    assert data["bank_count"] == 0


def test_api_sync_endpoint(test_client: TestClient, db_session: Session):
    """Test POST /api/memory/sync endpoint."""
    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    mock_client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)
    app.dependency_overrides[get_hindsight_client] = lambda: mock_client

    payload = {"product": "Mobile App", "dry_run": True}
    resp = test_client.post("/api/memory/sync", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["product"] == "Mobile App"
    assert data["dry_run"] is True
    assert "bank_id" in data


def test_api_recall_endpoint(test_client: TestClient, db_session: Session):
    """Test POST /api/memory/recall endpoint."""
    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    mock_client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)
    app.dependency_overrides[get_hindsight_client] = lambda: mock_client

    payload = {"product": "Mobile App", "query": "login issues", "limit": 3}
    resp = test_client.post("/api/memory/recall", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert len(data["memories"]) == 1
    assert data["memories"][0]["hindsight_memory_id"] == "hind-mem-001"


def test_api_reflect_endpoint(test_client: TestClient, db_session: Session):
    """Test POST /api/memory/reflect endpoint."""
    transport = MockHindsightTransport(healthy=True)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    mock_client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)
    app.dependency_overrides[get_hindsight_client] = lambda: mock_client

    payload = {"product": "Mobile App", "query": "summarize user sentiment trajectory"}
    resp = test_client.post("/api/memory/reflect", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert "Synthesized" in data["reasoning"]
    assert "derived authoritatively from PostgreSQL" in data["disclaimer"]


def test_api_degraded_server_offline(test_client: TestClient, db_session: Session):
    """Test API behavior when Hindsight server is offline (graceful degradation, no 500 error)."""
    transport = MockHindsightTransport(healthy=False)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://mock-hindsight:8888")
    mock_client = HindsightClient(base_url="http://mock-hindsight:8888", async_client=async_client)
    app.dependency_overrides[get_hindsight_client] = lambda: mock_client

    # Recall during server outage
    recall_resp = test_client.post("/api/memory/recall", json={"product": "Mobile App", "query": "crash"})
    assert recall_resp.status_code == 200
    assert recall_resp.json()["available"] is False
    assert recall_resp.json()["memories"] == []

    # Reflect during server outage
    reflect_resp = test_client.post("/api/memory/reflect", json={"product": "Mobile App", "query": "trend"})
    assert reflect_resp.status_code == 200
    assert reflect_resp.json()["available"] is False
    assert reflect_resp.json()["reasoning"] is None
