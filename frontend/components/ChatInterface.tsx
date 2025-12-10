"use client";

import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Stethoscope, Trash2, CheckCircle, AlertCircle, HelpCircle, Users, Calendar, Pill, CreditCard, FileText } from 'lucide-react';

type RichContent = {
  type: 'text' | 'table' | 'success' | 'error' | 'clarification';
  message: string;
  data?: any[];
  table_type?: string;
  count?: number;
  action?: string;
  suggestion?: string;
};

type Message = {
  role: 'user' | 'assistant';
  content: string;
  richContent?: RichContent;
  timestamp: Date;
};

// Parse response to extract rich content
const parseResponse = (content: string): RichContent | null => {
  try {
    const parsed = JSON.parse(content);
    if (parsed.type) {
      return parsed as RichContent;
    }
  } catch {
    // Not JSON, return null
  }
  return null;
};

// Get icon for table type
const getTableIcon = (tableType: string) => {
  switch (tableType) {
    case 'patients': return <Users className="w-4 h-4" />;
    case 'visits': return <Calendar className="w-4 h-4" />;
    case 'prescriptions': return <Pill className="w-4 h-4" />;
    case 'billing': return <CreditCard className="w-4 h-4" />;
    case 'audit': return <FileText className="w-4 h-4" />;
    default: return <FileText className="w-4 h-4" />;
  }
};

// Format column headers
const formatHeader = (key: string) => {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

// Format cell values
const formatCellValue = (key: string, value: any) => {
  if (value === null || value === undefined) return '—';
  if (key === 'amount') return `$${Number(value).toFixed(2)}`;
  if (key === 'status') {
    const colors: Record<string, string> = {
      'Paid': 'bg-emerald-500/20 text-emerald-400',
      'Pending': 'bg-amber-500/20 text-amber-400',
      'Overdue': 'bg-red-500/20 text-red-400',
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs ${colors[value] || 'bg-slate-600'}`}>{value}</span>;
  }
  if (key === 'gender') {
    return <span className={`px-2 py-0.5 rounded-full text-xs ${value === 'Male' ? 'bg-blue-500/20 text-blue-400' : 'bg-pink-500/20 text-pink-400'}`}>{value}</span>;
  }
  return String(value);
};

// Rich Message Component
const RichMessage = ({ content }: { content: RichContent }) => {
  const [expanded, setExpanded] = useState(false);

  if (content.type === 'success') {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-emerald-400">
          <CheckCircle className="w-5 h-5" />
          <span className="font-medium">Success!</span>
        </div>
        <p className="text-slate-300 text-sm">{content.message}</p>
      </div>
    );
  }

  if (content.type === 'error') {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span className="font-medium">Error</span>
        </div>
        <p className="text-slate-300 text-sm">{content.message}</p>
        {content.suggestion && (
          <p className="text-slate-400 text-xs italic">{content.suggestion}</p>
        )}
      </div>
    );
  }

  if (content.type === 'clarification') {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-amber-400">
          <HelpCircle className="w-5 h-5" />
          <span className="font-medium">Need more info</span>
        </div>
        <p className="text-slate-300 text-sm">{content.message}</p>
      </div>
    );
  }

  if (content.type === 'table' && content.data && content.data.length > 0) {
    const displayData = expanded ? content.data : content.data.slice(0, 3);
    const columns = Object.keys(content.data[0]);

    return (
      <div className="space-y-3">
        {/* Summary */}
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-slate-600/50 rounded-lg">
            {getTableIcon(content.table_type || 'data')}
          </div>
          <span className="text-slate-300 text-sm">{content.message}</span>
        </div>

        {/* Count badge */}
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-xs font-medium">
            {content.count} record{content.count !== 1 ? 's' : ''} found
          </span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-600/50">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-700/50">
                {columns.map(col => (
                  <th key={col} className="px-3 py-2 text-left text-slate-400 font-medium">
                    {formatHeader(col)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {displayData.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-700/30">
                  {columns.map(col => (
                    <td key={col} className="px-3 py-2 text-slate-300">
                      {formatCellValue(col, row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Show more button */}
        {content.data.length > 3 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            {expanded ? 'Show less' : `Show ${content.data.length - 3} more...`}
          </button>
        )}
      </div>
    );
  }

  // Default text
  return <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-300">{content.message}</p>;
};

// Generate a unique session ID for this browser session
const getSessionId = () => {
  if (typeof window === 'undefined') return 'default';
  let sessionId = sessionStorage.getItem('chat_session_id');
  if (!sessionId) {
    sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    sessionStorage.setItem('chat_session_id', sessionId);
  }
  return sessionId;
};

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('default');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSessionId(getSessionId());
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { role: 'user', content: input, timestamp: new Date() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage.content, session_id: sessionId }),
      });
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response, timestamp: new Date() }]);
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { role: 'assistant', content: "Error communicating with server.", timestamp: new Date() }]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = async () => {
    try {
      await fetch(`http://localhost:8000/api/chat/clear?session_id=${sessionId}`, {
        method: 'POST',
      });
      setMessages([]);
    } catch (error) {
      console.error('Failed to clear chat:', error);
      setMessages([]);
    }
  };

  const suggestedQueries = [
    "Show all patients",
    "Create a new patient",
    "Show pending bills",
  ];

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="p-5 border-b border-slate-700/50 bg-slate-800/50 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl shadow-lg shadow-emerald-500/20">
              <Stethoscope className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-lg text-white">Medical AI Assistant</h2>
              <p className="text-xs text-slate-400">Powered by Natural Language</p>
            </div>
          </div>
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
              title="Clear conversation"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="p-4 bg-gradient-to-br from-emerald-500/20 to-teal-600/20 rounded-2xl mb-4">
              <Sparkles className="w-10 h-10 text-emerald-400" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Welcome!</h3>
            <p className="text-slate-400 text-sm mb-6 max-w-xs">
              I can help you manage patient records, visits, prescriptions, and billing using natural language.
            </p>
            <div className="space-y-2 w-full max-w-xs">
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Try asking:</p>
              {suggestedQueries.map((query, idx) => (
                <button
                  key={idx}
                  onClick={() => setInput(query)}
                  className="w-full text-left px-4 py-3 bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 rounded-xl text-sm text-slate-300 transition-all hover:border-emerald-500/50 hover:text-emerald-400"
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => {
          const richContent = msg.role === 'assistant' ? parseResponse(msg.content) : null;

          return (
            <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center self-start ${msg.role === 'user'
                ? 'bg-gradient-to-br from-blue-500 to-indigo-600'
                : 'bg-gradient-to-br from-emerald-500 to-teal-600'
                }`}>
                {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
              </div>
              <div className={`rounded-2xl px-4 py-3 ${msg.role === 'user'
                ? 'max-w-[75%] bg-gradient-to-br from-blue-500 to-indigo-600 text-white rounded-tr-sm'
                : 'max-w-[85%] bg-slate-700/50 text-slate-100 border border-slate-600/50 rounded-tl-sm'
                }`}>
                {msg.role === 'assistant' && richContent ? (
                  <RichMessage content={richContent} />
                ) : (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                )}
                <p className={`text-xs mt-2 ${msg.role === 'user' ? 'text-blue-200' : 'text-slate-500'}`}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-slate-700/50 border border-slate-600/50 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
                <span className="text-sm text-slate-400">Processing...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-slate-700/50 bg-slate-800/30 backdrop-blur-sm">
        <div className="flex gap-3 items-center">
          <input
            type="text"
            className="flex-1 bg-slate-700/50 border border-slate-600/50 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition-all"
            placeholder="Type your request..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="p-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-xl hover:from-emerald-600 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
