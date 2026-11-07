import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { ArrowRight, Menu, X } from "lucide-react";

const links = [
  { href: "#platform", id: "platform", label: "Platform" },
  { href: "#ingestion", id: "ingestion", label: "How It Works" },
  { href: "#hindsight", id: "hindsight", label: "Intelligence" },
  { href: "#actions", id: "actions", label: "Features" },
  { href: "#about", id: "about", label: "About" },
];

const watched = ["ingestion", "classification", "themes", "hindsight", "actions", "about"];

export function SiteNav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [current, setCurrent] = useState("");
  const location = useLocation();

  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 8);
      let active = "";
      for (const id of watched) {
        const element = document.getElementById(id);
        if (!element) continue;
        if (element.getBoundingClientRect().top < 160) active = id;
      }
      if (active === "classification") active = "ingestion";
      if (active === "themes") active = "actions";
      setCurrent(active || "platform");
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [location]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header
      className={`sticky top-0 z-40 border-b bg-paper ${scrolled ? "border-line" : "border-transparent"}`}
    >
      <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between gap-6 px-5">
        <Link to="/" className="flex shrink-0 items-center gap-2.5 text-ink">
          <span className="grid h-7 w-7 place-items-center bg-ink text-[13px] text-paper">S</span>
          <span className="text-[15px] tracking-[-0.03em]">Synthesizer</span>
        </Link>
        <nav className="hidden items-center gap-8 lg:flex" aria-label="Primary">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={`text-[14px] transition-colors duration-200 hover:text-ink ${
                current === link.id ? "text-ink" : "text-mute"
              }`}
              aria-current={current === link.id ? "true" : undefined}
            >
              {link.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <NavLink
            to="/console"
            className="hidden items-center gap-2 rounded-pill bg-ink px-4 py-2 text-[13px] text-paper transition-colors duration-200 hover:bg-ink-soft lg:inline-flex"
          >
            Open console
            <ArrowRight size={14} strokeWidth={1.75} />
          </NavLink>
          <button
            type="button"
            className="grid h-10 w-10 place-items-center border border-line text-ink transition-colors duration-200 hover:border-ink lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={16} strokeWidth={1.75} /> : <Menu size={16} strokeWidth={1.75} />}
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-nav" className="border-t border-line px-5 py-4 lg:hidden" aria-label="Mobile">
          <div className="mx-auto grid max-w-[1180px] gap-1">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className={`px-1 py-3 text-[16px] transition-colors duration-200 hover:text-ink ${
                  current === link.id ? "text-ink" : "text-ink-soft"
                }`}
                aria-current={current === link.id ? "true" : undefined}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <NavLink
              to="/console"
              className="mt-3 inline-flex items-center justify-center gap-2 rounded-pill bg-ink px-4 py-3 text-center text-[14px] text-paper transition-colors duration-200 hover:bg-ink-soft"
            >
              Open console
              <ArrowRight size={14} strokeWidth={1.75} />
            </NavLink>
          </div>
        </nav>
      )}
    </header>
  );
}
