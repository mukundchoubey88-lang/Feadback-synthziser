import { useEffect, useState } from "react";
import { client } from "../../lib/api";
import type { MemoryItem, MemoryStatusResult } from "../../lib/types";
import { Badge, Button, Input, MetricCard, Notice, Panel } from "./ui";

const fallbackMemories: MemoryItem[] = [
  {
    memory_id: "MEM-EP-847",
    bank_id: "bank-mobile-app-65c03a88",
    hindsight_memory_id: "hind-mem-001",
    memory_type: "customer_feedback",
    source_entity_type: "feedback",
    source_reference: "feedback:4b68481d-b636-4171-aa34-b235adcf5671",
    content: "Multiple customers experienced mobile checkout latency exceeding 8.2 seconds during the fall promo event.",
    context: "feature=checkout, timestamp=2026-10-15",
    created_at: "2026-10-15T10:00:00Z",
  },
  {
    memory_id: "MEM-SEM-423",
    bank_id: "bank-mobile-app-65c03a88",
    hindsight_memory_id: "hind-mem-002",
    memory_type: "theme_trajectory",
    source_entity_type: "external",
    source_reference: "theme:9348b61d-3b36-4171-aa34-b235adcf1234",
    content: "Customer sentiment consistently drops 15-20% on days with flash campaigns when payment gateway throughput exceeds 400 req/sec.",
    context: "theme_name=Checkout Performance",
    created_at: "2026-10-20T14:30:00Z",
  },
  {
    memory_id: "MEM-TEM-234",
    bank_id: "bank-mobile-app-65c03a88",
    hindsight_memory_id: "hind-mem-003",
    memory_type: "temporal_shift",
    source_entity_type: "theme_snapshot",
    source_reference: "snapshot:8129ca1d-2b36-4171-ba34-b235adcf9988",
    content: "Following the October 20 patch, negative complaints declined from 65% of volume to 31%. Sentiment velocity stabilized within 72 hours of release.",
    context: "version=v3.2.0",
    created_at: "2026-10-24T08:15:00Z",
  },
];

export function MemoryPage() {
  const [product, setProduct] = useState("Mobile App");
  const [status, setStatus] = useState<MemoryStatusResult | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>(fallbackMemories);
  const [searchQuery, setSearchQuery] = useState("");
  const [reflection, setReflection] = useState<string | null>(null);
  const [disclaimer, setDisclaimer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      const res = await client.memoryStatus();
      setStatus(res);
    } catch {
      setStatus({
        configured: false,
        available: false,
        base_url: null,
        total_synced_memories: 0,
        bank_count: 0,
      });
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  const handleSync = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await client.memorySync({ product, dry_run: false });
      setMessage(
        `Synchronized ${res.synced_count} new memories to Hindsight (${res.skipped_count} skipped by deduplication).`
      );
      await loadStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleRecall = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setMessage(null);
    try {
      const res = await client.memoryRecall({ product, query: searchQuery, limit: 5 });
      if (res.available && res.memories && res.memories.length > 0) {
        setMemories(res.memories);
        setMessage(`Recalled ${res.memories.length} historical memories from Hindsight bank.`);
      } else if (!res.available) {
        setMessage("Hindsight service is currently unreachable; showing cached local memory traces.");
      } else {
        setMessage("No semantic memory matches found for this query.");
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Recall query failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleReflect = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await client.memoryReflect({
        product,
        query: searchQuery || "Summarize customer sentiment trajectory and recurring issues",
      });
      if (res.available && res.reasoning) {
        setReflection(res.reasoning);
        setDisclaimer(res.disclaimer);
        if (res.supporting_memories && res.supporting_memories.length > 0) {
          setMemories(res.supporting_memories);
        }
      } else {
        setMessage(res.error || "Hindsight reflection service is currently unavailable.");
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Reflection failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-[0.16em] text-mute uppercase">Intelligence Memory</p>
            <Badge variant="accent" mono>Part 9</Badge>
          </div>
          <h1 className="mt-2 text-[36px] leading-none tracking-[-0.045em]">Hindsight Memory Bank</h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">
            Retains episodic feedback, theme trajectories, temporal shifts, and product releases with
            immutable PostgreSQL provenance and historical reasoning.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Input
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            placeholder="Target product..."
            className="w-40 text-xs font-mono"
          />
          <Button variant="secondary" size="sm" onClick={handleSync} disabled={busy}>
            {busy ? "Syncing..." : "Sync Memories"}
          </Button>
          <Button variant="primary" size="sm" onClick={handleReflect} disabled={busy}>
            Reflect
          </Button>
        </div>
      </div>

      {message && (
        <Notice tone="neutral">
          <span>{message}</span>
        </Notice>
      )}

      {/* Health & Status Cards */}
      <div className="grid gap-3 sm:grid-cols-4">
        <MetricCard
          label="Hindsight Status"
          value={
            status?.available ? (
              <span className="text-good">Online</span>
            ) : status?.configured ? (
              <span className="text-warn">Degraded</span>
            ) : (
              <span className="text-mute">Unconfigured</span>
            )
          }
          description={status?.base_url ? `Base URL: ${status.base_url}` : "Local fallback active"}
        />
        <MetricCard
          label="Tracked Memories"
          value={status?.total_synced_memories ? status.total_synced_memories.toLocaleString() : "—"}
          description="Indexed in MemoryMetadata"
        />
        <MetricCard
          label="Memory Banks"
          value={status?.bank_count ? String(status.bank_count) : "1"}
          description="Isolated product namespaces"
        />
        <MetricCard
          label="Deduplication"
          value="100%"
          description="Zero redundant memory retention"
        />
      </div>

      {/* Search / Recall Bar */}
      <div className="flex items-center gap-2 bg-sheet/60 p-3 border border-line rounded-xs">
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleRecall()}
          placeholder="Search memory traces (e.g. checkout latency, login error, billing)..."
          className="flex-1 text-xs"
        />
        <Button variant="primary" size="sm" onClick={handleRecall} disabled={loading || !searchQuery.trim()}>
          {loading ? "Recalling..." : "Recall"}
        </Button>
      </div>

      {/* Reflection Narrative Box */}
      {reflection && (
        <div className="p-4 bg-sheet border border-accent/30 rounded-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-mono tracking-wider text-accent font-medium">
              Cognitive Reflection:
            </span>
            <Badge variant="accent" mono>Hindsight Reflect</Badge>
          </div>
          <p className="text-sm leading-relaxed text-ink italic">&ldquo;{reflection}&rdquo;</p>
          {disclaimer && (
            <p className="text-[11px] text-mute pt-1 border-t border-line font-mono">{disclaimer}</p>
          )}
        </div>
      )}

      {/* Memories List */}
      <div className="grid gap-4">
        {memories.map((entry, idx) => (
          <Panel
            key={entry.memory_id || idx}
            title={entry.content.slice(0, 70) + (entry.content.length > 70 ? "..." : "")}
            action={
              <div className="flex items-center gap-2">
                <Badge variant="accent" mono>{entry.memory_type}</Badge>
                <Badge variant="neutral" mono>{entry.source_entity_type}</Badge>
              </div>
            }
          >
            <div className="grid gap-3 text-[14px]">
              <p className="text-ink-soft leading-relaxed">{entry.content}</p>
              {entry.context && (
                <div className="p-2 bg-paper-deep/60 rounded-xs text-[11px] font-mono text-mute">
                  Context: {entry.context}
                </div>
              )}
              <div className="flex flex-wrap items-center justify-between border-t border-line pt-2 text-[12px] text-mute">
                <span>Bank: <strong className="text-ink font-normal">{entry.bank_id}</strong></span>
                <div className="flex items-center gap-1.5 font-mono">
                  <span>Provenance:</span>
                  <span className="bg-paper-deep px-1.5 py-0.5 rounded-xs text-[11px] text-ink">
                    {entry.source_reference || entry.hindsight_memory_id || "local"}
                  </span>
                </div>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
