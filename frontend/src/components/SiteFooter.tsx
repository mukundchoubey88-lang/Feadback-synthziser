import { Link } from "react-router-dom";

const platform = [
  { href: "/#platform", label: "Platform" },
  { href: "/#ingestion", label: "How it works" },
  { href: "/#hindsight", label: "Intelligence" },
  { href: "/#actions", label: "Features" },
  { href: "/#about", label: "About" },
];

const linkClass = "text-[14px] text-ink-soft transition-colors duration-200 hover:text-ink";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-paper">
      <div className="mx-auto grid max-w-[1180px] gap-12 px-5 py-16 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div className="sm:col-span-2 lg:col-span-1">
          <p className="flex items-center gap-2.5 text-[15px] tracking-[-0.03em] text-ink">
            <span className="grid h-7 w-7 place-items-center bg-ink text-[13px] text-paper">S</span>
            Synthesizer
          </p>
          <p className="mt-4 max-w-sm text-[14px] leading-relaxed text-ink-soft">
            User Feedback Synthesizer is a feedback intelligence agent. It keeps the original customer voice,
            structures what arrives, and is being built to remember what the product has already learned.
          </p>
        </div>
        <div>
          <p className="text-[11px] tracking-[0.16em] text-mute uppercase">Platform</p>
          <ul className="mt-4 grid gap-2.5">
            {platform.map((item) => (
              <li key={item.href}>
                <a href={item.href} className={linkClass}>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-[11px] tracking-[0.16em] text-mute uppercase">Workspace</p>
          <ul className="mt-4 grid gap-2.5">
            <li>
              <Link to="/console" className={linkClass}>
                Live console
              </Link>
            </li>
            <li>
              <a href="http://127.0.0.1:8000/docs" className={linkClass}>
                API reference
              </a>
            </li>
          </ul>
        </div>
        <div>
          <p className="text-[11px] tracking-[0.16em] text-mute uppercase">Project</p>
          <ul className="mt-4 grid gap-2.5 text-[14px] text-ink-soft">
            <li>Mukund Choubey</li>
            <li>B.Tech CSE, AI & ML · S-VYASA</li>
            <li>
              <a className={linkClass} href="https://github.com/mukundchoubey88-lang/Feadback-synthziser">
                GitHub repository
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-3 px-5 py-4 text-[12px] text-mute">
          <p>Feedback Intelligence Agent</p>
          <p>Illustrations on this page use sample data. The console uses the live API.</p>
        </div>
      </div>
    </footer>
  );
}
