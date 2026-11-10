# Feedback Intelligence — Frontend

The Vite entry is `src/main.tsx`. It serves the landing page and the API console at `/console` (health, feedback, ingestion, and quality). Styling is Tailwind CSS 4 through the Vite plugin.

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Start the backend before using `/console`.

`src/App.jsx` and `src/pages/*.jsx` are an earlier mock dashboard. `index.html` does not mount them.

---

# Earlier mock dashboard notes

A dark-mode dashboard sketch built with **React + Vite + TailwindCSS + Plotly.js**, inspired by the visual polish of [Jimo.ai](https://jimo.ai). The notes below describe that sketch, not the running app.

## 🎨 Design Features

- **Deep dark theme** with soft rounded cards (16–24px radius)
- **Subtle accent color** (#7AB1FE — soft blue)
- **Clean Inter font** with generous spacing
- **Trend badges** with sparklines and delta indicators (↑ 4.2%)
- **Docked right-side agent panel** (Jimo-style collapsible chat)
- **Evidence-backed insights** with expandable citation trails
- **Real-time system catalog** showing agent-tracked elements
- **Plotly visualizations** for themes and sentiment trends

## 📦 Tech Stack

- **React 18** — UI framework
- **Vite** — Build tool & dev server
- **TailwindCSS** — Utility-first styling
- **Plotly.js** — Interactive charts
- **Lucide React** — Icon library
- **clsx + tailwind-merge** — Conditional styling utilities

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at **http://localhost:5173**

### Build for Production

```bash
npm run build
```

Output will be in the `dist/` directory.

## 📱 Dashboard Views

### 1. **Overview**
- 4 stat cards with sparklines (Feedback Volume, Quality Score, PII Flags, Active Provider)
- **Live System Catalog** — real-time table of data sources, themes, and provider status
- Synced 2s ago indicator

### 2. **Ingestion & Jobs**
- Drag-and-drop CSV/JSON upload area
- Job status table with progress indicators
- Duplicate and rejection counts
- Auto PII detection and two-tier deduplication badges

### 3. **AI Provider Rail**
- Three provider cards (Gemini / OpenRouter / Grok)
- Live status dots, latency, token usage, success rates
- Circuit breaker configuration panel
- Cost per 1M tokens tracking

### 4. **Insights Feed**
- Evidence-backed insight cards with confidence scores
- Expandable citation trails showing source feedback IDs
- Recommended actions with priority flags (HIGH PRIORITY for urgent items)
- Theme tags and time periods

### 5. **Reasoning Trace**
- Step-by-step pipeline visualization
- Ingestion → Dedup → PII → Classification → Theme → Memory → Insight
- Duration tracking and completion estimates
- Color-coded status (completed, in_progress, pending)

### 6. **Analytics**
- **Top Themes by Volume** — horizontal bar chart with percentages
- **Sentiment Trend Over Time** — stacked line chart with release markers
- Plotly interactive visualizations with dark theme

### 7. **Memory Explorer**
- Episodic, semantic, and temporal memory entries
- Searchable by theme, content, or time period
- Source citation links and theme tags
- Memory statistics dashboard

## 🤖 Docked Agent Panel

- **Chat interface** on the right side (collapsible)
- Evidence-backed answers with **source citations** under each response
- Suggested queries (e.g., "Payment issues")
- Floating button when panel is closed

## 🎯 Governance Footer

- **Quality breakdown** — excellent / good / acceptable / poor distribution
- **System health indicator** — green checkmark or degraded mode banner
- **Degraded mode alert** — yellow banner when Hindsight memory is unavailable
- Last updated timestamp

## 🛠 Customization

### Colors

Edit `tailwind.config.js`:

```js
colors: {
  primary: '#7AB1FE', // Change accent color
  dark: {
    DEFAULT: '#0A0B0E',
    50: '#14151A',
    // ... customize dark shades
  }
}
```

### Mock Data

All mock data is in `src/data/mockData.js`. Replace with API calls:

```js
// Example: Replace mock stats with API
import { stats } from '../data/mockData'; // Remove this
const stats = await fetch('/api/stats').then(r => r.json()); // Add this
```

### Backend Integration

Update API endpoints in each page component:

```js
// Overview.jsx
useEffect(() => {
  fetch('http://localhost:8000/api/stats')
    .then(res => res.json())
    .then(data => setStats(data));
}, []);
```

## 📊 Data Flow

```
Mock Data (mockData.js)
    ↓
Page Components (pages/)
    ↓
Reusable Components (components/)
    ↓
Rendered UI
```

In production:

```
FastAPI Backend
    ↓
REST API Calls
    ↓
React State Management
    ↓
UI Updates
```

## 🎨 Component Structure

```
src/
├── components/
│   ├── Sidebar.jsx              # Left navigation
│   ├── StatCard.jsx             # Stat cards with sparklines
│   ├── AgentPanel.jsx           # Docked chat interface
│   └── GovernanceFooter.jsx     # Quality & health status
├── pages/
│   ├── Overview.jsx             # Dashboard home
│   ├── Ingestion.jsx            # Upload & jobs
│   ├── AIProviders.jsx          # Provider rail
│   ├── InsightsFeed.jsx         # Evidence-backed insights
│   ├── ReasoningTrace.jsx       # Step-by-step pipeline
│   ├── Analytics.jsx            # Charts & trends
│   └── MemoryExplorer.jsx       # Hindsight memory browser
├── data/
│   └── mockData.js              # Sample data for demo
├── lib/
│   └── utils.js                 # Helper functions
└── App.jsx                      # Main layout orchestrator
```

## 🚢 Deployment

### Vercel / Netlify

```bash
npm run build
```

Deploy the `dist/` folder.

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 5173
CMD ["npm", "run", "preview"]
```

## 🧪 Development Tips

- Use **React DevTools** for component debugging
- **Plotly** charts can be slow — use `config={{ displayModeBar: false }}` for performance
- **TailwindCSS IntelliSense** extension recommended for VSCode
- Hot reload enabled by default with Vite

## 📝 License

Match your backend license (e.g., MIT).

---

**Built by:** Mukund Choubey  
**Project:** User Feedback Synthesizer — AI-Powered Feedback Intelligence Platform  
**Inspiration:** Jimo.ai's product page design system
