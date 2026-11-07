import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { client, formatScore, formatWhen } from "../../lib/api";
import type { FeedbackPage, FeedbackRecord, HealthResponse, QualitySummary, RootInfo } from "../../lib/types";
import { Badge, EmptyState, MetricCard, Notice, Panel } from "./ui";

function statusVariant(status?: string | null): "good" | "warn" | "bad" | "neutral" {
  if (!status) return "neutral";
  const s = status.toLowerCase();
  if (["healthy", "ok", "completed", "clean"].includes(s)) return "good";
  if (["warning", "pending"].includes(s)) return "warn";
  if (["failed", "unavailable", "error"].includes(s)) return "bad";
  return "neutral";
}

const fallbackRoot: RootInfo = {
  name: "Feedback Synthesizer API",
  version: "1.0.0",
  environment: "demo-preview",
  status: "healthy",
  docs_url: "/docs",
};

const fallbackHealth: HealthResponse = {
  status: "healthy",
  app_name: "Feedback Synthesizer",
  version: "1.0.0",
  environment: "demo-preview",
  dependencies: {
    postgresql: { status: "healthy", details: "Connected · 1,284 rows" },
    redis_cache: { status: "healthy", details: "Memory active · ping 1.1ms" },
    gemini_classifier: { status: "healthy", details: "Model 1.5 Pro ready" },
  },
};

const fallbackSummary: QualitySummary = {
  total_records: 1284,
  average_quality_score: 0.88,
  pii_detected_count: 24,
  quality_status_counts: { clean: 1142, flagged: 118, rejected: 24 },
  processing_status_counts: { completed: 1260, pending: 24 },
  flag_distribution: { low_clarity: 62, offensive_language: 14, gibberish: 42 },
};

const makeRecord = (partial: Partial<FeedbackRecord> & { feedback_id: string; feedback_text: string; product: string; source: string; quality_status: string }): FeedbackRecord => ({
  customer_id: "cust-demo",
  feature: null,
  timestamp: "2026-11-07T14:30:00Z",
  app_version: "2.4.0",
  created_at: "2026-11-07T14:30:00Z",
  deleted_at: null,
  cleaned_feedback_text: partial.feedback_text,
  quality_score: 0.94,
  content_quality_score: 0.96,
  metadata_completeness_score: 0.92,
  quality_flags: null,
  pii_detected: false,
  pii_types: null,
  cleaning_version: "v1",
  cleaned_at: "2026-11-07T14:30:00Z",
  processing_status: "completed",
  processing_error: null,
  ...partial,
});

const fallbackFeedback: FeedbackPage = {
  items: [
    makeRecord({
      feedback_id: "fb-7382-d91a",
      customer_id: "cust-902",
      feedback_text: "The new search filters on the analytics dashboard are 10x faster than last month. Really appreciate the keyboard shortcut support.",
      product: "Analytics Portal",
      source: "in_app",
      quality_status: "clean",
    }),
    makeRecord({
      feedback_id: "fb-7381-c42b",
      customer_id: "cust-481",
      feedback_text: "Exporting raw feedback to CSV fails when filtering over 500 records. Webhook logs show gateway timeout 504.",
      product: "Analytics Portal",
      source: "zendesk",
      quality_status: "clean",
    }),
    makeRecord({
      feedback_id: "fb-7380-e88f",
      customer_id: "cust-129",
      feedback_text: "Stripe recurring billing charged twice for the team seat upgrade. Support team was helpful but billing webhook needs attention.",
      product: "Billing",
      source: "email",
      quality_status: "flagged",
    }),
    makeRecord({
      feedback_id: "fb-7379-a110",
      customer_id: "cust-552",
      feedback_text: "Love the automated theme discovery! It pinpointed our mobile onboarding drop-off immediately after the v2.4 launch.",
      product: "Mobile App",
      source: "app_store",
      quality_status: "clean",
    }),
    makeRecord({
      feedback_id: "fb-7378-b394",
      customer_id: "cust-304",
      feedback_text: "Please add dark mode support to the console and webhooks event payload preview.",
      product: "Developer Console",
      source: "slack",
      quality_status: "clean",
    }),
  ],
  total: 1284,
  page: 1,
  page_size: 5,
  total_pages: 257,
};

export function OverviewPage() {
  const reduce = useReducedMotion();
  const [root, setRoot] = useState<RootInfo | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [feedback, setFeedback] = useState<FeedbackPage | null>(null);
  const [isDemoMode, setIsDemoMode] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadData = async () => {
      try {
        const [r, h, s, f] = await Promise.all([
          client.root(),
          client.health(),
          client.qualitySummary(),
          client.feedback({ page: 1, page_size: 5 }),
        ]);
        if (!cancelled) {
          setRoot(r);
          setHealth(h);
          setSummary(s);
          setFeedback(f);
          setIsDemoMode(false);
        }
      } catch {
        if (!cancelled) {
          setRoot(fallbackRoot);
          setHealth(fallbackHealth);
          setSummary(fallbackSummary);
          setFeedback(fallbackFeedback);
          setIsDemoMode(true);
        }
      }
    };

    void loadData();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Overview</p>
            {isDemoMode && <Badge variant="accent" mono>Preview Dummy Data</Badge>}
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">What the API can show right now.</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Counts below reflect feedback records and system status. Sentiment charts, themes, and Hindsight memory are
            also previewed in the console workspace.
          </p>
        </div>
      </div>

      {isDemoMode && (
        <Notice tone="neutral">
          <strong>Demo Preview Mode:</strong> The local FastAPI backend at <code>http://127.0.0.1:8000</code> is offline,
          so this console is displaying dummy data to preview features and layout.
        </Notice>
      )}

      <motion.div
        className="grid gap-3 md:grid-cols-3"
        initial={reduce ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <MetricCard
          label="Service"
          value={
            root ? (
              <div className="flex items-center gap-2">
                <span className="capitalize">{root.status}</span>
                <Badge variant={statusVariant(root.status)} mono>
                  {root.status}
                </Badge>
              </div>
            ) : (
              "…"
            )
          }
          description={root ? `${root.name} · ${root.version} · ${root.environment}` : "Waiting for GET /"}
        />
        <MetricCard
          label="Records"
          value={summary ? summary.total_records.toLocaleString() : "—"}
          description="Active feedback in the database"
        />
        <MetricCard
          label="Average quality"
          value={summary ? formatScore(summary.average_quality_score) : "—"}
          description={
            summary ? `${summary.pii_detected_count} records with PII detected` : "From the quality summary"
          }
        />
      </motion.div>

      <motion.div
        className="grid gap-3 lg:grid-cols-2"
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.45, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
      >
        <Panel title="Dependencies">
          {health ? (
            <ul className="grid gap-3">
              {Object.entries(health.dependencies).map(([name, dependency]) => (
                <li key={name} className="flex items-center justify-between gap-4 text-[13px]">
                  <span className="capitalize">{name.replaceAll("_", " ")}</span>
                  <div className="flex items-center gap-2">
                    {dependency.details && <span className="text-mute">{dependency.details}</span>}
                    <Badge variant={statusVariant(dependency.status)} mono>
                      {dependency.status}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="Health has not loaded"
              description="Waiting for dependency health response from GET /api/health."
            />
          )}
        </Panel>

        <Panel
          title="Recent feedback"
          action={
            <Link to="/console/feedback" className="text-[13px] text-accent">
              View all
            </Link>
          }
        >
          {feedback && feedback.items.length > 0 ? (
            <ul className="grid gap-3">
              {feedback.items.map((item) => (
                <li key={item.feedback_id}>
                  <Link to={`/console/feedback/${item.feedback_id}`} className="block hover:text-accent">
                    <span className="line-clamp-2 text-[14px] leading-snug">{item.feedback_text}</span>
                    <span className="mt-1 block text-[12px] text-mute">
                      {item.product} · {item.source} · {formatWhen(item.timestamp)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No feedback records"
              description="No feedback records returned from the database."
            />
          )}
        </Panel>
      </motion.div>
    </div>
  );
}
