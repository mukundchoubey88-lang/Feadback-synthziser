import { useState } from 'react';
import { MessageSquare } from 'lucide-react';
import Sidebar from './components/Sidebar';
import AgentPanel from './components/AgentPanel';
import GovernanceFooter from './components/GovernanceFooter';
import Overview from './pages/Overview';
import Ingestion from './pages/Ingestion';
import AIProviders from './pages/AIProviders';
import InsightsFeed from './pages/InsightsFeed';
import ReasoningTrace from './pages/ReasoningTrace';
import Analytics from './pages/Analytics';
import MemoryExplorer from './pages/MemoryExplorer';

function App() {
  const [activeView, setActiveView] = useState('overview');
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);

  const renderView = () => {
    switch (activeView) {
      case 'overview':
        return <Overview />;
      case 'ingestion':
        return <Ingestion />;
      case 'providers':
        return <AIProviders />;
      case 'insights':
        return <InsightsFeed />;
      case 'reasoning':
        return <ReasoningTrace />;
      case 'analytics':
        return <Analytics />;
      case 'memory':
        return <MemoryExplorer />;
      default:
        return <Overview />;
    }
  };

  return (
    <div className="h-screen flex bg-dark overflow-hidden">
      {/* Sidebar */}
      <Sidebar activeView={activeView} setActiveView={setActiveView} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto p-8">
            {renderView()}
          </div>
        </main>

        {/* Footer */}
        <GovernanceFooter />
      </div>

      {/* Agent Panel */}
      <AgentPanel isOpen={agentPanelOpen} onClose={() => setAgentPanelOpen(false)} />

      {/* Floating Agent Button (when panel closed) */}
      {!agentPanelOpen && (
        <button
          onClick={() => setAgentPanelOpen(true)}
          className="fixed bottom-8 right-8 w-14 h-14 bg-gradient-to-br from-primary to-purple-500 rounded-2xl flex items-center justify-center shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 z-40"
        >
          <MessageSquare className="w-6 h-6 text-white" />
        </button>
      )}
    </div>
  );
}

export default App;
