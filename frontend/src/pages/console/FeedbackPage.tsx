import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { client, formatScore, formatWhen } from "../../lib/api";
import type { FeedbackPage, FeedbackRecord, QualityInspection } from "../../lib/types";
import { Notice, Panel } from "./ui";

export function FeedbackPage() {
  const { feedbackId } = useParams();
  const [page, setPage] = useState(1);
  const [product, setProduct] = useState("");
  const [source, setSource] = useState("");
  const [applied, setApplied] = useState({ product: "", source: "" });
  const [list, setList] = useState<FeedbackPage | null>(null);
  const [record, setRecord] = useState<FeedbackRecord | null>(null);
  const [quality, setQuality] = useState<QualityInspection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    client
      .feedback({ page, page_size: 12, product: applied.product || undefined, source: applied.source || undefined })
      .then((value) => {
        if (!cancelled) setList(value);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not list feedback");
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
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load this record");
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
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Cleaning failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6">
      <div>
        <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Feedback</p>
        <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Records stored by the API.</h1>
      </div>
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
          <input
            value={product}
            onChange={(event) => setProduct(event.target.value)}
            className="border border-line bg-sheet px-3 py-2 text-[14px] text-ink"
          />
        </label>
        <label className="grid gap-1 text-[12px] text-mute">
          Source
          <input
            value={source}
            onChange={(event) => setSource(event.target.value)}
            className="border border-line bg-sheet px-3 py-2 text-[14px] text-ink"
          />
        </label>
        <button type="submit" className="bg-ink px-3 py-2 text-[13px] text-paper">
          Filter
        </button>
      </form>

      <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel title={list ? `${list.total} records` : "Records"}>
          <ul className="grid gap-3">
            {list?.items.map((item) => (
              <li key={item.feedback_id}>
                <Link to={`/console/feedback/${item.feedback_id}`} className="block hover:text-accent">
                  <span className="line-clamp-2 text-[14px]">{item.feedback_text}</span>
                  <span className="mt-1 block text-[12px] text-mute">
                    {item.product} · {item.source} · {item.quality_status} · {formatWhen(item.timestamp)}
                  </span>
                </Link>
              </li>
            ))}
            {list && list.items.length === 0 && <li className="text-[13px] text-mute">No records match.</li>}
          </ul>
          {list && list.total_pages > 1 && (
            <div className="mt-4 flex items-center gap-3 text-[13px]">
              <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="border border-line px-2 py-1 disabled:opacity-40">
                Previous
              </button>
              <span>
                {list.page} / {list.total_pages}
              </span>
              <button
                type="button"
                disabled={page >= list.total_pages}
                onClick={() => setPage((value) => value + 1)}
                className="border border-line px-2 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </Panel>

        <Panel title="Record">
          {record && quality ? (
            <div className="grid gap-4 text-[14px]">
              <p className="leading-relaxed">{quality.original_feedback_text}</p>
              <p className="text-[13px] leading-relaxed text-ink-soft">
                Cleaned: {quality.cleaned_feedback_text ?? "Not cleaned yet"}
              </p>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-mute">Quality</dt>
                <dd>
                  {quality.quality_status} · {formatScore(quality.quality_score)}
                </dd>
                <dt className="text-mute">Content</dt>
                <dd>{formatScore(quality.content_quality_score)}</dd>
                <dt className="text-mute">Metadata</dt>
                <dd>{formatScore(quality.metadata_completeness_score)}</dd>
                <dt className="text-mute">PII</dt>
                <dd>{quality.pii_detected ? (quality.pii_types ?? []).join(", ") : "None detected"}</dd>
                <dt className="text-mute">Flags</dt>
                <dd>{quality.quality_flags?.join(", ") || "—"}</dd>
                <dt className="text-mute">Processing</dt>
                <dd>{quality.processing_status}</dd>
              </dl>
              <button type="button" onClick={() => void cleanRecord()} disabled={busy} className="w-fit bg-ink px-3 py-2 text-[13px] text-paper disabled:opacity-50">
                {busy ? "Cleaning…" : "Run cleaning on this record"}
              </button>
            </div>
          ) : (
            <p className="text-[13px] text-mute">Select a record to inspect the original text, cleaned copy, and quality scores.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
