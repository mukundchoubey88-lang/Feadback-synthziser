import { Zap, Activity, DollarSign, CheckCircle, Clock } from 'lucide-react';
import { providers } from '../data/mockData';
import { cn } from '../lib/utils';

const getRoleColor = (role) => {
  const colors = {
    Primary: 'badge-success',
    Fallback: 'badge-warning',
    Cooldown: 'badge bg-purple-500/10 text-purple-400 border-purple-500/20',
  };
  return colors[role] || 'badge-info';
};

const getStatusDot = (status) => {
  const dots = {
    active: 'status-active',
    standby: 'status-dot bg-gray-400',
    cooldown: 'status-cooldown',
    error: 'status-error',
  };
  return dots[status] || 'status-dot bg-gray-400';
};

export default function AIProviders() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white mb-1">AI Provider Rail</h1>
          <p className="text-sm text-gray-400">Three-tier fallback architecture with circuit breakers</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-dark-100 rounded-xl border border-dark-300">
          <div className="status-active"></div>
          <span className="text-sm text-gray-300">System Healthy</span>
        </div>
      </div>

      {/* Provider Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {providers.map((provider) => (
          <div key={provider.name} className="card hover:border-primary/30 transition-all duration-300">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-xl font-semibold text-white">{provider.name}</h3>
                  <div className={getStatusDot(provider.status)}></div>
                </div>
                <span className={cn('badge', getRoleColor(provider.role))}>
                  {provider.role}
                </span>
              </div>
              <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center">
                <Zap className="w-6 h-6 text-primary" />
              </div>
            </div>

            {/* Metrics */}
            <div className="space-y-4 mt-6">
              {provider.latency !== null && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Latency</span>
                  <span className="text-lg font-semibold text-white">{provider.latency}ms</span>
                </div>
              )}

              {provider.remaining && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Cooldown</span>
                  <span className="text-lg font-semibold text-yellow-400">{provider.remaining}</span>
                </div>
              )}

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Requests</span>
                <span className="text-sm font-medium text-white">{provider.requests.toLocaleString()}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Tokens Used</span>
                <span className="text-sm font-medium text-white">{provider.tokens}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Success Rate</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-green-400">{provider.successRate}%</span>
                  <CheckCircle className="w-4 h-4 text-green-400" />
                </div>
              </div>

              <div className="pt-4 border-t border-dark-300">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Cost per 1M tokens</span>
                  <span className="text-sm font-semibold text-primary">{provider.costPerM}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Circuit Breaker Status */}
      <div className="card">
        <h2 className="text-xl font-semibold text-white mb-4">Circuit Breaker Configuration</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-4 bg-dark-200 rounded-xl border border-dark-300">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
                <Activity className="w-5 h-5 text-green-400" />
              </div>
              <h3 className="text-sm font-medium text-white">Failure Threshold</h3>
            </div>
            <p className="text-2xl font-semibold text-white mb-1">5 errors</p>
            <p className="text-xs text-gray-400">in 60 seconds triggers fallback</p>
          </div>

          <div className="p-4 bg-dark-200 rounded-xl border border-dark-300">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-yellow-500/10 rounded-lg flex items-center justify-center">
                <Clock className="w-5 h-5 text-yellow-400" />
              </div>
              <h3 className="text-sm font-medium text-white">Cooldown Period</h3>
            </div>
            <p className="text-2xl font-semibold text-white mb-1">5 minutes</p>
            <p className="text-xs text-gray-400">before retry attempt</p>
          </div>

          <div className="p-4 bg-dark-200 rounded-xl border border-dark-300">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-sm font-medium text-white">Total Cost (24h)</h3>
            </div>
            <p className="text-2xl font-semibold text-white mb-1">$8.47</p>
            <p className="text-xs text-gray-400">across all providers</p>
          </div>
        </div>
      </div>
    </div>
  );
}
