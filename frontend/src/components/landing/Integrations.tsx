import { Braces, FileSpreadsheet, Waypoints } from "lucide-react";
import { Kicker, Reveal } from "./ui";

const items = [
  {
    icon: FileSpreadsheet,
    title: "CSV",
    body: "A spreadsheet upload is accepted by the ingestion endpoint, within the existing file and record limits.",
  },
  {
    icon: Braces,
    title: "JSON",
    body: "A JSON file uses the same upload route. Duplicates are counted, not rewritten.",
  },
  {
    icon: Waypoints,
    title: "REST API",
    body: "The console reads health, feedback, jobs, quality, and cleaning from the existing HTTP API.",
  },
];

export function Integrations() {
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <Reveal>
          <Kicker>Integrations</Kicker>
          <h2 className="section-title mt-4 max-w-[16ch]">The ways feedback can arrive.</h2>
          <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-ink-soft">
            The product accepts files and HTTP requests. There is no catalog of third-party connections.
          </p>
        </Reveal>
        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {items.map((item, index) => {
            const Icon = item.icon;
            return (
              <Reveal key={item.title} delay={index * 0.05} className="border border-line p-6">
                <Icon size={20} strokeWidth={1.5} aria-hidden />
                <h3 className="mt-6 text-[20px] tracking-[-0.03em]">{item.title}</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">{item.body}</p>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
