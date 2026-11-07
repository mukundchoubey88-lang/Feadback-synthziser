import { 
  LayoutDashboard, 
  Upload, 
  Zap, 
  Lightbulb, 
  GitBranch, 
  BarChart3, 
  Brain,
  Settings
} from 'lucide-react';
import { cn } from '../lib/utils';

const navItems = [
  { icon: LayoutDashboard, label: 'Overview', id: 'overview' },
  { icon: Upload, label: 'Ingestion & Jobs', id: 'ingestion' },
  { icon: Zap, label: 'AI Providers', id: 'providers' },
  { icon: Lightbulb, label: 'Insights Feed', id: 'insights' },
  { icon: GitBranch, label: 'Reasoning Trace', id: 'reasoning' },
  { icon: BarChart3, label: 'Analytics', id: 'analytics' },
  { icon: Brain, label: 'Memory Explorer', id: 'memory' },
];

export default function Sidebar({ activeView, setActiveView }) {
  return (
    <div className="w-64 bg-dark-50 border-r border-dark-300 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-dark-300">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary to-purple-500 rounded-xl flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">Feedback Intel</h1>
            <p className="text-xs text-gray-400">Agent Platform</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200",
                isActive 
                  ? "bg-primary/10 text-primary border border-primary/20" 
                  : "text-gray-400 hover:text-gray-200 hover:bg-dark-100"
              )}
            >
              <Icon className="w-5 h-5" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Settings */}
      <div className="p-4 border-t border-dark-300">
        <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-gray-400 hover:text-gray-200 hover:bg-dark-100 transition-all duration-200">
          <Settings className="w-5 h-5" />
          <span>Settings</span>
        </button>
      </div>
    </div>
  );
}
