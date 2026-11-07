import { NavLink, Outlet, Link } from "react-router-dom";
import { API_BASE } from "../../lib/api";

const items = [
  { to: "/console", label: "Overview", end: true },
  { to: "/console/feedback", label: "Feedback" },
  { to: "/console/ingestion", label: "Ingestion" },
  { to: "/console/quality", label: "Quality" },
  { to: "/console/themes", label: "Themes", planned: true },
  { to: "/console/insights", label: "Insights", planned: true },
  { to: "/console/memory", label: "Intelligence Memory", planned: true },
  { to: "/console/reports", label: "Reports", planned: true },
];

export function ConsoleLayout() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line">
        <div className="mx-auto flex h-16 max-w-[1240px] items-center justify-between gap-4 px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center bg-ink text-[13px] text-paper">S</span>
            <span className="text-[15px] tracking-[-0.03em]">Synthesizer</span>
          </Link>
          <p className="hidden items-center gap-1.5 text-[13px] text-mute sm:flex">
            <span className="inline-block h-2 w-2 rounded-full bg-good animate-pulse-subtle" />
            Live console • <span className="font-mono text-[12px]">{API_BASE}</span>
          </p>
          <Link to="/" className="text-[13px] text-ink-soft hover:text-ink">
            Back to site
          </Link>
        </div>
      </header>
      <div className="mx-auto grid max-w-[1240px] lg:grid-cols-[220px_1fr]">
        <aside className="border-b border-line lg:min-h-[calc(100vh-4rem)] lg:border-r lg:border-b-0">
          <p className="px-5 pt-5 text-[11px] tracking-[0.16em] text-mute uppercase">Workspace</p>
          <nav className="flex gap-1 overflow-x-auto px-3 py-3 lg:grid lg:px-3" aria-label="Console">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex shrink-0 items-center justify-between gap-3 px-2 py-2 text-[14px] ${
                    isActive ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
                  }`
                }
              >
                <span>{item.label}</span>
                {item.planned && <span className="text-[10px] tracking-[0.12em] uppercase opacity-70">Soon</span>}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="px-5 py-8 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
