import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Reveal, primaryCta, secondaryCta } from "./ui";

export function Closing() {
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <Reveal>
          <h2 className="section-title max-w-[14ch]">Read the feedback that is already arriving.</h2>
          <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-ink-soft">
            Open the console to use the live ingestion, quality, and cleaning routes. The story of themes, memory, and
            recommendations stays marked as illustration until those endpoints exist.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/console" className={primaryCta}>
              Open console
              <ArrowRight size={15} strokeWidth={1.75} />
            </Link>
            <a href="#ingestion" className={secondaryCta}>
              Explore how it works
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
