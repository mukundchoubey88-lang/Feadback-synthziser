import { Link } from "react-router-dom";
import { Kicker, Reveal, primaryCta } from "./ui";

export function Pricing() {
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <Reveal className="max-w-2xl">
          <Kicker>Pricing</Kicker>
          <h2 className="section-title mt-4">Pricing is not published.</h2>
          <p className="mt-5 text-[16px] leading-relaxed text-ink-soft">
            This project does not list plans, prices, or subscription terms. The console is the working surface for the
            API that exists today.
          </p>
          <Link to="/console" className={`${primaryCta} mt-8`}>
            Open console
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
