import { Badge, Button, MetricCard, Panel } from "./ui";

const memories = [
  {
    id: "MEM-EP-847",
    type: "episodic",
    badgeTone: "good" as const,
    title: "September 2026 Checkout Incident",
    content: "Multiple customers (n=1,847) experienced mobile checkout latency exceeding 8.2 seconds during the fall promo event. Root cause was unindexed customer balance lookups.",
    theme: "Checkout Performance",
    timestamp: "2026-09-15",
    provenance: ["FB-7234", "FB-7245", "FB-7289"],
  },
  {
    id: "MEM-SEM-423",
    type: "semantic",
    badgeTone: "accent" as const,
    title: "Recurring Pattern: Payment Spikes on Promotion Days",
    content: "Customer sentiment consistently drops 15-20% on days with flash campaigns when payment gateway throughput exceeds 400 req/sec.",
    theme: "Payment Reliability",
    timestamp: "2026-10-01",
    provenance: ["MEM-EP-782", "MEM-EP-801", "MEM-EP-847"],
  },
  {
    id: "MEM-TEM-234",
    type: "temporal",
    badgeTone: "warn" as const,
    title: "Temporal Shift: v2.4.0 Optimization Recovery",
    content: "Following the October 20 patch, negative complaints declined from 65% of volume to 31%. Sentiment velocity stabilized within 72 hours of release.",
    theme: "Checkout Performance",
    timestamp: "2026-10-24",
    provenance: ["FB-8473", "FB-8534", "FB-8567"],
  },
];

export function MemoryPage() {
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Intelligence Memory</p>
            <Badge variant="accent" mono>Part 9 • Demo Data</Badge>
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Hindsight Memory Bank</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Retains episodic events, semantic knowledge graphs, and temporal trends across product releases with
            immutable provenance records.
          </p>
        </div>
        <Button variant="secondary" size="sm">Search Memory Index</Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="Stored Traces" value="482" description="Episodic, semantic & temporal" />
        <MetricCard label="Context Retention" value="180 Days" description="Temporal reasoning horizon" />
        <MetricCard label="Provenance Links" value="100%" description="Zero ungrounded hallucinations" />
      </div>

      <div className="grid gap-4">
        {memories.map((entry) => (
          <Panel
            key={entry.id}
            title={entry.title}
            action={
              <div className="flex items-center gap-2">
                <Badge variant={entry.badgeTone} mono>{entry.type}</Badge>
                <Badge variant="neutral" mono>{entry.timestamp}</Badge>
              </div>
            }
          >
            <div className="grid gap-3 text-[14px]">
              <p className="text-ink-soft leading-relaxed">{entry.content}</p>
              <div className="flex flex-wrap items-center justify-between border-t border-line pt-2 text-[12px] text-mute">
                <span>Theme: <strong className="text-ink font-normal">{entry.theme}</strong></span>
                <div className="flex items-center gap-1.5 font-mono">
                  <span>Provenance:</span>
                  {entry.provenance.map((p) => (
                    <span key={p} className="bg-paper-deep px-1.5 py-0.5 rounded-xs text-[11px] text-ink">{p}</span>
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
