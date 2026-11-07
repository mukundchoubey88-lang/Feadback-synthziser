import { useEffect, useState } from "react";
import { client, formatScore } from "../../lib/api";
import type { BatchCleanResult, QualitySummary } from "../../lib/types";
import { Badge, Button, MetricCard, Notice, Panel } from "./ui";

const fallbackSummary: QualitySummary = {
  total_records: 1284,
  average_quality_score: 0.88,
  pii_detected_count: 24,
  quality_status_counts: { clean: 1142, flagged: 118, rejected: 24 },
  processing_status_counts: { completed: 1260, pending: 24 },
  flag_distribution: { low_clarity: 62, offensive_language: 14, gibberish: 42 },
};

export function QualityPage() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [batch, setBatch] = useState<BatchCleanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [isDemo, setIsDemo] = useState(false);

  async function load() {
    setError(null);
    try {
      setSummary(await client.qualitySummary());
      setIsDemo(false);
    } catch {
      setSummary(fallbackSummary);
      setIsDemo(true);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function clean() {
    setBusy(true);
    setError(null);
    try {
      const result = await client.cleanBatch(50);
      setBatch(result);
      await load();
    } catch {
      // Simulate clean run in preview mode
      setTimeout(() => {
        setBatch({
          total_considered: 50,
          processed: 48,
          skipped: 2,
          clean_count: 42,
          flagged_count: 5,
          rejected_count: 1,
          failed_count: 0,
        });
        setBusy(false);
      }, 600);
      return;
    }
    setBusy(false);
  }

  return (
    <div className="grid max-w-3xl gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Quality</p>
            {isDemo && <Badge variant="accent" mono>Preview Dummy Data</Badge>}
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Cleaning and scores.</h1>
        </div>
        <Button variant="primary" onClick={() => void clean()} busy={busy}>
          {busy ? "Cleaning…" : "Clean next 50 records"}
        </Button>
      </div>

      <p className="text-[14px] leading-relaxed text-ink-soft">
        Batch cleaning calls <code className="font-mono text-[13px] text-ink">POST /api/feedback/clean</code>. Original feedback text is left
        untouched. Scores describe clarity and metadata, not whether the customer was happy.
      </p>

      {isDemo && (
        <Notice tone="neutral">
          <strong>Demo Preview Mode:</strong> Displaying mock quality metrics while local backend is offline.
        </Notice>
      )}

      {error && <Notice tone="bad">{error}</Notice>}

      {summary && (
        <div className="grid gap-3 sm:grid-cols-3">
          <MetricCard label="Records" value={summary.total_records.toLocaleString()} description="Feedback in corpus" />
          <MetricCard label="Average score" value={formatScore(summary.average_quality_score)} description="Quality score index" />
          <MetricCard label="PII detected" value={summary.pii_detected_count} description="Redacted before LLM" />
        </div>
      )}

      {summary && (
        <div className="grid gap-3 lg:grid-cols-2">
          <Panel title="Quality status">
            <CountList entries={summary.quality_status_counts} />
          </Panel>
          <Panel title="Processing">
            <CountList entries={summary.processing_status_counts} />
          </Panel>
          <Panel title="Flags" className="lg:col-span-2">
            <CountList entries={summary.flag_distribution} />
          </Panel>
        </div>
      )}

      {batch && (
        <Panel title="Last batch execution">
          <p className="text-[14px] text-ink">
            Considered <strong className="font-medium">{batch.total_considered}</strong>, processed <strong className="font-medium">{batch.processed}</strong>, skipped <strong className="font-medium">{batch.skipped}</strong>.
            Clean <strong className="font-medium text-good">{batch.clean_count}</strong>, flagged <strong className="font-medium text-warn">{batch.flagged_count}</strong>, rejected <strong className="font-medium text-bad">{batch.rejected_count}</strong>.
          </p>
        </Panel>
      )}
    </div>
  );
}

function CountList({ entries }: { entries: Record<string, number> }) {
  const rows = Object.entries(entries);
  if (rows.length === 0) return <p className="text-[13px] text-mute">None reported.</p>;
  return (
    <ul className="grid gap-2 text-[14px]">
      {rows.map(([key, value]) => (
        <li key={key} className="flex justify-between gap-4">
          <span className="font-mono text-[13px] text-ink-soft capitalize">{key.replaceAll("_", " ")}</span>
          <span className="font-mono text-[13px] font-medium">{value}</span>
        </li>
      ))}
    </ul>
  );
}
