import { Badge, MetricCard, Panel } from "./ui";

const themes = [
  {
    id: "THM-101",
    name: "Checkout Performance",
    status: "recurring",
    records: 1847,
    sentiment: "negative",
    trend: "+24% vs last month",
    description: "Latency complaints during credit card processing and cart completion on mobile Safari.",
    topQuotes: [
      "Payment spinner spins for 15+ seconds before timing out.",
      "Checkout on iOS browser freezes after clicking place order.",
    ],
  },
  {
    id: "THM-102",
    name: "Payment Gateway Failures",
    status: "emerging",
    records: 428,
    sentiment: "negative",
    trend: "+38% this week",
    description: "3DS verification failures and unexpected declined card notifications primarily on EU debit cards.",
    topQuotes: [
      "Bank SMS code was entered but checkout redirected to an error screen.",
      "Card was charged but invoice marked as unpaid.",
    ],
  },
  {
    id: "THM-103",
    name: "UI/UX & Design System v3",
    status: "declining",
    records: 312,
    sentiment: "positive",
    trend: "-18% complaints",
    description: "Positive reception to improved contrast, navigation hierarchy, and table filtering.",
    topQuotes: [
      "The new layout is much clearer and faster to scan.",
      "Filters now stay sticky when scrolling long feedback tables.",
    ],
  },
  {
    id: "THM-104",
    name: "Search Accuracy & Speed",
    status: "recurring",
    records: 264,
    sentiment: "neutral",
    trend: "+4% volume",
    description: "Requests for multi-keyword boolean search and timestamp range filters in record search.",
    topQuotes: [
      "Need ability to filter by both product category and customer tier.",
    ],
  },
];

export function ThemesPage() {
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Themes</p>
            <Badge variant="accent" mono>Part 6 • Demo Data</Badge>
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Discovered Themes & Clusters</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Unsupervised clustering groups normalized feedback sentences into persistent topic patterns and tracks
            volume shifts across releases.
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        <MetricCard label="Active Themes" value="12" description="4 recurring · 2 emerging" />
        <MetricCard label="Clustered Records" value="2,851" description="88.4% of total volume" />
        <MetricCard label="Dominant Sentiment" value="61% Pos" description="Across 8 healthy themes" />
        <MetricCard label="Fastest Growing" value="Payment" description="+38% velocity in 7d" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {themes.map((theme) => (
          <Panel
            key={theme.id}
            title={theme.name}
            action={
              <div className="flex items-center gap-2">
                <Badge variant={theme.status === "emerging" ? "warn" : theme.status === "declining" ? "good" : "neutral"} mono>
                  {theme.status}
                </Badge>
                <Badge variant={theme.sentiment === "negative" ? "bad" : "good"} mono>
                  {theme.sentiment}
                </Badge>
              </div>
            }
          >
            <div className="grid gap-3 text-[13px]">
              <p className="text-ink-soft leading-relaxed">{theme.description}</p>
              <div className="flex items-center justify-between border-t border-line pt-2 text-[12px] text-mute">
                <span><strong className="text-ink font-normal">{theme.records.toLocaleString()}</strong> records</span>
                <span className="font-mono text-ink">{theme.trend}</span>
              </div>
              <div className="bg-sheet/80 border border-line p-3">
                <p className="text-[11px] uppercase tracking-wider text-mute">Representative Feedback</p>
                <ul className="mt-2 space-y-1.5 text-[12px] italic text-ink-soft">
                  {theme.topQuotes.map((quote, idx) => (
                    <li key={idx}>"{quote}"</li>
                  ))}
                </ul>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
