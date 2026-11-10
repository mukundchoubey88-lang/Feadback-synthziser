import { Badge, Button, MetricCard, Panel } from "./ui";

const reportReleases = [
  {
    version: "v2.4.0 — Checkout Optimization",
    date: "October 20, 2026",
    impact: "+34.2% Positive Shift",
    status: "Verified",
    summary: "Refactored payment gateway handshakes and caching layer. Checkout timeouts dropped to near zero.",
    positive: 74,
    neutral: 18,
    negative: 8,
  },
  {
    version: "v2.3.2 — Mobile Navigation Refresh",
    date: "September 28, 2026",
    impact: "+18.7% Favorable",
    status: "Verified",
    summary: "Replaced nested hamburger drawers with bottom tab navigation for mobile users.",
    positive: 62,
    neutral: 24,
    negative: 14,
  },
  {
    version: "v2.3.0 — European Gateway Migration",
    date: "September 10, 2026",
    impact: "-12.4% Negative Shift",
    status: "Investigated",
    summary: "Initial rollout of 3DS bank verification caused initial latency spike before patch v2.4.0 resolved it.",
    positive: 48,
    neutral: 22,
    negative: 30,
  },
];

export function ReportsPage() {
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Reports</p>
            
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Release Impact & Sentiment</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Correlates customer sentiment shifts with exact engineering deployments and release changelogs.
          </p>
        </div>
        <Button variant="secondary" size="sm">Export PDF Summary</Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="Analyzed Releases" value="6" description="Q3-Q4 2026 changelogs" />
        <MetricCard label="Net Sentiment Lift" value="+22.8%" description="Across major milestone releases" />
        <MetricCard label="Average Lead Time" value="48 hrs" description="Time to detect user sentiment shift" />
      </div>

      <div className="grid gap-4">
        {reportReleases.map((rep) => (
          <Panel
            key={rep.version}
            title={rep.version}
            action={
              <div className="flex items-center gap-2">
                <Badge variant={rep.positive >= 60 ? "good" : "warn"} mono>{rep.impact}</Badge>
                <Badge variant="neutral" mono>{rep.date}</Badge>
              </div>
            }
          >
            <div className="grid gap-3 text-[14px]">
              <p className="text-ink-soft leading-relaxed">{rep.summary}</p>
              
              <div>
                <p className="text-[11px] font-medium uppercase tracking-wider text-mute mb-1.5">Sentiment Distribution</p>
                <div className="flex h-3 w-full overflow-hidden rounded-xs bg-paper-deep">
                  <div style={{ width: `${rep.positive}%` }} className="bg-good" title={`Positive: ${rep.positive}%`} />
                  <div style={{ width: `${rep.neutral}%` }} className="bg-line-strong" title={`Neutral: ${rep.neutral}%`} />
                  <div style={{ width: `${rep.negative}%` }} className="bg-bad" title={`Negative: ${rep.negative}%`} />
                </div>
                <div className="mt-2 flex gap-4 text-[12px] text-mute">
                  <span><strong className="text-good font-medium">{rep.positive}%</strong> Positive</span>
                  <span><strong className="text-ink-soft font-medium">{rep.neutral}%</strong> Neutral</span>
                  <span><strong className="text-bad font-medium">{rep.negative}%</strong> Negative</span>
                </div>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
