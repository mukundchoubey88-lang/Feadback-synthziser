import { CheckCircle, Loader, Clock } from 'lucide-react';
import { reasoningSteps } from '../data/mockData';
import { cn } from '../lib/utils';

const getStepIcon = (status) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-5 h-5 text-green-400" />;
    case 'in_progress':
      return <Loader className="w-5 h-5 text-primary animate-spin" />;
    case 'pending':
      return <Clock className="w-5 h-5 text-gray-400" />;
    default:
      return <Clock className="w-5 h-5 text-gray-400" />;
  }
};

const getStepColor = (status) => {
  switch (status) {
    case 'completed':
      return 'border-green-500/30 bg-green-500/5';
    case 'in_progress':
      return 'border-primary/30 bg-primary/5';
    case 'pending':
      return 'border-dark-300';
    default:
      return 'border-dark-300';
  }
};

export default function ReasoningTrace() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white mb-1">Reasoning Trace</h1>
        <p className="text-sm text-gray-400">Step-by-step pipeline execution with timing and details</p>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-white mb-1">Processing Pipeline</h2>
            <p className="text-sm text-gray-400">
              Job: <span className="font-mono text-primary">JOB-1847</span> • 
              File: feedback_nov_batch1.csv
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Loader className="w-4 h-4 text-primary animate-spin" />
            <span className="text-sm text-gray-300">Processing...</span>
          </div>
        </div>

        {/* Steps */}
        <div className="space-y-3">
          {reasoningSteps.map((step, idx) => (
            <div 
              key={step.step}
              className={cn(
                'relative p-5 rounded-xl border-2 transition-all duration-300',
                getStepColor(step.status)
              )}
            >
              {/* Connector Line */}
              {idx < reasoningSteps.length - 1 && (
                <div className="absolute left-7 top-full w-0.5 h-3 bg-dark-300"></div>
              )}

              <div className="flex items-start gap-4">
                {/* Icon */}
                <div className="flex-shrink-0 mt-0.5">
                  {getStepIcon(step.status)}
                </div>

                {/* Content */}
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-gray-500">Step {step.step}</span>
                      <h3 className="text-base font-semibold text-white">{step.name}</h3>
                    </div>
                    {step.duration !== '—' && (
                      <span className="text-sm text-gray-400">{step.duration}</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-300 leading-relaxed">{step.detail}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="mt-6 p-4 bg-dark-200 rounded-xl border border-dark-300">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-gray-400 mb-1">Completed Steps</p>
              <p className="text-xl font-semibold text-green-400">5 / 7</p>
            </div>
            <div>
              <p className="text-gray-400 mb-1">Total Duration</p>
              <p className="text-xl font-semibold text-white">10.1s</p>
            </div>
            <div>
              <p className="text-gray-400 mb-1">Estimated Remaining</p>
              <p className="text-xl font-semibold text-primary">~6s</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
