import { FileSpreadsheet, ListChecks, ScanSearch, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Kicker, Reveal } from "./ui";

const capabilities: Array<{
  id?: string;
  index: string;
  title: string;
  body: string;
  state: "Live" | "Illustrated";
  note: string;
  icon: LucideIcon;
}> = [
  {
    index: "01",
    title: "Feedback ingestion",
    body: "CSV and JSON files enter through the upload endpoint. The pipeline checks timestamps, skips duplicates, and keeps the original sentence.",
    state: "Live",
    note: "POST /api/feedback/upload is implemented.",
    icon: FileSpreadsheet,
  },
  {
    index: "02",
    title: "Feedback quality",
    body: "Each record can be validated, scored, and cleaned. Personal data is redacted on the cleaned copy. The original text stays intact.",
    state: "Live",
    note: "Quality summary, inspection, and cleaning routes are implemented.",
    icon: ShieldCheck,
  },
  {
    id: "hindsight",
    index: "03",
    title: "Feedback intelligence",
    body: "Sentiment, topics, and themes are how a single note becomes a pattern, read against what the product has already seen.",
    state: "Illustrated",
    note: "Classification, theme discovery, and Hindsight are not API routes yet.",
    icon: ScanSearch,
  },
  {
    id: "actions",
    index: "04",
    title: "Evidence-backed decisions",
    body: "A useful recommendation names what changed, which history it was compared with, and which records it came from.",
    state: "Illustrated",
    note: "Insight routes are specified and not implemented.",
    icon: ListChecks,
  },
];

export function Capabilities() {
  return (
    <section id="platform" className="border-t border-line">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <Reveal>
          <Kicker>Capabilities</Kicker>
          <h2 className="section-title mt-4 max-w-[16ch]">What the agent is built to do.</h2>
        </Reveal>
        <div className="mt-16 grid gap-px bg-line sm:grid-cols-2">
          {capabilities.map((item, index) => {
            const Icon = item.icon;
            return (
              <Reveal key={item.index} delay={index * 0.05} className="bg-paper">
                <article id={item.id} className="flex h-full flex-col p-6 sm:p-8">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-[12px] tracking-[0.16em] text-mute">{item.index}</span>
                    <span
                      className={`text-[11px] tracking-[0.14em] uppercase ${
                        item.state === "Live" ? "text-good" : "text-mute"
                      }`}
                    >
                      {item.state}
                    </span>
                  </div>
                  <Icon className="mt-8 text-ink" size={20} strokeWidth={1.5} aria-hidden />
                  <h3 className="mt-4 text-[22px] tracking-[-0.03em]">{item.title}</h3>
                  <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">{item.body}</p>
                  <p className="mt-6 text-[13px] leading-relaxed text-mute">{item.note}</p>
                </article>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
