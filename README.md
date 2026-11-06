# 🧠 User Feedback Synthesizer — Feedback Intelligence Agent

> An AI product analyst that **remembers** customer feedback, understands how it **changes over time**, and helps product teams make better decisions.

![Status](https://img.shields.io/badge/status-MVP%20%2F%20Ideathon-blue)
![Version](https://img.shields.io/badge/version-1.0-green)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB)
![DB](https://img.shields.io/badge/database-PostgreSQL-336791)
![Memory](https://img.shields.io/badge/memory-Hindsight-purple)
![LLM](https://img.shields.io/badge/LLM-Gemini-orange)

---

## 📑 Table of Contents

1. [Overview](#-overview)
2. [The Problem](#-the-problem)
3. [Key Features](#-key-features)
4. [System Architecture](#-system-architecture)
5. [Hindsight Memory Layer](#-hindsight-memory-layer)
6. [Tech Stack](#-tech-stack)
7. [Database Schema](#-database-schema)
8. [API Reference](#-api-reference)
9. [Project Structure](#-project-structure)
10. [Getting Started](#-getting-started)
11. [Demo Scenario](#-demo-scenario)
12. [Edge Cases & Reliability](#-edge-cases--reliability)
13. [MVP Roadmap](#-mvp-roadmap)
14. [Success Metrics](#-success-metrics)
15. [Future Scope](#-future-scope)
16. [Contributing](#-contributing)

---

## 🔭 Overview

**User Feedback Synthesizer** collects customer feedback from multiple sources, cleans and standardises it, identifies themes and sentiment, and stores everything in PostgreSQL. What makes it different is a **long-term memory layer (Hindsight)**: when new feedback arrives, the agent retrieves what customers said before, compares patterns across time, and links feedback trends to product releases.

### 🎯 Current Status

**✅ Frontend Dashboard** — Fully functional React + Vite + TailwindCSS + Plotly.js dashboard with all 7 views, mock data, and complete UI/UX (deployed in `frontend/`)

**🚧 Backend API** — Architecture documented, implementation pending (FastAPI + PostgreSQL + Gemini + Hindsight)

**📚 Documentation** — Complete system architecture, database schema, API reference, and MVP roadmap

> **You can run the frontend now** to see the full dashboard experience. The backend is described in detail in this README for implementation.

| Traditional feedback tools | This platform |
|---|---|
| Analyse feedback in isolation | Remembers historical feedback |
| Show what customers say *now* | Shows how concerns *evolve* |
| Charts without context | Evidence-backed recommendations |
| No link to product decisions | Correlates feedback with releases |

**Core innovation:** Persistent memory + temporal feedback intelligence + product change correlation + evidence-backed recommendations.

---

## ❗ The Problem

Product teams receive feedback through app reviews, support tickets, surveys, emails, and social platforms, but:

- Feedback is scattered across platforms.
- Repeated complaints are hard to spot over time.
- Emerging problems are hard to separate from recurring ones.
- Sentiment changes are not consistently tracked.
- Product improvements are not compared with later feedback.
- Historical feedback is forgotten or analysed separately.
- Teams lack evidence for product decisions.

---

## ✨ Key Features

- **Multi-source ingestion** — CSV / JSON uploads, app reviews, support tickets, surveys.
- **Data quality pipeline** — validation, UTC timestamp normalisation, deduplication, PII redaction, idempotent imports.
- **AI classification** — topic, feature, sentiment, intensity, pain point, intent, keywords, confidence. Supports **multiple themes per feedback** with **aspect-level sentiment**.
- **Theme discovery** — semantic grouping, recurring / emerging / declining / resolved status, manual merge and correction.
- **Sentiment trend tracking** — daily, weekly, monthly; feature-level; filters out low-volume noise.
- **Emerging theme detection** — compares recent feedback to historical patterns with minimum-evidence thresholds.
- **Product change correlation** — before/after release comparison using *"associated with"* language (never claims causation).
- **Evidence-backed insights** — every insight links to source feedback, shows confidence and time period.
- **Hindsight memory** — episodic, semantic and temporal memory with traceable source IDs.
- **AI research chat** — ask questions like *"Have customers complained about checkout before?"*

> **Principle:** The LLM *explains* calculated results — it never invents metrics. All counts, percentages and comparisons come from PostgreSQL.

---

## 🏗 System Architecture

![System Architecture](docs/architecture.png)

The MVP is a **modular monolith** (FastAPI backend + React frontend) to keep development simple and the demo easy to run.

### Layers

| # | Layer | Components |
|---|---|---|
| 1 | **Data Sources** | Surveys & interviews, app reviews, support tickets, Slack / email, CSV / JSON upload |
| 2 | **Ingestion & Quality Control** | FastAPI ingestion API → format normalisation → validation & missing data → deduplication & spam detection → PII redaction |
| 3 | **Structured Data Layer** | PostgreSQL — insights & evidence, raw feedback, themes & sentiment, product releases |
| 4 | **Feedback Intelligence Agent** | Orchestrator → feedback classifier → theme discovery & clustering → emerging theme detection, aspect-based sentiment → temporal trend & anomaly detection → product change correlation → evidence validation → insight synthesiser |
| 5 | **Hindsight Long-Term Memory** | Memory update & reconciliation, episodic / semantic / temporal memory, memory retrieval |
| 6 | **Reliability & Governance** | Access control & data retention, retry & error handling, confidence & evidence thresholds |
| 7 | **Product Intelligence Interface** | AI research chat, memory explorer, executive dashboard, actionable recommendations, theme explorer, sentiment timeline, product impact tracker |

### Data flow

```mermaid
flowchart TD
    A["Feedback Sources"] --> B["FastAPI Ingestion"]
    B --> C["Validation and Normalisation"]
    C --> D["Deduplication and PII Redaction"]
    D --> E["PostgreSQL"]

    E --> F["AI Agent Orchestrator"]

    F --> G["Feedback Classification"]
    G --> H["Theme and Sentiment Analysis"]
    H --> I["Trend and Emerging Theme Detection"]

    I --> J["Hindsight Memory Retrieval"]
    J --> K["Historical Pattern Comparison"]

    K --> L["Product Change Correlation"]
    L --> M["Evidence Validation"]

    M --> N["AI Insight Generation"]
    N --> O["Hindsight Memory Update"]
    N --> P["Dashboard and AI Chat"]

    Q["Product Release Data"] --> L
```

### Agent processing flow

1. Receive and validate feedback.
2. Store the original record in PostgreSQL.
3. Classify feedback with the LLM.
4. Extract themes and sentiment.
5. Retrieve related memories from Hindsight.
6. Compare with historical patterns.
7. Identify recurring or emerging themes.
8. Check relevant product release information.
9. Validate all insights against source records.
10. Generate recommendations.
11. Update Hindsight with meaningful new knowledge.
12. Refresh dashboard analytics.

---

## 🧠 Hindsight Memory Layer

Hindsight is the **long-term memory** of the agent. **PostgreSQL remains the source of truth** — Hindsight stores contextual knowledge and references, not the only copy of business data.

| Memory type | Stores | Example |
|---|---|---|
| **Episodic** | Meaningful individual events | "In Sept 2026, multiple customers reported slow checkout." |
| **Semantic** | Generalised knowledge from recurring feedback | "Checkout performance is a recurring concern." |
| **Temporal** | How themes and sentiment change over time | "Checkout complaints declined after the October release." |

**Memory rules**

- Don't store every raw feedback record — store events, patterns and validated insights.
- Preserve history instead of overwriting it.
- Retrieve by product, theme, feature and time context.
- Keep source IDs so memories trace back to original feedback.
- Validate retrieved memories against current database data before making important claims.

**If Hindsight is unavailable:** ingestion and basic analytics continue in PostgreSQL, memory-dependent insights are marked *limited*, and memory operations are retried safely.

---

## 🧰 Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Frontend | React + Vite | User interface |
| Backend | Python + FastAPI | API and business logic |
| LLM | Gemini API | Classification, reasoning, summaries |
| Memory | Hindsight | Long-term agent memory |
| Database | PostgreSQL | Structured data and analytics |
| Visualisation | Plotly | Charts and trends |
| Similarity | Embeddings | Semantic grouping of feedback |
| Clustering (optional) | BERTopic | Theme discovery |
| Deployment | Docker | Packaging |

---

## 🗄 Database Schema

| Table | Purpose | Key fields |
|---|---|---|
| `feedback` | Original customer feedback | `feedback_id` (PK), source, customer_id, feedback_text, product, feature, timestamp, app_version, created_at |
| `themes` | Identified themes | `theme_id` (PK), theme_name, description, category, status, created_at |
| `feedback_themes` | Feedback ↔ theme mapping (many-to-many) | feedback_id (FK), theme_id (FK), relevance_score, aspect_sentiment |
| `sentiment_history` | Sentiment results | `sentiment_id` (PK), feedback_id, theme_id, sentiment_label, sentiment_score, confidence_score, analysed_at |
| `product_changes` | Releases and changes | `release_id` (PK), product, feature, release_description, release_date, version, change_category |
| `theme_snapshots` | Historical theme metrics | `snapshot_id` (PK), theme_id, period_start, period_end, feedback_count, positive/negative/neutral counts, sentiment_average |
| `insights` | AI-generated insights | `insight_id` (PK), title, summary, recommendation, confidence_score, status, created_at |
| `insight_evidence` | Insight ↔ supporting feedback | insight_id (FK), feedback_id (FK), evidence_type |
| `memory_metadata` | References to Hindsight records | memory_id, memory_type, source_reference, related_theme, created_at, last_updated |

### Standard feedback format

```json
{
  "feedback_id": "FB001",
  "source": "app_review",
  "customer_id": "C101",
  "feedback_text": "Checkout is too slow",
  "product": "Mobile App",
  "feature": "Checkout",
  "timestamp": "2026-11-01T10:30:00Z",
  "app_version": "2.4.0"
}
```

---

## 🔌 API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/feedback/upload` | Upload feedback files (CSV / JSON) |
| `GET` | `/api/feedback` | Retrieve feedback |
| `POST` | `/api/feedback/analyze` | Trigger analysis |
| `GET` | `/api/themes` | Retrieve identified themes |
| `GET` | `/api/sentiment/trends` | Retrieve sentiment trends |
| `GET` | `/api/insights` | Retrieve generated insights |
| `POST` | `/api/product-changes` | Add product releases |
| `GET` | `/api/product-impact` | Compare releases and feedback |
| `POST` | `/api/agent/chat` | Chat with the AI agent |
| `GET` | `/api/memory/search` | Search historical memories |
| `GET` | `/api/memory/history` | View memory history |
| `GET` | `/api/health` | Health check |

> For larger uploads, add background processing and a job-status endpoint.

---

## 📁 Project Structure

*Suggested layout — adjust to match your repository.*

```
feedback-synthesizer/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes
│   │   ├── ingestion/      # parsers, validator, deduplicator, PII redactor
│   │   ├── agent/          # orchestrator, classifier, theme/trend/correlation logic
│   │   ├── memory/         # Hindsight client, retrieval, reconciliation
│   │   ├── models/         # SQLAlchemy models
│   │   ├── services/       # insights, analytics, evidence validation
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/          # Dashboard, ThemeExplorer, SentimentTimeline,
│   │   │                   # ProductImpact, MemoryExplorer, AIChat
│   │   └── components/
│   └── package.json
├── data/                   # sample CSV / JSON datasets
├── docs/
│   └── architecture.png
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+ (for backend, coming soon)
- Node.js 18+
- PostgreSQL 15+ (for backend, coming soon)
- Docker & Docker Compose (optional)
- A Gemini API key (for backend)
- Access to a Hindsight memory service (for backend)

### 1. Clone

```bash
git clone https://github.com/mukundchoubey88-lang/Feadback-synthziser.git
cd Feadback-synthziser
```

### 2. Run the Frontend Dashboard (Available Now)

The frontend is a complete, working dashboard with mock data that demonstrates all features.

```bash
cd frontend
npm install
npm run dev
```

**Open:** <http://localhost:5173>

The dashboard includes:
- ✅ 7 complete views (Overview, Ingestion, AI Providers, Insights, Reasoning, Analytics, Memory)
- ✅ Live system catalog with agent-tracked elements
- ✅ Interactive Plotly charts
- ✅ Docked agent chat panel
- ✅ Evidence-backed insights with citation trails
- ✅ Reasoning trace visualization
- ✅ Mock data demonstrating all features

See `frontend/README.md` for detailed documentation.

### 3. Backend Setup (Coming Soon)

The backend (FastAPI + PostgreSQL + Gemini + Hindsight) is described in this README but not yet implemented.

Once available:

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**API docs:** <http://localhost:8000/docs>

### 4. Configure environment (Backend)

Create a `.env` file:

```env
# LLM
GEMINI_API_KEY=your_gemini_api_key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/feedback_db

# Hindsight memory
HINDSIGHT_URL=http://localhost:8888
HINDSIGHT_API_KEY=your_hindsight_key

# App
ENVIRONMENT=development
```

---

## 🎬 Demo Scenario

**Checkout Improvement and Emerging Payment Issues**

| When | What happens |
|---|---|
| **Sept 2026** | Customers repeatedly report slow checkout → theme *Checkout performance* flagged as recurring, mostly negative → stored in Hindsight. |
| **20 Oct 2026** | Checkout optimisation released → added to `product_changes`. |
| **Nov 2026** | New feedback says checkout is faster but payments are failing. |

The agent then:

1. Analyses the new feedback.
2. Retrieves September's checkout complaints from memory.
3. Recognises the previously recurring issue.
4. Compares feedback before vs. after the October release.
5. Finds a reduction in checkout complaints.
6. Detects *Payment failures* as a separate emerging theme.
7. Produces an evidence-backed recommendation.

**Output**

- **Checkout performance:** complaints declined following the October optimisation release.
- **Emerging concern:** payment failures are appearing in recent feedback.
- **Recommended action:** review payment gateway reliability and monitor transaction success rates.

---

## 🛡 Edge Cases & Reliability

| Edge case | Expected behaviour |
|---|---|
| Duplicate feedback / repeated uploads | Idempotent ingestion, no duplicate processing |
| Missing timestamps | Flag record, exclude from time-based analysis |
| Invalid CSV / JSON | Report validation errors (never drop silently) |
| Multiple themes / mixed sentiment | Multiple theme links, aspect-level sentiment |
| Sarcasm / very short feedback | Lower confidence or mark ambiguous |
| Multilingual feedback | Process supported languages or flag unsupported |
| Low feedback volume | Avoid strong trend conclusions |
| Seasonal spikes | Compare appropriate historical periods |
| Unrelated release and issue | Avoid unsupported attribution |
| Conflicting memories | Preserve history, reconcile against source data |
| Hindsight unavailable | Continue structured ingestion, mark memory limits |
| LLM API failure | Retry and preserve unprocessed work |
| Prompt injection | Treat feedback as untrusted data, not instructions |
| PII in feedback | Redact and apply access controls |
| User disputes an insight | Allow review and correction |
| Stale dashboard | Show last successful update time |

### Security & privacy

- API keys via environment variables only.
- No database credentials in the frontend.
- Access control on uploaded data; no cross-user / cross-tenant leakage.
- Data deletion and retention policies supported.

---

## 🗺 MVP Roadmap

| Phase | Focus | Deliverable |
|---|---|---|
| **1 – Foundation** | React, FastAPI, PostgreSQL, models, CSV/JSON upload, validation, dedup | Working ingestion system |
| **2 – AI Intelligence** | Gemini integration, classification, sentiment, theme extraction | Feedback intelligence pipeline |
| **3 – Memory Integration** | Hindsight config, memory write/retrieve, episodic / semantic / temporal workflows | Agent with persistent historical context |
| **4 – Trend & Product Analysis** | Theme snapshots, emerging detection, trends, release records, before/after comparison | Historical & product-change intelligence |
| **5 – Insight Generation** | Evidence validation, recommendations, confidence thresholds | Evidence-backed AI insights |
| **6 – Frontend & Testing** | Dashboard, theme explorer, timeline, impact tracker, memory explorer, chat, edge-case tests | End-to-end MVP |

### Priorities

- **P0 (must have):** CSV/JSON ingestion, validation & dedup, theme classification, sentiment, PostgreSQL, Hindsight integration & retrieval, emerging theme detection, release correlation, evidence-backed insights, basic dashboard.
- **P1 (should have):** multilingual support, theme merge/split, advanced trends, memory correction, version-based comparisons, stronger privacy controls.
- **P2 (future):** live integrations, Jira/Linear automation, advanced anomaly detection, churn-risk indicators, causal impact analysis, multi-tenant access control.

### MVP acceptance criteria

- [ ] Upload historical feedback via CSV / JSON
- [ ] Validate and store feedback in PostgreSQL
- [ ] Identify multiple themes and sentiment per record
- [ ] Detect recurring and emerging themes
- [ ] Store and retrieve meaningful memories in Hindsight
- [ ] Answer questions using previous feedback
- [ ] Add product release information
- [ ] Compare feedback across release periods
- [ ] Link insights to supporting feedback
- [ ] Display current analytics on the dashboard
- [ ] Handle duplicates and invalid inputs
- [ ] Memory / LLM failures never silently corrupt structured data

---

## 📊 Success Metrics

| Metric | Measurement |
|---|---|
| Feedback ingestion | Successfully processed records |
| Duplicate detection | % of duplicates identified |
| Theme identification | Accuracy vs. reviewed samples |
| Sentiment analysis | Agreement with human labels |
| Emerging issue detection | Relevant new themes identified |
| Memory retrieval | Relevance of retrieved memories |
| Evidence coverage | % of insights backed by source feedback |
| Processing reliability | Successful processing rate |
| Dashboard freshness | Time from ingestion to updated analytics |

The MVP establishes **measurable baselines** rather than promising arbitrary accuracy figures.

---

## 🔮 Future Scope

- Google Play and Apple App Store integrations
- Zendesk, Intercom, Slack and email connectors
- Automatic Jira / Linear issue creation
- Competitor review analysis
- Churn and dissatisfaction signals
- Advanced multilingual analysis
- Release impact forecasting
- Human-in-the-loop insight approval
- Multi-product and multi-tenant support

---

## 👥 Target Users

| Persona | Uses it to |
|---|---|
| **Product Managers** | Spot pain points, monitor release impact, prioritise work |
| **Customer Experience Teams** | Find repeated complaints, track satisfaction |
| **Leadership** | See high-level trends and make data-driven decisions |
| **Product Analysts** | Explore history, compare periods, validate AI insights |

---

## 🤝 Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

Add your license here (e.g., MIT).

---

## 👤 Author

**Mukund Choubey** — B.Tech CSE (AI & ML), S-VYASA, Bengaluru

---

<p align="center"><i>Move from collecting customer feedback to continuously learning from it.</i></p>
