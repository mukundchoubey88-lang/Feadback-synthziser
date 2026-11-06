import { useState } from 'react';
import { Brain, Search, ExternalLink, Calendar, Tag } from 'lucide-react';
import { memoryEntries } from '../data/mockData';
import { cn } from '../lib/utils';

const getMemoryTypeColor = (type) => {
  const colors = {
    episodic: 'badge bg-blue-500/10 text-blue-400 border-blue-500/20',
    semantic: 'badge bg-purple-500/10 text-purple-400 border-purple-500/20',
    temporal: 'badge bg-green-500/10 text-green-400 border-green-500/20',
  };
  return colors[type] || 'badge-info';
};

export default function MemoryExplorer() {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredMemories = memoryEntries.filter(entry =>
    entry.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
    entry.theme.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white mb-1">Memory Explorer</h1>
        <p className="text-sm text-gray-400">Hindsight long-term memory: episodic, semantic, and temporal knowledge</p>
      </div>

      {/* Search */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search memories by theme, content, or time period..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-4 bg-dark-200 border border-dark-300 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-primary/50 transition-colors"
          />
        </div>
      </div>

      {/* Memory Type Legend */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-gray-400">Memory Types:</span>
        <div className="flex items-center gap-2">
          <span className={getMemoryTypeColor('episodic')}>Episodic</span>
          <span className="text-gray-500 text-xs">— specific events</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={getMemoryTypeColor('semantic')}>Semantic</span>
          <span className="text-gray-500 text-xs">— general knowledge</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={getMemoryTypeColor('temporal')}>Temporal</span>
          <span className="text-gray-500 text-xs">— time-based patterns</span>
        </div>
      </div>

      {/* Memory Entries */}
      <div className="space-y-4">
        {filteredMemories.length === 0 ? (
          <div className="card text-center py-12">
            <Brain className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400">No memories found matching your search.</p>
          </div>
        ) : (
          filteredMemories.map((entry) => (
            <div key={entry.id} className="card hover:border-primary/30 transition-all duration-300">
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Brain className="w-5 h-5 text-primary flex-shrink-0" />
                  <span className={cn(getMemoryTypeColor(entry.type), 'uppercase text-xs')}>
                    {entry.type}
                  </span>
                  <span className="text-xs font-mono text-gray-500">{entry.id}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Calendar className="w-3 h-3" />
                  {entry.timestamp}
                </div>
              </div>

              {/* Content */}
              <p className="text-sm text-gray-300 leading-relaxed mb-4">{entry.content}</p>

              {/* Metadata */}
              <div className="flex items-center justify-between pt-4 border-t border-dark-300">
                <div className="flex items-center gap-2">
                  <Tag className="w-4 h-4 text-gray-400" />
                  <span className="badge-info">{entry.theme}</span>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">
                    {entry.sources.length} source{entry.sources.length !== 1 ? 's' : ''}
                  </span>
                  <button className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors">
                    View sources
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>

              {/* Sources (collapsed) */}
              <div className="mt-4 pt-4 border-t border-dark-300">
                <div className="flex items-center gap-2 flex-wrap">
                  {entry.sources.map((source) => (
                    <span
                      key={source}
                      className="px-2 py-1 bg-dark-200 rounded-lg text-xs font-mono text-gray-400 border border-dark-300"
                    >
                      {source}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Stats */}
      <div className="card">
        <h3 className="text-sm font-medium text-white mb-4">Memory Statistics</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-dark-200 rounded-xl border border-dark-300">
            <p className="text-sm text-gray-400 mb-1">Total Memories</p>
            <p className="text-2xl font-semibold text-white">{memoryEntries.length}</p>
          </div>
          <div className="p-4 bg-dark-200 rounded-xl border border-dark-300">
            <p className="text-sm text-gray-400 mb-1">Unique Themes</p>
            <p className="text-2xl font-semibold text-white">
              {new Set(memoryEntries.map(e => e.theme)).size}
            </p>
          </div>
          <div className="p-4 bg-dark-200 rounded-xl border border-dark-300">
            <p className="text-sm text-gray-400 mb-1">Source References</p>
            <p className="text-2xl font-semibold text-white">
              {memoryEntries.reduce((acc, e) => acc + e.sources.length, 0)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
