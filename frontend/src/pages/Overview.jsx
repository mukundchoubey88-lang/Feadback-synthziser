import { Activity, Target, Shield, Zap } from 'lucide-react';
import StatCard from '../components/StatCard';
import { stats, catalogElements } from '../data/mockData';
import { cn } from '../lib/utils';

const getStatusColor = (status) => {
  const colors = {
    active: 'text-green-400 bg-green-500/10 border-green-500/20',
    recurring: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
    emerging: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    declining: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    standby: 'text-gray-400 bg-gray-500/10 border-gray-500/20',
    cooldown: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  };
  return colors[status] || colors.active;
};

const getVisibilityBadge = (visibility) => {
  return visibility === 'Visible to agent' 
    ? 'badge-info' 
    : 'badge bg-dark-300 text-gray-400 border-dark-400';
};

export default function Overview() {
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Feedback Volume"
          value={stats.feedbackVolume.value}
          trend={stats.feedbackVolume.trend}
          sparkline={stats.feedbackVolume.sparkline}
          icon={Activity}
        />
        <StatCard
          title="Avg Quality Score"
          value={stats.qualityScore.value}
          trend={stats.qualityScore.trend}
          sparkline={stats.qualityScore.sparkline}
          suffix="%"
          icon={Target}
        />
        <StatCard
          title="PII Flagged"
          value={stats.piiFlags.value}
          trend={stats.piiFlags.trend}
          sparkline={stats.piiFlags.sparkline}
          suffix="%"
          icon={Shield}
        />
        <StatCard
          title="Active AI Provider"
          value={stats.activeProvider.value}
          trend={stats.activeProvider.trend}
          icon={Zap}
        />
      </div>

      {/* Live Catalog Panel */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-white mb-1">Live System Catalog</h2>
            <p className="text-sm text-gray-400">Real-time view of elements tracked by the agent</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="status-active"></div>
            <span className="text-xs text-gray-400">Synced 2s ago</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-300">
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Type</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Name</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Visibility</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-400 uppercase tracking-wider">Metrics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-300">
              {catalogElements.map((element) => (
                <tr key={element.id} className="hover:bg-dark-200 transition-colors">
                  <td className="py-4 px-4">
                    <span className="text-sm text-gray-400">{element.type}</span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm font-medium text-white">{element.name}</span>
                  </td>
                  <td className="py-4 px-4">
                    <span className={cn('badge', getStatusColor(element.status))}>
                      {element.status}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className={cn('badge', getVisibilityBadge(element.visibility))}>
                      {element.visibility}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="text-sm text-gray-300">
                      {element.records && `${element.records.toLocaleString()} records`}
                      {element.feedback && `${element.feedback.toLocaleString()} feedback`}
                      {element.latency && element.latency}
                      {element.remaining && element.remaining}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
