import { useState } from 'react';
import { Lightbulb, ChevronDown, ChevronUp, ExternalLink, Award } from 'lucide-react';
import { insights } from '../data/mockData';
import { cn } from '../lib/utils';

export default function InsightsFeed() {
  const [expandedId, setExpandedId] = useState(null);

  const getConfidenceColor = (confidence) => {
    if (confidence >= 90) return 'text-green-400 bg-green-500/10 border-green-500/20';
    if (confidence >= 75) return 'text-primary bg-primary/10 border-primary/20';
    return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20';
  };

  const getRecommendationPriority = (text) => {
    if (text.includes('HIGH PRIORITY')) return 'border-red-500/50 bg-red-500/5';
    return 'border-dark-300';
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white mb-1">Insights Feed</h1>
        <p className="text-sm text-gray-400">Evidence-backed recommendations with full citation trails</p>
      </div>

      <div className="space-y-4">
        {insights.map((insight) => {
          const isExpanded = expandedId === insight.id;

          return (
            <div 
              key={insight.id}
              className={cn(
                'card hover:border-primary/30 transition-all duration-300',
                getRecommendationPriority(insight.recommendation)
              )}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <Lightbulb className="w-5 h-5 text-primary flex-shrink-0" />
                    <h3 className="text-lg font-semibold text-white">{insight.title}</h3>
                  </div>
                  <p className="text-sm text-gray-300 leading-relaxed">{insight.summary}</p>
                </div>

                <div className="flex flex-col items-end gap-2 ml-4">
                  <div className={cn('badge', getConfidenceColor(insight.confidence))}>
                    <Award className="w-3 h-3 mr-1 inline" />
                    {insight.confidence}% confidence
                  </div>
                  <span className="text-xs text-gray-500 font-mono">{insight.id}</span>
                </div>
              </div>

              {/* Metadata */}
              <div className="flex items-center gap-4 mb-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">Theme:</span>
                  <span className="badge-info">{insight.theme}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">Period:</span>
                  <span className="text-gray-300">{insight.period}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">Evidence:</span>
                  <span className="text-primary font-medium">{insight.evidenceCount} records</span>
                </div>
              </div>

              {/* Recommendation Box */}
              <div className="p-4 bg-dark-200 rounded-xl border border-dark-300 mb-4">
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-primary text-sm font-semibold">→</span>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-white mb-1">Recommended Action</h4>
                    <p className="text-sm text-gray-300 leading-relaxed">{insight.recommendation}</p>
                  </div>
                </div>
              </div>

              {/* Expand/Collapse */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : insight.id)}
                className="w-full flex items-center justify-center gap-2 py-2 text-sm text-gray-400 hover:text-primary transition-colors"
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    Hide evidence trail
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    Show evidence trail ({insight.citations.length} citations)
                  </>
                )}
              </button>

              {/* Evidence Trail */}
              {isExpanded && (
                <div className="mt-4 pt-4 border-t border-dark-300">
                  <h4 className="text-sm font-medium text-white mb-3">Supporting Evidence</h4>
                  <div className="space-y-2">
                    {insight.citations.map((citation, idx) => (
                      <div 
                        key={citation}
                        className="flex items-center justify-between p-3 bg-dark-200 rounded-lg border border-dark-300 hover:border-primary/30 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono text-gray-500">#{idx + 1}</span>
                          <span className="text-sm font-mono text-primary">{citation}</span>
                        </div>
                        <button className="flex items-center gap-1 text-xs text-gray-400 hover:text-primary transition-colors">
                          View source
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
