import type { ReactNode } from "react";

export function Panel({ title, action, children }: { title?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="border border-line bg-sheet">
      {title && (
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="text-[14px]">{title}</h2>
          {action}
        </div>
      )}
      <div className="px-4 py-4">{children}</div>
    </section>
  );
}

export function Notice({ tone = "neutral", children }: { tone?: "neutral" | "bad"; children: ReactNode }) {
  return (
    <p className={`border px-3 py-2 text-[13px] leading-relaxed ${tone === "bad" ? "border-bad/30 text-bad" : "border-line text-ink-soft"}`}>
      {children}
    </p>
  );
}

export function PlannedPage({ kicker, title, body }: { kicker: string; title: string; body: string }) {
  return (
    <div className="max-w-xl">
      <p className="text-[12px] tracking-[0.16em] text-mute uppercase">{kicker}</p>
      <h1 className="mt-3 text-[32px] leading-[1.05] tracking-[-0.04em]">{title}</h1>
      <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">{body}</p>
    </div>
  );
}
