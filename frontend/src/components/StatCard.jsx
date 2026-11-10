import { TrendingUp, TrendingDown } from 'lucide-react';
import Plot from 'react-plotly.js';
import { formatNumber, formatTrend } from '../lib/utils';

export default function StatCard({ title, value, trend, sparkline, suffix = '', icon: Icon }) {
  const isPositive = trend > 0;
  
  return (
    <div className="stat-card">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-sm text-gray-400 mb-1">{title}</p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-3xl font-semibold text-white">
              {typeof value === 'number' && !suffix ? formatNumber(value) : value}
              {suffix && <span className="text-lg">{suffix}</span>}
            </h3>
          </div>
        </div>
        {Icon && (
          <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center">
            <Icon className="w-5 h-5 text-primary" />
          </div>
        )}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isPositive ? (
            <TrendingUp className="w-4 h-4 text-green-400" />
          ) : (
            <TrendingDown className="w-4 h-4 text-red-400" />
          )}
          <span className={`text-sm font-medium ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
            {formatTrend(trend)}
          </span>
          <span className="text-xs text-gray-500">vs last period</span>
        </div>

        {sparkline && (
          <div className="w-24 h-12">
            <Plot
              data={[{
                x: sparkline.map((_, i) => i),
                y: sparkline,
                type: 'scatter',
                mode: 'lines',
                line: {
                  color: isPositive ? '#4ADE80' : '#F87171',
                  width: 2,
                },
                fill: 'tozeroy',
                fillcolor: isPositive ? 'rgba(74, 222, 128, 0.1)' : 'rgba(248, 113, 113, 0.1)',
              }]}
              layout={{
                margin: { t: 0, r: 0, b: 0, l: 0 },
                xaxis: { visible: false },
                yaxis: { visible: false },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                showlegend: false,
              }}
              config={{ displayModeBar: false }}
              style={{ width: '100%', height: '100%' }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
