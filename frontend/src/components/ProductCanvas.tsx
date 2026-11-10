import type { ReactElement } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

export type SceneId = "overview" | "ingest" | "classify" | "themes" | "memory" | "action";

const sceneMeta: Record<SceneId, { crumb: string; nav: string }> = {
  overview: { crumb: "Overview", nav: "Overview" },
  ingest: { crumb: "Ingestion", nav: "Feedback" },
  classify: { crumb: "Reading a record", nav: "Feedback" },
  themes: { crumb: "Themes", nav: "Themes" },
  memory: { crumb: "Intelligence memory", nav: "Intelligence Memory" },
  action: { crumb: "Insights", nav: "Insights" },
};

const nav = ["Overview", "Feedback", "Themes", "Insights", "Intelligence Memory", "Reports"];

function Sidebar({ active }: { active: string }) {
  return (
    <aside className="hidden w-[148px] shrink-0 flex-col border-r border-line bg-paper-deep px-3 py-3 sm:flex">
      <p className="px-2 pb-3 text-[10px] tracking-[0.16em] text-mute uppercase">Workspace</p>
      {nav.map((item) => {
        const on = item === active;
        return (
          <div
            key={item}
            className={`mb-0.5 rounded-md px-2 py-1.5 text-[12px] ${on ? "bg-ink text-paper" : "text-ink-soft"}`}
          >
            {item}
          </div>
        );
      })}
    </aside>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="border border-line bg-sheet px-3 py-2.5">
      <p className="text-[10px] tracking-[0.14em] text-mute uppercase">{label}</p>
      <p className="mt-1 text-[20px] leading-none tracking-[-0.04em]">{value}</p>
      <p className="mt-1.5 text-[11px] text-mute">{note}</p>
    </div>
  );
}

function OverviewScene() {
  const themes = [
    ["Login difficulties", "186", "Negative", "+24"],
    ["Slow performance", "142", "Negative", "+11"],
    ["Payment failures", "97", "Negative", "+38%"],
    ["Export requests", "74", "Request", "+6"],
  ];
  return (
    <div className="grid gap-2.5">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Metric label="Feedback" value="1,284" note="Last 30 days" />
        <Metric label="Positive" value="61%" note="782 records" />
        <Metric label="Neutral" value="22%" note="283 records" />
        <Metric label="Negative" value="17%" note="219 records" />
      </div>
      <div className="grid gap-2 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="border border-line bg-sheet p-3">
          <p className="text-[10px] tracking-[0.14em] text-mute uppercase">Sentiment distribution</p>
          <div className="mt-3 flex h-2 overflow-hidden bg-paper-deep">
            <div className="w-[61%] bg-good" />
            <div className="w-[22%] bg-[#b7b1a4]" />
            <div className="w-[17%] bg-bad" />
          </div>
          <div className="mt-3 grid grid-cols-3 text-[11px] text-ink-soft">
            <span>Positive 61%</span>
            <span>Neutral 22%</span>
            <span>Negative 17%</span>
          </div>
        </div>
        <div className="border border-line bg-sheet p-3">
          <p className="text-[10px] tracking-[0.14em] text-mute uppercase">Priority issues</p>
          <ul className="mt-2 space-y-1.5 text-[12px]">
            <li className="flex justify-between gap-3">
              <span>Checkout timeouts returning</span>
              <span className="text-bad">High</span>
            </li>
            <li className="flex justify-between gap-3">
              <span>Login codes expire early</span>
              <span className="text-bad">High</span>
            </li>
            <li className="flex justify-between gap-3">
              <span>Mobile search latency</span>
              <span className="text-warn">Medium</span>
            </li>
          </ul>
        </div>
      </div>
      <div className="border border-line bg-sheet">
        <div className="grid grid-cols-[1.4fr_0.5fr_0.7fr_0.4fr] border-b border-line px-3 py-1.5 text-[10px] tracking-[0.12em] text-mute uppercase">
          <span>Emerging theme</span>
          <span>Volume</span>
          <span>Sentiment</span>
          <span>Change</span>
        </div>
        {themes.map((row) => (
          <div key={row[0]} className="grid grid-cols-[1.4fr_0.5fr_0.7fr_0.4fr] px-3 py-1.5 text-[12px]">
            {row.map((cell, index) => (
              <span key={`${row[0]}-${index}`}>{cell}</span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function IngestScene() {
  const incoming = [
    ["App Store", "Checkout spinner is back during the evening sale."],
    ["Zendesk", "Please reach out to support@mycompany.org about login."],
    ["In-app", "Search results still take several seconds on mobile."],
    ["Interview", "We need CSV export once a table passes 500 rows."],
  ];
  const steps = ["Validate timestamp", "Deduplicate", "Normalize text", "Redact PII", "Score quality"];
  return (
    <div className="grid gap-2.5 lg:grid-cols-[1.15fr_0.85fr]">
      <div className="border border-line bg-sheet">
        <p className="border-b border-line px-3 py-2 text-[10px] tracking-[0.14em] text-mute uppercase">
          Arriving now
        </p>
        {incoming.map(([source, text]) => (
          <div key={text} className="grid grid-cols-[88px_1fr] gap-3 border-b border-line px-3 py-2 last:border-b-0">
            <span className="text-[11px] text-accent">{source}</span>
            <span className="text-[12px] leading-snug text-ink-soft">{text}</span>
          </div>
        ))}
      </div>
      <div className="grid gap-2.5">
        <div className="border border-line bg-sheet p-3">
          <p className="text-[10px] tracking-[0.14em] text-mute uppercase">Becomes a record</p>
          <ol className="mt-2 space-y-1.5">
            {steps.map((step, index) => (
              <li key={step} className="flex items-center gap-2 text-[12px]">
                <span className="w-4 text-[11px] text-mute">0{index + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="border border-line bg-ink px-3 py-3 text-paper">
          <p className="text-[10px] tracking-[0.14em] text-[#c8c2b6] uppercase">Stored, original intact</p>
          <p className="mt-2 text-[12px] leading-relaxed text-[#f3f0e8]">
            Cleaned copy: “Please reach out to [EMAIL] about login.”
          </p>
          <p className="mt-2 text-[11px] text-[#c8c2b6]">Raw text is never overwritten.</p>
        </div>
      </div>
    </div>
  );
}

function ClassifyScene() {
  const fields = [
    ["Sentiment", "Negative"],
    ["Category", "Authentication"],
    ["Topic", "Login codes"],
    ["Priority", "High"],
    ["Confidence", "0.92"],
  ];
  return (
    <div className="grid gap-2.5 lg:grid-cols-[1.2fr_0.8fr]">
      <div className="border border-line bg-sheet p-4">
        <p className="text-[10px] tracking-[0.14em] text-mute uppercase">One piece of feedback</p>
        <p className="mt-3 text-[20px] leading-[1.25] tracking-[-0.03em]">
          “The login code expires before I can switch from email back to the app. This is the third time this week.”
        </p>
        <p className="mt-4 text-[12px] text-mute">In-app · Mobile App · Auth · v3.1.0</p>
      </div>
      <div className="border border-line bg-sheet">
        {fields.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between border-b border-line px-3 py-2.5 last:border-b-0">
            <span className="text-[11px] tracking-[0.12em] text-mute uppercase">{label}</span>
            <span className="text-[13px]">{value}</span>
          </div>
        ))}
        <div className="px-3 py-3">
          <div className="h-1.5 bg-paper-deep">
            <div className="h-full w-[92%] bg-accent" />
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-mute">
            Confidence is a model score for this reading, kept beside the original sentence.
          </p>
        </div>
      </div>
    </div>
  );
}

function ThemesScene() {
  const themes = [
    { name: "Login difficulties", count: 186, width: "100%", tone: "Negative · rising" },
    { name: "Slow application performance", count: 142, width: "76%", tone: "Negative · steady" },
    { name: "Payment failures", count: 97, width: "52%", tone: "Negative · accelerating" },
    { name: "Feature requests · export", count: 74, width: "40%", tone: "Request · recurring" },
  ];
  return (
    <div className="border border-line bg-sheet">
      <div className="flex items-end justify-between border-b border-line px-3 py-2.5">
        <div>
          <p className="text-[10px] tracking-[0.14em] text-mute uppercase">Themes formed from records</p>
          <p className="mt-1 text-[13px]">499 individual notes, four recurring themes</p>
        </div>
        <p className="text-[11px] text-mute">Sample window · 30 days</p>
      </div>
      <div className="grid gap-3 px-3 py-3">
        {themes.map((theme) => (
          <div key={theme.name}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-[12px]">
              <span>{theme.name}</span>
              <span className="text-mute">
                {theme.count} · {theme.tone}
              </span>
            </div>
            <div className="h-1.5 bg-paper-deep">
              <div className="h-full bg-ink" style={{ width: theme.width }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MemoryScene() {
  return (
    <div className="grid gap-2.5">
      <div className="grid gap-2 lg:grid-cols-3">
        <article className="border border-line bg-sheet p-3">
          <p className="text-[10px] tracking-[0.14em] text-mute uppercase">Earlier record</p>
          <p className="mt-2 text-[13px] leading-snug">October 2026 · 42 checkout timeouts after v2.4.0.</p>
          <p className="mt-3 text-[12px] leading-relaxed text-ink-soft">
            Complaints fell 68% after v2.5. Stored as an episodic event tied to that release, not as a loose note.
          </p>
        </article>
        <article className="border border-ink bg-ink p-3 text-paper">
          <p className="text-[10px] tracking-[0.14em] text-[#c8c2b6] uppercase">New feedback</p>
          <p className="mt-2 text-[13px] leading-snug">“Checkout spinner is back during the evening sale.”</p>
          <p className="mt-3 text-[12px] leading-relaxed text-[#e6e0d4]">App Store · today · v2.6.1</p>
        </article>
        <article className="border border-line bg-sheet p-3">
          <p className="text-[10px] tracking-[0.14em] text-accent uppercase">Retrieved context</p>
          <p className="mt-2 text-[13px] leading-snug">This matches the October cluster.</p>
          <p className="mt-3 text-[12px] leading-relaxed text-ink-soft">
            Read as a return of a resolved issue. Volume is climbing again after the fix, so the trend is a regression.
          </p>
        </article>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border border-line bg-paper-deep px-3 py-2 text-[11px] text-ink-soft">
        <span>Episodic · October timeouts</span>
        <span>Temporal · −68% after v2.5</span>
        <span>Provenance · source records retained</span>
      </div>
    </div>
  );
}

function ActionScene() {
  const items = [
    ["Payment failures are becoming more frequent", "+38% versus the prior 14 days", "27 records", "Investigate gateway timeouts before the next release."],
    ["Dissatisfaction with login is increasing", "Sentiment moved −0.22 over three weeks", "41 records", "Treat expired codes as an open reliability issue."],
    ["CSV export keeps being requested", "19 requests, mostly constructive", "19 records", "Schedule the export path rather than a bugfix."],
    ["A resolved checkout issue is returning", "Improved after v2.5, rising in v2.6", "16 records", "Compare the evening-sale path with the v2.5 fix."],
  ];
  return (
    <div className="border border-line bg-sheet">
      {items.map(([title, change, evidence, action]) => (
        <div key={title} className="grid gap-1 border-b border-line px-3 py-2.5 last:border-b-0 lg:grid-cols-[1.3fr_0.9fr_0.5fr]">
          <div>
            <p className="text-[13px]">{title}</p>
            <p className="mt-1 text-[12px] text-ink-soft">{action}</p>
          </div>
          <p className="text-[12px] text-mute lg:pt-0.5">{change}</p>
          <p className="text-[12px] text-accent lg:text-right">{evidence}</p>
        </div>
      ))}
    </div>
  );
}

const scenes: Record<SceneId, () => ReactElement> = {
  overview: OverviewScene,
  ingest: IngestScene,
  classify: ClassifyScene,
  themes: ThemesScene,
  memory: MemoryScene,
  action: ActionScene,
};

export function ProductCanvas({ scene }: { scene: SceneId }) {
  const reduce = useReducedMotion();
  const meta = sceneMeta[scene];
  const Scene = scenes[scene];

  return (
    <div className="overflow-hidden border border-line-strong bg-sheet shadow-[0_24px_60px_rgba(17,17,16,0.06)]">
      <div className="flex items-center justify-between gap-3 border-b border-line px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="flex gap-1" aria-hidden>
            <i className="block h-2 w-2 rounded-full bg-line-strong" />
            <i className="block h-2 w-2 rounded-full bg-line-strong" />
            <i className="block h-2 w-2 rounded-full bg-line-strong" />
          </span>
          <span className="text-[12px] text-ink-soft">Analytics Portal · {meta.crumb}</span>
        </div>
        <span className="border border-line px-2 py-0.5 text-[10px] tracking-[0.14em] text-mute uppercase">
          Sample data
        </span>
      </div>
      <div className="flex min-h-[280px]">
        <Sidebar active={meta.nav} />
        <div className="min-w-0 flex-1 p-3">
          <AnimatePresence mode="wait">
            <motion.div
              key={scene}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -6 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            >
              <Scene />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
