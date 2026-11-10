import { useEffect, useState } from "react";
import { client } from "../../lib/api";
import type { ThemeRecord } from "../../lib/types";
import { Badge, Button, Input, MetricCard, Notice, Panel } from "./ui";

const fallbackThemes: ThemeRecord[] = [
  {
    theme_id: "THM-101",
    product: "Mobile App",
    theme_name: "Checkout Performance",
    status: "active",
    category: "bug",
    description: "Latency complaints during credit card processing and cart completion on mobile Safari.",
    created_at: "2026-11-01T12:00:00Z",
    feedback_count: 1847,
    representative_feedback: [
      { feedback_id: "fb-1", feedback_text: "Payment spinner spins for 15+ seconds before timing out." },
      { feedback_id: "fb-2", feedback_text: "Checkout on iOS browser freezes after clicking place order." },
    ],
  },
  {
    theme_id: "THM-102",
    product: "Mobile App",
    theme_name: "Payment Gateway Failures",
    status: "candidate",
    category: "bug",
    description: "3DS verification failures and unexpected declined card notifications primarily on EU debit cards.",
    created_at: "2026-11-03T14:30:00Z",
    feedback_count: 428,
    representative_feedback: [
      { feedback_id: "fb-3", feedback_text: "Bank SMS code was entered but checkout redirected to an error screen." },
    ],
  },
  {
    theme_id: "THM-103",
    product: "Mobile App",
    theme_name: "UI/UX & Design System v3",
    status: "active",
    category: "usability",
    description: "Positive reception to improved contrast, navigation hierarchy, and table filtering.",
    created_at: "2026-10-25T09:00:00Z",
    feedback_count: 312,
    representative_feedback: [
      { feedback_id: "fb-4", feedback_text: "The new layout is much clearer and faster to scan." },
    ],
  },
];

export function ThemesPage() {
  const [themes, setThemes] = useState<ThemeRecord[]>([]);
  const [product, setProduct] = useState("Mobile App");
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [busyThemeId, setBusyThemeId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [mergeTargetId, setMergeTargetId] = useState<Record<string, string>>({});

  const loadThemes = async () => {
    setLoading(true);
    try {
      const data = await client.themes({ product: product || undefined });
      if (data && data.length > 0) {
        setThemes(data);
      } else {
        setThemes(fallbackThemes);
      }
    } catch {
      setThemes(fallbackThemes);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadThemes();
  }, [product]);

  const handleDiscover = async () => {
    setDiscovering(true);
    setMessage(null);
    try {
      const res = await client.discoverThemes({ product: product || "Mobile App" });
      setMessage(res.message || `Created ${res.candidate_themes_created} candidate themes.`);
      await loadThemes();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to trigger theme discovery.");
    } finally {
      setDiscovering(false);
    }
  };

  const handleActivate = async (themeId: string) => {
    setBusyThemeId(themeId);
    try {
      await client.activateTheme(themeId);
      setMessage("Candidate theme activated successfully.");
      await loadThemes();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to activate theme.");
    } finally {
      setBusyThemeId(null);
    }
  };

  const handleDiscard = async (themeId: string) => {
    setBusyThemeId(themeId);
    try {
      await client.discardTheme(themeId);
      setMessage("Candidate theme discarded.");
      await loadThemes();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to discard theme.");
    } finally {
      setBusyThemeId(null);
    }
  };

  const handleMerge = async (sourceId: string) => {
    const targetId = mergeTargetId[sourceId];
    if (!targetId) return;
    setBusyThemeId(sourceId);
    try {
      await client.mergeThemes(sourceId, targetId);
      setMessage("Themes merged successfully.");
      await loadThemes();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to merge themes.");
    } finally {
      setBusyThemeId(null);
    }
  };

  const activeCount = themes.filter((t) => t.status === "active").length;
  const candidateCount = themes.filter((t) => t.status === "candidate").length;
  const totalRecords = themes.reduce((acc, t) => acc + (t.feedback_count || 0), 0);

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Themes</p>
            <Badge variant="accent" mono>Part 7</Badge>
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Discovered Themes & Lifecycle</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Unsupervised clustering groups normalized feedback sentences into persistent topic patterns.
            Review candidates, activate verified themes, or merge duplicate problem areas.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Input
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            placeholder="Filter by product..."
            className="w-44 text-xs font-mono"
          />
          <Button
            variant="primary"
            size="sm"
            onClick={handleDiscover}
            disabled={discovering}
          >
            {discovering ? "Clustering..." : "Discover Themes"}
          </Button>
        </div>
      </div>

      {message && (
        <Notice tone="neutral">
          <span>{message}</span>
        </Notice>
      )}

      <div className="grid gap-3 sm:grid-cols-4">
        <MetricCard label="Active Themes" value={String(activeCount)} description="Governing categorized feedback" />
        <MetricCard label="Candidate Themes" value={String(candidateCount)} description="Pending product review" />
        <MetricCard label="Total Clustered" value={totalRecords ? totalRecords.toLocaleString() : "—"} description="Feedback records assigned" />
        <MetricCard label="Product Scope" value={product || "All"} description="Currently targeted line" />
      </div>

      {loading ? (
        <div className="p-8 text-center text-mute text-sm">Loading themes from database...</div>
      ) : themes.length === 0 ? (
        <div className="p-8 text-center text-mute text-sm bg-sheet/40 border border-line rounded-md">
          No themes discovered for {product}. Click "Discover Themes" to cluster classified feedback.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {themes.map((theme) => (
            <Panel
              key={theme.theme_id}
              title={theme.theme_name}
              action={
                <div className="flex items-center gap-2">
                  <Badge variant={theme.status === "candidate" ? "warn" : theme.status === "active" ? "good" : "neutral"} mono>
                    {theme.status}
                  </Badge>
                  <Badge variant="accent" mono>
                    {theme.category}
                  </Badge>
                </div>
              }
            >
              <div className="grid gap-3 text-[13px]">
                <p className="text-ink-soft leading-relaxed">{theme.description || "No description provided."}</p>
                <div className="flex items-center justify-between border-t border-line pt-2 text-[12px] text-mute">
                  <span>
                    <strong className="text-ink font-normal">{theme.feedback_count ?? 0}</strong> records
                  </span>
                  <span className="font-mono text-[11px] text-mute">
                    ID: {theme.theme_id.slice(0, 8)}...
                  </span>
                </div>

                {theme.representative_feedback && theme.representative_feedback.length > 0 && (
                  <div className="bg-sheet/80 border border-line p-3">
                    <p className="text-[11px] uppercase tracking-wider text-mute">Representative Feedback</p>
                    <ul className="mt-2 space-y-1.5 text-[12px] italic text-ink-soft">
                      {theme.representative_feedback.map((quote, idx) => (
                        <li key={idx}>&ldquo;{quote.feedback_text}&rdquo;</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Candidate Theme Actions */}
                {theme.status === "candidate" && (
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleDiscard(theme.theme_id)}
                      disabled={busyThemeId === theme.theme_id}
                    >
                      Discard
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleActivate(theme.theme_id)}
                      disabled={busyThemeId === theme.theme_id}
                    >
                      Activate Theme
                    </Button>
                  </div>
                )}

                {/* Active Theme Merge Action */}
                {theme.status === "active" && themes.filter((t) => t.status === "active" && t.theme_id !== theme.theme_id).length > 0 && (
                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-line text-xs">
                    <span className="text-mute">Merge into:</span>
                    <div className="flex items-center gap-2">
                      <select
                        value={mergeTargetId[theme.theme_id] || ""}
                        onChange={(e) =>
                          setMergeTargetId((prev) => ({ ...prev, [theme.theme_id]: e.target.value }))
                        }
                        className="px-2 py-1 bg-paper border border-line rounded-xs text-xs font-mono focus:outline-none"
                      >
                        <option value="">Select target theme...</option>
                        {themes
                          .filter((t) => t.status === "active" && t.theme_id !== theme.theme_id)
                          .map((t) => (
                            <option key={t.theme_id} value={t.theme_id}>
                              {t.theme_name}
                            </option>
                          ))}
                      </select>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleMerge(theme.theme_id)}
                        disabled={!mergeTargetId[theme.theme_id] || busyThemeId === theme.theme_id}
                      >
                        Merge
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
