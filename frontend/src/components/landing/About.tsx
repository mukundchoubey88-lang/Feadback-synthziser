import { Link } from "react-router-dom";
import { Kicker, Reveal, primaryCta } from "./ui";

export function About() {
  return (
    <section id="about" className="border-t border-line">
      <div className="mx-auto grid max-w-[1180px] gap-12 px-5 py-24 lg:grid-cols-[0.9fr_1.1fr]">
        <Reveal>
          <Kicker>About the product</Kicker>
          <h2 className="section-title mt-4">What is running, and what is being shown.</h2>
          <p className="mt-5 max-w-md text-[16px] leading-relaxed text-ink-soft">
            The landing page demonstrates the intelligence the platform is built to provide. The console beside it
            speaks only to endpoints that exist today.
          </p>
          <Link to="/console" className={`${primaryCta} mt-8`}>
            Open the live console
          </Link>
        </Reveal>
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
