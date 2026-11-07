from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, patch
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.feedback import read_bounded_file
from app.core.config import settings
from app.core.exceptions import PayloadTooLargeError
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.feedback import Feedback

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup isolated in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


# 1. Valid CSV upload
def test_valid_csv_upload():
    csv_data = (
        "source,customer_id,feedback_text,product,feature,timestamp,app_version\n"
        "csv,user-101,Great search experience,Storefront,Search,2026-11-01T12:00:00Z,1.2.0\n"
        "csv,user-102,Checkout button is sluggish,Storefront,Checkout,2026-11-02T14:30:00Z,1.2.0\n"
    )
    files = {"file": ("feedback.csv", csv_data.encode("utf-8-sig"), "text/csv")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_records"] == 2
    assert data["inserted_records"] == 2
    assert data["duplicate_records"] == 0
    assert data["rejected_records"] == 0
    assert "Successfully ingested 2" in data["message"]


# 2. Valid JSON upload
def test_valid_json_upload():
    json_data = [
        {
            "source": "json",
            "customer_id": "cust-201",
            "feedback_text": "Dark mode looks amazing",
            "product": "Mobile App",
            "feature": "Theme",
            "timestamp": "2026-11-03T09:15:00Z",
            "app_version": "3.0.1",
        },
        {
            "source": "json",
            "customer_id": "cust-202",
            "feedback_text": "Battery drains quickly while syncing",
            "product": "Mobile App",
            "feature": "Sync",
            "timestamp": "2026-11-03T10:00:00Z",
            "app_version": "3.0.1",
        },
    ]
    files = {"file": ("feedback.json", json.dumps(json_data).encode("utf-8"), "application/json")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_records"] == 2
    assert data["inserted_records"] == 2


# 3. Empty CSV
def test_empty_csv():
    files = {"file": ("empty.csv", b"", "text/csv")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_UPLOAD"


# 4. Malformed CSV (missing required headers)
def test_malformed_csv():
    csv_data = "source,customer_id\n"
    files = {"file": ("malformed.csv", csv_data.encode("utf-8"), "text/csv")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_UPLOAD"
    assert "missing required header" in data["error"]["message"].lower()


# Empty CSV with valid headers returns 0 records
def test_empty_csv_with_valid_headers():
    csv_data = "source,product,feedback_text,timestamp\n"
    files = {"file": ("empty_rows.csv", csv_data.encode("utf-8"), "text/csv")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 0


# 5. Malformed JSON
def test_malformed_json():
    files = {"file": ("bad.json", b"{invalid-json", "application/json")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_UPLOAD"


# 6. JSON root is not an array
def test_json_root_not_array():
    obj = {"source": "json", "feedback_text": "Single object"}
    files = {"file": ("bad_root.json", json.dumps(obj).encode("utf-8"), "application/json")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_UPLOAD"
    assert "array" in data["error"]["message"].lower()


# 7. Unsupported file extension
def test_unsupported_file_extension():
    files = {"file": ("data.xml", b"<xml></xml>", "application/xml")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_UPLOAD"
    assert "unsupported" in data["error"]["message"].lower()


# 8. Missing required fields
def test_missing_required_fields():
    # Missing 'product' and 'source'
    json_data = [
        {
            "feedback_text": "Missing source and product",
            "timestamp": "2026-11-01T12:00:00Z",
        }
    ]
    files = {"file": ("test.json", json.dumps(json_data).encode("utf-8"), "application/json")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["rejected_records"] == 1
    assert data["inserted_records"] == 0
    assert len(data["errors"]) > 0


# 9. Invalid timestamp
def test_invalid_timestamp():
    json_data = [
        {
            "source": "json",
            "product": "Web App",
            "feedback_text": "Invalid timestamp format",
            "timestamp": "not-a-timestamp",
        }
    ]
    files = {"file": ("test.json", json.dumps(json_data).encode("utf-8"), "application/json")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["rejected_records"] == 1
    assert data["errors"][0]["field"] == "timestamp"


# 10. Empty feedback text
def test_empty_feedback_text():
    json_data = [
        {
            "source": "json",
            "product": "Web App",
            "feedback_text": "   ",
            "timestamp": "2026-11-01T12:00:00Z",
        }
    ]
    files = {"file": ("test.json", json.dumps(json_data).encode("utf-8"), "application/json")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["rejected_records"] == 1
    assert data["errors"][0]["field"] == "feedback_text"


# 11. Duplicate rows within one upload
def test_duplicate_rows_within_one_upload():
    json_data = [
        {
            "source": "json",
            "customer_id": "cust-1",
            "product": "Portal",
            "feedback_text": "Identical feedback text",
            "timestamp": "2026-11-01T12:00:00Z",
        },
        {
            "source": "json",
            "customer_id": "cust-1",
            "product": "Portal",
            "feedback_text": "Identical feedback text",
            "timestamp": "2026-11-01T12:00:00Z",
        },
    ]
    files = {"file": ("dups.json", json.dumps(json_data).encode("utf-8"), "application/json")}
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 2
    assert data["inserted_records"] == 1
    assert data["duplicate_records"] == 1
    assert data["status"] == "completed_with_errors"


# 12. Repeated upload of the same data
def test_repeated_upload_of_same_data():
    json_data = [
        {
            "source": "json",
            "customer_id": "cust-repeated",
            "product": "Portal",
            "feedback_text": "Persistent feedback row",
            "timestamp": "2026-11-01T12:00:00Z",
        }
    ]
    payload = json.dumps(json_data).encode("utf-8")
    # First upload
    res1 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("upload1.json", payload, "application/json")},
    )
    assert res1.json()["inserted_records"] == 1
    assert res1.json()["duplicate_records"] == 0

    # Second upload of identical content
    res2 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("upload2.json", payload, "application/json")},
    )
    assert res2.json()["inserted_records"] == 0
    assert res2.json()["duplicate_records"] == 1


# 13. Pagination
def test_feedback_pagination():
    records = [
        {
            "source": "batch",
            "product": "Pagination App",
            "feedback_text": f"Feedback item number {i}",
            "timestamp": f"2026-11-01T{10 + (i // 60):02d}:{i % 60:02d}:00Z",
        }
        for i in range(15)
    ]
    client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("batch.json", json.dumps(records).encode("utf-8"), "application/json")},
    )

    # Page 1 with page_size=5
    res_p1 = client.get(f"{settings.API_V1_PREFIX}/feedback?page=1&page_size=5")
    assert res_p1.status_code == 200
    p1 = res_p1.json()
    assert len(p1["items"]) == 5
    assert p1["total"] == 15
    assert p1["page"] == 1
    assert p1["total_pages"] == 3

    # Page 3 with page_size=5
    res_p3 = client.get(f"{settings.API_V1_PREFIX}/feedback?page=3&page_size=5")
    assert res_p3.status_code == 200
    p3 = res_p3.json()
    assert len(p3["items"]) == 5
    assert p3["page"] == 3


# 14. Product filtering
def test_feedback_product_filtering():
    records = [
        {"source": "test", "product": "AppA", "feedback_text": "Feedback A", "timestamp": "2026-11-01T10:00:00Z"},
        {"source": "test", "product": "AppB", "feedback_text": "Feedback B", "timestamp": "2026-11-01T11:00:00Z"},
    ]
    client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("filter.json", json.dumps(records).encode("utf-8"), "application/json")},
    )

    res_a = client.get(f"{settings.API_V1_PREFIX}/feedback?product=AppA")
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total"] == 1
    assert data_a["items"][0]["product"] == "AppA"


# 15. Source filtering
def test_feedback_source_filtering():
    records = [
        {"source": "zendesk", "product": "App", "feedback_text": "Zendesk ticket", "timestamp": "2026-11-01T10:00:00Z"},
        {"source": "app_store", "product": "App", "feedback_text": "Store review", "timestamp": "2026-11-01T11:00:00Z"},
    ]
    client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("filter_src.json", json.dumps(records).encode("utf-8"), "application/json")},
    )

    res = client.get(f"{settings.API_V1_PREFIX}/feedback?source=app_store")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["source"] == "app_store"


# 16. Individual feedback retrieval
def test_individual_feedback_retrieval():
    records = [{"source": "test", "product": "App", "feedback_text": "Unique individual item", "timestamp": "2026-11-01T10:00:00Z"}]
    client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("item.json", json.dumps(records).encode("utf-8"), "application/json")},
    )
    list_res = client.get(f"{settings.API_V1_PREFIX}/feedback")
    fb_id = list_res.json()["items"][0]["feedback_id"]

    res = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}")
    assert res.status_code == 200
    fb = res.json()
    assert fb["feedback_id"] == fb_id
    assert fb["feedback_text"] == "Unique individual item"


# 17. Unknown feedback ID returns 404
def test_unknown_feedback_id_returns_404():
    random_id = str(uuid.uuid4())
    res = client.get(f"{settings.API_V1_PREFIX}/feedback/{random_id}")
    assert res.status_code == 404
    data = res.json()
    assert data["error"]["code"] == "NOT_FOUND"


# 18. Upload job retrieval
def test_upload_job_retrieval():
    records = [{"source": "test", "product": "App", "feedback_text": "Job track item", "timestamp": "2026-11-01T10:00:00Z"}]
    upload_res = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("track.json", json.dumps(records).encode("utf-8"), "application/json")},
    )
    job_id = upload_res.json()["job_id"]

    job_res = client.get(f"{settings.API_V1_PREFIX}/feedback/jobs/{job_id}")
    assert job_res.status_code == 200
    job = job_res.json()
    assert job["job_id"] == job_id
    assert job["filename"] == "track.json"
    assert job["status"] == "completed"
    assert job["inserted_records"] == 1


# 19. Unknown job ID returns 404
def test_unknown_job_id_returns_404():
    random_id = str(uuid.uuid4())
    res = client.get(f"{settings.API_V1_PREFIX}/feedback/jobs/{random_id}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


# 20. Oversized file rejection (HTTP 413 Payload Too Large)
def test_oversized_file_rejection():
    with patch.object(settings, "MAX_UPLOAD_FILE_SIZE_BYTES", 100):
        oversized_data = b"a" * 150
        files = {"file": ("big.csv", oversized_data, "text/csv")}
        res = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
        assert res.status_code == 413
        assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


# 21. Record limit enforcement
def test_record_limit_enforcement():
    with patch.object(settings, "MAX_UPLOAD_RECORDS", 2):
        records = [
            {"source": "test", "product": "App", "feedback_text": f"Item {i}", "timestamp": "2026-11-01T10:00:00Z"}
            for i in range(5)
        ]
        files = {"file": ("toomany.json", json.dumps(records).encode("utf-8"), "application/json")}
        res = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_UPLOAD"
        assert "exceeds" in res.json()["error"]["message"].lower()


# 22. Database failure handling
def test_database_failure_handling():
    records = [{"source": "test", "product": "App", "feedback_text": "Will fail", "timestamp": "2026-11-01T10:00:00Z"}]
    payload = json.dumps(records).encode("utf-8")

    with patch("sqlalchemy.orm.Session.flush", side_effect=Exception("Simulated DB constraint error")):
        res = client.post(
            f"{settings.API_V1_PREFIX}/feedback/upload",
            files={"file": ("db_fail.json", payload, "application/json")},
        )
        assert res.status_code == 500
        assert res.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"


# === PART 3.1 SPECIFIC TESTS ===

# FIX 1: Bounded file upload reading stops immediately after exceeding ceiling
@pytest.mark.anyio
async def test_bounded_file_reading_stops_early():
    """Verify that read_bounded_file stops reading as soon as max_bytes is exceeded."""
    mock_file = AsyncMock()
    # 10 chunks of 100 bytes each
    mock_file.read.side_effect = [b"x" * 100] * 10
    mock_file.close = AsyncMock()

    # Ceiling is 250 bytes: after 3 chunks (300 bytes), reading must terminate early
    with pytest.raises(PayloadTooLargeError):
        await read_bounded_file(mock_file, max_bytes=250)

    assert mock_file.read.call_count == 3
    mock_file.close.assert_awaited_once()


# FIX 2: Strict Timestamp Validation
def test_strict_timestamp_validation():
    """Verify timestamp parsing: Z accepted, valid offset converted to UTC, naive rejected."""
    # 1. Z format accepted and stored as UTC
    rec_z = [
        {
            "source": "test",
            "product": "App",
            "feedback_text": "UTC timestamp test",
            "timestamp": "2026-11-01T12:00:00Z",
        }
    ]
    res_z = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("utc.json", json.dumps(rec_z).encode("utf-8"), "application/json")},
    )
    assert res_z.status_code == 200
    assert res_z.json()["inserted_records"] == 1

    # 2. Offset format (+05:30) accepted and converted to UTC (12:00:00Z)
    rec_offset = [
        {
            "source": "test",
            "product": "App",
            "feedback_text": "Offset timestamp test",
            "timestamp": "2026-11-01T17:30:00+05:30",
        }
    ]
    res_offset = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("offset.json", json.dumps(rec_offset).encode("utf-8"), "application/json")},
    )
    assert res_offset.status_code == 200
    assert res_offset.json()["inserted_records"] == 1

    # Query feedback to verify stored timestamp is converted to UTC
    fb_res = client.get(f"{settings.API_V1_PREFIX}/feedback?product=App")
    items = fb_res.json()["items"]
    offset_item = next(it for it in items if it["feedback_text"] == "Offset timestamp test")
    assert "2026-11-01T12:00:00" in offset_item["timestamp"]

    # 3. Naive timestamp rejected
    rec_naive = [
        {
            "source": "test",
            "product": "App",
            "feedback_text": "Naive timestamp test",
            "timestamp": "2026-11-01T12:00:00",
        }
    ]
    res_naive = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("naive.json", json.dumps(rec_naive).encode("utf-8"), "application/json")},
    )
    assert res_naive.status_code == 200
    assert res_naive.json()["rejected_records"] == 1
    assert "explicit timezone" in res_naive.json()["errors"][0]["error"]


# FIX 3: Cross-source feedback preservation
def test_cross_source_feedback_preservation():
    """Verify that identical feedback text/time from different sources are preserved, not deduplicated."""
    rec_zendesk = [
        {
            "source": "zendesk",
            "customer_id": "user-404",
            "product": "Store",
            "feedback_text": "Cart checkout failed with error 500",
            "timestamp": "2026-11-01T14:00:00Z",
        }
    ]
    rec_store = [
        {
            "source": "app_store",
            "customer_id": "user-404",
            "product": "Store",
            "feedback_text": "Cart checkout failed with error 500",
            "timestamp": "2026-11-01T14:00:00Z",
        }
    ]
    res1 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("zd.json", json.dumps(rec_zendesk).encode("utf-8"), "application/json")},
    )
    res2 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("as.json", json.dumps(rec_store).encode("utf-8"), "application/json")},
    )
    assert res1.json()["inserted_records"] == 1
    assert res2.json()["inserted_records"] == 1
    assert res2.json()["duplicate_records"] == 0


# FIX 3: Anonymous feedback handling
def test_anonymous_feedback_handling():
    """Verify consistent handling of anonymous (null customer_id) feedback and repeated uploads."""
    rec_anon = [
        {
            "source": "web_survey",
            "customer_id": None,
            "product": "Analytics",
            "feedback_text": "Navigation is confusing",
            "timestamp": "2026-11-01T15:00:00Z",
        }
    ]
    payload = json.dumps(rec_anon).encode("utf-8")
    res1 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("anon1.json", payload, "application/json")},
    )
    assert res1.json()["inserted_records"] == 1
    assert res1.json()["duplicate_records"] == 0

    # Repeated upload of the exact same anonymous record is flagged as duplicate
    res2 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("anon2.json", payload, "application/json")},
    )
    assert res2.json()["inserted_records"] == 0
    assert res2.json()["duplicate_records"] == 1


# FIX 3: Soft-deleted feedback allows re-uploading identical feedback
def test_soft_deleted_feedback_allows_reupload():
    """Verify that a soft-deleted record does not block active re-upload of identical feedback."""
    rec = [
        {
            "source": "chat",
            "customer_id": "u-soft",
            "product": "Portal",
            "feedback_text": "Need dark mode immediately",
            "timestamp": "2026-11-01T16:00:00Z",
        }
    ]
    payload = json.dumps(rec).encode("utf-8")
    res1 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("chat1.json", payload, "application/json")},
    )
    assert res1.json()["inserted_records"] == 1

    # Soft delete the inserted record
    fb_list = client.get(f"{settings.API_V1_PREFIX}/feedback?product=Portal").json()["items"]
    fb_id = fb_list[0]["feedback_id"]

    # Access database session through test setup to mark deleted_at
    # Using client to verify 404 after soft-delete
    # Manually soft-delete via direct update
    db_session = next(app.dependency_overrides[get_db]())
    db_fb = db_session.get(Feedback, uuid.UUID(fb_id))
    assert db_fb is not None
    db_fb.deleted_at = datetime.now(timezone.utc)
    db_session.commit()
    db_session.close()

    # Verify GET single feedback returns 404 for soft-deleted record
    get_res = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}")
    assert get_res.status_code == 404

    # Now re-upload identical feedback: should be inserted as new active record
    res2 = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("chat2.json", payload, "application/json")},
    )
    assert res2.json()["inserted_records"] == 1
    assert res2.json()["duplicate_records"] == 0


# FIX 4: Job failure persistence on unexpected exceptions
def test_unexpected_exception_persists_failed_job():
    """Verify that unexpected exceptions persist a 'failed' job state without getting stuck in 'processing'."""
    rec = [{"source": "test", "product": "App", "feedback_text": "Boom", "timestamp": "2026-11-01T12:00:00Z"}]
    payload = json.dumps(rec).encode("utf-8")

    # Simulate unexpected runtime error during row processing
    with patch("app.services.feedback_ingestion.parse_json_content", side_effect=RuntimeError("Unexpected memory fault")):
        res = client.post(
            f"{settings.API_V1_PREFIX}/feedback/upload",
            files={"file": ("crash.json", payload, "application/json")},
        )
        assert res.status_code == 500

    # Verify stored job in DB was updated to 'failed' and not stuck in 'processing'
    db_session = next(app.dependency_overrides[get_db]())
    from app.models.upload_job import UploadJob
    job = db_session.query(UploadJob).filter(UploadJob.filename == "crash.json").first()
    assert job is not None
    assert job.status == "failed"
    assert "unexpected error" in job.error_summary.lower()
    assert job.completed_at is not None
    db_session.close()


# FIX 5: CSV header validation rejects missing headers upfront
def test_csv_missing_required_headers():
    """Verify that a CSV missing required headers is rejected upfront with a clear error."""
    csv_missing = "name,email,score\nAlice,alice@example.com,5\n"
    files = {"file": ("bad_headers.csv", csv_missing.encode("utf-8"), "text/csv")}
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/upload", files=files)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_UPLOAD"
    assert "missing required header" in res.json()["error"]["message"].lower()


# FIX 6: Content-Type Validation
def test_content_type_validation():
    """Verify content type handling: invalid rejected, standard accepted."""
    valid_csv = "source,product,feedback_text,timestamp\ncsv,App,Hello,2026-11-01T12:00:00Z\n"

    # Incompatible content type for CSV
    res_bad = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("data.csv", valid_csv.encode("utf-8"), "image/png")},
    )
    assert res_bad.status_code == 400
    assert "incompatible content-type" in res_bad.json()["error"]["message"].lower()

    # Allowed content type for CSV
    res_good = client.post(
        f"{settings.API_V1_PREFIX}/feedback/upload",
        files={"file": ("data.csv", valid_csv.encode("utf-8"), "text/csv")},
    )
    assert res_good.status_code == 200
    assert res_good.json()["inserted_records"] == 1
