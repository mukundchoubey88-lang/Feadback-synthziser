# Feedback Intelligence Agent – Backend

Backend foundation for **User Feedback Synthesizer – Feedback Intelligence Agent**, an AI-powered customer feedback intelligence and persistent memory platform.

The system ingests multi-channel customer feedback, synthesizes recurring and emerging issues, correlates feedback with product releases, and uses Gemini AI alongside Hindsight persistent memory to power historical reasoning and research.

---

## Technology Stack

- **Runtime:** Python 3.11+
- **API Framework:** FastAPI
- **ASGI Server:** Uvicorn
- **Configuration & Validation:** Pydantic v2 & Pydantic Settings
- **Database Engine (Prepared):** SQLAlchemy 2.x
- **PostgreSQL Driver:** Psycopg 3 (`psycopg[binary]`)
- **Database Migrations (Prepared):** Alembic
- **Testing:** Pytest & HTTPX (AsyncClient)
- **Environment Management:** python-dotenv

---

## Project Structure

```text
backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # Application factory & lifespan setup
│   │
│   ├── api/                        # API router definitions
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── health.py           # Health check & dependency status
│   │
│   ├── core/                       # Core configuration & error handling
│   │   ├── __init__.py
│   │   ├── config.py               # Pydantic Settings configuration
│   │   ├── logging.py              # Centralized logging setup
│   │   └── exceptions.py           # Custom exceptions & handlers
│   │
│   ├── db/                         # SQLAlchemy infrastructure
│   │   ├── __init__.py
│   │   ├── base.py                 # DeclarativeBase base model
│   │   └── session.py              # Session factory & dependency injection
│   │
│   ├── models/                     # SQLAlchemy models (Part 2)
│   │   └── __init__.py
│   │
│   ├── schemas/                    # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   └── health.py
│   │
│   ├── services/                   # Business logic services (Part 3+)
│   │   └── __init__.py
│   │
│   └── integrations/               # External provider integrations
│       ├── __init__.py
│       ├── gemini/                 # Gemini AI integration placeholder (Part 4)
│       │   └── __init__.py
│       └── hindsight/              # Hindsight memory integration placeholder (Part 9)
│           └── __init__.py
│
├── tests/                          # Automated test suite
│   ├── __init__.py
│   └── test_health.py
│
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore patterns
├── requirements.txt                # Python project dependencies
└── README.md                       # Documentation
```

---

## Prerequisites

- **Python:** 3.11 or newer (verify with `python --version`)
- **PowerShell:** Windows PowerShell 5.1 or PowerShell 7+
- **PostgreSQL:** (Required starting in Part 2; not required for Part 1)

---

## Windows PowerShell Setup Instructions

### 1. Navigate to the backend directory
```powershell
cd backend
```

### 2. Create Python virtual environment
```powershell
python -m venv venv
```

### 3. Activate the virtual environment
```powershell
.\venv\Scripts\Activate.ps1
```

> **Note:** If script execution is restricted on your machine, enable local script execution for the current session:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
> ```

### 4. Install dependencies
```powershell
pip install -r requirements.txt
```

### 5. Configure environment variables
```powershell
Copy-Item .env.example .env
```

### 6. Start the FastAPI development server
```powershell
uvicorn app.main:app --reload
```

---

## API Documentation & Endpoints

Once the application is running:

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `http://localhost:8000/` | `GET` | Application metadata and documentation links |
| `http://localhost:8000/api/health` | `GET` | Health status and external dependency readiness |
| `http://localhost:8000/api/feedback/upload` | `POST` | Ingest CSV or JSON feedback files |
| `http://localhost:8000/api/feedback` | `GET` | List active feedback with pagination and filters |
| `http://localhost:8000/api/feedback/{feedback_id}` | `GET` | Retrieve single feedback record by ID |
| `http://localhost:8000/api/feedback/jobs/{job_id}` | `GET` | Retrieve status of an upload job |
| `http://localhost:8000/docs` | `GET` | Interactive Swagger UI API documentation |
| `http://localhost:8000/redoc` | `GET` | Interactive ReDoc API documentation |

---

## Feedback Ingestion API (Part 3)

The feedback ingestion API allows clients to upload batch feedback datasets via CSV or JSON, validates records against strict schemas, detects duplicates, and tracks ingestion lifecycle with dedicated upload jobs.

### Supported File Formats

- **CSV (`.csv`):** Standard CSV format with UTF-8 or UTF-8 with BOM (`utf-8-sig`) encoding. Header row required. Empty rows are safely skipped.
- **JSON (`.json`):** Root must be a JSON array containing feedback objects.

### Expected Input Fields

| Field | Type | Required | Description & Constraints |
| :--- | :--- | :--- | :--- |
| `source` | `string` | **Yes** | Source channel (e.g., `csv`, `zendesk`, `app_store`). Max 100 chars. |
| `customer_id` | `string` | No | External customer or account ID. Max 255 chars. |
| `feedback_text` | `string` | **Yes** | Raw customer feedback text. Max 10,000 chars. Surrounding whitespace trimmed. |
| `product` | `string` | **Yes** | Target product line or application. Max 100 chars. |
| `feature` | `string` | No | Component or feature name. Max 100 chars. |
| `timestamp` | `string` | **Yes** | ISO 8601 UTC timestamp (e.g., `2026-11-01T12:00:00Z`). Missing or invalid timestamps are rejected; synthetic timestamps are never silently generated. |
| `app_version` | `string` | No | Client application release version. Max 50 chars. |

### Configurable File & Ingestion Limits

- **Maximum file upload size:** 10 MB (`MAX_UPLOAD_FILE_SIZE_BYTES = 10485760`)
- **Maximum records per upload:** 10,000 records (`MAX_UPLOAD_RECORDS = 10000`)
- **Maximum feedback text length:** 10,000 characters (`MAX_FEEDBACK_TEXT_LENGTH = 10000`)

### Duplicate Detection Strategy

Duplicates are detected at two levels without placing restrictive unique constraints on free-text database columns:
1. **Intra-batch Deduplication:** Tracks `(product, customer_id, timestamp, feedback_text)` within the uploaded file. Repeated identical rows within the same payload are skipped and recorded under `duplicate_records`.
2. **Database-level Deduplication:** Queries existing active feedback records leveraging the composite index on `(product, timestamp)` for high-performance exact matching of `product`, `customer_id`, `timestamp`, and `feedback_text`. Existing entries are recorded under `duplicate_records` and not re-inserted.

### Upload Job Lifecycle & Statuses

Each upload creates a persistent `UploadJob` record with one of the following statuses:
- `pending`: Job queued or initialized.
- `processing`: File parsed and records being evaluated/inserted.
- `completed`: All records were valid and successfully persisted.
- `completed_with_errors`: Completed, but some records were rejected or flagged as duplicates.
- `failed`: Fatal error occurred (e.g., all rows invalid, schema mismatch, or DB transaction failure).

### Sample Payloads

#### Sample CSV (`feedback.csv`)
```csv
source,customer_id,feedback_text,product,feature,timestamp,app_version
csv,cust-101,Search results load slowly on mobile web,Analytics Portal,Search,2026-11-01T10:00:00Z,2.4.0
zendesk,cust-102,Export to CSV fails when table has over 500 rows,Analytics Portal,Export,2026-11-01T11:30:00Z,2.4.0
```

#### Sample JSON (`feedback.json`)
```json
[
  {
    "source": "in_app",
    "customer_id": "cust-201",
    "feedback_text": "The new dark mode contrast is fantastic.",
    "product": "Mobile App",
    "feature": "Theme",
    "timestamp": "2026-11-02T08:15:00Z",
    "app_version": "3.1.0"
  },
  {
    "source": "app_store",
    "customer_id": "cust-202",
    "feedback_text": "Push notifications are delayed by several minutes.",
    "product": "Mobile App",
    "feature": "Notifications",
    "timestamp": "2026-11-02T09:00:00Z",
    "app_version": "3.1.0"
  }
]
```

### API Examples

#### 1. Upload Feedback File
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/feedback/upload" -Form @{
    file = Get-Item -Path "feedback.json"
}
```

**Response (HTTP 200):**
```json
{
  "job_id": "b3e210d7-2fa5-45d2-b6be-ca0e10f135b6",
  "status": "completed",
  "filename": "feedback.json",
  "total_records": 2,
  "inserted_records": 2,
  "duplicate_records": 0,
  "rejected_records": 0,
  "errors": [],
  "message": "Successfully ingested 2 feedback records."
}
```

#### 2. Query Feedback Listing with Pagination and Filtering
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/feedback?page=1&page_size=10&product=Mobile%20App"
```

**Response (HTTP 200):**
```json
{
  "items": [
    {
      "feedback_id": "90e184e9-11ba-4ce7-a9a3-ea5ef20fc1aa",
      "source": "in_app",
      "customer_id": "cust-201",
      "feedback_text": "The new dark mode contrast is fantastic.",
      "product": "Mobile App",
      "feature": "Theme",
      "timestamp": "2026-11-02T08:15:00Z",
      "app_version": "3.1.0",
      "created_at": "2026-11-05T23:55:00Z",
      "deleted_at": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

#### 3. Retrieve Ingestion Job Status
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/feedback/jobs/b3e210d7-2fa5-45d2-b6be-ca0e10f135b6"
```

---

## Part 4 — Data Cleaning and Quality Pipeline

The data-cleaning pipeline deterministically validates, normalizes, detects/redacts PII, scores quality, and filters noise from feedback records prior to AI classification and memory storage.

### Pipeline Architecture

```text
Raw Feedback
    ↓
Input Integrity Check
    ↓
Text Normalization (Unicode NFC, whitespace, CRLF, control characters, emoji preservation)
    ↓
PII Detection (Email, Phone, URL, IP, SSN/Credit Cards)
    ↓
PII Redaction in Processed Copy ([EMAIL], [PHONE], [URL], [IP_ADDRESS], [ID_NUMBER])
    ↓
Spam and Noise Assessment (Empty, Meaningless, Repeated chars, Spam patterns, URL-only)
    ↓
Data Quality Scoring (0.0 to 100.0 formula)
    ↓
Quality Status Assignment (clean, flagged, rejected)
    ↓
Persistence in Processed Columns (Original feedback_text strictly immutable)
```

### Core Invariants

1. **Original Feedback Immutability:** `Feedback.feedback_text` is NEVER modified. All normalized and redacted copy is stored in `Feedback.cleaned_feedback_text`.
2. **Deterministic & Versioned:** Every run records `cleaning_version = "1.0.0"`. Batch jobs skip previously processed records unless `reprocess=true` is requested.
3. **Sentiment Neutrality:** Highly negative or emotional customer feedback is never penalized or rejected; quality scoring evaluates solely detail, clarity, and metadata completeness.

### Data Cleaning API Endpoints

#### 1. Batch Clean Ingested Feedback
Runs the cleaning pipeline across pending or uncleaned records with bounded batch sizes.

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/feedback/clean?limit=100&reprocess=false"
```

**Response:**
```json
{
  "total_considered": 100,
  "processed": 100,
  "skipped": 0,
  "clean_count": 92,
  "flagged_count": 6,
  "rejected_count": 2,
  "failed_count": 0
}
```

#### 2. Clean Single Feedback Record
Cleans a single specific record by `feedback_id`.

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/feedback/858bca08-0db4-4696-857c-fe051871a2e9/clean"
```

**Response:**
```json
{
  "feedback_id": "858bca08-0db4-4696-857c-fe051871a2e9",
  "source": "zendesk",
  "customer_id": "cust-102",
  "feedback_text": "Please reach out to support@mycompany.org regarding my login issue.",
  "cleaned_feedback_text": "Please reach out to [EMAIL] regarding my login issue.",
  "product": "Storefront",
  "feature": "Auth",
  "timestamp": "2026-11-04T10:15:00Z",
  "quality_status": "clean",
  "quality_score": 95.0,
  "content_quality_score": 95.0,
  "metadata_completeness_score": 100.0,
  "quality_flags": ["PII_PRESENT"],
  "pii_detected": true,
  "pii_types": ["email"],
  "cleaning_version": "1.0.0",
  "cleaned_at": "2026-11-06T08:00:00Z",
  "processing_status": "processed"
}
```

#### 3. Inspect Individual Quality Details
Retrieves detailed diagnostic inspection of a record's quality state.

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/feedback/858bca08-0db4-4696-857c-fe051871a2e9/quality"
```

**Response:**
```json
{
  "feedback_id": "858bca08-0db4-4696-857c-fe051871a2e9",
  "original_feedback_text": "Please reach out to support@mycompany.org regarding my login issue.",
  "cleaned_feedback_text": "Please reach out to [EMAIL] regarding my login issue.",
  "quality_status": "clean",
  "quality_score": 95.0,
  "content_quality_score": 95.0,
  "metadata_completeness_score": 100.0,
  "quality_flags": ["PII_PRESENT"],
  "pii_detected": true,
  "pii_types": ["email"],
  "cleaning_version": "1.0.0",
  "cleaned_at": "2026-11-06T08:00:00Z",
  "processing_status": "processed",
  "processing_error": null
}
```

#### 4. Quality Summary & Distribution
Returns aggregate counts of quality statuses, PII occurrences, and flag distributions. Supports optional `?product=` filtering.

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/feedback/quality/summary?product=Storefront"
```

**Response:**
```json
{
  "total_records": 100,
  "quality_status_counts": {
    "clean": 92,
    "flagged": 6,
    "rejected": 2,
    "pending": 0,
    "failed": 0
  },
  "processing_status_counts": {
    "processed": 100,
    "unprocessed": 0,
    "failed": 0
  },
  "pii_detected_count": 14,
  "average_quality_score": 91.4,
  "flag_distribution": {
    "PII_PRESENT": 14,
    "VERY_SHORT": 8,
    "REPEATED_CHARS": 4,
    "SPAM_PATTERN": 2
  }
}
```

---

## Database Migrations (Alembic)

Database schema migrations are managed via Alembic and dynamically load `DATABASE_URL` from `.env`.

```powershell
# Generate a new migration revision
alembic revision -m "revision_name"

# Apply pending migrations (requires running PostgreSQL instance)
alembic upgrade head

# Rollback latest migration
alembic downgrade -1
```

---

## Running Automated Tests

To execute the test suite:

```powershell
pytest -v
```

---

## Current Status & Roadmap

### Part 1: Backend Foundation and Project Setup (Completed)
- [x] Modular directory structure and architectural placeholders
- [x] Centralized Pydantic Settings configuration (`.env` support)
- [x] Application lifespan, centralized logging, and exception handling
- [x] SQLAlchemy 2.x session and declarative base foundation
- [x] Health check and root information endpoints
- [x] Architectural separation for Gemini AI and Hindsight Memory
- [x] Unit test suite with Pytest and HTTPX

### Part 2: PostgreSQL Database Models & Alembic Migrations (Completed)
- [x] SQLAlchemy 2.x typed declarative models for all 8 PRD entities (9 tables)
- [x] UUID primary keys and UTC timezone-aware timestamps
- [x] Explicit foreign keys, check constraints, cascade behaviors, and indexes
- [x] Many-to-many junction tables (`feedback_themes`, `insight_evidence`)
- [x] Initial migration script (`ae66156cfb1a_initial_schema.py`)

### Part 2.1: Database Schema Refinement (Completed)
- [x] Hindsight memory provenance refinement (`bank_id`, `hindsight_memory_id`, `source_entity_type`, and typed source foreign keys)
- [x] Product-scoped theme uniqueness (`UniqueConstraint("product", "theme_name")`)
- [x] Evidence protection: Soft deletion (`deleted_at`) on `Feedback` and `ON DELETE RESTRICT` on `InsightEvidence`
- [x] ThemeSnapshot data integrity check constraints (`period_start <= period_end` and category count sum)
- [x] New migration revision (`b702ef22d23b_refine_schema_provenance_and_constraints.py`) chained to initial migration
- [x] 16 automated tests covering all schema invariants, constraints, and migrations (100% passing)

### Part 3: Feedback Ingestion API (Completed)
- [x] Ingestion endpoints: `POST /api/feedback/upload`, `GET /api/feedback`, `GET /api/feedback/{feedback_id}`, `GET /api/feedback/jobs/{job_id}`
- [x] Multipart CSV & JSON dataset ingestion with UTF-8 and UTF-8 BOM support
- [x] Strict validation (required non-empty strings, ISO 8601 UTC timestamps, rejection of missing timestamps)
- [x] Dedicated `UploadJob` model and table tracking counts, lifecycle states, and structured row errors
- [x] Intra-batch and database-level duplicate detection using `(product, timestamp)` index
- [x] Configurable safeguards for file size (10 MB), batch record count (10k), and text length (10k chars)
- [x] Safeguard A: Removal of temporary server_default on `themes.product`
- [x] Safeguard B: Provenance consistency constraint and validation on `MemoryMetadata`
- [x] Alembic migration (`c3f912b4e87a_add_upload_jobs_and_safeguards.py`)
- [x] 40 comprehensive automated tests covering all positive, negative, and edge cases

### Part 4: Data Cleaning and Quality Pipeline (Completed)
- [x] Deterministic text normalization (Unicode NFC, whitespace, CRLF, control characters, emoji preservation)
- [x] Sensitive PII detection & redaction (emails, phone numbers, URLs, IP addresses, identification/card numbers)
- [x] Spam and noise classification (empty text, meaningless content, repeated characters, spam phrases, URL-only)
- [x] Transparent quality scoring formula (0.0 to 100.0) with sentiment neutrality guarantees
- [x] Original feedback immutability: `feedback_text` strictly preserved; processed copy stored in `cleaned_feedback_text`
- [x] Cleaning endpoints: `POST /api/feedback/clean`, `POST /api/feedback/{feedback_id}/clean`, `GET /api/feedback/{feedback_id}/quality`, `GET /api/feedback/quality/summary`
- [x] Alembic migration (`e5a8f23c91d4_add_feedback_cleaning_and_quality_fields.py`)

### Part 4.1: Data Cleaning Corrections and Hardening (Completed)
- [x] Unicode-aware multilingual meaningful character detection (Latin, Hindi, Arabic, Cyrillic, Chinese, Japanese, Korean)
- [x] Conservative HTML normalization preserving code generics (`Map<String, Object>`, `List<User>`) and comparisons (`x < y and y > z`)
- [x] URL sanitization preserving host/path debugging context while redacting sensitive tokens and credentials
- [x] Strict IPv4 address filtering distinguishing 4-part software versions (`10.0.19041.1`, `1.2.0.0`) from host IPs
- [x] International phone coverage across UK, France, Germany, India, and US with zero false redactions on dates/order IDs
- [x] Decoupling of `content_quality_score` (unpenalized text usefulness) from `metadata_completeness_score`
- [x] Database-side SQL aggregations for quality summary (`COUNT`, `GROUP BY`, `AVG`)
- [x] Row-level batch locking (`SKIP LOCKED`) for PostgreSQL environments with SQLite test compatibility
- [x] Alembic migration (`f6b903e1a82d_add_content_and_metadata_quality_scores.py`)
- [x] 39 cleaning and hardening tests (88/88 total test suite passing) with 0 Pyright typing errors

### Upcoming Development Parts
- **Part 5:** AI Classification and Sentiment Analysis (Gemini API)
- **Part 6:** Theme Extraction and Trend Identification
- **Part 7:** Recommendation & Evidence Synthesis Engine
- **Part 8:** AI Research Agent & Memory-Augmented QA
- **Part 9:** Deep Hindsight Integration (Persistent Memory, Recall, and Evolution)
- **Part 10:** Production Hardening & Deployment
