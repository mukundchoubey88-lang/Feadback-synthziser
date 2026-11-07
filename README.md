# 🧠 User Feedback Synthesizer — Feedback Intelligence Agent

> An AI-powered customer feedback intelligence platform that **remembers** historical context across product iterations, tracks how customer sentiment **evolves over time**, and delivers **evidence-backed product recommendations**.

![Status](https://img.shields.io/badge/status-Active%20Development%20(Phase%204.1%20Completed)-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-brightgreen)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Database](https://img.shields.io/badge/database-PostgreSQL%20%2F%20SQLAlchemy%202.x-336791)
![Migrations](https://img.shields.io/badge/migrations-Alembic-orange)
![Tests](https://img.shields.io/badge/tests-88%20passing%20(pytest)-success)
![AI Providers (Planned)](https://img.shields.io/badge/AI%20Providers-Gemini%20%7C%20OpenRouter%20%7C%20xAI%20Grok-purple)
![Memory (Planned)](https://img.shields.io/badge/memory-Hindsight-informational)

---

## 📑 Table of Contents

1. [Project Overview](#-project-overview)
2. [The Problem It Solves](#-the-problem-it-solves)
3. [Implemented vs. Planned Capabilities](#-implemented-vs-planned-capabilities)
4. [System Architecture](#-system-architecture)
5. [Multi-Provider AI Architecture (Planned)](#-multi-provider-ai-architecture-planned)
6. [Hindsight Memory Layer (Planned)](#-hindsight-memory-layer-planned)
7. [Technology Stack](#-technology-stack)
8. [Database Schema & Data Models](#-database-schema--data-models)
9. [Feedback Ingestion & Quality Control Pipeline](#-feedback-ingestion--quality-control-pipeline)
10. [API Reference](#-api-reference)
11. [Repository Structure](#-repository-structure)
12. [Getting Started & Local Setup](#-getting-started--local-setup)
13. [Running Automated Tests](#-running-automated-tests)
14. [Edge Cases & Reliability](#-edge-cases--reliability)
15. [Development Roadmap](#-development-roadmap)
16. [Author & License](#-author--license)

---

## 🔭 Project Overview

**User Feedback Synthesizer – Feedback Intelligence Agent** transforms raw, multi-source customer feedback into continuous, historical, evidence-backed product intelligence.

Standard feedback analytics tools evaluate customer input as isolated, point-in-time snapshots. When users report issues, teams see aggregate complaint counts for the current sprint, but lose context on whether an issue is recurring, worsening, or previously resolved.

### Current status

The ingestion and data-quality backend is implemented (FastAPI, PostgreSQL, 88 passing tests). The React + Vite + TypeScript app in `frontend/` includes the public landing page and a console for the live health, feedback, ingestion, and quality APIs. Multi-provider AI, theme discovery, evidence-backed insights, and Hindsight memory are specified and not served by the API yet.

| Traditional feedback tools | This platform |
|---|---|
| Analyse feedback in isolation | Remembers historical feedback |
| Show what customers say *now* | Shows how concerns *evolve* |
| Charts without context | Evidence-backed recommendations |
| No link to product decisions | Correlates feedback with releases |

This platform bridges that gap by combining:
- **Strict Ingestion & Quality Control:** Deterministic ingestion, schema validation, intra-batch and database deduplication, multilingual normalization, PII sanitization, and spam detection.
- **Relational Source of Truth:** A structured PostgreSQL schema capturing feedback, upload jobs, themes, aspect sentiment, snapshots, releases, and insight evidence.
- **Multi-Provider AI Intelligence (Planned):** Orchestrated inference across Google Gemini, OpenRouter, and direct xAI Grok with automated fallback and structured output contracts.
- **Persistent Contextual Memory via Hindsight (Planned):** Long-term episodic, semantic, and temporal reasoning that connects current feedback to historical patterns and specific product releases.

```
Raw Customer Feedback (CSV / JSON / Reviews / Tickets)
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│     Feedback Ingestion & Quality Control Pipeline      │
│  Validation ──► Dedup ──► Normalization ──► PII Scrub  │
└────────────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│         Structured PostgreSQL Source of Truth          │
│   Feedback (Immutable) │ Upload Jobs │ Themes │ Links  │
└────────────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│    Feedback Intelligence Agent (Multi-Provider AI)     │
│  Gemini (Primary) ──► OpenRouter ──► Grok (xAI Direct) │
└────────────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│          Hindsight Long-Term Memory Layer              │
│    Episodic Memory │ Semantic Trends │ Temporal Diffs  │
└────────────────────────────────────────────────────────┘
                      │
                      ▼
Evidence-Backed Product Recommendations & Interactive Analytics
```

---

## ❗ The Problem It Solves

Modern product teams collect customer feedback from disparate channels—app store reviews, Zendesk support tickets, in-app surveys, customer interviews, and social media. However:

1. **Fragmented Channels:** Feedback is siloed across separate tools with incompatible schemas and varying data quality.
2. **Loss of Historical Context:** Teams repeatedly investigate recurring issues because past customer complaints and bug reports are forgotten across planning cycles.
3. **Emerging vs. Chronic Confusion:** It is difficult to separate brand-new bugs introduced by recent deployments from persistent, low-grade background dissatisfaction.
4. **Unverifiable AI Summaries:** Generic LLM dashboards often hallucinate trends or summarize feedback without linking back to traceable customer records.
5. **No Direct Correlation with Releases:** Teams cannot easily measure whether a product update actually resolved targeted customer pain points without manual post-mortems.

**Core Value Proposition:** Move from *collecting* customer feedback to *continuously learning* from it with mathematical evidence, historical continuity, and data immutability.

---

## ✨ Implemented vs. Planned Capabilities

To provide complete transparency between active code and future roadmap items:

### ✅ Genuinely Implemented & Tested Capabilities

| Capability | Module | Description & Status |
| :--- | :--- | :--- |
| **FastAPI Backend Core** | `backend/app/` | Lifespan application factory, centralized Pydantic v2 settings, structured logging, and unified exception handling. |
| **Health & Readiness API** | `backend/app/api/routes/health.py` | `GET /` and `GET /api/health` providing database connectivity status and dependency readiness. |
| **Relational Data Layer** | `backend/app/models/` | 9 SQLAlchemy 2.x relational tables covering all 8 core entities with UUID PKs, UTC timestamps, and explicit constraints. |
| **Alembic Migrations** | `backend/alembic/` | 5 chained revisions (`ae66156cfb1a` → `b702ef22d23b` → `c3f912b4e87a` → `e5a8f23c91d4` → `f6b903e1a82d`). |
| **Feedback Ingestion** | `backend/app/services/feedback_ingestion.py` | Multipart CSV (`utf-8`, `utf-8-sig`) and JSON array ingestion with strict timestamp validation. |
| **Upload Job Tracking** | `backend/app/models/upload_job.py` | `UploadJob` lifecycle tracking (`pending`, `processing`, `completed`, `completed_with_errors`, `failed`) with row error recording. |
| **Deduplication Engine** | `backend/app/services/feedback_ingestion.py` | Two-tier deduplication: intra-batch SHA-256 content hashing and database index-assisted lookup on `(product, timestamp)`. |
| **Ingestion Safeguards** | `backend/app/core/config.py` | Hard limits: 10 MB maximum file size, 10,000 records per upload, 10,000 characters per feedback item. |
| **Feedback Immutability** | `backend/app/models/feedback.py` | Original customer input (`feedback_text`) is strictly read-only; processed data is stored in `cleaned_feedback_text`. |
| **Text Normalization** | `backend/app/services/text_normalization.py` | Unicode NFC normalization, CRLF to LF, whitespace collapsing, emoji preservation, and code syntax preservation. |
| **PII Detection & Redaction**| `backend/app/services/pii_detector.py` | Redacts emails, international phones (US, UK, FR, DE, IN), IPv4 addresses, URLs (preserving debug paths), and SSN/card patterns. |
| **Spam & Noise Detection** | `backend/app/services/spam_detector.py` | Identifies empty strings, repeated characters, spam keywords, URL-only text, and short strings (preserving non-Latin alphabets). |
| **Transparent Quality Scoring** | `backend/app/services/quality_scorer.py` | Decoupled `content_quality_score` and `metadata_completeness_score` (0.0 to 100.0) with guaranteed sentiment neutrality. |
| **Batch Row-Level Locking** | `backend/app/services/feedback_cleaning.py` | PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` for concurrent workers with fallback for SQLite testing. |
| **Automated Test Suite** | `backend/tests/` | 88 automated pytest unit and integration tests passing with 100% pass rate. |
| **Web App** | `frontend/` | React 19, TypeScript, and Vite landing page plus a console for the live health, feedback, ingestion, and quality APIs. |

### ⏳ Planned Capabilities (In Active Design & Development)

- **Multi-Provider AI Orchestration (Part 5 & 5.1):** Dynamic failover across Gemini, OpenRouter, and direct xAI Grok with circuit breakers and retry policies (settings drafted; provider clients and failover orchestration in development).
- **AI Classification & Sentiment Analysis:** Multi-theme extraction, aspect-based sentiment, pain-point intensity, and customer intent classification via LLM.
- **Theme Discovery & Trend Engine:** Semantic clustering, recurring/emerging theme flags, sentiment velocity over time, and release before/after correlation.
- **Hindsight Persistent Memory Integration (Part 9):** Episodic, semantic, and temporal memory synchronization with source ID provenance.
- **Evidence-Backed Insight Synthesizer:** Rule-governed recommendation engine requiring underlying database citations before generating insights.

---

## 🏗 System Architecture

The platform is designed as a **modular service-oriented architecture** centered around a structured relational database as the authoritative source of truth.

```mermaid
flowchart TD
    subgraph DataSources["Data Sources (Multi-Channel)"]
        CSV["CSV Datasets"]
        JSON["JSON Payloads"]
        Reviews["App Store / Play Store (Planned)"]
        Tickets["Support Tickets / CRM (Planned)"]
    end

    subgraph IngestionLayer["Ingestion & Quality Assurance (Implemented)"]
        API["FastAPI Ingestion Endpoint"]
        Val["Strict Schema & Timestamp Validation"]
        Dedup["Intra-Batch & DB Deduplication"]
        Clean["Text Normalization & PII Redaction"]
        Scorer["Spam Check & Quality Scoring"]
    end

    subgraph StorageLayer["Authoritative Relational Core (Implemented)"]
        DB[(PostgreSQL 15+)]
        FB["Feedback Table (Immutable Raw Text)"]
        Jobs["Upload Jobs Table"]
        CleanFB["Cleaned Feedback & Quality Flags"]
        DB --> FB
        DB --> Jobs
        DB --> CleanFB
    end

    subgraph AIOrchestration["AI Intelligence Layer (Planned)"]
        Router{"AI Provider Router"}
        Gemini["Google Gemini (Primary)"]
        OpenRouter["OpenRouter (Secondary Routing)"]
        Grok["xAI Grok Direct (Tertiary)"]
        Router -->|1. Try| Gemini
        Router -->|2. Fallback on 429/5xx| OpenRouter
        Router -->|3. Fallback on exhaustion| Grok
    end

    subgraph MemoryLayer["Persistent Contextual Memory (Planned)"]
        Hindsight["Hindsight Engine"]
        Episodic["Episodic Memory (Events)"]
        Semantic["Semantic Memory (Themes)"]
        Temporal["Temporal Memory (Changes Over Time)"]
        Hindsight --> Episodic
        Hindsight --> Semantic
        Hindsight --> Temporal
    end

    subgraph PresentationLayer["Presentation & Exploration (Planned)"]
        UI["React / Vite Web UI"]
        Plotly["Plotly Interactive Analytics"]
        Chat["Memory-Augmented Research Agent"]
    end

    DataSources --> API
    API --> Val --> Dedup --> Clean --> Scorer --> DB
    CleanFB -.-> Router
    Router -.-> Hindsight
    Hindsight -.-> PresentationLayer
    DB -.-> PresentationLayer
```

### Architectural Principles

1. **PostgreSQL Is the Sole Source of Truth:** Neither LLM responses nor external memory services serve as the authoritative store for raw records or analytics metrics. All aggregate statistics are computed directly in SQL.
2. **Original Data Immutability:** Raw customer feedback is preserved in its exact uploaded form. Normalization, redaction, and classification are persisted in distinct columns.
3. **Evidence Grounding:** AI insights must explicitly cite source `feedback_id` records. If an insight cannot be substantiated with database records, it is rejected.
4. **Graceful Degradation:** If AI providers or memory services experience downtime, ingestion, data quality processing, and relational querying continue without disruption.

---

## 🤖 Multi-Provider AI Architecture (Planned)

To ensure uninterrupted intelligence processing under production workloads, the system features a unified multi-provider orchestration strategy:

```
Provider Request Order:
1. Google Gemini (Primary)
        │
        ├── [Quota Exhaustion / Rate Limit 429 / 5xx Error]
        ▼
2. OpenRouter (Secondary / Dynamic Multi-Model Routing)
        │
        ├── [Provider Outage / Upstream Failure]
        ▼
3. xAI Grok Direct API (Tertiary / Fallback)
```

### Key Components

- **Common Provider Abstraction:** A standard `BaseAIProvider` interface defining uniform signatures for classification, theme extraction, and insight synthesis.
- **Consistent Structured Response Contracts:** All models produce validated Pydantic schemas using structured outputs or JSON-schema constraints, ensuring field-level predictability regardless of the underlying LLM.
- **Provider-Specific Error Normalization:** Translates proprietary SDK exceptions into uniform internal error types:
  - `RateLimitException` (HTTP 429)
  - `QuotaExceededException` (Billing/exhaustion)
  - `AuthenticationException` (Invalid credentials)
  - `ModelUnavailableException` (HTTP 502/503/504)
- **Bounded Retries with Exponential Backoff:** Configurable transient retry attempts before escalating to the fallback provider.
- **Provider Cooldown & Circuit Breaking:** Temporarily trips offline providers into a cooling state (e.g., 60 seconds) after consecutive failures, routing traffic directly to the active secondary provider.
- **Observability & Audit Trails:** Every classification record tracks `ai_provider_used`, `ai_model_name`, `tokens_consumed`, and `latency_ms`.

> *Note: Settings and schema structures for multi-provider routing are configured in `backend/app/core/config.py`. Provider clients and live failover handlers are currently in development.*

---

## 🧠 Hindsight Memory Layer (Planned)

The integration with **Hindsight** provides the agent with human-like memory across sprint cycles and quarterly product roadmaps.

| Memory Tier | What It Stores | Example |
| :--- | :--- | :--- |
| **Episodic Memory** | Discrete events and significant feedback clusters | *"In October 2026, 42 users reported checkout timeouts after v2.4.0."* |
| **Semantic Memory** | General synthesized product domain knowledge | *"Checkout performance has historically been a high-churn driver for European users."* |
| **Temporal Memory** | Trajectory and evolution of customer sentiment over time | *"Complaints regarding payment latency decreased by 68% following the v2.5 release."* |

### Strict Provenance Rules
- **No Uncurated Memory Ingestion:** Raw feedback is never dumped blindly into long-term memory; only validated themes, verified anomalies, and synthesized milestones are retained.
- **Bi-directional Provenance:** Every memory entry in PostgreSQL references its upstream `bank_id`, `hindsight_memory_id`, and source entity IDs.
- **Resilience:** If the Hindsight service is unavailable, core ingestion and relational queries remain fully operational, with memory-dependent insights flagged as *limited context*.

---

## 🧰 Technology Stack

### Backend (Implemented)
- **Language & Runtime:** Python 3.11+
- **Web Framework:** FastAPI 0.115+
- **ASGI Server:** Uvicorn (with standard worker support)
- **Validation & Settings:** Pydantic v2 & Pydantic Settings
- **ORM / Database Access:** SQLAlchemy 2.x
- **Database Driver:** Psycopg 3 (`psycopg[binary]`)
- **Schema Migrations:** Alembic
- **Testing:** Pytest, AnyIO, HTTPX (`AsyncClient`)

### Database (Implemented)
- **Primary Engine:** PostgreSQL 15+ (Production)
- **Test Engine:** SQLite (in-memory and file-based test isolation)

### AI & Memory (Planned / In Active Integration)
- **Primary Provider:** Google Gemini API (`gemini-2.5-flash`)
- **Secondary Provider:** OpenRouter API (`google/gemini-2.0-flash-001`, with Claude & Llama fallbacks)
- **Tertiary Provider:** xAI Grok direct API (`grok-4.7`)
- **Persistent Memory:** Hindsight API

### Frontend
- **Framework:** React 19 with TypeScript and Vite
- **Routing:** React Router
- **Styling:** Tailwind CSS 4
- **Motion:** Motion (Framer Motion)

---

## 🗄 Database Schema & Data Models

The database models are implemented using SQLAlchemy 2.x declarative mappings and managed via Alembic:

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│           upload_jobs           │           │            feedback             │
├─────────────────────────────────┤           ├─────────────────────────────────┤
│ job_id (PK, UUID)               │1         *│ feedback_id (PK, UUID)          │
│ filename                        │───────────│ upload_job_id (FK)              │
│ status                          │           │ source, customer_id             │
│ total_records, inserted_records │           │ feedback_text (Original Raw)    │
│ duplicate_records, rejected     │           │ cleaned_feedback_text (Cleaned) │
│ errors (JSONB)                  │           │ quality_status, quality_score   │
│ created_at, completed_at        │           │ pii_detected, pii_types (JSONB) │
└─────────────────────────────────┘           │ deleted_at (Soft Delete)        │
                                              └─────────────────────────────────┘
                                                               │ 1
                                                               │
                                                               │ *
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│             themes              │           │         feedback_themes         │
├─────────────────────────────────┤           ├─────────────────────────────────┤
│ theme_id (PK, UUID)             │1         *│ feedback_id (FK)                │
│ product, theme_name (Unique)    │───────────│ theme_id (FK)                   │
│ category, status, description   │           │ relevance_score, sentiment      │
└─────────────────────────────────┘           └─────────────────────────────────┘
                │ 1                                            │ 1
                │                                              │
                │ *                                            │ *
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│         theme_snapshots         │           │        sentiment_history        │
├─────────────────────────────────┤           ├─────────────────────────────────┤
│ snapshot_id (PK, UUID)          │           │ sentiment_id (PK, UUID)         │
│ theme_id (FK)                   │           │ feedback_id (FK), theme_id (FK) │
│ period_start, period_end        │           │ sentiment_label, score          │
│ feedback_count, sentiment_avg   │           │ confidence_score                │
└─────────────────────────────────┘           └─────────────────────────────────┘
```

### Table Descriptions & Invariants

1. **`feedback`:** Preserves raw customer submissions alongside data-quality metrics and processed text. Soft-delete support via `deleted_at` guarantees historical auditability.
2. **`upload_jobs`:** Persistent audit log of every batch file upload, tracking total, inserted, duplicate, and rejected counts alongside row error details.
3. **`themes`:** Canonical topics extracted from customer feedback, uniquely constrained by `(product, theme_name)`.
4. **`feedback_themes`:** Many-to-many junction associating feedback records with themes, including aspect-level sentiment.
5. **`sentiment_history`:** Granular sentiment scores and model confidence metrics per record and theme.
6. **`product_changes`:** Tracks internal release versions, dates, and descriptions to correlate customer sentiment shifts with product updates.
7. **`theme_snapshots`:** Aggregated periodic rollups of theme volumes and sentiment distributions (`CHECK (period_start <= period_end)`).
8. **`insights` & `insight_evidence`:** AI-generated recommendations linked to supporting feedback records (`ON DELETE RESTRICT` protects cited evidence).
9. **`memory_metadata`:** Tracks external Hindsight memory identifiers and source entity relationships.

---

## 🧹 Feedback Ingestion & Quality Control Pipeline

The ingestion and cleaning pipeline enforces strict data integrity before records reach AI models or analytics views:

```
[Uploaded File] ──► Format Detection (CSV / JSON)
                       │
                       ▼
               Schema Validation
               - Required fields present
               - Valid ISO 8601 UTC timestamp
               - Non-empty feedback text
                       │
                       ▼
             Duplicate Detection
             - Intra-batch content hash check
             - DB query on (product, timestamp)
                       │
                       ▼
             Text Normalization
             - Unicode NFC conversion
             - CRLF normalized to LF
             - Whitespace trimmed; emojis preserved
             - Code snippets preserved (e.g. Map<String, Object>)
                       │
                       ▼
            Sensitive PII Redaction
            - Emails replaced with [EMAIL]
            - Phone numbers replaced with [PHONE]
            - URLs sanitized (credentials removed; debug paths kept)
            - IPv4 addresses scrubbed (software versions preserved)
                       │
                       ▼
            Spam & Noise Evaluation
            - Repetitive characters flagged
            - Gibberish / low-information text detected
            - Non-Latin scripts (Devanagari, CJK, Cyrillic) protected
                       │
                       ▼
         Quality Scoring (0.0 to 100.0)
         - content_quality_score (text clarity & detail)
         - metadata_completeness_score (optional fields populated)
         - Sentiment Neutrality: emotional text is never penalized
                       │
                       ▼
       Persistence (Atomic & Versioned)
       - Raw text strictly preserved
       - Cleaned text written to cleaned_feedback_text
       - Cleaning run versioned (e.g. '1.0.0')
```

---

## 🔌 API Reference

### 1. Implemented Endpoints

#### Health & Root Metadata

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Returns service name, version, and API documentation links. |
| `GET` | `/api/health` | Verifies database connectivity and reports application health. |

**Example Health Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "database": {
    "status": "connected",
    "details": "PostgreSQL connection active"
  }
}
```

---

#### Feedback Ingestion & Retrieval

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/feedback/upload` | Ingests multipart CSV or JSON feedback files. |
| `GET` | `/api/feedback` | Lists feedback records with pagination and filtering. |
| `GET` | `/api/feedback/{feedback_id}` | Retrieves a single feedback record by UUID. |
| `GET` | `/api/feedback/jobs/{job_id}` | Retrieves status and metrics of an ingestion job. |

**Upload Ingestion Example:**
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/feedback/upload" -Form @{
    file = Get-Item -Path "feedback.json"
}
```

**Upload Response (HTTP 200):**
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

---

#### Data Cleaning & Quality Control

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/feedback/clean` | Batch cleans unprocessed feedback records using row-level locking. |
| `POST` | `/api/feedback/{feedback_id}/clean` | Executes the cleaning pipeline on a single record. |
| `GET` | `/api/feedback/{feedback_id}/quality` | Returns quality scores, detected PII types, and flags. |
| `GET` | `/api/feedback/quality/summary` | Returns aggregated quality distributions and metrics. |

**Batch Clean Request Example:**
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/feedback/clean?limit=100&reprocess=false"
```

**Quality Summary Response Example:**
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

### 2. Planned Endpoints (Specification)

The following endpoints represent the target API contract for upcoming development parts:

| Method | Endpoint | Target Milestone | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/feedback/analyze` | Part 5 | Triggers multi-provider AI classification and aspect sentiment analysis. |
| `GET` | `/api/themes` | Part 6 | Retrieves identified themes, status, and feedback volume. |
| `GET` | `/api/sentiment/trends` | Part 6 | Returns daily, weekly, and monthly sentiment trajectories. |
| `GET` | `/api/insights` | Part 7 | Returns evidence-grounded product insights and recommendations. |
| `POST` | `/api/product-changes` | Part 7 | Records product releases, version tags, and feature flags. |
| `GET` | `/api/product-impact` | Part 7 | Compares sentiment before and after specific release dates. |
| `POST` | `/api/agent/chat` | Part 8 | Interactive Q&A with the memory-augmented product intelligence agent. |
| `GET` | `/api/memory/search` | Part 9 | Semantic search over Hindsight episodic and temporal memories. |

---

## 📁 Repository Structure

```text
Feedback/
├── backend/
│   ├── alembic/                    # Database migration environment
│   │   ├── versions/               # Versioned migration scripts
│   │   └── env.py                  # Alembic runner configuration
│   ├── app/
│   │   ├── api/                    # API routing layer
│   │   │   └── routes/
│   │   │       ├── health.py       # Health check endpoints
│   │   │       └── feedback.py     # Ingestion & cleaning endpoints
│   │   ├── core/                   # Infrastructure configuration
│   │   │   ├── config.py           # Pydantic Settings & environment parsing
│   │   │   ├── exceptions.py       # Centralized exception handlers
│   │   │   └── logging.py          # Structured logging setup
│   │   ├── db/                     # Database session management
│   │   │   ├── base.py             # DeclarativeBase base model
│   │   │   └── session.py          # Session factory & dependency injection
│   │   ├── integrations/           # External service adapters
│   │   │   ├── ai/                 # Multi-provider AI routing & failover (In progress)
│   │   │   ├── gemini/             # Google Gemini integration client
│   │   │   └── hindsight/          # Hindsight persistent memory client
│   │   ├── models/                 # SQLAlchemy 2.x declarative models
│   │   │   ├── feedback.py         # Feedback records & quality fields
│   │   │   ├── upload_job.py       # Ingestion job tracking
│   │   │   ├── theme.py            # Themes & theme snapshots
│   │   │   ├── sentiment.py        # Sentiment history
│   │   │   ├── product_change.py   # Product releases & feature flags
│   │   │   ├── insight.py          # Insights & citation evidence
│   │   │   └── memory.py           # Hindsight metadata tracking
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   │   ├── feedback.py         # Feedback & cleaning DTOs
│   │   │   └── health.py           # Health response schemas
│   │   ├── services/               # Core business logic
│   │   │   ├── feedback_ingestion.py   # Parsing, validation & deduplication
│   │   │   ├── feedback_cleaning.py    # Batch orchestrator with row locking
│   │   │   ├── text_normalization.py   # Unicode & whitespace normalization
│   │   │   ├── pii_detector.py         # PII detection & redaction
│   │   │   ├── spam_detector.py        # Noise & spam classification
│   │   │   └── quality_scorer.py       # Decoupled quality scoring
│   │   └── main.py                 # FastAPI application factory
│   ├── tests/                      # Automated test suite (88 passing tests)
│   │   ├── test_health.py
│   │   ├── test_models.py
│   │   ├── test_database_session.py
│   │   ├── test_schema_refinements.py
│   │   ├── test_alembic.py
│   │   ├── test_safeguards.py
│   │   ├── test_feedback_ingestion.py
│   │   └── test_feedback_cleaning.py
│   ├── .env.example                # Template configuration file
│   ├── alembic.ini                 # Alembic configuration
│   └── requirements.txt            # Python dependencies
├── frontend/                       # React + Vite landing page and API console
├── .gitignore                      # Git ignore patterns
└── README.md                       # Root documentation
```

---

## 🚀 Getting Started & Local Setup

### Prerequisites

- **Python:** 3.11 or newer (`python --version`)
- **Node.js:** 18 or newer, for the frontend
- **PostgreSQL:** Version 15+ (Required for persistent production usage; SQLite is supported for local tests)
- **PowerShell:** PowerShell 5.1+ (Windows) or standard bash shell (macOS/Linux)

### Frontend

From `frontend/`:

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The landing page loads on its own. `/console` calls the API, so start the backend in the steps below before using it.

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/mukundchoubey88-lang/Feadback-synthziser.git
cd Feadback-synthziser
```

---

### Step 2: Set Up Virtual Environment

#### Windows (PowerShell):
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

*(If script execution is blocked on Windows, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`)*

#### macOS / Linux:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

---

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 4: Configure Environment Variables

Create your local `.env` file from the provided template:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings:

```env
# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
API_V1_PREFIX=/api

# Database Connection (PostgreSQL with psycopg v3 driver)
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/feedback_db

# Multi-Provider AI Configuration (Part 5 & 5.1)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=google/gemini-2.0-flash-001
OPENROUTER_FALLBACK_MODELS=anthropic/claude-3.5-haiku,meta-llama/llama-3.3-70b-instruct

XAI_API_KEY=your_xai_api_key_here
XAI_MODEL=grok-4.7

AI_PRIMARY_PROVIDER=gemini
AI_PROVIDER_FALLBACK_ENABLED=true
AI_PROVIDER_PRIORITY=gemini,openrouter,grok
AI_REQUEST_TIMEOUT=30.0
AI_PROVIDER_MAX_RETRIES=2
AI_PROVIDER_COOLDOWN_SECONDS=60

# Hindsight Persistent Memory Configuration (Part 9)
HINDSIGHT_API_KEY=
HINDSIGHT_BASE_URL=

# Upload Safeguards
MAX_UPLOAD_FILE_SIZE_BYTES=10485760
MAX_UPLOAD_RECORDS=10000
MAX_FEEDBACK_TEXT_LENGTH=10000

# CORS Configuration
CORS_ORIGINS=http://localhost:5173
```

---

### Step 5: Run Database Migrations

Apply the Alembic migration history to your PostgreSQL database:

```bash
alembic upgrade head
```

---

### Step 6: Start the Development Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, navigate to:
- **Interactive Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Service Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 🧪 Running Automated Tests

The backend includes a comprehensive automated test suite leveraging `pytest` and `httpx`. The test suite uses isolated in-memory and SQLite test databases, meaning tests run cleanly without requiring a live PostgreSQL instance.

Execute all tests from the `backend/` directory:

```powershell
pytest -v
```

**Test Coverage Summary (88 passing tests):**
- `test_health.py` — Health check status and service metadata.
- `test_models.py` — Model relationships, constraints, and table definitions.
- `test_database_session.py` — Database engine initialization and session management.
- `test_schema_refinements.py` — Soft deletes, foreign key protections, and snapshot checks.
- `test_alembic.py` — Migration script validity and head alignment.
- `test_safeguards.py` — File upload size, record count, and text length bounds.
- `test_feedback_ingestion.py` — CSV/JSON ingestion, deduplication, and job tracking.
- `test_feedback_cleaning.py` — Normalization, PII redaction, noise filtering, and scoring.

---

## 🛡 Edge Cases & Reliability

| Scenario | Handled Behavior | Implementation Status |
| :--- | :--- | :--- |
| **Duplicate Submissions** | Deduplicated intra-batch and against the database via indexed lookup on `(product, timestamp)`. | ✅ Implemented |
| **Missing Timestamps** | Rejected explicitly with validation error; synthetic timestamps are never fabricated. | ✅ Implemented |
| **PII Exposure** | Detected and scrubbed into generic placeholders (`[EMAIL]`, `[PHONE]`, `[URL]`, `[IP_ADDRESS]`, `[ID_NUMBER]`). | ✅ Implemented |
| **Raw Data Loss** | Original feedback is preserved in immutable database columns; only cleaned copies are processed. | ✅ Implemented |
| **High Concurrency Cleaning** | Handled with `SELECT ... FOR UPDATE SKIP LOCKED` to prevent duplicate processing by worker threads. | ✅ Implemented |
| **Emotional / Critical Feedback** | Evaluated with strictly neutral quality scoring; negative sentiment is never penalized as low quality. | ✅ Implemented |
| **Multilingual Input** | Protected across Latin, Devanagari, Cyrillic, CJK, and Arabic scripts. | ✅ Implemented |
| **AI Provider Quota Exhaustion** | Failover routing from Gemini to OpenRouter to direct xAI Grok with exponential backoff. | ⏳ In Active Integration |
| **Memory Service Outage** | PostgreSQL continues serving structured analytics; memory-augmented insights are marked as limited. | ⏳ Planned |

---

## 🗺 Development Roadmap

```
[Part 1: Foundation] ──► [Part 2: DB Models] ──► [Part 2.1: Schema Hardening]
        ✓                         ✓                            ✓
                                                               │
[Part 4.1: Cleaning Hardening] ◄── [Part 4: Data Quality] ◄── [Part 3: Ingestion API]
        ✓                                    ✓                         ✓
        │
        ▼
[Part 5 / 5.1: Multi-Provider AI Failover] (In Progress)
        │
        ▼
[Part 6: Theme Discovery & Aspect Sentiment] (Upcoming)
        │
        ▼
[Part 7: Product Release Correlation & Insights] (Upcoming)
        │
        ▼
[Part 8 & 9: Hindsight Persistent Memory & Research Agent] (Upcoming)
        │
        ▼
[Part 10: Frontend UI (React + Vite) & Production Deployment] (Landing page and API console in place)
```

- [x] **Part 1:** Backend Foundation, FastAPI Factory, Settings & Logging
- [x] **Part 2:** PostgreSQL Relational Models (9 Tables) & Alembic Migrations
- [x] **Part 2.1:** Schema Refinement, Soft Deletes & Integrity Constraints
- [x] **Part 3:** CSV/JSON Ingestion API, Duplicate Detection & Upload Job Tracking
- [x] **Part 4:** Data Cleaning, Text Normalization, PII Scrubbing & Quality Scoring
- [x] **Part 4.1:** Data Cleaning Corrections, Multilingual Hardening & Row Locking
- [ ] **Part 5 / 5.1:** Multi-Provider AI Orchestration (Gemini → OpenRouter → xAI Grok)
- [ ] **Part 6:** Semantic Theme Extraction, Aspect-Based Sentiment & Volume Velocity
- [ ] **Part 7:** Product Change Correlation & Evidence-Backed Recommendation Engine
- [ ] **Part 8:** AI Research Agent & Memory-Augmented Natural Language Q&A
- [ ] **Part 9:** Deep Hindsight Integration (Episodic, Semantic & Temporal Recall)
- [x] **Part 10:** Frontend landing page and API console (React, Vite, TypeScript). Production deployment is still ahead.

---

## 👤 Author & License

- **Author:** Mukund Choubey — *B.Tech CSE (AI & ML), S-VYASA, Bengaluru*
- **Repository:** [https://github.com/mukundchoubey88-lang/Feadback-synthziser.git](https://github.com/mukundchoubey88-lang/Feadback-synthziser.git)
- **License:** Licensed under the [MIT License](LICENSE).

<p align="center"><i>Move from collecting customer feedback to continuously learning from it.</i></p>
