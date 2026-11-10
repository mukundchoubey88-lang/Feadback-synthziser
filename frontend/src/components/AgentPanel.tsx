import { useState } from 'react';
import { X, Send, Database, Brain, AlertTriangle, Info } from 'lucide-react';
import { client } from '../lib/api';
import type { HistoricalIntelligenceResult } from '../lib/types';

interface AgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
  defaultProduct?: string;
}

export default function AgentPanel({ isOpen, onClose, defaultProduct = 'Mobile App' }: AgentPanelProps) {
  const [product, setProduct] = useState(defaultProduct);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Array<{
    role: 'user' | 'agent';
    content: string;
    data?: HistoricalIntelligenceResult;
    error?: string;
  }>>([
    {
      role: 'agent',
      content: 'Welcome to the Feedback Intelligence Agent. Ask me questions about customer sentiment, historical themes, or how feedback shifted across product releases.',
    }
  ]);

  const handleSend = async (questionText?: string) => {
    const q = (questionText || input).trim();
    if (!q || loading) return;

    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setInput('');
    setLoading(true);

    try {
      const res = await client.askIntelligence({ product, question: q });
      setMessages(prev => [
        ...prev,
        {
          role: 'agent',
          content: res.answer,
          data: res,
        }
      ]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'agent',
          content: 'Failed to retrieve historical intelligence from the backend.',
          error: err instanceof Error ? err.message : 'Unknown network or service error',
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 h-screen w-[440px] max-w-[95vw] bg-paper text-ink border-l border-line flex flex-col shadow-2xl z-50">
      {/* Header */}
      <div className="p-4 border-b border-line flex items-center justify-between bg-paper-deep/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-ink text-paper rounded-lg flex items-center justify-center font-mono text-sm font-semibold">
            AI
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-medium tracking-tight">Intelligence Agent</h2>
              <span className="text-[10px] font-mono uppercase bg-paper-deep border border-line px-1.5 py-0.5 rounded-xs">
                Part 10
              </span>
            </div>
            <p className="text-[11px] text-mute">SQL ground truth & Hindsight persistent memory</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded-xs hover:bg-paper-deep text-mute hover:text-ink transition-colors"
          title="Close agent panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Product Scoping Selector */}
      <div className="px-4 py-2 border-b border-line bg-sheet/40 flex items-center justify-between gap-2 text-xs">
        <span className="text-mute font-mono uppercase text-[10px] tracking-wider">Scoped Product:</span>
        <input
          type="text"
          value={product}
          onChange={(e) => setProduct(e.target.value)}
          className="px-2 py-1 bg-paper border border-line rounded-xs text-xs font-mono w-40 text-right focus:outline-none focus:border-ink"
          placeholder="Product name"
        />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.map((message, idx) => (
          <div key={idx} className={message.role === 'user' ? 'flex justify-end' : ''}>
            <div
              className={`max-w-[92%] rounded-md p-3.5 leading-relaxed ${
                message.role === 'user'
                  ? 'bg-ink text-paper ml-auto'
                  : 'bg-sheet border border-line text-ink'
              }`}
            >
              <p className="whitespace-pre-line text-[13px]">{message.content}</p>

              {message.error && (
                <div className="mt-2.5 p-2 bg-bad/10 border border-bad/20 rounded-xs text-bad text-[11px] flex items-start gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{message.error}</span>
                </div>
              )}

              {message.data && (
                <div className="mt-3 pt-3 border-t border-line space-y-3">
                  {/* Status Badges */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs text-[10px] font-mono ${
                        message.data.hindsight_available
                          ? 'bg-good/15 text-good border border-good/30'
                          : 'bg-warn/15 text-warn border border-warn/30'
                      }`}
                    >
                      <Brain className="w-3 h-3" />
                      {message.data.hindsight_available ? 'Hindsight Active' : 'Hindsight Offline'}
                    </span>
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs text-[10px] font-mono bg-paper-deep text-ink-soft border border-line">
                      <Database className="w-3 h-3" />
                      PostgreSQL Grounded
                    </span>
                  </div>

                  {/* Key Findings */}
                  {message.data.key_findings && message.data.key_findings.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-mute">Key Findings:</p>
                      <ul className="space-y-1 pl-3 list-disc text-ink-soft text-[12px]">
                        {message.data.key_findings.map((finding, fIdx) => (
                          <li key={fIdx}>{finding}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* SQL Metrics Grid */}
                  {message.data.sql_metrics && (
                    <div className="p-2.5 bg-paper-deep/60 rounded-xs border border-line space-y-1.5">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-mute">Total Volume:</span>
                        <strong className="font-mono text-ink">{message.data.sql_metrics.total_feedback} records</strong>
                      </div>
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-mute">Sentiment Split:</span>
                        <span className="font-mono text-[11px]">
                          <strong className="text-good">{message.data.sql_metrics.positive_percentage}% Pos</strong> ·{' '}
                          <strong className="text-bad">{message.data.sql_metrics.negative_percentage}% Neg</strong>
                        </span>
                      </div>
                      {message.data.sql_metrics.pre_post_comparison && (
                        <div className="pt-1.5 border-t border-line text-[11px] space-y-0.5">
                          <span className="text-mute block text-[10px] uppercase font-mono">
                            Release {message.data.sql_metrics.pre_post_comparison.release_version} Shift:
                          </span>
                          <div className="flex justify-between">
                            <span>Pre-release Negative:</span>
                            <span className="font-mono">{message.data.sql_metrics.pre_post_comparison.pre_release.negative_percentage}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Post-release Negative:</span>
                            <span className="font-mono">{message.data.sql_metrics.pre_post_comparison.post_release.negative_percentage}%</span>
                          </div>
                          {message.data.sql_metrics.pre_post_comparison.delta_negative_percentage !== null && (
                            <div className="flex justify-between font-medium">
                              <span>Delta Shift:</span>
                              <span className={`font-mono ${message.data.sql_metrics.pre_post_comparison.delta_negative_percentage < 0 ? 'text-good' : 'text-bad'}`}>
                                {message.data.sql_metrics.pre_post_comparison.delta_negative_percentage > 0 ? '+' : ''}
                                {message.data.sql_metrics.pre_post_comparison.delta_negative_percentage}%
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Historical Context from Hindsight */}
                  {message.data.historical_context && (
                    <div className="p-2.5 bg-paper rounded-xs border border-line text-[12px] space-y-1">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-mute flex items-center gap-1">
                        <Brain className="w-3 h-3 text-accent" /> Hindsight Trajectory:
                      </p>
                      <p className="text-ink-soft italic leading-relaxed">
                        &ldquo;{message.data.historical_context}&rdquo;
                      </p>
                    </div>
                  )}

                  {/* Supporting Evidence Quotes */}
                  {message.data.evidence?.feedback_quotes && message.data.evidence.feedback_quotes.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-mute">Verifiable Evidence:</p>
                      <div className="space-y-1">
                        {message.data.evidence.feedback_quotes.map((quote) => (
                          <div key={quote.feedback_id} className="p-2 bg-paper rounded-xs border border-line text-[11px]">
                            <div className="flex items-center justify-between text-[10px] text-mute mb-1 font-mono">
                              <span>{quote.feedback_id.slice(0, 8)}...</span>
                              <span className={quote.sentiment === 'negative' ? 'text-bad' : quote.sentiment === 'positive' ? 'text-good' : 'text-ink'}>
                                {quote.sentiment || 'unclassified'}
                              </span>
                            </div>
                            <p className="text-ink-soft leading-normal">&ldquo;{quote.quote}&rdquo;</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Causal Guardrail Limitations */}
                  {message.data.limitations && message.data.limitations.length > 0 && (
                    <div className="p-2 bg-sheet/80 border border-line rounded-xs text-[10px] text-mute space-y-1">
                      <div className="flex items-center gap-1 font-mono uppercase tracking-wider text-ink-soft">
                        <Info className="w-3 h-3" /> Limitations & Guardrails
                      </div>
                      {message.data.limitations.map((limit, lIdx) => (
                        <p key={lIdx} className="leading-tight">{limit}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="bg-sheet border border-line rounded-md p-3.5 max-w-[85%] text-xs text-mute flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent animate-ping" />
            <span>Querying PostgreSQL metrics and recalling Hindsight memories...</span>
          </div>
        )}
      </div>

      {/* Suggested Questions & Input */}
      <div className="p-3.5 border-t border-line bg-paper-deep/30 space-y-2.5">
        <div className="flex items-center gap-1.5 text-[11px] text-mute overflow-x-auto pb-1 scrollbar-none">
          <span className="shrink-0 text-[10px] uppercase font-mono">Try:</span>
          <button
            onClick={() => handleSend("Did checkout complaints improve after our latest release?")}
            className="shrink-0 px-2 py-0.5 bg-paper border border-line rounded-xs hover:border-ink hover:text-ink transition-colors"
          >
            Checkout release impact?
          </button>
          <button
            onClick={() => handleSend("What are the most frequent customer complaints?")}
            className="shrink-0 px-2 py-0.5 bg-paper border border-line rounded-xs hover:border-ink hover:text-ink transition-colors"
          >
            Frequent complaints?
          </button>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={`Ask about ${product} feedback patterns...`}
            disabled={loading}
            className="flex-1 px-3 py-2 bg-paper border border-line rounded-xs text-ink placeholder-mute text-xs focus:outline-none focus:border-ink transition-colors disabled:opacity-50"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="px-3 py-2 bg-ink text-paper hover:bg-ink/90 disabled:opacity-40 disabled:cursor-not-allowed rounded-xs flex items-center justify-center transition-colors text-xs font-medium"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
