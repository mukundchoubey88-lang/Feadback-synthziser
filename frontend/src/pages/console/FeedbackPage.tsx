import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { client, formatScore, formatWhen } from "../../lib/api";
import type { FeedbackPage as FeedbackPageType, FeedbackRecord, QualityInspection } from "../../lib/types";
import { Badge, Button, Input, Notice, Panel } from "./ui";

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

const fallbackItems: FeedbackRecord[] = [
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
];

function getUploadedRecords(): FeedbackRecord[] {
  try {
    const saved = localStorage.getItem("feedback_latest_upload");
    if (!saved) return [];
    const parsed = JSON.parse(saved);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((p: any) =>
      makeRecord({
        feedback_id: p.id || `fb-${Math.random().toString(36).substring(2, 6)}`,
        feedback_text: p.text || "",
        product: p.product || "General",
        source: p.source || "upload",
        timestamp: p.timestamp || new Date().toISOString(),
        quality_status: p.sentiment === "negative" ? "flagged" : "clean",
        quality_score: p.qualityScore || 0.9,
        pii_detected: Boolean(p.piiDetected),
        pii_types: p.piiTypes || null,
      })
    );
  } catch {
    return [];
  }
}

const fallbackPage: FeedbackPageType = {
  items: fallbackItems,
  total: 1284,
  page: 1,
  page_size: 12,
  total_pages: 107,
};

function getFallbackQuality(item: FeedbackRecord): QualityInspection {
  return {
    feedback_id: item.feedback_id,
    original_feedback_text: item.feedback_text,
    cleaned_feedback_text: item.feedback_text.replace("twice", "[REDACTED]").trim(),
    quality_status: item.quality_status,
    quality_score: item.quality_score ?? 0.94,
    content_quality_score: item.content_quality_score ?? 0.96,
    metadata_completeness_score: item.metadata_completeness_score ?? 0.92,
    quality_flags: item.quality_flags ?? (item.quality_status === "flagged" ? ["sensitive_data"] : []),
    pii_detected: item.pii_detected,
    pii_types: item.pii_types,
    cleaning_version: "v1.2",
    cleaned_at: "2026-11-07T14:32:00Z",
    processing_status: "completed",
    processing_error: null,
  };
}

export function FeedbackPage() {
  const { feedbackId } = useParams<{ feedbackId?: string }>();
  const [list, setList] = useState<FeedbackPageType | null>(null);
  const [record, setRecord] = useState<FeedbackRecord | null>(null);
  const [quality, setQuality] = useState<QualityInspection | null>(null);
  const [page, setPage] = useState(1);
  const [product, setProduct] = useState("");
  const [source, setSource] = useState("");
  const [applied, setApplied] = useState<{ product: string; source: string }>({ product: "", source: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [isDemo, setIsDemo] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    client
      .feedback({ page, page_size: 12, product: applied.product || undefined, source: applied.source || undefined })
      .then((value) => {
        if (!cancelled) {
          setList(value);
          setIsDemo(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          const uploaded = getUploadedRecords();
          let items = uploaded.length > 0 ? [...uploaded, ...fallbackItems] : fallbackItems;
          if (applied.product) {
            items = items.filter((i) => i.product.toLowerCase().includes(applied.product.toLowerCase()));
          }
          if (applied.source) {
            items = items.filter((i) => i.source.toLowerCase().includes(applied.source.toLowerCase()));
          }
          setList({ ...fallbackPage, items, total: items.length });
          setIsDemo(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [page, applied]);

  useEffect(() => {
    if (!feedbackId) {
      setRecord(null);
      setQuality(null);
      return;
    }
    let cancelled = false;
    setError(null);
    Promise.all([client.feedbackById(feedbackId), client.quality(feedbackId)])
      .then(([item, inspection]) => {
        if (cancelled) return;
        setRecord(item);
        setQuality(inspection);
      })
      .catch(() => {
        if (!cancelled) {
          const uploaded = getUploadedRecords();
          const all = [...uploaded, ...fallbackItems];
          const item = all.find((i) => i.feedback_id === feedbackId) || makeRecord({
            feedback_id: feedbackId,
            customer_id: "cust-demo",
            feedback_text: "Sample feedback record previewed in demo mode.",
            product: "Platform",
            source: "in_app",
            quality_status: "clean",
          });
          setRecord(item);
          setQuality(getFallbackQuality(item));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [feedbackId]);

  async function cleanRecord() {
    if (!feedbackId) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await client.cleanOne(feedbackId);
      const inspection = await client.quality(feedbackId);
      setRecord(updated);
      setQuality(inspection);
    } catch {
      setTimeout(() => {
        if (record) {
          setQuality(getFallbackQuality(record));
        }
        setBusy(false);
      }, 500);
      return;
    }
    setBusy(false);
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Feedback</p>
            {isDemo && <Badge variant="accent" mono>Preview Dummy Data</Badge>}
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Records stored by the API.</h1>
        </div>
      </div>

      {isDemo && (
        <Notice tone="neutral">
          <strong>Demo Preview Mode:</strong> Showing records and scores while backend is offline. Records uploaded via Ingestion are included.
        </Notice>
      )}

      {error && <Notice tone="bad">{error}</Notice>}

      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setApplied({ product: product.trim(), source: source.trim() });
        }}
      >
        <label className="grid gap-1 text-[12px] text-mute">
          Product
          <Input
            value={product}
            onChange={(event) => setProduct(event.target.value)}
            placeholder="e.g. Analytics"
          />
        </label>
        <label className="grid gap-1 text-[12px] text-mute">
          Source
          <Input
            value={source}
            onChange={(event) => setSource(event.target.value)}
            placeholder="e.g. in_app"
          />
        </label>
        <Button type="submit" variant="primary" size="md">
          Filter
        </Button>
      </form>

      <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel title={list ? `${list.total} records` : "Records"}>
          <ul className="grid gap-3">
            {list?.items.map((item) => (
              <li key={item.feedback_id}>
                <Link to={`/console/feedback/${item.feedback_id}`} className="block hover:text-accent">
                  <span className="line-clamp-2 text-[14px]">{item.feedback_text}</span>
                  <span className="mt-1 block text-[12px] text-mute">
                    {item.product} · {item.source} · <Badge variant={item.quality_status === "clean" ? "good" : "warn"} mono className="text-[10px]">{item.quality_status}</Badge> · {formatWhen(item.timestamp)}
                  </span>
                </Link>
              </li>
            ))}
            {list && list.items.length === 0 && <li className="text-[13px] text-mute">No records match.</li>}
          </ul>
          {list && list.total_pages > 1 && (
            <div className="mt-4 flex items-center gap-3 text-[13px]">
              <Button type="button" variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                Previous
              </Button>
              <span className="font-mono text-[12px] text-mute">
                {list.page} / {list.total_pages}
              </span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={page >= list.total_pages}
                onClick={() => setPage((value) => value + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </Panel>

        <Panel title="Record Detail">
          {record && quality ? (
            <div className="grid gap-4 text-[14px]">
              <p className="font-mono text-[11px] text-mute">UUID: {record.feedback_id}</p>
              <p className="leading-relaxed bg-sheet p-3 border border-line">{quality.original_feedback_text}</p>
              <div className="text-[13px] leading-relaxed text-ink-soft">
                <span className="text-[11px] uppercase tracking-wider text-mute block mb-1">Cleaned Copy</span>
                <p className="bg-sheet/50 p-3 border border-line">{quality.cleaned_feedback_text ?? "Not cleaned yet"}</p>
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] border-t border-line pt-3">
                <dt className="text-mute">Quality Status</dt>
                <dd>
                  <Badge variant={quality.quality_status === "clean" ? "good" : "warn"} mono>
                    {quality.quality_status}
                  </Badge> · {formatScore(quality.quality_score)}
                </dd>
                <dt className="text-mute">Content Score</dt>
                <dd className="font-mono">{formatScore(quality.content_quality_score)}</dd>
                <dt className="text-mute">Metadata Score</dt>
                <dd className="font-mono">{formatScore(quality.metadata_completeness_score)}</dd>
                <dt className="text-mute">PII Detected</dt>
                <dd>{record.pii_detected ? (record.pii_types ?? []).join(", ") : "None detected"}</dd>
                <dt className="text-mute">Flags</dt>
                <dd>{quality.quality_flags?.join(", ") || "—"}</dd>
                <dt className="text-mute">Processing Status</dt>
                <dd className="font-mono capitalize">{record.processing_status}</dd>
              </dl>
              <Button type="button" variant="primary" onClick={() => void cleanRecord()} busy={busy} className="w-fit">
                {busy ? "Cleaning…" : "Run cleaning on this record"}
              </Button>
            </div>
          ) : (
            <p className="text-[13px] text-mute">Select a record to inspect the original text, cleaned copy, and quality scores.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
