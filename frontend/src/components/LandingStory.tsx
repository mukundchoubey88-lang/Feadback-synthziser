import { useEffect, useState } from "react";
import { motion, useReducedMotion, useScroll, useTransform, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { ProductCanvas, type SceneId } from "./ProductCanvas";

export const stages: Array<{
  id: string;
  scene: SceneId;
  index: string;
  kicker: string;
  title: string;
  body: string;
  points: string[];
}> = [
  {
    id: "ingestion",
    scene: "ingest",
    index: "01",
    kicker: "Feedback ingestion",
    title: "Raw voices arrive. A record leaves.",
    body: "Reviews, tickets, surveys, and files enter as uneven text. The live pipeline checks the timestamp, skips duplicates, normalizes the wording, and redacts personal data. The original sentence stays immutable.",
    points: ["CSV and JSON uploads are live", "Duplicates are counted, not rewritten", "PII is replaced only in the cleaned copy"],
  },
  {
    id: "classification",
    scene: "classify",
    index: "02",
    kicker: "Reading a single voice",
    title: "Each note is understood before it is counted.",
    body: "Sentiment, category, topic, priority, and confidence belong to the individual piece of feedback. A score sits next to the sentence it came from, so a trend can be opened back up.",
    points: ["Negative is not treated as low quality", "Priority is separate from volume", "This reading is illustrated — classification is not an API yet"],
  },
  {
    id: "themes",
    scene: "themes",
    index: "03",
    kicker: "Theme discovery",
    title: "Separate complaints become a pattern.",
    body: "Login failures, slow screens, payment errors, and repeated requests stop looking like a queue. Frequency and sentiment move together, so a loud new bug is not confused with a long-running request.",
    points: ["Volume shows how often a theme returns", "Sentiment shows how it feels", "Theme clustering is illustrated, not queried live"],
  },
  {
    id: "hindsight",
    scene: "memory",
    index: "04",
    kicker: "Hindsight",
    title: "New feedback is read with what already happened.",
    body: "Hindsight is the product’s memory. It keeps episodic events, the meaning of a theme, and how sentiment moved after a release. A fresh checkout complaint can be recognized as the return of an issue v2.5 already reduced.",
    points: ["Earlier evidence stays attached to a release", "Temporal change is part of the reading", "It is not a chat box and not a dump of every raw comment"],
  },
  {
    id: "actions",
    scene: "action",
    index: "05",
    kicker: "Actionable intelligence",
    title: "The decision names its evidence.",
    body: "A recommendation is useful when it says what changed, against which history, and from which records. Rising payment failures, worsening login sentiment, a repeated export request, and a fix that is slipping are different decisions.",
    points: ["Direction is compared with a prior window", "Evidence is a count of source records", "Insight routes are specified and not implemented yet"],
  },
];

function useActiveStage(enabled: boolean) {
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const section = document.getElementById("platform");
    if (!section) return;

    const update = () => {
      const rect = section.getBoundingClientRect();
      const total = section.offsetHeight - window.innerHeight;
      if (total <= 0) return;
      const progress = Math.min(0.999, Math.max(0, -rect.top / total));
      setActive(Math.min(stages.length - 1, Math.floor(progress * stages.length)));
    };

    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [enabled]);

  return active;
}

export function Hero() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const y = useTransform(scrollY, [0, 420], [0, reduce ? 0 : 36]);
  const fade = useTransform(scrollY, [0, 380], [1, reduce ? 1 : 0.35]);

  return (
    <section className="mx-auto grid max-w-[1180px] gap-8 px-5 pt-8 pb-6 lg:min-h-[calc(100vh-4rem)] lg:grid-rows-[auto_1fr] lg:pt-10">
      <motion.div style={{ y, opacity: fade }} className="grid items-end gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          <p className="text-[12px] tracking-[0.18em] text-mute uppercase">Feedback Intelligence Agent</p>
          <h1 className="editorial mt-4">
            <span className="block">Every piece of feedback</span>
            <span className="mt-1 block font-normal text-ink-soft italic">has something to tell you.</span>
          </h1>
        </div>
        <div className="max-w-md pb-1">
          <p className="text-[16px] leading-relaxed text-ink-soft">
            An AI-powered feedback intelligence agent that connects customer voices, discovers emerging themes,
            remembers historical context, and turns scattered feedback into actionable intelligence.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href="#platform" className="bg-ink px-4 py-2.5 text-[14px] text-paper hover:bg-accent-deep">
              Explore the Platform
            </a>
            <a href="#ingestion" className="border border-line-strong px-4 py-2.5 text-[14px] hover:border-ink">
              See How It Works
            </a>
          </div>
        </div>
      </motion.div>
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="motion-safe:animate-[float_7s_ease-in-out_infinite]">
          <ProductCanvas scene="overview" />
        </div>
        <p className="mt-3 text-[12px] text-mute">
          Illustrative interface. These figures are sample data and are not read from the backend.
        </p>
      </motion.div>
    </section>
  );
}

function StageCopy({ stage }: { stage: (typeof stages)[number] }) {
  return (
    <div>
      <p className="text-[12px] tracking-[0.18em] text-accent uppercase">
        {stage.index} — {stage.kicker}
      </p>
      <h2 className="section-title mt-4 max-w-[16ch]">{stage.title}</h2>
      <p className="mt-5 max-w-md text-[16px] leading-relaxed text-ink-soft">{stage.body}</p>
      <ul className="mt-6 grid gap-2">
        {stage.points.map((point) => (
          <li key={point} className="border-l border-line-strong pl-3 text-[14px] text-ink">
            {point}
          </li>
        ))}
      </ul>
    </div>
  );
}

function prefersStoryScroll() {
  return (
    window.matchMedia("(min-width: 1024px)").matches &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function Story() {
  const reduce = useReducedMotion();
  const [wide, setWide] = useState(prefersStoryScroll);
  const active = useActiveStage(wide && !reduce);
  const stage = stages[active];

  useEffect(() => {
    const wideMedia = window.matchMedia("(min-width: 1024px)");
    const motionMedia = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setWide(wideMedia.matches && !motionMedia.matches);
    apply();
    wideMedia.addEventListener("change", apply);
    motionMedia.addEventListener("change", apply);
    return () => {
      wideMedia.removeEventListener("change", apply);
      motionMedia.removeEventListener("change", apply);
    };
  }, []);

  if (!wide || reduce) {
    return (
      <section id="platform" className="mx-auto max-w-[1180px] px-5 py-16">
        <div className="grid gap-20">
          {stages.map((item) => (
            <article id={item.id} key={item.id} className="grid gap-8">
              <StageCopy stage={item} />
              <ProductCanvas scene={item.scene} />
            </article>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section id="platform" className="relative" style={{ height: `${stages.length * 100}vh` }}>
      {stages.map((item, index) => (
        <div key={item.id} id={item.id} className="absolute left-0 h-px w-px" style={{ top: `${index * 100}vh` }} />
      ))}
      <div className="sticky top-16 flex h-[calc(100vh-4rem)] items-center">
        <div className="mx-auto grid w-full max-w-[1180px] items-center gap-12 px-5 lg:grid-cols-[0.82fr_1.18fr]">
          <AnimatePresence mode="wait">
            <motion.div
              key={stage.id}
              initial={reduce ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            >
              <StageCopy stage={stage} />
            </motion.div>
          </AnimatePresence>
          <ProductCanvas scene={stage.scene} />
        </div>
      </div>
    </section>
  );
}

export function About() {
  return (
    <section id="about" className="border-t border-line">
      <div className="mx-auto grid max-w-[1180px] gap-12 px-5 py-20 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="text-[12px] tracking-[0.18em] text-mute uppercase">About the product</p>
          <h2 className="section-title mt-4">What is running, and what is being shown.</h2>
          <p className="mt-5 max-w-md text-[16px] leading-relaxed text-ink-soft">
            The landing page demonstrates the intelligence the platform is built to provide. The console beside it
            speaks only to endpoints that exist today.
          </p>
          <Link to="/console" className="mt-8 inline-block bg-ink px-4 py-2.5 text-[14px] text-paper hover:bg-accent-deep">
            Open the live console
          </Link>
        </div>
        <div className="grid gap-px bg-line sm:grid-cols-2">
          <div className="bg-paper p-6">
            <p className="text-[12px] tracking-[0.16em] text-good uppercase">Live API</p>
            <ul className="mt-4 grid gap-2 text-[14px] leading-relaxed">
              <li>Health and service metadata</li>
              <li>CSV and JSON ingestion</li>
              <li>Upload job status</li>
              <li>Feedback list and record detail</li>
              <li>Cleaning, PII redaction, quality scores</li>
            </ul>
          </div>
          <div className="bg-paper p-6">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Illustrated, not served</p>
            <ul className="mt-4 grid gap-2 text-[14px] leading-relaxed text-ink-soft">
              <li>Sentiment classification</li>
              <li>Theme discovery</li>
              <li>Hindsight recall</li>
              <li>Evidence-backed recommendations</li>
              <li>Release impact reports</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
