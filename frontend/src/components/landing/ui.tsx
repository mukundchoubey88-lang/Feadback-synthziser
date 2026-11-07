import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

export const primaryCta =
  "inline-flex items-center justify-center gap-2 rounded-pill bg-ink px-4 py-2.5 text-[14px] text-paper transition-colors duration-200 hover:bg-ink-soft";

export const secondaryCta =
  "inline-flex items-center justify-center gap-2 rounded-pill border border-line-strong px-4 py-2.5 text-[14px] text-ink transition-colors duration-200 hover:border-ink";

export function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const reduce = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -48px 0px" }}
      transition={reduce ? { duration: 0 } : { duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function Kicker({ children, tone = "mute" }: { children: ReactNode; tone?: "mute" | "paper" }) {
  return (
    <p className={`text-[12px] tracking-[0.18em] uppercase ${tone === "paper" ? "text-paper/60" : "text-mute"}`}>
      {children}
    </p>
  );
}
