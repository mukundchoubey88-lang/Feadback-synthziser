import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Kicker } from "./ui";

const steps = [
  {
    id: "collect",
    numeral: "I",
    title: "Collect feedback",
    body: "Reviews, tickets, surveys, and files arrive as uneven text. CSV and JSON uploads are checked for a timestamp, counted when they duplicate an existing record, and stored without rewriting the original sentence.",
    note: "Live",
  },
  {
    id: "classification",
    numeral: "II",
    title: "Clean and understand feedback",
    body: "The live pipeline normalizes wording, scores quality, and redacts personal data on the cleaned copy. Sentiment, category, and topic belong beside that sentence. That reading is illustrated, because classification is not an API yet.",
    note: "Cleaning is live. Classification is illustrated.",
  },
  {
    id: "decide",
    numeral: "III",
    title: "Turn feedback into actionable intelligence",
    body: "Themes, Hindsight, and recommendations are the point of the agent: a pattern, the history around it, and a decision that names its records. Those routes are specified and not served yet.",
    note: "Illustrated",
  },
];

export function Workflow() {
  const [active, setActive] = useState(0);
  const reduce = useReducedMotion();
  const step = steps[active];

  return (
    <section id="ingestion" className="bg-ink text-paper">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <Kicker tone="paper">How it works</Kicker>
        <h2 className="section-title mt-4 max-w-[14ch] text-paper">Three steps. One reading of the record.</h2>
        <div className="mt-14 grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
          <div className="grid gap-3">
            {steps.map((item, index) => {
              const selected = index === active;
              return (
                <button
                  key={item.id}
                  id={item.id === "classification" ? "classification" : undefined}
                  type="button"
                  aria-pressed={selected}
                  className={`border px-5 py-4 text-left transition-colors duration-200 ${
                    selected ? "border-paper bg-paper text-ink" : "border-paper/20 text-paper hover:border-paper/50"
                  }`}
                  onClick={() => setActive(index)}
                >
                  <span className={`text-[12px] tracking-[0.16em] ${selected ? "text-mute" : "text-paper/50"}`}>
                    {item.numeral}
                  </span>
                  <span className="mt-2 block text-[18px] tracking-[-0.03em]">{item.title}</span>
                </button>
              );
            })}
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={step.id}
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -8 }}
              transition={reduce ? { duration: 0 } : { duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="border border-paper/20 p-6 sm:p-8"
            >
              <p className="text-[12px] tracking-[0.16em] text-paper/55 uppercase">{step.note}</p>
              <h3 className="mt-4 text-[28px] tracking-[-0.04em]">{step.title}</h3>
              <p className="mt-4 max-w-xl text-[16px] leading-relaxed text-paper/75">{step.body}</p>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
