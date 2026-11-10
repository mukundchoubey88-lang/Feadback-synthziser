import { Badge, Button, MetricCard, Panel } from "./ui";

const sampleInsights = [
  {
    id: "INS-847",
    title: "Checkout complaints declined by 34% after v2.4.0 release",
    summary:
      "Following the checkout optimization patch deployed on Oct 20, negative sentiment specifically regarding mobile payment completion dropped significantly compared to the prior 30-day window.",
    confidence: "94.3%",
    evidenceCount: 1847,
    theme: "Checkout Performance",
    period: "Oct 20 - Nov 7",
    recommendation: "Continue telemetry monitoring. Prepare release correlation summary for engineering.",
    citations: ["fb-7382-d91a", "fb-7381-c42b", "fb-7234-a10c"],
  },
  {
    id: "INS-846",
    title: "Emerging risk: European 3D-Secure card verification failures",
    summary:
      "A sudden cluster of 428 records within 7 days reports payment timeouts on Stripe 3DS challenges. Customers are redirected to failure states despite bank SMS confirmation.",
    confidence: "91.8%",
    evidenceCount: 428,
    theme: "Payment Failures",
    period: "Nov 1 - Nov 7",
    recommendation: "HIGH PRIORITY: Verify Stripe webhook response timeouts and EU SCA redirect endpoints.",
    citations: ["fb-8912-e192", "fb-8934-f823", "fb-9001-c309"],
  },
  {
    id: "INS-845",
    title: "Positive reception to v3 design system and dark theme previews",
    summary:
      "Customer sentiment regarding dashboard speed and visual hierarchy rose from 58% to 82% favorable after the latest UI refactoring.",
    confidence: "88.5%",
    evidenceCount: 312,
    theme: "UI/UX Issues",
    period: "Oct 1 - Nov 7",
    recommendation: "Standardize new typography tokens across all remaining secondary console surfaces.",
    citations: ["fb-7634-b811", "fb-7689-d902"],
  },
];

export function InsightsPage() {
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Insights</p>
            <Badge variant="accent" mono>Part 7</Badge>
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Actionable Product Insights</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Evidence-backed intelligence synthesized across thousands of feedback records, citing exact UUIDs and
            measuring impact across release dates.
          </p>
        </div>
        <Button variant="secondary" size="sm">Export Insights JSON</Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="Synthesized Insights" value="3" description="2 positive shifts · 1 critical alert" />
        <MetricCard label="Average Confidence" value="91.5%" description="Weighted by evidence citations" />
        <MetricCard label="Cited Records" value="2,587" description="Direct feedback references" />
      </div>

      <div className="grid gap-4">
        {sampleInsights.map((insight) => (
          <Panel
            key={insight.id}
            title={insight.title}
            action={
              <div className="flex items-center gap-2">
                <Badge variant="accent" mono>{insight.confidence} confidence</Badge>
                <Badge variant="neutral" mono>{insight.theme}</Badge>
              </div>
            }
          >
            <div className="grid gap-3 text-[14px]">
              <p className="text-ink-soft leading-relaxed">{insight.summary}</p>
              
              <div className="border border-line bg-sheet/60 p-3.5">
                <p className="text-[11px] font-medium uppercase tracking-wider text-mute">Actionable Recommendation</p>
                <p className="mt-1 text-[13px] text-ink font-normal">{insight.recommendation}</p>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 text-[12px] text-mute pt-1">
                <span>Period: <strong className="text-ink font-normal">{insight.period}</strong> · <strong className="text-ink font-normal">{insight.evidenceCount}</strong> evidence records</span>
                <div className="flex items-center gap-1.5 font-mono">
                  <span>Citations:</span>
                  {insight.citations.map((id) => (
                    <span key={id} className="bg-paper-deep px-1.5 py-0.5 rounded-xs text-[11px] text-ink">
                      {id}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
