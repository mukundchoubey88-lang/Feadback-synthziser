# Feedback Intelligence Agent 🧠📊
### Enterprise-Grade AI Platform for Automated Customer Feedback Synthesis & Theme Intelligence

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![pgvector](https://img.shields.io/badge/pgvector-0.5+-green.svg)](https://github.com/pgvector/pgvector)
[![Google Gemini API](https://img.shields.io/badge/Gemini_Embedding-2-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![Tests Passing](https://img.shields.io/badge/tests-244%20passed-brightgreen.svg)](https://docs.pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An asynchronous, production-conscious intelligence backend that ingests noisy multi-channel customer feedback, cleans and redacts PII, performs multi-topic aspect sentiment classification via LLM orchestration, generates 768-dimensional semantic embeddings, and groups customer feedback into deterministic problem themes using pure agglomerative hierarchical clustering.

---

## 🌟 Executive Summary & Problem Solved

Product and engineering teams receive thousands of feedback items daily from diverse channels—App Store reviews, support tickets, survey responses, and Discord chats. Manually synthesizing this unstructured text into actionable engineering initiatives is slow, biased, and error-prone.

The **Feedback Intelligence Agent** automates this end-to-end pipeline with:
- **Zero Data Leakage:** Deterministic PII detection and regex-based redaction (credit cards, emails, phone numbers, IP addresses, SSNs).
- **Cost-Conscious AI Orchestration:** Circuit-breaker-enabled multi-provider failover (Google Gemini, OpenRouter, xAI Grok) with token budget controls.
- **Persistent Vector Memory:** Embeddings generated via Google `gemini-embedding-2` stored with deterministic SHA-256 hashes to prevent redundant billable API calls.
- **Mathematical Clustering Integrity:** Zero-dependency, pure-Python Agglomerative Average-Linkage clustering with deterministic tie-breaking ($O(N^2 \log N)$) and unit-normalized centroid calculation.
- **Enterprise Database Design:** Dual-dialect portable vector support (`pgvector` on PostgreSQL and JSON arrays on SQLite for instant local testing), with complete lineage tracking for theme merges and splits.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Ingestion ["1. Data Ingestion & Quality Gateway"]
        A[Raw Input CSV / JSON] --> B[Streaming Chunked Reader 64KB]
        B --> C[PII Masking & Regex Redaction]
        C --> D[Spam & Quality Scorer]
        D --> E[(PostgreSQL: feedback)]
    end

    subgraph Intelligence ["2. Multi-Provider AI Classification"]
        E -->|Cleaned Text Only| F[AI Provider Manager]
        F --> G{Primary: Gemini 2.0}
        G -->|Failover| H[Secondary: OpenRouter]
        H -->|Fallback| I[Tertiary: xAI Grok]
        G & H & I --> J[(feedback_classifications)]
    end

    subgraph VectorEngine ["3. Semantic Vector Persistence"]
        E -->|Product + Cleaned Text| K[Deterministic SHA-256 Hasher]
        K --> L{Hash Cache Hit?}
        L -->|Yes| M[Bypass API Call]
        L -->|No| N[Gemini Embedding 2: 768D]
        N --> O[(feedback_embeddings: PortableVector)]
    end

    subgraph Clustering ["4. Deterministic Clustering Engine"]
        O --> P[Product-Isolated Data Retrieval]
        P --> Q[Pairwise Cosine Distance Matrix]
        Q --> R[Agglomerative Average Linkage UPGMA]
        R --> S[Lance-Williams Min-Heap Priority Queue]
        S --> T[Centroid & Medoid Representative Selection]
        T --> U[Candidate Clusters & Noise Classification]
    end
```

---

## 🚀 Key Architectural Highlights

### 1. Multi-Provider AI Orchestration with Resilient Failover
- **Tiered Failover:** Automatically routes classification prompts across **Google Gemini** $\to$ **OpenRouter** (Claude 3.5 Haiku / Llama 3.3 70B) $\to$ **xAI Grok**.
- **Self-Healing:** Provider health tracking with dynamic exponential backoff, cooldown timers, and structured fallback recovery.
- **Evidence Grounding:** AI classifications verify extracted customer pain points and aspect sentiments against the original text to prevent LLM hallucinations.

### 2. High-Performance Vector Embeddings (`gemini-embedding-2`)
- **Deterministic SHA-256 Hashing:** Computes `hash(product, cleaned_text, model, dimensions, version)`. If the hash matches an existing record, the billable API call is completely bypassed.
- **Atomic Concurrency Recovery:** In-place vector updates on text changes, and automatic savepoint recovery on concurrent insert race conditions.
- **Exclusivity:** Raw uncleaned feedback is **never** embedded. Only normalized, PII-sanitized text is vectorized.

### 3. Pure-Python Agglomerative Average-Linkage Clustering
- **Zero Heavy C-Dependencies:** Implemented strictly using the Python standard library (`math`, `heapq`), avoiding 200MB+ binary wheels for lightweight, portable deployment.
- **Deterministic Results:** Tie-breaking orders cluster merges by $(d, \min(u_A, u_B), \max(u_A, u_B))$, guaranteeing 100% reproducible cluster trees across 100+ consecutive runs.
- **Lance-Williams Incremental Updates:** Updates cluster distances in $O(N \log N)$ during merges:
  $$D(A \cup B, C) = \frac{|A| \cdot D(A, C) + |B| \cdot D(B, C)}{|A| + |B|}$$
- **Medoid Exemplars:** Selects representative feedback records closest to the unit-normalized centroid vector $\mathbf{c} = \frac{\sum \mathbf{v}_i}{\|\sum \mathbf{v}_i\|_2}$.

### 4. Enterprise Database Engineering
- **`PortableVector` Type Decorator:** Compiles seamlessly to native `pgvector.sqlalchemy.Vector(768)` on PostgreSQL (for HNSW / IVFFlat cosine search `<#>`) and to JSON arrays on SQLite (with Python-level dimension and finite float enforcement).
- **Theme Lineage DAG:** Self-referencing foreign keys (`merged_into_id`, `split_from_id`) and structured `lineage_metadata` preserve full historical auditability when themes merge or split.
- **Transaction Safety:** Read phases and vector calculations are decoupled from database transactions, preventing connection pool starvation.

---

## 🛠️ Technology Stack

| Domain | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Language & Runtime** | Python | 3.11+ | Modern type annotations, async/await, high-performance concurrency |
| **Web Framework** | FastAPI | 0.115+ | High-throughput asynchronous REST API & OpenAPI docs |
| **Server** | Uvicorn | 0.30+ | Production ASGI web server |
| **ORM & Database** | SQLAlchemy 2.0 | 2.0.30+ | Modern mapped column models, typed queries, connection pooling |
| **Vector Database** | pgvector | 0.5.1+ | Native PostgreSQL vector operations and vector indexing |
| **Migrations** | Alembic | 1.13+ | Version-controlled database schema migrations |
| **Validation & Config** | Pydantic v2 | 2.7+ | Strict schema validation, model serialization, Pydantic Settings |
| **HTTP Client** | HTTPX | 0.27+ | Asynchronous non-blocking HTTP requests for LLM APIs |
| **Embeddings Model** | Gemini Embedding 2 | 768D | Google DeepMind's flagship dense text vector model |
| **AI LLMs** | Gemini 2.0 / Grok / Claude | Multi | Multi-topic classification, aspect sentiment, intent detection |
| **Testing** | Pytest & AnyIO | 8.2+ | Unit, integration, regression, and transaction testing (244 tests) |

---

## 📂 Project Structure

```text
Feedback/
├── backend/
│   ├── alembic/                    # Database migration scripts
│   │   └── versions/               # Incremental schema migration versions
│   │
│   ├── app/
│   │   ├── api/                    # API Route Handlers
│   │   │   └── routes/
│   │   │       ├── health.py       # Health checks & dependency telemetry
│   │   │       ├── feedback.py     # Upload, cleaning, classification & embeddings
│   │   │       └── classification.py # Classification summaries & query endpoints
│   │   │
│   │   ├── core/                   # Framework Core
│   │   │   ├── config.py           # Pydantic Settings configuration & bounds
│   │   │   ├── exceptions.py       # Typed custom exception hierarchy
│   │   │   └── logging.py          # Centralized structured logging
│   │   │
│   │   ├── db/                     # Persistence Layer
│   │   │   ├── base.py             # Declarative Base
│   │   │   ├── session.py          # SQLAlchemy session lifecycle management
│   │   │   └── types.py            # PortableVector (pgvector / SQLite JSON)
│   │   │
│   │   ├── models/                 # SQLAlchemy 2.x Entity Models
│   │   │   ├── feedback.py         # Feedback & FeedbackThemes junction
│   │   │   ├── feedback_embeddings.py # Vector persistence & input hashes
│   │   │   ├── classification.py   # Topics, aspects, intent, run number
│   │   │   ├── sentiment.py        # Historical sentiment tracking
│   │   │   ├── theme.py            # Themes, centroids, snapshots & lineage
│   │   │   └── memory.py           # Persistent memory metadata
│   │   │
│   │   ├── schemas/                # Pydantic v2 Contracts
│   │   │   ├── feedback.py         # Ingestion & cleaning schemas
│   │   │   ├── classification.py   # AI classification & sentiment schemas
│   │   │   ├── embedding.py        # Embedding requests & batch responses
│   │   │   └── theme_clustering.py # Candidate clusters & unassigned noise
│   │   │
│   │   ├── services/               # Core Business Domain Services
│   │   │   ├── feedback_ingestion.py # Streaming chunked parser
│   │   │   ├── feedback_cleaning.py  # PII redaction & quality gatekeeping
│   │   │   ├── feedback_classification.py # LLM classification orchestrator
│   │   │   ├── embedding_service.py  # Embedding caching & persistence service
│   │   │   └── theme_clustering_service.py # Agglomerative clustering engine
│   │   │
│   │   └── integrations/           # External AI Integrations
│   │       ├── ai/                 # Multi-provider LLM failover manager
│   │       └── embeddings/         # GeminiEmbeddingProvider & MockProvider
│   │
│   ├── tests/                      # Comprehensive Automated Test Suite (244 tests)
│   ├── requirements.txt            # Python dependencies
│   └── .env.example                # Environment configuration template
│
└── README.md                       # Repository Documentation
```

---

## ⚡ Quickstart & Setup Guide

### 1. Prerequisites
- **Python 3.11+** installed
- **Git** installed
- **PostgreSQL 15+** with `pgvector` extension *(Optional for local test execution; SQLite is used automatically out-of-the-box)*

### 2. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/your-username/Feedback-Intelligence-Agent.git
cd Feedback-Intelligence-Agent/backend

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:
```ini
APP_NAME="Feedback Intelligence API"
APP_ENV=development
DEBUG=true

# Database: Leave empty for SQLite in-memory/fallback, or provide PostgreSQL URL:
# DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/feedback_db

# AI Embedding Provider
AI_EMBEDDING_PROVIDER=gemini
AI_EMBEDDING_MODEL=gemini-embedding-2
AI_EMBEDDING_DIMENSIONS=768
GEMINI_API_KEY=your_gemini_api_key_here

# Multi-Provider AI Classification
AI_PRIMARY_PROVIDER=gemini
GEMINI_MODEL=gemini-2.0-flash
OPENROUTER_API_KEY=your_openrouter_key_here
XAI_API_KEY=your_xai_key_here

# Theme Clustering Parameters
THEME_CLUSTERING_SIMILARITY_THRESHOLD=0.80
THEME_CLUSTERING_MIN_CLUSTER_SIZE=3
THEME_CLUSTERING_MAX_BATCH_SIZE=250
THEME_CLUSTERING_REPRESENTATIVE_COUNT=3
```

### 4. Run Database Migrations (PostgreSQL)

```bash
alembic upgrade head
```

### 5. Launch the Application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI Swagger UI is available at:  
👉 **`http://localhost:8000/docs`**

---

## 🧪 Comprehensive Test Suite (244 Tests Passing)

The platform features an exhaustive, regression-proof test suite covering unit math, AI provider fallbacks, transaction rollbacks, PII redaction, and clustering determinism.

```bash
# Run all 244 tests
pytest tests -v
```

### Test Suite Execution Output:
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\intel\Desktop\Feedback
collected 244 items

backend/tests/test_ai_providers.py .................................     [ 13%]
backend/tests/test_alembic.py .                                          [ 13%]
backend/tests/test_classification_model.py ........                      [ 17%]
backend/tests/test_classification_schemas_and_prompts.py ..............  [ 22%]
backend/tests/test_concurrent_reclassification.py ...                    [ 24%]
backend/tests/test_database_session.py .                                 [ 24%]
backend/tests/test_embedding_persistence.py ....                         [ 26%]
backend/tests/test_embedding_provider.py ....................            [ 34%]
backend/tests/test_embedding_service.py ..................               [ 41%]
backend/tests/test_feedback_classification_api.py ...................... [ 50%]
backend/tests/test_feedback_classification_service.py ..........         [ 54%]
backend/tests/test_feedback_cleaning.py ................................ [ 68%]
backend/tests/test_feedback_ingestion.py ............................... [ 83%]
backend/tests/test_health.py ....                                        [ 85%]
backend/tests/test_migration_downgrade_safety.py ..                      [ 86%]
backend/tests/test_models.py ...                                         [ 87%]
backend/tests/test_safeguards.py ..                                      [ 88%]
backend/tests/test_schema_refinements.py .......                         [ 90%]
backend/tests/test_theme_clustering_service.py ......................    [100%]

======================= 244 passed, 1 warning in 20.47s =======================
```

---

## 📡 Core API Reference

| Method | Endpoint | Description | Key Features |
| :---: | :--- | :--- | :--- |
| `GET` | `/api/health` | System Health & Dependency Telemetry | Database connectivity, provider readiness |
| `POST` | `/api/feedback/upload` | Multipart Dataset Upload (CSV/JSON) | Streaming 64KB chunks, size ceiling (10MB) |
| `POST` | `/api/feedback/clean` | Batch Data Cleaning & PII Sanitization | Regex redaction, spam scoring, quality flags |
| `POST` | `/api/feedback/{id}/classify` | AI Multi-Topic & Sentiment Classification | Grounding checks, aspect sentiment, intent |
| `POST` | `/api/feedback/classify` | Bounded Batch AI Classification | Isolated item failures, retry backoff |
| `GET` | `/api/classifications/summary` | Aggregated Analytics by Product | Sentiment breakdown, intent distribution |
| `POST` | `/api/feedback/{id}/embed` | Generate Feedback Embedding (768D) | SHA-256 caching, in-place update on text edit |
| `POST` | `/api/feedback/embed` | Bounded Batch Feedback Embedding | Pre-filtered cache hits, savepoint rollback |

---

## 📊 Performance Benchmarks (Pure-Python Clustering)

Evaluated with synthetic unit-normalized 768-dimensional vectors on standard CPU hardware:

| Evaluated Feedback ($N$) | Vector Dimensions ($D$) | Clusters Formed | Noise Detected | Latency |
| :---: | :---: | :---: | :---: | :---: |
| **50** | 768 | 5 | 0 | **236 ms** |
| **100** | 768 | 5 | 0 | **740 ms** |
| **150** | 768 | 5 | 0 | **1.55 s** |
| **250** | 768 | 5 | 0 | **4.61 s** |

*Note: For batches $N \le 250$, pure Python provides excellent interactive performance without introducing heavy C-dependencies.*

---

## 🗺️ Project Roadmap

- [x] **Part 1–3:** Streaming Ingestion & Database Foundations (FastAPI, PostgreSQL, Alembic)
- [x] **Part 4:** Data Cleaning, Quality Gatekeeping & PII Sanitization Engine
- [x] **Part 5–6:** Multi-Provider AI Classification & Evidence-Grounded Aspect Sentiment
- [x] **Part 7 (Step 1–3):** `gemini-embedding-2` Provider, Database Persistence & SHA-256 Caching
- [x] **Part 7 (Step 4):** Deterministic Agglomerative Theme Clustering Engine
- [ ] **Part 7 (Step 5):** Theme Lifecycle Management (Activation, Review, DAG Merge & Split)
- [ ] **Part 8:** Emerging & Declining Theme Detection (Velocity & Z-Score Anomaly Tracking)
- [ ] **Part 9:** Hindsight Persistent Memory Integration (Temporal Product Intelligence)
- [ ] **Part 10:** Autonomous Feedback Intelligence Agent (Natural Language Research Assistant)

---

## 📄 License & Attribution

This project is open-source under the [MIT License](LICENSE).  
Developed with focus on mathematical rigor, resilience, and production-grade software craftsmanship.
