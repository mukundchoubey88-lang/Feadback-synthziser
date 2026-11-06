import { useState } from 'react';
import { X, Send, MessageSquare, ExternalLink, ChevronRight } from 'lucide-react';

const mockConversation = [
  {
    role: 'user',
    content: 'Have customers complained about checkout before?'
  },
  {
    role: 'agent',
    content: 'Yes. Historical memory shows recurring checkout performance concerns dating back to Sept 2026. Key findings:\n\n• 1,847 feedback records mentioned slow checkout (Sept-Oct)\n• Average completion time: 8.2s vs. target 3s\n• Primarily affecting mobile users during peak traffic\n• Oct 20 optimization release reduced complaints by 34.2%\n\nThe theme has shifted from "recurring" to "declining" status following the v2.4.0 release.',
    sources: ['MEM-EP-847', 'MEM-TEM-234', 'FB-7234', 'FB-8534']
  }
];

export default function AgentPanel({ isOpen, onClose }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState(mockConversation);

  const handleSend = () => {
    if (!input.trim()) return;
    
    setMessages([...messages, { role: 'user', content: input }]);
    setInput('');
    
    // Simulate agent response
    setTimeout(() => {
      setMessages(prev => [...prev, {
        role: 'agent',
        content: 'This is a simulated response. In production, this would query the Hindsight memory layer and cite real feedback records.',
        sources: ['FB-9001', 'MEM-SEM-423']
      }]);
    }, 1000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 h-screen w-96 bg-dark-50 border-l border-dark-300 flex flex-col shadow-2xl z-50">
      {/* Header */}
      <div className="p-4 border-b border-dark-300 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary to-purple-500 rounded-xl flex items-center justify-center">
            <MessageSquare className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">Agent Chat</h2>
            <p className="text-xs text-gray-400">Evidence-backed answers</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-dark-200 transition-colors"
        >
          <X className="w-5 h-5 text-gray-400" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, idx) => (
          <div key={idx} className={message.role === 'user' ? 'flex justify-end' : ''}>
            <div className={`max-w-[85%] ${message.role === 'user' ? 'bg-primary text-white' : 'bg-dark-100 text-gray-300'} rounded-2xl p-4`}>
              <p className="text-sm leading-relaxed whitespace-pre-line">{message.content}</p>
              
              {message.sources && (
                <div className="mt-3 pt-3 border-t border-dark-300">
                  <p className="text-xs text-gray-400 mb-2">Sources:</p>
                  <div className="flex flex-wrap gap-2">
                    {message.sources.map((source) => (
                      <button
                        key={source}
                        className="flex items-center gap-1 px-2 py-1 bg-dark-200 rounded-lg text-xs font-mono text-primary hover:bg-dark-300 transition-colors"
                      >
                        {source}
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-dark-300">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about feedback patterns..."
            className="flex-1 px-4 py-3 bg-dark-100 border border-dark-300 rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-primary/50 transition-colors"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="w-10 h-10 bg-primary hover:bg-primary/90 disabled:bg-dark-300 disabled:cursor-not-allowed rounded-xl flex items-center justify-center transition-colors"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
        
        <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
          <span>Suggested:</span>
          <button className="flex items-center gap-1 px-2 py-1 bg-dark-200 rounded-lg hover:bg-dark-300 transition-colors">
            Payment issues
            <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
