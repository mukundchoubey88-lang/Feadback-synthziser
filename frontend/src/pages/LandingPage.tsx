import { SiteFooter } from "../components/SiteFooter";
import { SiteNav } from "../components/SiteNav";
import { About } from "../components/landing/About";
import { Capabilities } from "../components/landing/Capabilities";
import { Closing } from "../components/landing/Closing";
import { Developers } from "../components/landing/Developers";
import { Hero } from "../components/landing/Hero";
import { Integrations } from "../components/landing/Integrations";
import { Metrics } from "../components/landing/Metrics";
import { Pricing } from "../components/landing/Pricing";
import { Security } from "../components/landing/Security";
import { Workflow } from "../components/landing/Workflow";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <SiteNav />
      <main>
        <Hero />
        <Capabilities />
        <Workflow />
        <Metrics />
        <Integrations />
        <Security />
        <Developers />
        <About />
        <Pricing />
        <Closing />
      </main>
      <SiteFooter />
    </div>
  );
}
