import { AlertTriangle, CheckCircle } from 'lucide-react';
import { qualityBreakdown } from '../data/mockData';

export default function GovernanceFooter() {
  const total = Object.values(qualityBreakdown).reduce((a, b) => a + b, 0);
  
  const systemHealthy = true; // In production, this would come from API

  return (
    <div className="border-t border-dark-300 bg-dark-50">
      {/* Degraded Mode Banner (conditional) */}
      {!systemHealthy && (
        <div className="bg-yellow-500/10 border-b border-yellow-500/20 px-6 py-3">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-yellow-400">Degraded Mode</p>
              <p className="text-xs text-yellow-400/80">Hindsight memory service unavailable. Operating with PostgreSQL only.</p>
            </div>
            <button className="text-xs text-yellow-400 hover:text-yellow-300 font-medium">
              Details →
            </button>
          </div>
        </div>
      )}

      {/* Quality Breakdown */}
      <div className="px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-400" />
              <span className="text-xs text-gray-400">System Status:</span>
              <span className="text-xs font-medium text-green-400">Healthy</span>
            </div>

            <div className="h-4 w-px bg-dark-300"></div>

            <div className="text-xs text-gray-400">
              Quality Distribution:
            </div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-400"></div>
                <span className="text-xs text-gray-300">
                  {qualityBreakdown.excellent.toLocaleString()} excellent
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-primary"></div>
                <span className="text-xs text-gray-300">
                  {qualityBreakdown.good.toLocaleString()} good
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
                <span className="text-xs text-gray-300">
                  {qualityBreakdown.acceptable.toLocaleString()} acceptable
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-400"></div>
                <span className="text-xs text-gray-300">
                  {qualityBreakdown.poor.toLocaleString()} poor
                </span>
              </div>
            </div>
          </div>

          <div className="text-xs text-gray-500">
            Last updated: 2s ago
          </div>
        </div>
      </div>
    </div>
  );
}
