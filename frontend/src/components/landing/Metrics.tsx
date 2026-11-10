import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { client, formatScore } from "../../lib/api";
import type { HealthResponse, QualitySummary } from "../../lib/types";
import { Kicker, Reveal } from "./ui";

type Snapshot = {
  health: HealthResponse | null;
  summary: QualitySummary | null;
  errors: string[];
  kept: boolean;
};

function message(reason: unknown, fallback: string): string {
  return reason instanceof Error && reason.message ? reason.message : fallback;
}

function label(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function count(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("en").format(value);
}

export function Metrics() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(true);
  const inFlight = useRef(false);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    const errors: string[] = [];
    let health: HealthResponse | null = null;
    let summary: QualitySummary | null = null;

    try {
      [health, summary] = await Promise.all([
        client.health().catch((reason: unknown) => {
          errors.push(message(reason, "Health request failed"));
          return null;
        }),
        client.qualitySummary().catch((reason: unknown) => {
          errors.push(message(reason, "Quality summary failed"));
          return null;
        }),
      ]);
    } finally {
      inFlight.current = false;
      if (mounted.current) {
        setSnapshot((previous) => ({
          health: health ?? previous?.health ?? null,
          summary: summary ?? previous?.summary ?? null,
          errors: [...new Set(errors)],
          kept: (health == null && previous?.health != null) || (summary == null && previous?.summary != null),
        }));
        setBusy(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
    };
  }, [load]);

  const health = snapshot?.health ?? null;
  const summary = snapshot?.summary ?? null;
  const errors = snapshot?.errors ?? [];
  const unavailable = !busy && !health && !summary;
  const showCards = Boolean(health || summary);

  const status = label(health?.status);
  const service = [label(health?.app_name), label(health?.version), label(health?.environment)].filter(Boolean);
  const dependencies =
    health && health.dependencies && typeof health.dependencies === "object"
      ? Object.entries(health.dependencies)
      : [];
  const records = count(summary?.total_records);
  const average = count(summary?.average_quality_score);
  const pii = count(summary?.pii_detected_count);

  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <Reveal>
            <Kicker>Infrastructure</Kicker>
            <h2 className="section-title mt-4 max-w-[16ch]">What the API can report.</h2>
            <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-ink-soft">
              Service health comes from GET /api/health. Record count, average quality score, and PII detections come
              from GET /api/feedback/quality/summary.
            </p>
          </Reveal>
          <button
            type="button"
            onClick={() => void load()}
            disabled={busy}
            aria-busy={busy}
            className="inline-flex items-center gap-2 border border-line px-3 py-2 text-[13px] text-ink transition-colors duration-200 hover:border-ink disabled:opacity-50"
          >
            <RefreshCw size={14} strokeWidth={1.75} className={busy ? "motion-safe:animate-spin" : undefined} aria-hidden />
            {busy ? "Refreshing" : "Refresh"}
          </button>
        </div>

        {busy && !showCards && (
          <p className="mt-12 text-[14px] text-mute" role="status">
            Asking the API for health and the quality summary.
          </p>
        )}

        {errors.length > 0 && (
          <div className="mt-12 border border-bad/30 px-5 py-4 text-[14px] leading-relaxed text-bad" role="alert">
            {errors.map((item) => (
              <p key={item} className="break-words">
                {item}
              </p>
            ))}
            {snapshot?.kept && <p className="mt-2 text-ink-soft">The last successful values are still shown.</p>}
          </div>
        )}

        {unavailable && errors.length === 0 && (
          <p className="mt-12 text-[14px] text-mute" role="status">
            The API did not return health or a quality summary.
          </p>
        )}

        {showCards && (
          <div className="mt-14 grid gap-px bg-line md:grid-cols-2">
            <div className="min-w-0 bg-paper p-6 sm:p-8">
              <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Service health</p>
              {health ? (
                <>
                  <p className="mt-4 text-[40px] leading-none tracking-[-0.045em] break-words">{status ?? "—"}</p>
                  <p className="mt-3 text-[14px] break-words text-ink-soft">
                    {service.length > 0 ? service.join(" · ") : "The health response did not include a service name."}
                  </p>
                  {dependencies.length > 0 ? (
                    <ul className="mt-6 grid gap-2">
                      {dependencies.map(([name, dependency]) => (
                        <li key={name} className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 border-t border-line pt-2 text-[14px]">
                          <span className="break-words">{name}</span>
                          <span className="text-ink-soft">{label(dependency?.status) ?? "—"}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-6 text-[14px] text-mute">No dependency statuses were returned.</p>
                  )}
                </>
              ) : (
                <p className="mt-4 text-[14px] leading-relaxed text-mute">Health was not returned.</p>
              )}
              <p className="mt-6 text-[12px] text-mute">From GET /api/health</p>
            </div>
            <div className="min-w-0 bg-paper p-6 sm:p-8">
              <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Quality summary</p>
              {summary ? (
                <dl className="mt-4 grid gap-6">
                  <div>
                    <dt className="text-[13px] text-mute">Feedback records</dt>
                    <dd className="mt-1 text-[40px] leading-none tracking-[-0.045em] break-words">
                      {records === null ? "—" : formatCount(records)}
                    </dd>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="min-w-0">
                      <dt className="text-[13px] text-mute">Average quality score</dt>
                      <dd className="mt-1 text-[28px] tracking-[-0.04em] break-words">
                        {average === null ? "—" : formatScore(average)}
                      </dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-[13px] text-mute">Records with PII detected</dt>
                      <dd className="mt-1 text-[28px] tracking-[-0.04em] break-words">
                        {pii === null ? "—" : formatCount(pii)}
                      </dd>
                    </div>
                  </div>
                </dl>
              ) : (
                <p className="mt-4 text-[14px] leading-relaxed text-mute">A quality summary was not returned.</p>
              )}
              {records === 0 && average === 0 && (
                <p className="mt-4 text-[12px] leading-relaxed text-mute">
                  No records are stored. The API returns an average of 0.0 when no quality scores exist.
                </p>
              )}
              <p className="mt-6 text-[12px] text-mute">From GET /api/feedback/quality/summary</p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
