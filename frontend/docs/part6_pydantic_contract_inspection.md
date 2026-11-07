# Part 6: Source Inspection & Pydantic vs. Database Contract Report

**Inspection Date & Time:** 2026-11-07T11:45:00+05:30  
**Target Repository:** `C:\Users\Neeraj Kumar Rana\Downloads\feedback\Feadback-synthziser`  
**Git Branch & Commit:** `main` at `57248af`  

---

## 1. Pydantic Classification Schemas Inspection

### Verified Facts
* **There are currently NO Pydantic classification schemas committed to the repository.**
* `backend/app/schemas/` contains only three files:
  1. `backend/app/schemas/feedback.py`
  2. `backend/app/schemas/health.py`
  3. `backend/app/schemas/__init__.py`
* The schemas in `backend/app/schemas/feedback.py` belong strictly to Part 3 (Ingestion) and Part 4 (Cleaning & Quality):
  * `FeedbackResponse` (lines 7–35)
  * `FeedbackPaginationResponse` (lines 38–45)
  * `UploadRowError` (lines 48–54)
  * `UploadJobResponse` (lines 57–73)
  * `UploadResponse` (lines 76–89)
  * `BatchCleanResponse` (lines 92–101)
  * `FeedbackQualityResponse` (lines 104–122)
  * `QualitySummaryResponse` (lines 125–136)
* The frontend types file `frontend/src/lib/types.ts` similarly contains only Part 4 quality and ingestion TypeScript interfaces.

---

## 2. Existing Pydantic Schemas: Field Extraction

From `backend/app/schemas/feedback.py` (lines 7–35), the active feedback model fields are:

| Field Name | Type | Optionality | Default | Constraints / Descriptions | Line Number |
|---|---|---|---|---|---|
| `feedback_id` | `uuid.UUID` | Required | *None* | Primary identifier | Line 12 |
| `source` | `str` | Required | *None* | Origin (e.g. csv, zendesk) | Line 13 |
| `customer_id` | `str` | Optional | `None` | External customer ID | Line 14 |
| `feedback_text` | `str` | Required | *None* | Raw feedback text | Line 15 |
| `product` | `str` | Required | *None* | Target product | Line 16 |
| `feature` | `str` | Optional | `None` | Target feature | Line 17 |
| `timestamp` | `datetime` | Required | *None* | Source creation timestamp | Line 18 |
| `app_version` | `str` | Optional | `None` | Application version | Line 19 |
| `created_at` | `datetime` | Required | *None* | Ingestion timestamp | Line 20 |
| `deleted_at` | `datetime` | Optional | `None` | Soft deletion timestamp | Line 21 |
| `cleaned_feedback_text`| `str` | Optional | `None` | Cleaned / redacted text | Line 24 |
| `quality_status` | `str` | Required | `"pending"` | `pending`, `clean`, `flagged`, `rejected`, `failed` | Line 25 |
| `quality_score` | `float` | Optional | `None` | Overall score [0.0 - 100.0] | Line 26 |
| `content_quality_score`| `float` | Optional | `None` | Content score [0.0 - 100.0] | Line 27 |
| `metadata_completeness_score`| `float`| Optional | `None` | Metadata score [0.0 - 100.0] | Line 28 |
| `quality_flags` | `List[str]` | Optional | `None` | Diagnostic flags list | Line 29 |
| `pii_detected` | `bool` | Required | `False` | PII presence indicator | Line 30 |
| `pii_types` | `List[str]` | Optional | `None` | Detected PII types | Line 31 |
| `cleaning_version` | `str` | Optional | `None` | Cleaning algorithm version | Line 32 |
| `cleaned_at` | `datetime` | Optional | `None` | Cleaning timestamp | Line 33 |
| `processing_status` | `str` | Required | `"unprocessed"` | `unprocessed`, `processing`, `processed`, `failed` | Line 34 |
| `processing_error` | `str` | Optional | `None` | Cleaning error message | Line 35 |

*Note: `FeedbackResponse` does NOT currently expose `classification_status` or classification relation data.*

---

## 3. Inspection of Existing SQLAlchemy Models

### A. `backend/app/models/classification.py` (`FeedbackClassification`)

* **Table:** `feedback_classifications` (line 32)
* **Check Constraints (lines 34–61):**
  * `ck_feedback_classifications_status`: `status IN ('classified', 'failed', 'pending_review')`
  * `ck_feedback_classifications_overall_sentiment`: `overall_sentiment IS NULL OR overall_sentiment IN ('positive', 'negative', 'neutral', 'mixed')`
  * `ck_feedback_classifications_sentiment_score`: `sentiment_score IS NULL OR (sentiment_score >= -1.0 AND sentiment_score <= 1.0)`
  * `ck_feedback_classifications_sentiment_intensity`: `sentiment_intensity IS NULL OR sentiment_intensity IN ('low', 'medium', 'high')`
  * `ck_feedback_classifications_customer_intent`: `customer_intent IS NULL OR customer_intent IN ('complaint', 'suggestion', 'praise', 'question', 'feature_request', 'other')`
  * `ck_feedback_classifications_confidence_score`: `confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)`
  * `ck_feedback_classifications_latency_ms`: `latency_ms IS NULL OR latency_ms >= 0`
* **Indexes (lines 63–67):**
  * `ix_feedback_classifications_feedback_id` on `feedback_id`
  * `ix_feedback_classifications_classified_at` on `classified_at`
  * `ix_feedback_classifications_version` on `classification_version`
  * `ix_feedback_classifications_feedback_version` on `(feedback_id, classification_version)`
  * `ix_feedback_classifications_status` on `status`
* **Columns (lines 71–208):**
  * `classification_id`: `Uuid(as_uuid=True)`, PK, default `uuid.uuid4`
  * `feedback_id`: `Uuid(as_uuid=True)`, `ForeignKey("feedback.feedback_id", ondelete="CASCADE")`, nullable=False
  * `classification_version`: `String(50)`, nullable=False
  * `status`: `String(50)`, nullable=False, default `"classified"`
  * `overall_sentiment`: `Optional[str]`, `String(50)`, nullable=True
  * `sentiment_score`: `Optional[float]`, `Float`, nullable=True
  * `sentiment_intensity`: `Optional[str]`, `String(50)`, nullable=True
  * `customer_intent`: `Optional[str]`, `String(50)`, nullable=True
  * `identified_product`: `Optional[str]`, `String(100)`, nullable=True
  * `identified_feature`: `Optional[str]`, `String(100)`, nullable=True
  * `topics`: `Optional[List[str]]`, `JSON`, `default=list`
  * `aspects`: `Optional[List[Dict[str, Any]]]`, `JSON`, `default=list`
  * `pain_points`: `Optional[List[str]]`, `JSON`, `default=list`
  * `keywords`: `Optional[List[str]]`, `JSON`, `default=list`
  * `confidence_score`: `Optional[float]`, `Float`, nullable=True
  * `needs_review`: `bool`, `Boolean`, nullable=False, default `False`
  * `review_reason`: `Optional[str]`, `Text`, nullable=True
  * `provider`: `Optional[str]`, `String(50)`, nullable=True
  * `model_name`: `Optional[str]`, `String(100)`, nullable=True
  * `latency_ms`: `Optional[int]`, `Integer`, nullable=True
  * `token_usage`: `Optional[Dict[str, Any]]`, `JSON`, `default=dict`
  * `error_message`: `Optional[str]`, `Text`, nullable=True
  * `classified_at`: `datetime`, `DateTime(timezone=True)`, server default `func.now()`, default `datetime.now(timezone.utc)`
* **Relationship (lines 211–214):**
  * `feedback`: `relationship("Feedback", back_populates="classifications")`

### B. `backend/app/models/feedback.py` (`Feedback`)

* **New Classification Column (lines 217–222):**
  * `classification_status`: `Mapped[str] = mapped_column(String(50), nullable=False, default="pending")`
* **Table Constraint & Index (lines 81–84, 89):**
  * `CheckConstraint("classification_status IN ('pending', 'processing', 'completed', 'failed')", name="ck_feedback_classification_status")`
  * `Index("ix_feedback_classification_status", "classification_status")`
* **Relationship (lines 252–257):**
  * `classifications: Mapped[List["FeedbackClassification"]] = relationship("FeedbackClassification", back_populates="feedback", cascade="all, delete-orphan", order_by="desc(FeedbackClassification.classified_at)")`

### C. `backend/app/models/sentiment.py` (`SentimentHistory`)

* **Current Columns (lines 40–81):**
  * `sentiment_id`: `Uuid(as_uuid=True)`, PK
  * `feedback_id`: `Uuid(as_uuid=True)`, `ForeignKey("feedback.feedback_id", ondelete="CASCADE")`
  * `theme_id`: `Optional[uuid.UUID]`, `ForeignKey("themes.theme_id", ondelete="SET NULL")`
  * `sentiment_label`: `String(50)`, nullable=False
  * `sentiment_score`: `Float`, nullable=False (`-1.0` to `1.0`)
  * `confidence_score`: `Float`, nullable=False (`0.0` to `1.0`)
  * `analysed_at`: `DateTime(timezone=True)`
* **Current Relationships (lines 83–85):**
  * `feedback`: `relationship("Feedback", back_populates="sentiment_history")`
  * `theme`: `relationship("Theme", back_populates="sentiment_history")`
* **Missing Column:** `classification_id` is currently **absent** from `SentimentHistory`.

---

## 4. Existing Alembic Migrations Inspection

The Alembic migration directory `backend/alembic/versions/` contains exactly 5 migrations forming a linear chain:

| Revision ID | Migration File | Down Revision | Description |
|---|---|---|---|
| `ae66156cfb1a` | `ae66156cfb1a_initial_schema.py` | `None` | Creates initial tables (`feedback`, `themes`, `feedback_themes`, `sentiment_history`, `product_changes`, `theme_snapshots`, `insights`, `insight_evidence`, `memory_metadata`) |
| `b702ef22d23b` | `b702ef22d23b_refine_schema_provenance_and_constraints.py` | `ae66156cfb1a` | Adds `deleted_at` to `feedback`; composite unique on `themes(product, theme_name)` |
| `c3f912b4e87a` | `c3f912b4e87a_add_upload_jobs_and_safeguards.py` | `b702ef22d23b` | Creates `upload_jobs` table; memory metadata check constraints |
| `e5a8f23c91d4` | `e5a8f23c91d4_add_feedback_cleaning_and_quality_fields.py` | `c3f912b4e87a` | Adds Part 4 data cleaning, PII redaction, and quality fields to `feedback` |
| `f6b903e1a82d` | `f6b903e1a82d_add_content_and_metadata_quality_scores.py` | `e5a8f23c91d4` | Adds `content_quality_score` and `metadata_completeness_score` (**Current HEAD**) |

* **Verified Fact:** No migration exists for `feedback_classifications`, `Feedback.classification_status`, or `SentimentHistory.classification_id`.

---

## 5. Classification API Routes & Schemas Inspection

In `backend/app/api/routes/feedback.py` (lines 49–245), exactly 8 routes are defined:
* `POST /upload` (line 49) — File upload ingestion
* `GET /upload/{job_id}` (line 105) — Ingestion job status
* `GET /` (line 135) — Paginated feedback list
* `POST /clean-batch` (line 152) — Batch cleaning trigger
* `GET /quality-summary` (line 174) — Quality metrics aggregation
* `GET /{feedback_id}` (line 189) — Single feedback item
* `POST /{feedback_id}/clean` (line 206) — Single feedback cleaning trigger
* `GET /{feedback_id}/quality` (line 227) — Single feedback quality inspection

* **Verified Fact:** There are zero classification API routes (such as `POST /api/feedback/analyze` or `GET /api/feedback/{id}/classifications`).

---

## 6. Differences Between Pydantic and SQLAlchemy

| Feature / Domain | SQLAlchemy Model (`FeedbackClassification`) | Planned / Expected Pydantic Contract | Status & Difference |
|---|---|---|---|
| **Pydantic Schema File** | Model exists in `classification.py` | Schema file does not exist in `backend/app/schemas/` | **Missing File:** Teammate must supply `classification.py` schemas. |
| **Feedback API Response** | `Feedback.classification_status` present | `FeedbackResponse` in `schemas/feedback.py` lacks `classification_status` | **Mismatch:** `FeedbackResponse` must be updated to include `classification_status: str = "pending"`. |
| **Topics Structure** | Generic `JSON` (`List[str]`) | Unresolved: May be `List[str]` or `List[TopicObject]` with confidence | **Provisional:** Handled by JSON type, pending Pydantic schema. |
| **Aspects Structure** | Generic `JSON` (`List[Dict[str, Any]]`) | Unresolved: May include `aspect`, `sentiment`, `score`, `confidence`, `evidence` | **Provisional:** Handled by JSON type, pending Pydantic schema. |
| **Token Usage** | Generic `JSON` (`Dict[str, Any]`) | Likely `TokenUsage(prompt_tokens: int, completion_tokens: int, total_tokens: int)` | **Provisional:** Maps cleanly to JSON. |
| **Customer Intent** | Constrained to 6 values | Often includes `bug_report`, `churn_risk` | **Risk:** DB check constraint will fail if Pydantic emits unlisted intents. |
| **Sentiment Intensity** | Constrained to `('low', 'medium', 'high')` | Unresolved: May include `extreme` | **Risk:** DB check constraint will fail if Pydantic emits `extreme`. |

---

## 7. Database Constraints Status & Deficiencies

### In `backend/app/models/classification.py`:
1. **Missing `run_number`:** The model currently uses `classification_version: str` without `run_number`. It does not enforce `UniqueConstraint("feedback_id", "run_number")`.
2. **Timestamps:** Model uses `classified_at` instead of the approved `created_at` (non-null) and `completed_at` (nullable).
3. **Provider Nullability:** `provider` and `model_name` are nullable `String` fields (correct per pre-provider selection requirements).
4. **Error Sanitization:** Field is named `error_message: Mapped[Optional[str]] = mapped_column(Text)`. Recommended: rename to `sanitized_error_message: String(500)` to reinforce the security policy.

### In `backend/app/models/sentiment.py`:
1. **Missing `classification_id` Foreign Key:** `SentimentHistory` currently lacks `classification_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("feedback_classifications.classification_id", ondelete="SET NULL"), nullable=True, index=True)`.

---

## 8. Run Number Uniqueness & Concurrency Requirements

* **Current Implementation:** `FeedbackClassification` has non-unique index `ix_feedback_classifications_feedback_version` on `(feedback_id, classification_version)`.
* **Required Unified Contract:**
  1. Add `run_number: Mapped[int] = mapped_column(Integer, nullable=False)`.
  2. Add `UniqueConstraint("feedback_id", "run_number", name="uq_feedback_classification_run")`.
  3. Index: `Index("ix_feedback_classifications_lookup_latest", "feedback_id", "status", "run_number")`.
  4. Service-layer allocation:
     * **PostgreSQL:** Execute `SELECT 1 FROM feedback WHERE feedback_id = :id FOR UPDATE` before `SELECT COALESCE(MAX(run_number), 0) + 1 FROM feedback_classifications WHERE feedback_id = :id`.
     * **SQLite:** Retry loop (up to 3 retries with jitter) catching `sqlite3.OperationalError` (database locked) and `IntegrityError` on `uq_feedback_classification_run`. Roll back transaction prior to each retry. Do not retry other errors.

---

## 9. `sentiment_history.classification_id` Deletion Behavior

* **Verified Current State:** `sentiment_history` has no relationship or FK to `feedback_classifications`.
* **Required Verified Behavior:**
  1. Column: `classification_id` on `sentiment_history` must have `ondelete="SET NULL"`, `nullable=True`.
  2. Relationship on `FeedbackClassification`:
     ```python
     sentiment_records: Mapped[List["SentimentHistory"]] = relationship(
         "SentimentHistory",
         back_populates="classification",
         passive_deletes=True,  # NEVER delete-orphan
     )
     ```
  3. When a `FeedbackClassification` record is deleted:
     * Its associated `sentiment_history` rows **must NOT be deleted**.
     * Their `classification_id` is automatically set to `NULL`.
  4. When a `Feedback` record is physically deleted:
     * Both its `classifications` and its `sentiment_history` cascade delete directly via their respective `feedback_id` foreign keys (`ondelete="CASCADE"`).

---

## 10. Field-by-Field Comparison & Proposed Unified Database Contract

Below is the verified mapping and unified proposal for the `feedback_classifications` table:

| Field Name | Type / Nullability | Current Model Status | Proposed Unified Database Contract | Verified vs. Recommendation |
|---|---|---|---|---|
| `classification_id` | `UUID`, Not Null | Present (PK) | `classification_id: Uuid(as_uuid=True)`, PK, default `uuid.uuid4` | **Verified Match** |
| `feedback_id` | `UUID`, Not Null | Present (FK) | `feedback_id: Uuid(as_uuid=True)`, `ForeignKey("feedback.feedback_id", ondelete="CASCADE")` | **Verified Match** |
| `run_number` | `INTEGER`, Not Null | **Missing** | `run_number: int`, allocated via transaction service | **Recommendation** |
| `classification_version` | `VARCHAR(50)`, Not Null | Present | `classification_version: str` (e.g. `"v1.0.0"`) | **Verified Match** |
| `prompt_version` | `VARCHAR(50)`, Nullable | Missing | `prompt_version: Optional[str]` | **Recommendation** |
| `status` | `VARCHAR(50)`, Not Null | Present (`classified`) | `status: str`, values: `'classified'`, `'failed'`, `'pending_review'` | **Verified Match** |
| `overall_sentiment` | `VARCHAR(50)`, Nullable | Present | `overall_sentiment: Optional[str]`, check: `'positive'`, `'negative'`, `'neutral'`, `'mixed'` | **Verified Match** |
| `sentiment_score` | `FLOAT`, Nullable | Present | `sentiment_score: Optional[float]`, check: `[-1.0, 1.0]` | **Verified Match** |
| `sentiment_intensity` | `VARCHAR(50)`, Nullable | Present | `sentiment_intensity: Optional[str]`, check: `'low'`, `'medium'`, `'high'` *(or omit check until Pydantic confirmed)* | **Provisional** |
| `customer_intent` | `VARCHAR(50)`, Nullable | Present | `customer_intent: Optional[str]`, recommend `VARCHAR(100)` without strict check constraint | **Provisional / Recommended** |
| `identified_product` | `VARCHAR(100)`, Nullable | Present | `identified_product: Optional[str]` | **Verified Match** |
| `identified_feature` | `VARCHAR(100)`, Nullable | Present | `identified_feature: Optional[str]` | **Verified Match** |
| `topics` | `JSON`, Nullable | Present | `topics: JSON`, `default=list` | **Provisional (Handles List[str] or Objects)** |
| `aspects` | `JSON`, Nullable | Present | `aspects: JSON`, `default=list` | **Provisional (Handles Dicts/Models)** |
| `pain_points` | `JSON`, Nullable | Present | `pain_points: JSON`, `default=list` | **Provisional** |
| `keywords` | `JSON`, Nullable | Present | `keywords: JSON`, `default=list` | **Provisional** |
| `confidence_score` | `FLOAT`, Nullable | Present | `confidence_score: Optional[float]`, check: `[0.0, 1.0]` | **Verified Match** |
| `needs_review` | `BOOLEAN`, Not Null | Present (`False`) | `needs_review: bool`, default `False` | **Verified Match** |
| `review_reason` | `TEXT`, Nullable | Present | `review_reason: Optional[str]` | **Verified Match** |
| `provider` | `VARCHAR(50)`, Nullable | Present | `provider: Optional[str]` (runtime values: `'gemini'`, `'openrouter'`, `'grok'`) | **Verified Match** |
| `model_name` | `VARCHAR(100)`, Nullable | Present | `model_name: Optional[str]` | **Verified Match** |
| `latency_ms` | `INTEGER`, Nullable | Present | `latency_ms: Optional[int]`, check: `>= 0` | **Verified Match** |
| `token_usage` | `JSON`, Nullable | Present | `token_usage: JSON`, `default=dict` | **Provisional (Handles TokenUsage dict)** |
| `sanitized_error_message` | `VARCHAR(500)`, Nullable | `error_message (Text)` | `sanitized_error_message: Optional[str]`, `String(500)` | **Recommendation** |
| `created_at` | `TIMESTAMP`, Not Null | Missing (`classified_at`) | `created_at: DateTime(timezone=True)`, server_default `func.now()` | **Recommendation** |
| `completed_at` | `TIMESTAMP`, Nullable | Missing | `completed_at: Optional[DateTime(timezone=True)]` | **Recommendation** |
