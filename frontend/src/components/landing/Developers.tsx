import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Copy } from "lucide-react";
import { API_BASE } from "../../lib/api";
import { Kicker, Reveal, primaryCta, secondaryCta } from "./ui";

const snippet = `const health = await fetch("${API_BASE}/api/health");
const summary = await fetch("${API_BASE}/api/feedback/quality/summary");

// CSV or JSON upload
const body = new FormData();
body.append("file", file);
await fetch("${API_BASE}/api/feedback/upload", { method: "POST", body });`;

export function Developers() {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopyError(null);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
      setCopyError("Clipboard access was blocked. Select the example and copy it manually.");
    }
  }

  return (
    <section className="border-t border-line">
      <div className="mx-auto grid max-w-[1180px] gap-12 px-5 py-24 lg:grid-cols-[0.85fr_1.15fr] lg:items-start">
        <Reveal>
          <Kicker>Developers</Kicker>
          <h2 className="section-title mt-4">The calls the console already makes.</h2>
          <p className="mt-5 text-[16px] leading-relaxed text-ink-soft">
            Health, the quality summary, and file upload are live routes. The base URL follows the frontend
            configuration, which defaults to the local API.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/console" className={primaryCta}>
              Open console
            </Link>
            <a href={`${API_BASE}/docs`} className={secondaryCta}>
              API reference
            </a>
          </div>
        </Reveal>
        <Reveal delay={0.06}>
          <div className="border border-line bg-sheet">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <p className="text-[12px] tracking-[0.14em] text-mute uppercase">Existing endpoints</p>
              <button
                type="button"
                onClick={() => void copy()}
                className="inline-flex items-center gap-2 text-[13px] text-ink transition-colors duration-200 hover:text-ink-soft"
              >
                {copied ? <Check size={14} strokeWidth={1.75} /> : <Copy size={14} strokeWidth={1.75} />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="overflow-x-auto px-4 py-5 font-mono text-[13px] leading-relaxed text-ink">
              <code className="font-mono">{snippet}</code>
            </pre>
          </div>
          {copyError && <p className="mt-3 text-[13px] text-bad">{copyError}</p>}
        </Reveal>
      </div>
    </section>
  );
}
