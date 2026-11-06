from datetime import datetime, timezone
from unittest.mock import patch
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.feedback import Feedback
from app.services.text_normalization import normalize_text
from app.services.pii_detector import PIIDetector
from app.services.spam_detector import SpamAndQualityDetector
from app.services.quality_scorer import QualityScorer
from app.services.feedback_cleaning import FeedbackCleaningService, CURRENT_CLEANING_VERSION

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


def create_sample_feedback(
    text: str = "Great product! Works well.",
    product: str = "Storefront",
    feature: str = "Search",
    customer_id: str = "user-1",
    source: str = "web",
    app_version: str = "1.0.0",
) -> str:
    """Helper to create a raw feedback entry directly via DB."""
    fb_uuid = uuid.uuid4()
    db = next(app.dependency_overrides[get_db]())
    feedback = Feedback(
        feedback_id=fb_uuid,
        source=source,
        customer_id=customer_id,
        feedback_text=text,
        product=product,
        feature=feature,
        app_version=app_version,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(feedback)
    db.commit()
    db.close()
    return str(fb_uuid)


# ==============================================================================
# 1. TEXT NORMALIZATION TESTS (INCLUDING TECHNICAL AND HTML PRESERVATION)
# ==============================================================================

def test_normalization_whitespace_collapsing():
    raw = "Multiple    spaces \t and \t\ttabs should be  collapsed."
    cleaned = normalize_text(raw)
    assert cleaned == "Multiple spaces and tabs should be collapsed."


def test_normalization_line_endings():
    raw = "Line 1\r\nLine 2\rLine 3\n\n\n\nLine 4"
    cleaned = normalize_text(raw)
    assert cleaned == "Line 1\nLine 2\nLine 3\n\nLine 4"


def test_normalization_unicode_nfc():
    decomposed = "Cafe\u0301"
    cleaned = normalize_text(decomposed)
    assert cleaned == "Café"


def test_normalization_emoji_preservation():
    raw = "The app is totally broken! 😡 But support was nice 👍 🚀"
    cleaned = normalize_text(raw)
    assert "😡" in cleaned
    assert "👍" in cleaned
    assert "🚀" in cleaned
    assert cleaned == "The app is totally broken! 😡 But support was nice 👍 🚀"


def test_normalization_preserves_code_generics_and_comparisons():
    # Technical feedback with generics, operators, and comparisons must survive intact
    raw = (
        "In Map<String, Object> and List<User>, "
        "if x < y and y > z: check response.status_code < 500."
    )
    cleaned = normalize_text(raw)
    assert "Map<String, Object>" in cleaned
    assert "List<User>" in cleaned
    assert "if x < y and y > z:" in cleaned
    assert "response.status_code < 500" in cleaned


def test_normalization_genuine_and_encoded_html():
    # Genuine HTML tags stripped; encoded HTML decoded then stripped; inner text preserved
    raw = "<p>Welcome to <b>our</b> site!</p> <script>alert('xss')</script> &lt;script&gt;bad()&lt;/script&gt;"
    cleaned = normalize_text(raw)
    assert "<p>" not in cleaned
    assert "<b>" not in cleaned
    assert "<script>" not in cleaned
    assert "&lt;script&gt;" not in cleaned
    assert "Welcome to our site!" in cleaned
    assert "alert('xss')" in cleaned
    assert "bad()" in cleaned


def test_normalization_control_characters_stripped():
    raw = "Clean\x00 text\x07 with\x1b control\x08 characters."
    cleaned = normalize_text(raw)
    assert cleaned == "Clean text with control characters."


def test_normalization_preserves_punctuation_and_capitalization():
    raw = "I LOVE THIS FEATURE!!! Really, why wasn't this added earlier?"
    cleaned = normalize_text(raw)
    assert cleaned == "I LOVE THIS FEATURE!!! Really, why wasn't this added earlier?"


# ==============================================================================
# 2. PII DETECTION AND REDACTION TESTS
# ==============================================================================

def test_pii_email_detection_and_redaction():
    text = "Please reach out to support@mycompany.org or ceo.jane+alert@startup.io for help."
    redacted, detected, pii_types = PIIDetector.redact_pii(text)
    assert detected is True
    assert "email" in pii_types
    assert "support@mycompany.org" not in redacted
    assert "ceo.jane+alert@startup.io" not in redacted
    assert "[EMAIL]" in redacted


def test_pii_international_phones():
    samples = [
        ("UK mobile: call +44 20 7946 0958 tomorrow", "+44 20 7946 0958"),
        ("France office: contact 01 40 00 00 00 now", "01 40 00 00 00"),
        ("Germany phone: +49 30 123456 reached", "+49 30 123456"),
        ("India support: +91 98765 43210 available", "+91 98765 43210"),
        ("US desk: (800) 123-4567 available", "(800) 123-4567"),
    ]
    for text, raw_num in samples:
        redacted, detected, pii_types = PIIDetector.redact_pii(text)
        assert detected is True, f"Failed to detect {raw_num}"
        assert "phone" in pii_types
        assert raw_num not in redacted
        assert "[PHONE]" in redacted


def test_pii_phone_negative_cases():
    # Dates, timestamps, and order numbers should NOT be redacted as phone numbers
    text = "Order ORD-1234-5678 created at 2026-11-06 08:45:00 UTC."
    redacted, detected, pii_types = PIIDetector.redact_pii(text)
    assert "2026-11-06" in redacted
    assert "ORD-1234-5678" in redacted
    assert "phone" not in pii_types


def test_pii_url_sanitization():
    # Host and path preserved, sensitive query parameters redacted
    text = "Error calling https://api.example.com/v2/orders?token=SECRET_123&client_id=42 for details."
    redacted, detected, pii_types = PIIDetector.redact_pii(text)
    assert detected is True
    assert "url" in pii_types
    assert "SECRET_123" not in redacted
    assert "token=%5BREDACTED%5D" in redacted or "token=[REDACTED]" in redacted
    assert "https://api.example.com/v2/orders" in redacted
    assert "client_id=42" in redacted


def test_pii_url_credentials_removed():
    text = "Access database at https://admin:supersecret@cluster.internal/status for info."
    redacted, detected, pii_types = PIIDetector.redact_pii(text)
    assert detected is True
    assert "supersecret" not in redacted
    assert "admin@" not in redacted
    assert "cluster.internal/status" in redacted


def test_pii_ipv4_vs_software_versions():
    # Valid IPv4 is redacted; software versions and invalid octets are preserved
    text = (
        "Server 192.168.1.100 failed running client v1.2.0.0 on build 10.0.19041.1 "
        "with gateway 256.300.1.1"
    )
    redacted, detected, pii_types = PIIDetector.redact_pii(text)
    assert detected is True
    assert "ip_address" in pii_types
    assert "192.168.1.100" not in redacted
    assert "[IP_ADDRESS]" in redacted
    # Software versions must NOT be redacted
    assert "1.2.0.0" in redacted
    assert "10.0.19041.1" in redacted
    assert "256.300.1.1" in redacted  # Invalid IPv4 octets


def test_pii_id_detection_and_redaction():
    text = "My SSN is 123-45-6789 and card is 4532-1234-5678-9012."
    redacted, detected, pii_types = PIIDetector.redact_pii(text)
    assert detected is True
    assert "ssn" in pii_types
    assert "credit_card" in pii_types
    assert "123-45-6789" not in redacted
    assert "4532-1234-5678-9012" not in redacted
    assert "[ID_NUMBER]" in redacted


def test_pii_no_leakage_and_original_unaffected():
    original = "My email is secret_user@domain.com, please fix the bug."
    fb_id = create_sample_feedback(text=original)

    db = next(app.dependency_overrides[get_db]())
    feedback = db.query(Feedback).filter(Feedback.feedback_id == uuid.UUID(fb_id)).first()
    FeedbackCleaningService.clean_single_record(feedback)
    db.commit()

    assert feedback.feedback_text == original
    assert "secret_user@domain.com" not in feedback.cleaned_feedback_text
    assert "[EMAIL]" in feedback.cleaned_feedback_text
    assert feedback.pii_detected is True
    assert feedback.pii_types == ["email"]
    db.close()


# ==============================================================================
# 3. MULTILINGUAL AND SPAM DETECTION TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "text,expected_lang",
    [
        ("素晴らしいアプリです", "Japanese"),
        ("很好用", "Chinese"),
        ("यह ऐप बहुत अच्छा है", "Hindi"),
        ("التطبيق لا يعمل", "Arabic"),
        ("Приложение работает хорошо", "Russian"),
        ("The app works perfectly", "English"),
    ],
)
def test_multilingual_feedback_survives_meaningless_check(text, expected_lang):
    status, flags = SpamAndQualityDetector.assess_quality(text)
    assert "MEANINGLESS_TEXT" not in flags, f"Falsely rejected {expected_lang} as meaningless"
    assert "EMPTY_TEXT" not in flags
    assert status == "clean"


def test_spam_empty_and_whitespace():
    status, flags = SpamAndQualityDetector.assess_quality("")
    assert "EMPTY_TEXT" in flags
    assert status == "rejected"

    status_ws, flags_ws = SpamAndQualityDetector.assess_quality("   \n\t  ")
    assert "EMPTY_TEXT" in flags_ws
    assert status_ws == "rejected"


def test_spam_punctuation_only_rejected():
    status, flags = SpamAndQualityDetector.assess_quality("??? !!! ... ---")
    assert "MEANINGLESS_TEXT" in flags
    assert status == "rejected"


def test_spam_keyboard_mash():
    status, flags = SpamAndQualityDetector.assess_quality("asdfghjkl zxcvbnm qwertyuiop")
    assert "MEANINGLESS_TEXT" in flags
    assert status == "flagged"


def test_spam_repeated_characters():
    text = "Noooooooooooooooo waaaaaaaaaay this works"
    status, flags = SpamAndQualityDetector.assess_quality(text)
    assert "REPEATED_CHARS" in flags
    assert status == "flagged"


def test_spam_phrases():
    text = "Buy cheap products now and click here to win"
    status, flags = SpamAndQualityDetector.assess_quality(text)
    assert "SPAM_PATTERN" in flags
    assert status == "flagged"


def test_spam_url_only():
    text = "https://spamsite.org/promo"
    status, flags = SpamAndQualityDetector.assess_quality(text)
    assert "URL_ONLY" in flags
    assert status == "flagged"


def test_negative_review_not_penalized_or_rejected():
    text = "Horrible service, worst app update ever, totally broken and I hate it."
    status, flags = SpamAndQualityDetector.assess_quality(text)
    assert status == "clean"

    content_score = QualityScorer.calculate_content_quality_score(
        text=text,
        quality_status=status,
        quality_flags=flags,
    )
    assert content_score >= 90.0


# ==============================================================================
# 4. QUALITY SCORING: CONTENT QUALITY VS METADATA COMPLETENESS
# ==============================================================================

def test_anonymous_feedback_receives_full_content_quality():
    detailed_text = "The new checkout flow crashes whenever a user enters a billing address with special characters."
    status, flags = SpamAndQualityDetector.assess_quality(detailed_text)

    overall, content_score, meta_score = QualityScorer.calculate_score(
        text=detailed_text,
        quality_status=status,
        quality_flags=flags,
        has_customer_id=False,  # Anonymous
        has_feature=False,      # Untagged
        has_app_version=False,  # No version
    )

    # Content quality must NOT be penalized for missing metadata
    assert content_score == 100.0
    assert overall == 100.0
    assert meta_score == 0.0


def test_metadata_completeness_calculation():
    score_full = QualityScorer.calculate_metadata_completeness_score(
        has_customer_id=True,
        has_feature=True,
        has_app_version=True,
    )
    assert score_full == 100.0

    score_partial = QualityScorer.calculate_metadata_completeness_score(
        has_customer_id=True,
        has_feature=False,
        has_app_version=False,
    )
    assert score_partial == 35.0


# ==============================================================================
# 5. PROCESSING, BATCH SAFETY, AND ENDPOINT TESTS
# ==============================================================================

def test_endpoint_clean_single_record():
    raw_text = "The search bar lags terribly when typing fast."
    fb_id = create_sample_feedback(text=raw_text)

    response = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/clean")
    assert response.status_code == 200
    data = response.json()

    assert data["feedback_id"] == fb_id
    assert data["cleaned_feedback_text"] == raw_text
    assert data["feedback_text"] == raw_text
    assert data["quality_status"] == "clean"
    assert data["content_quality_score"] >= 80.0
    assert data["metadata_completeness_score"] == 100.0
    assert data["cleaning_version"] == CURRENT_CLEANING_VERSION
    assert data["processing_status"] == "processed"


def test_endpoint_clean_single_record_404():
    non_existent_id = str(uuid.uuid4())
    response = client.post(f"{settings.API_V1_PREFIX}/feedback/{non_existent_id}/clean")
    assert response.status_code == 404
    body = response.json()
    error_msg = body.get("error", {}).get("message", "") or body.get("detail", "")
    assert "not found" in error_msg.lower()


def test_endpoint_get_quality_single_record():
    raw_text = "Contact support at test@example.com immediately."
    fb_id = create_sample_feedback(text=raw_text)

    client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/clean")

    response = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/quality")
    assert response.status_code == 200
    data = response.json()

    assert data["feedback_id"] == fb_id
    assert data["content_quality_score"] is not None
    assert data["metadata_completeness_score"] is not None
    assert data["pii_detected"] is True
    assert "email" in data["pii_types"]
    assert "[EMAIL]" in data["cleaned_feedback_text"]
    assert "test@example.com" not in data["cleaned_feedback_text"]


def test_endpoint_batch_clean():
    create_sample_feedback(text="Feedback one", product="ProdA")
    create_sample_feedback(text="Feedback two", product="ProdA")
    create_sample_feedback(text="Feedback three", product="ProdB")

    response = client.post(
        f"{settings.API_V1_PREFIX}/feedback/clean",
        params={"product": "ProdA", "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_considered"] == 2
    assert data["processed"] == 2
    assert data["clean_count"] == 2
    assert data["skipped"] == 0
    assert data["failed_count"] == 0


def test_batch_clean_failure_isolation():
    # Verify that an unexpected failure on one record does not abort subsequent records
    fb1 = create_sample_feedback(text="First record succeeds")
    fb2 = create_sample_feedback(text="Second record will fail")
    fb3 = create_sample_feedback(text="Third record succeeds")

    original_clean = FeedbackCleaningService.clean_single_record

    def mock_clean(record, reprocess=False, version=CURRENT_CLEANING_VERSION):
        if record.feedback_text == "Second record will fail":
            raise RuntimeError("Simulated corruption on record 2")
        return original_clean(record, reprocess=reprocess, version=version)

    with patch.object(FeedbackCleaningService, "clean_single_record", side_effect=mock_clean):
        db = next(app.dependency_overrides[get_db]())
        result = FeedbackCleaningService.clean_feedback_batch(session=db, limit=10)
        db.close()

    assert result["total_considered"] == 3
    assert result["processed"] == 2
    assert result["failed_count"] == 1


def test_batch_clean_idempotency():
    create_sample_feedback(text="Solid experience!")

    res1 = client.post(f"{settings.API_V1_PREFIX}/feedback/clean")
    assert res1.json()["processed"] >= 1

    res2 = client.post(f"{settings.API_V1_PREFIX}/feedback/clean", params={"reprocess": False})
    data2 = res2.json()
    assert data2["total_considered"] == 0
    assert data2["processed"] == 0


def test_quality_summary_endpoint_sql_aggregations():
    create_sample_feedback(text="Clean valid feedback item 1", product="SummaryProd")
    create_sample_feedback(text="Contact test@example.com for info", product="SummaryProd")
    create_sample_feedback(text="buy cheap products now click here to win", product="SummaryProd")

    # Clean them
    client.post(f"{settings.API_V1_PREFIX}/feedback/clean", params={"product": "SummaryProd"})

    # Get summary
    res = client.get(f"{settings.API_V1_PREFIX}/feedback/quality/summary", params={"product": "SummaryProd"})
    assert res.status_code == 200
    data = res.json()

    assert data["total_records"] == 3
    assert data["quality_status_counts"]["clean"] >= 1
    assert data["pii_detected_count"] >= 1
    assert data["average_quality_score"] is not None
    assert 0.0 <= data["average_quality_score"] <= 100.0


def test_original_feedback_text_never_overwritten():
    original = "  Original text with   spaces &amp; email test@org.com and code Map<String, Object>  "
    fb_id = create_sample_feedback(text=original)

    client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/clean")

    db = next(app.dependency_overrides[get_db]())
    record = db.query(Feedback).filter(Feedback.feedback_id == uuid.UUID(fb_id)).first()
    assert record.feedback_text == original
    assert record.cleaned_feedback_text != original
    assert "[EMAIL]" in record.cleaned_feedback_text
    assert "Map<String, Object>" in record.cleaned_feedback_text
    db.close()
