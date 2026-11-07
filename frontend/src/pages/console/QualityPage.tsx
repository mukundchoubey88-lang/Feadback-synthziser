import { useEffect, useState } from "react";
import { client, formatScore } from "../../lib/api";
import type { BatchCleanResult, QualitySummary } from "../../lib/types";
import { Notice, Panel } from "./ui";

export function QualityPage() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [batch, setBatch] = useState<BatchCleanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setError(null);
    try {
      setSummary(await client.qualitySummary());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load quality summary");
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
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Batch cleaning failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid max-w-3xl gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Quality</p>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Cleaning and scores.</h1>
        </div>
        <button type="button" onClick={() => void clean()} disabled={busy} className="bg-ink px-3 py-2 text-[13px] text-paper disabled:opacity-50">
          {busy ? "Cleaning…" : "Clean next 50 records"}
        </button>
      </div>
      <p className="text-[14px] leading-relaxed text-ink-soft">
        Batch cleaning calls <span className="text-ink">POST /api/feedback/clean</span>. Original feedback text is left
        untouched. Scores describe clarity and metadata, not whether the customer was happy.
      </p>
      {error && <Notice tone="bad">{error}</Notice>}
      {summary && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Panel title="Records">
            <p className="text-[28px] tracking-[-0.04em]">{summary.total_records}</p>
          </Panel>
          <Panel title="Average score">
            <p className="text-[28px] tracking-[-0.04em]">{formatScore(summary.average_quality_score)}</p>
          </Panel>
          <Panel title="PII detected">
            <p className="text-[28px] tracking-[-0.04em]">{summary.pii_detected_count}</p>
          </Panel>
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
          <Panel title="Flags">
            <CountList entries={summary.flag_distribution} />
          </Panel>
        </div>
      )}
      {batch && (
        <Panel title="Last batch">
          <p className="text-[14px]">
            Considered {batch.total_considered}, processed {batch.processed}, skipped {batch.skipped}. Clean{" "}
            {batch.clean_count}, flagged {batch.flagged_count}, rejected {batch.rejected_count}, failed {batch.failed_count}.
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
          <span className="text-ink-soft">{key}</span>
          <span>{value}</span>
        </li>
      ))}
    </ul>
  );
}
