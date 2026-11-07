import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { ProductCanvas } from "../ProductCanvas";
import { primaryCta, secondaryCta } from "./ui";

export function Hero() {
  const reduce = useReducedMotion();

  return (
    <section className="mx-auto grid max-w-[1180px] gap-14 px-5 pt-16 pb-20 lg:pt-24 lg:pb-28">
      <div className="grid items-end gap-10 lg:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={reduce ? { duration: 0 } : { duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <p className="text-[12px] tracking-[0.18em] text-mute uppercase">Feedback Intelligence Agent</p>
          <h1 className="editorial mt-5 max-w-[14ch]">
            Every piece of feedback has something to tell you.
          </h1>
        </motion.div>
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={reduce ? { duration: 0 } : { duration: 0.6, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
        >
          <p className="max-w-md text-[16px] leading-relaxed text-ink-soft">
            An AI-powered feedback intelligence agent that connects customer voices, discovers emerging themes,
            remembers historical context, and turns scattered feedback into actionable intelligence.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link to="/console" className={primaryCta}>
              Open console
              <ArrowRight size={15} strokeWidth={1.75} />
            </Link>
            <a href="#ingestion" className={secondaryCta}>
              Explore how it works
            </a>
          </div>
        </motion.div>
      </div>
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.7, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
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
