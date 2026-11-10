import Plot from 'react-plotly.js';
import { themeData, sentimentTrend } from '../data/mockData';

export default function Analytics() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white mb-1">Theme & Sentiment Analytics</h1>
        <p className="text-sm text-gray-400">Visual insights into feedback patterns and trends</p>
      </div>

      {/* Top Themes */}
      <div className="card">
        <h2 className="text-xl font-semibold text-white mb-6">Top Themes by Volume</h2>
        <Plot
          data={[{
            x: themeData.values,
            y: themeData.labels,
            type: 'bar',
            orientation: 'h',
            marker: {
              color: themeData.colors,
              line: {
                color: themeData.colors.map(c => c + '80'),
                width: 1
              }
            },
            text: themeData.values.map(v => v + '%'),
            textposition: 'outside',
            textfont: {
              color: '#F3F4F6',
              size: 12,
              family: 'Inter'
            },
            hovertemplate: '<b>%{y}</b><br>%{x}% of feedback<extra></extra>',
          }]}
          layout={{
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: {
              color: '#9CA3AF',
              family: 'Inter'
            },
            margin: { l: 180, r: 60, t: 20, b: 40 },
            height: 400,
            xaxis: {
              title: 'Percentage of Total Feedback',
              gridcolor: '#2A2C33',
              color: '#9CA3AF'
            },
            yaxis: {
              gridcolor: 'transparent',
              color: '#F3F4F6'
            },
            hoverlabel: {
              bgcolor: '#1A1B21',
              bordercolor: '#7AB1FE',
              font: { color: '#F3F4F6', family: 'Inter' }
            }
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
          useResizeHandler={true}
        />
      </div>

      {/* Sentiment Trend */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-white mb-1">Sentiment Trend Over Time</h2>
            <p className="text-sm text-gray-400">Release marker: Oct 20 (Checkout optimization)</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-400"></div>
              <span className="text-xs text-gray-400">Positive</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-gray-400"></div>
              <span className="text-xs text-gray-400">Neutral</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-400"></div>
              <span className="text-xs text-gray-400">Negative</span>
            </div>
          </div>
        </div>

        <Plot
          data={[
            {
              x: sentimentTrend.dates,
              y: sentimentTrend.positive,
              name: 'Positive',
              type: 'scatter',
              mode: 'lines+markers',
              line: { color: '#4ADE80', width: 3 },
              marker: { size: 8, color: '#4ADE80' },
              fill: 'tonexty',
              fillcolor: 'rgba(74, 222, 128, 0.1)',
            },
            {
              x: sentimentTrend.dates,
              y: sentimentTrend.neutral,
              name: 'Neutral',
              type: 'scatter',
              mode: 'lines+markers',
              line: { color: '#9CA3AF', width: 3 },
              marker: { size: 8, color: '#9CA3AF' },
              fill: 'tonexty',
              fillcolor: 'rgba(156, 163, 175, 0.1)',
            },
            {
              x: sentimentTrend.dates,
              y: sentimentTrend.negative,
              name: 'Negative',
              type: 'scatter',
              mode: 'lines+markers',
              line: { color: '#F87171', width: 3 },
              marker: { size: 8, color: '#F87171' },
              fill: 'tozeroy',
              fillcolor: 'rgba(248, 113, 113, 0.1)',
            }
          ]}
          layout={{
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: {
              color: '#9CA3AF',
              family: 'Inter'
            },
            margin: { l: 60, r: 40, t: 20, b: 60 },
            height: 400,
            xaxis: {
              gridcolor: '#2A2C33',
              color: '#9CA3AF',
            },
            yaxis: {
              title: 'Percentage (%)',
              gridcolor: '#2A2C33',
              color: '#9CA3AF',
              range: [0, 100]
            },
            shapes: [{
              type: 'line',
              x0: 'Oct 22',
              x1: 'Oct 22',
              y0: 0,
              y1: 100,
              line: {
                color: '#7AB1FE',
                width: 2,
                dash: 'dash'
              }
            }],
            annotations: [{
              x: 'Oct 22',
              y: 95,
              text: '← Release v2.4.0',
              showarrow: false,
              xanchor: 'left',
              font: {
                color: '#7AB1FE',
                size: 12
              }
            }],
            legend: {
              orientation: 'h',
              y: -0.2,
              x: 0.5,
              xanchor: 'center',
              font: { color: '#F3F4F6' }
            },
            hoverlabel: {
              bgcolor: '#1A1B21',
              bordercolor: '#7AB1FE',
              font: { color: '#F3F4F6', family: 'Inter' }
            }
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
          useResizeHandler={true}
        />
      </div>
    </div>
  );
}
