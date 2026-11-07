import { useEffect, useState } from "react";
import { client, formatScore } from "../../lib/api";
import type { HealthResponse, QualitySummary } from "../../lib/types";
import { Kicker, Reveal } from "./ui";

type LoadState = {
  health: HealthResponse | null;
  summary: QualitySummary | null;
  errors: string[];
  ready: boolean;
};

export function Metrics() {
  const [state, setState] = useState<LoadState>({ health: null, summary: null, errors: [], ready: false });

  useEffect(() => {
    let cancelled = false;
    const errors: string[] = [];

    void (async () => {
      const [health, summary] = await Promise.all([
        client.health().catch((reason: unknown) => {
          errors.push(reason instanceof Error ? reason.message : "Health request failed");
          return null;
        }),
        client.qualitySummary().catch((reason: unknown) => {
          errors.push(reason instanceof Error ? reason.message : "Quality summary failed");
          return null;
        }),
      ]);
      if (!cancelled) setState({ health, summary, errors, ready: true });
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const unavailable = state.ready && !state.health && !state.summary;

  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <Reveal>
          <Kicker>Infrastructure</Kicker>
          <h2 className="section-title mt-4 max-w-[16ch]">What the API can report.</h2>
          <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-ink-soft">
            These figures come from the running service. They are not a performance demo, and they stay blank until the
            backend answers.
          </p>
        </Reveal>

        {!state.ready && (
          <p className="mt-12 text-[14px] text-mute" role="status">
            Asking the API for health and the quality summary.
          </p>
        )}

        {unavailable && (
          <div className="mt-12 border border-bad/30 px-5 py-4 text-[14px] leading-relaxed text-bad" role="alert">
            {state.errors.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        )}

        {state.ready && !unavailable && (
          <div className="mt-14 grid gap-px bg-line md:grid-cols-2">
            <Reveal className="bg-paper p-6 sm:p-8">
              <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Service health</p>
              <p className="mt-4 text-[40px] leading-none tracking-[-0.045em]">{state.health?.status ?? "Unavailable"}</p>
              <p className="mt-3 text-[14px] text-ink-soft">
                {state.health
                  ? `${state.health.app_name} · ${state.health.version} · ${state.health.environment}`
                  : state.errors[0]}
              </p>
              {state.health && (
                <ul className="mt-6 grid gap-2">
                  {Object.entries(state.health.dependencies).map(([name, dependency]) => (
                    <li key={name} className="flex items-center justify-between gap-4 border-t border-line pt-2 text-[14px]">
                      <span>{name}</span>
                      <span className="text-ink-soft">{dependency.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Reveal>
            <Reveal delay={0.06} className="bg-paper p-6 sm:p-8">
              <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Quality summary</p>
              {state.summary ? (
                <dl className="mt-4 grid gap-6">
                  <div>
                    <dt className="text-[13px] text-mute">Feedback records</dt>
                    <dd className="mt-1 text-[40px] leading-none tracking-[-0.045em]">{state.summary.total_records}</dd>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <dt className="text-[13px] text-mute">Average quality score</dt>
                      <dd className="mt-1 text-[28px] tracking-[-0.04em]">
                        {formatScore(state.summary.average_quality_score)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[13px] text-mute">Records with PII detected</dt>
                      <dd className="mt-1 text-[28px] tracking-[-0.04em]">{state.summary.pii_detected_count}</dd>
                    </div>
                  </div>
                </dl>
              ) : (
                <p className="mt-4 text-[14px] leading-relaxed text-bad">{state.errors.at(-1)}</p>
              )}
              <p className="mt-6 text-[12px] text-mute">From GET /api/feedback/quality/summary</p>
            </Reveal>
          </div>
        )}
      </div>
    </section>
  );
}
