import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

// ============================================================================
// Button
// ============================================================================

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
  busy?: boolean;
}

const buttonVariantStyles: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-ink text-paper hover:bg-ink-soft active:bg-ink",
  secondary: "border border-line bg-sheet text-ink hover:border-line-strong hover:bg-paper active:bg-sheet",
  ghost: "text-ink-soft hover:text-ink hover:bg-paper-deep/60",
};

const buttonSizeStyles: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "rounded-sm px-2.5 py-1 text-[12px] leading-tight",
  md: "rounded-sm px-3.5 py-2 text-[13px] leading-normal",
};

export function Button({
  variant = "primary",
  size = "md",
  busy = false,
  disabled = false,
  className = "",
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || busy;

  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-busy={busy || undefined}
      className={`inline-flex items-center justify-center gap-2 font-normal transition-all duration-150 active:scale-[0.985] focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100 select-none ${buttonVariantStyles[variant]} ${buttonSizeStyles[size]} ${className}`}
      {...rest}
    >
      {busy && (
        <svg
          className="h-3.5 w-3.5 shrink-0 animate-spin"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}

// ============================================================================
// Input
// ============================================================================

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
}

export function Input({ mono = false, className = "", ...rest }: InputProps) {
  return (
    <input
      className={`border border-line bg-sheet px-3 py-2 text-[13px] text-ink placeholder:text-mute transition-colors focus:border-ink focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
        mono ? "font-mono" : ""
      } ${className}`}
      {...rest}
    />
  );
}

// ============================================================================
// Badge
// ============================================================================

export interface BadgeProps {
  variant?: "neutral" | "good" | "warn" | "bad" | "accent";
  mono?: boolean;
  className?: string;
  children: ReactNode;
}

const badgeVariantStyles: Record<NonNullable<BadgeProps["variant"]>, string> = {
  neutral: "bg-paper-deep text-ink-soft border-line",
  good: "bg-good/10 text-good border-good/25",
  warn: "bg-warn/10 text-warn border-warn/25",
  bad: "bg-bad/10 text-bad border-bad/25",
  accent: "bg-accent/10 text-accent border-accent/25",
};

export function Badge({
  variant = "neutral",
  mono = false,
  className = "",
  children,
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-pill border px-2 py-0.5 text-[11px] font-medium leading-none ${
        mono ? "font-mono" : ""
      } ${badgeVariantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

// ============================================================================
// Notice / Alert
// ============================================================================

export interface NoticeProps {
  tone?: "neutral" | "good" | "warn" | "bad";
  className?: string;
  children: ReactNode;
}

const noticeToneStyles: Record<NonNullable<NoticeProps["tone"]>, string> = {
  neutral: "border-line bg-sheet text-ink-soft",
  bad: "border-bad/30 bg-bad/5 text-bad",
  good: "border-good/30 bg-good/5 text-good",
  warn: "border-warn/30 bg-warn/5 text-warn",
};

export function Notice({ tone = "neutral", className = "", children }: NoticeProps) {
  return (
    <div className={`border px-3.5 py-2.5 text-[13px] leading-relaxed ${noticeToneStyles[tone]} ${className}`}>
      {children}
    </div>
  );
}

// ============================================================================
// MetricCard
// ============================================================================

export interface MetricCardProps {
  label: string;
  value: ReactNode;
  description?: ReactNode;
  className?: string;
}

export function MetricCard({ label, value, description, className = "" }: MetricCardProps) {
  return (
    <div className={`border border-line bg-sheet px-4 py-3.5 transition-all duration-200 hover:border-line-strong hover:shadow-xs ${className}`}>
      <p className="text-[11px] tracking-[0.14em] text-mute uppercase">{label}</p>
      <div className="mt-1 text-[24px] font-normal tracking-[-0.04em] text-ink break-words">{value}</div>
      {description && <div className="mt-1.5 text-[12px] text-mute">{description}</div>}
    </div>
  );
}

// ============================================================================
// EmptyState
// ============================================================================

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, className = "" }: EmptyStateProps) {
  return (
    <div className={`border border-dashed border-line bg-sheet/40 px-4 py-8 text-center ${className}`}>
      <p className="text-[13px] text-ink">{title}</p>
      {description && <p className="mt-1 text-[12px] text-mute">{description}</p>}
      {action && <div className="mt-3 flex justify-center">{action}</div>}
    </div>
  );
}

// ============================================================================
// Preserved Exports: Panel & PlannedPage
// ============================================================================

export function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`border border-line bg-sheet ${className}`}>
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

export function PlannedPage({ kicker, title, body }: { kicker: string; title: string; body: string }) {
  return (
    <div className="max-w-xl">
      <p className="text-[12px] tracking-[0.16em] text-mute uppercase">{kicker}</p>
      <h1 className="mt-3 text-[32px] leading-[1.05] tracking-[-0.04em]">{title}</h1>
      <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">{body}</p>
    </div>
  );
}
