export const stats = {
  feedbackVolume: { value: 12847, trend: 4.2, sparkline: [12, 19, 15, 25, 22, 30, 28] },
  qualityScore: { value: 87.3, trend: 2.1, sparkline: [82, 84, 83, 86, 85, 87, 87] },
  piiFlags: { value: 2.4, trend: -0.8, sparkline: [3.2, 3.0, 2.8, 2.6, 2.5, 2.4, 2.4] },
  activeProvider: { value: 'Gemini', latency: 245, trend: -12.3 }
};

export const catalogElements = [
  { id: 1, type: 'Data Source', name: 'CSV Upload', status: 'active', visibility: 'Visible to agent', records: 8234 },
  { id: 2, type: 'Data Source', name: 'JSON API', status: 'active', visibility: 'Visible to agent', records: 4613 },
  { id: 3, type: 'Theme', name: 'Checkout Performance', status: 'recurring', visibility: 'Visible to agent', feedback: 1847 },
  { id: 4, type: 'Theme', name: 'Payment Failures', status: 'emerging', visibility: 'Visible to agent', feedback: 428 },
  { id: 5, type: 'Theme', name: 'UI/UX Issues', status: 'declining', visibility: 'Visible to agent', feedback: 312 },
  { id: 6, type: 'Provider', name: 'Gemini Primary', status: 'active', visibility: 'Private', latency: '245ms' },
  { id: 7, type: 'Provider', name: 'OpenRouter Fallback', status: 'standby', visibility: 'Private', latency: '—' },
  { id: 8, type: 'Provider', name: 'Grok Cooldown', status: 'cooldown', visibility: 'Private', remaining: '3m 42s' }
];

export const jobs = [
  { id: 'JOB-1847', file: 'feedback_nov_batch1.csv', status: 'completed', records: 2847, duplicates: 24, rejected: 3, timestamp: '2026-11-07 14:32' },
  { id: 'JOB-1846', file: 'user_reviews_q4.json', status: 'completed', records: 1234, duplicates: 12, rejected: 1, timestamp: '2026-11-07 12:18' },
  { id: 'JOB-1845', file: 'support_tickets_oct.csv', status: 'processing', records: '—', progress: 67, timestamp: '2026-11-07 14:45' },
  { id: 'JOB-1844', file: 'survey_responses_nov.json', status: 'pending', records: '—', timestamp: '2026-11-07 14:50' }
];

export const providers = [
  {
    name: 'Gemini',
    role: 'Primary',
    status: 'active',
    latency: 245,
    requests: 8473,
    tokens: '2.4M',
    successRate: 99.7,
    costPerM: '$0.12'
  },
  {
    name: 'OpenRouter',
    role: 'Fallback',
    status: 'standby',
    latency: null,
    requests: 0,
    tokens: '0',
    successRate: 100,
    costPerM: '$0.18'
  },
  {
    name: 'Grok',
    role: 'Cooldown',
    status: 'cooldown',
    latency: null,
    requests: 234,
    tokens: '84K',
    remaining: '3m 42s',
    costPerM: '$0.08'
  }
];

export const insights = [
  {
    id: 'INS-847',
    title: 'Checkout complaints declined after Oct 20 release',
    summary: 'Following the checkout optimization release (v2.4.0), negative sentiment decreased by 34.2% compared to the previous 30-day period.',
    confidence: 94.3,
    evidenceCount: 1847,
    theme: 'Checkout Performance',
    period: 'Oct 20 - Nov 7',
    recommendation: 'Continue monitoring. Consider documentation update highlighting performance improvements.',
    citations: ['FB-8473', 'FB-8492', 'FB-8511', 'FB-8534', 'FB-8567']
  },
  {
    id: 'INS-846',
    title: 'Emerging: Payment gateway failures increasing',
    summary: 'New theme detected: payment failures mentioned in 428 recent feedback records (3.3% of volume), primarily affecting Stripe integration.',
    confidence: 87.6,
    evidenceCount: 428,
    theme: 'Payment Failures',
    period: 'Nov 1 - Nov 7',
    recommendation: 'HIGH PRIORITY: Review Stripe webhook reliability and transaction logs. Monitor for correlation with specific card types or regions.',
    citations: ['FB-8912', 'FB-8934', 'FB-8956', 'FB-8978', 'FB-9001']
  },
  {
    id: 'INS-845',
    title: 'UI/UX concerns declining steadily',
    summary: 'UI/UX-related negative feedback down 18.7% month-over-month. Design system updates (v3.0) showing positive reception.',
    confidence: 91.2,
    evidenceCount: 312,
    theme: 'UI/UX Issues',
    period: 'Oct 1 - Nov 7',
    recommendation: 'Track continuation of positive trend. Consider case study for internal documentation.',
    citations: ['FB-7634', 'FB-7689', 'FB-7712', 'FB-7745']
  }
];

export const reasoningSteps = [
  { step: 1, name: 'Ingestion', status: 'completed', duration: '0.8s', detail: 'Parsed CSV, validated 2847 records, normalized timestamps to UTC' },
  { step: 2, name: 'Deduplication', status: 'completed', duration: '1.2s', detail: 'Two-tier check: 24 exact duplicates, 3 semantic near-duplicates flagged' },
  { step: 3, name: 'PII Redaction', status: 'completed', duration: '2.1s', detail: 'Scanned for emails, phone numbers, SSNs — 68 patterns redacted' },
  { step: 4, name: 'Classification', status: 'completed', duration: '4.3s', detail: 'Gemini API: extracted themes, sentiment, intent, keywords with 94.3% avg confidence' },
  { step: 5, name: 'Theme Analysis', status: 'completed', duration: '1.7s', detail: 'Mapped to existing themes: 3 recurring, 1 emerging, 2 declining' },
  { step: 6, name: 'Memory Retrieval', status: 'in_progress', duration: '—', detail: 'Querying Hindsight for historical patterns (Oct 2026 checkout complaints)' },
  { step: 7, name: 'Insight Generation', status: 'pending', duration: '—', detail: 'Evidence validation and recommendation synthesis' }
];

export const themeData = {
  labels: ['Checkout Performance', 'Payment Failures', 'UI/UX Issues', 'Onboarding Flow', 'Search Accuracy', 'Mobile Performance'],
  values: [28.3, 18.7, 12.4, 11.2, 9.8, 8.1],
  colors: ['#7AB1FE', '#F472B6', '#FBBF24', '#34D399', '#A78BFA', '#FB923C']
};

export const sentimentTrend = {
  dates: ['Oct 1', 'Oct 8', 'Oct 15', 'Oct 22', 'Oct 29', 'Nov 5'],
  positive: [42, 44, 43, 48, 52, 54],
  neutral: [38, 36, 37, 34, 32, 31],
  negative: [20, 20, 20, 18, 16, 15],
  releaseMarker: 'Oct 20'
};

export const memoryEntries = [
  {
    id: 'MEM-EP-847',
    type: 'episodic',
    content: 'In Sept 2026, multiple customers (n=1847) reported slow checkout performance, avg completion time 8.2s vs. target 3s.',
    sources: ['FB-7234', 'FB-7245', 'FB-7289', 'FB-7334'],
    timestamp: '2026-09-15',
    theme: 'Checkout Performance'
  },
  {
    id: 'MEM-SEM-423',
    type: 'semantic',
    content: 'Checkout performance is a recurring concern across mobile and web platforms. Historical pattern: spikes correlate with traffic increases (sales events).',
    sources: ['MEM-EP-782', 'MEM-EP-801', 'MEM-EP-847'],
    timestamp: '2026-10-01',
    theme: 'Checkout Performance'
  },
  {
    id: 'MEM-TEM-234',
    type: 'temporal',
    content: 'Checkout complaints declined 34.2% following Oct 20, 2026 optimization release (v2.4.0). Sentiment shift: 65% negative → 31% negative.',
    sources: ['FB-8473', 'FB-8534', 'FB-8567', 'FB-8612'],
    timestamp: '2026-11-07',
    theme: 'Checkout Performance'
  },
  {
    id: 'MEM-EP-912',
    type: 'episodic',
    content: 'New payment failure theme emerged Nov 1-7, 2026. Primarily Stripe integration, 428 mentions, 3.3% of total feedback volume.',
    sources: ['FB-8912', 'FB-8934', 'FB-8956', 'FB-8978'],
    timestamp: '2026-11-07',
    theme: 'Payment Failures'
  }
];

export const qualityBreakdown = {
  excellent: 7234,
  good: 3847,
  acceptable: 1523,
  poor: 243
};
