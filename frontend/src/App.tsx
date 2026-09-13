import React, { useState, useEffect, useRef } from 'react';
import { api } from './api';
import type { Session, Message } from './api';
import { ArtifactViewer } from './components/ArtifactViewer';
import { Send, PlusCircle, User, Bot, Loader2, Zap } from 'lucide-react';
import './index.css';
import ReactMarkdown from 'react-markdown';

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [provider, setProvider] = useState<'ollama' | 'anthropic'>('ollama');
  const [isLoading, setIsLoading] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (currentSessionId) {
      loadMessages(currentSessionId);
    }
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const loadSessions = async () => {
    const data = await api.getSessions();
    setSessions(data);
    if (data.length > 0 && !currentSessionId) {
      setCurrentSessionId(data[0].id);
    }
  };

  const loadMessages = async (id: string) => {
    const session = await api.getSession(id);
    setMessages(session.messages || []);
    checkForArtifacts(session.messages || []);
  };

  const handleNewChat = async () => {
    const session = await api.createSession();
    setSessions([session, ...sessions]);
    setCurrentSessionId(session.id);
    setMessages([]);
    setActiveArtifact(null);
  };

  const extractArtifact = (text: string) => {
    const artifactMatch = text.match(/<artifact>([\s\S]*?)<\/artifact>/);
    return artifactMatch ? artifactMatch[1] : null;
  };

  const formatText = (text: string) => {
    let formatted = text.replace(/<artifact>[\s\S]*?<\/artifact>/g, '\n\n*(Artifact generated. View on the right pane)*\n\n');
    // Format citations beautifully
    formatted = formatted.replace(/Source: (.*?\.md)/g, '📄 **Source:** `$1`');
    return formatted;
  };

  const checkForArtifacts = (msgs: Message[]) => {
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        const artifact = extractArtifact(msgs[i].content);
        if (artifact) {
          setActiveArtifact(artifact);
          return;
        }
      }
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !currentSessionId) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      created_at: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const tempId = "streaming-" + Date.now();
      const streamingMsg: Message = {
        id: tempId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      };
      
      setMessages(prev => [...prev, streamingMsg]);
      
      const response = await api.sendMessage(currentSessionId, userMsg.content, provider, (chunk) => {
        setMessages(prev => {
          const newMsgs = [...prev];
          const target = newMsgs.find(m => m.id === tempId);
          if (target) {
            target.content += chunk;
          }
          return newMsgs;
        });
      });
      
      setMessages(prev => {
        const newMsgs = [...prev];
        const targetIdx = newMsgs.findIndex(m => m.id === tempId);
        if (targetIdx !== -1) {
          newMsgs[targetIdx] = response;
        }
        return newMsgs;
      });
      
      const artifact = extractArtifact(response.content);
      if (artifact) {
        setActiveArtifact(artifact);
      }
    } catch (error) {
      console.error("Failed to send message", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Zap size={20} color="var(--accent-primary)" /> Lenny Growth
        </h2>
        <button className="new-chat-btn" onClick={handleNewChat}>
          <PlusCircle size={16} /> New Chat
        </button>
        <div className="session-list">
          {sessions.map(s => (
            <div 
              key={s.id} 
              className={`session-item ${currentSessionId === s.id ? 'active' : ''}`}
              onClick={() => setCurrentSessionId(s.id)}
            >
              {s.title}
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat */}
      <div className="main-chat">
        <div className="chat-header">
          <div style={{ fontWeight: 500 }}>Chat Session</div>
          <div className="provider-toggle">
            <button 
              className={`provider-btn ${provider === 'anthropic' ? 'active' : ''}`}
              onClick={() => setProvider('anthropic')}
            >
              Claude 3.5
            </button>
            <button 
              className={`provider-btn ${provider === 'ollama' ? 'active' : ''}`}
              onClick={() => setProvider('ollama')}
            >
              Local (Ollama)
            </button>
          </div>
        </div>
        
        <div className="message-feed">
          {messages.length === 0 && !isLoading && (
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '4rem' }}>
              <h3>Welcome to the Lenny Growth Assistant</h3>
              <p>Ask a question about B2B growth, or ask me to write a "Ship 30 for 30" essay.</p>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className="message">
              <div className={`avatar ${msg.role}`}>
                {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
              </div>
              <div className="message-content markdown-body">
                <ReactMarkdown>{formatText(msg.content)}</ReactMarkdown>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message">
              <div className="avatar assistant">
                <Bot size={20} />
              </div>
              <div className="message-content" style={{ display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>
                <Loader2 size={16} className="animate-spin" style={{ marginRight: '0.5rem' }} />
                Thinking...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <div className="input-container">
            <textarea 
              className="chat-input" 
              placeholder="Message Lenny Assistant..." 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={1}
            />
            <button className="send-btn" onClick={handleSend} disabled={isLoading || !input.trim()}>
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>

      {/* Artifact Pane */}
      {activeArtifact && (
        <ArtifactViewer 
          content={activeArtifact} 
          onClose={() => setActiveArtifact(null)} 
        />
      )}
    </div>
  );
}

export default App;
