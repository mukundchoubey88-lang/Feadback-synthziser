import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { client, formatScore, formatWhen } from "../../lib/api";
import type { FeedbackPage, HealthResponse, QualitySummary, RootInfo } from "../../lib/types";
import { Notice, Panel } from "./ui";

export function OverviewPage() {
  const [root, setRoot] = useState<RootInfo | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [feedback, setFeedback] = useState<FeedbackPage | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    const failures: string[] = [];

    const settle = async <T,>(label: string, request: Promise<T>, apply: (value: T) => void) => {
      try {
        const value = await request;
        if (!cancelled) apply(value);
      } catch (error) {
        failures.push(`${label}: ${error instanceof Error ? error.message : "Request failed"}`);
      }
    };

    void (async () => {
      await Promise.all([
        settle("Service", client.root(), setRoot),
        settle("Health", client.health(), setHealth),
        settle("Quality", client.qualitySummary(), setSummary),
        settle("Feedback", client.feedback({ page: 1, page_size: 5 }), setFeedback),
      ]);
      if (!cancelled) setErrors(failures);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="grid gap-6">
      <div>
        <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Overview</p>
        <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">What the API can show right now.</h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
          Counts below are responses from the backend. Sentiment charts, themes, and Hindsight stay on the marketing
          page until those routes exist.
        </p>
      </div>

      {errors.length > 0 && (
        <Notice tone="bad">
          {errors.map((item) => (
            <span key={item} className="block">
              {item}
            </span>
          ))}
        </Notice>
      )}

      <div className="grid gap-3 md:grid-cols-3">
        <Panel title="Service">
          <p className="text-[22px] tracking-[-0.04em]">{root?.status ?? "…"}</p>
          <p className="mt-2 text-[13px] text-mute">
            {root ? `${root.name} · ${root.version} · ${root.environment}` : "Waiting for GET /"}
          </p>
        </Panel>
        <Panel title="Records">
          <p className="text-[22px] tracking-[-0.04em]">{summary ? summary.total_records : "—"}</p>
          <p className="mt-2 text-[13px] text-mute">Active feedback in the database</p>
        </Panel>
        <Panel title="Average quality">
          <p className="text-[22px] tracking-[-0.04em]">{summary ? formatScore(summary.average_quality_score) : "—"}</p>
          <p className="mt-2 text-[13px] text-mute">
            {summary ? `${summary.pii_detected_count} records with PII detected` : "From the quality summary"}
          </p>
        </Panel>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Dependencies">
          {health ? (
            <ul className="grid gap-3">
              {Object.entries(health.dependencies).map(([name, dependency]) => (
                <li key={name} className="flex items-start justify-between gap-4 text-[13px]">
                  <span className="capitalize">{name.replaceAll("_", " ")}</span>
                  <span className="text-right text-mute">
                    {dependency.status}
                    {dependency.details ? ` · ${dependency.details}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-mute">Health has not loaded.</p>
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
            <p className="text-[13px] text-mute">No feedback records returned.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
