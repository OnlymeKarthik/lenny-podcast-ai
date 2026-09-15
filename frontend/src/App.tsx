import React, { useState, useEffect, useRef } from 'react';
import { api } from './api';
import type { Session, Message } from './api';
import { ArtifactViewer } from './components/ArtifactViewer';
import { Send, PlusCircle, User, Bot, Zap, ThumbsUp, ThumbsDown, Trash2 } from 'lucide-react';
import './index.css';
import ReactMarkdown from 'react-markdown';
import { Toaster, toast } from 'sonner';

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [provider, setProvider] = useState<'ollama' | 'anthropic'>('ollama');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(true);
  const [activeArtifact, setActiveArtifact] = useState<string | null>(null);
  const [feedbackMap, setFeedbackMap] = useState<Record<string, number>>({});
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
    try {
      const data = await api.getSessions();
      setSessions(data);
      setIsConnected(true);
      if (data.length > 0 && !currentSessionId) {
        setCurrentSessionId(data[0].id);
      }
    } catch (e) {
      console.error("Failed to load sessions", e);
      setIsConnected(false);
      toast.error("Cannot connect to backend", { description: "Is the server running on port 8000?" });
    }
  };

  const loadMessages = async (id: string) => {
    try {
      const session = await api.getSession(id);
      setMessages(session.messages || []);
      checkForArtifacts(session.messages || []);
    } catch (e) {
      console.error("Failed to load messages", e);
    }
  };

  const handleNewChat = async () => {
    try {
      const session = await api.createSession();
      toast.success("New chat started");
      setSessions([session, ...sessions]);
      setCurrentSessionId(session.id);
      setMessages([]);
      setActiveArtifact(null);
    } catch (e) {
      toast.error("Failed to create session");
    }
  };

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent setting as current session
    if (!window.confirm('Are you sure you want to delete this chat?')) return;
    
    try {
      await api.deleteSession(id);
      setSessions(prev => prev.filter(s => s.id !== id));
      if (currentSessionId === id) {
        setCurrentSessionId(sessions.length > 1 ? sessions.find(s => s.id !== id)?.id || null : null);
        if (sessions.length <= 1) setMessages([]);
      }
      toast.success("Chat deleted");
    } catch (error) {
      toast.error("Failed to delete chat");
    }
  };

  const extractArtifact = (text: string) => {
    const artifactMatch = text.match(/<artifact>([\s\S]*?)<\/artifact>/);
    return artifactMatch ? artifactMatch[1] : null;
  };

  const formatText = (text: string) => {
    // Remove artifact blocks from inline display
    let formatted = text.replace(/<artifact>[\s\S]*?<\/artifact>/g, '\n\n*(Artifact generated — view in the right panel →)*\n\n');
    // Remove suggestion blocks (rendered separately as pills)
    formatted = formatted.replace(/<suggestions>[\s\S]*?<\/suggestions>/g, '');
    return formatted.trim();
  };

  const extractSuggestions = (text: string) => {
    const match = text.match(/<suggestions>([\s\S]*?)<\/suggestions>/);
    if (!match) return [];
    return match[1].split('\n')
      .map(l => l.replace(/^\d+\.\s*/, '').trim())
      .filter(l => l.length > 5);
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

  const handleFeedback = async (msgId: string, val: number) => {
    setFeedbackMap(prev => ({ ...prev, [msgId]: val }));
    try {
      await api.submitFeedback(msgId, val);
      toast.success(val === 1 ? "Thanks for the feedback!" : "We'll improve on this");
    } catch (e) {
      console.error(e);
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
    const currentInput = input;
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
      
      const response = await api.sendMessage(currentSessionId, currentInput, provider, (chunk) => {
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
        toast.success("Artifact generated — view in the right panel");
        setActiveArtifact(artifact);
      }
      
      // If this was the first message, refresh sessions to get the auto-generated title
      if (messages.length === 0) {
        loadSessions();
      }
    } catch (error: any) {
      console.error("Failed to send message", error);
      toast.error("Message failed", { description: error.message || "Could not connect to the backend." });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <Toaster theme="dark" position="top-right" closeButton richColors />
      {/* Sidebar */}
      <aside className="sidebar" aria-label="Chat sessions">
        <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Zap size={20} color="var(--accent-primary)" /> Lenny Growth
        </h2>
        <button className="new-chat-btn" onClick={handleNewChat} aria-label="Start new chat">
          <PlusCircle size={16} /> New Chat
        </button>
        <nav className="session-list" aria-label="Chat history">
          {sessions.map(s => (
            <div 
              key={s.id} 
              className={`session-item ${currentSessionId === s.id ? 'active' : ''}`}
              onClick={() => setCurrentSessionId(s.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && setCurrentSessionId(s.id)}
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.title}</span>
              <button 
                onClick={(e) => handleDeleteSession(s.id, e)}
                className="delete-session-btn"
                aria-label="Delete chat"
                title="Delete chat"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </nav>
      </aside>

      {/* Main Chat */}
      <main className="main-chat">
        <header className="chat-header">
          <div style={{ fontWeight: 500 }}>Chat Session</div>
          <div className="provider-toggle" role="radiogroup" aria-label="LLM Provider">
            <button 
              className={`provider-btn ${provider === 'anthropic' ? 'active' : ''}`}
              onClick={() => { setProvider('anthropic'); toast.info("Switched to Anthropic Claude"); }}
              role="radio"
              aria-checked={provider === 'anthropic'}
            >
              Anthropic Claude
            </button>
            <button 
              className={`provider-btn ${provider === 'ollama' ? 'active' : ''}`}
              onClick={() => { setProvider('ollama'); toast.info("Switched to Local (Ollama)"); }}
              role="radio"
              aria-checked={provider === 'ollama'}
            >
              Local (Ollama)
            </button>
          </div>
        </header>
        
        <div className="message-feed" role="log" aria-label="Chat messages">
          {!isConnected && (
            <div style={{ textAlign: 'center', marginTop: '3rem', padding: '2rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <Zap size={32} color="#ef4444" style={{ marginBottom: '1rem' }} />
              <h2 style={{ color: '#ef4444', marginBottom: '0.5rem' }}>Backend Disconnected</h2>
              <p style={{ color: 'var(--text-secondary)' }}>We couldn't reach the API server at port 8000. If you just started Docker, it may take a moment for the database and backend to initialize.</p>
              <button 
                onClick={loadSessions} 
                style={{ marginTop: '1.5rem', background: 'var(--accent-primary)', color: 'white', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer' }}
              >
                Try Again
              </button>
            </div>
          )}

          {isConnected && messages.length === 0 && !isLoading && (
            <div className="welcome-screen" style={{ textAlign: 'center', marginTop: '3rem' }}>
              <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: '2.5rem', marginBottom: '1rem', background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Lenny Growth Assistant</h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem', marginBottom: '3rem' }}>Ask a question about B2B growth, or ask me to write a "Ship 30 for 30" essay.</p>
              
              <div className="starter-prompts">
                {[
                  "What are the most common mistakes founders make when trying to find product-market fit?",
                  "Write a Ship 30 for 30 essay on how to build a growth team from scratch.",
                  "According to the podcast, what is the best way to reduce churn in early-stage SaaS?",
                  "How did Airbnb approach their early growth strategy?"
                ].map((prompt, i) => (
                  <button 
                    key={i} 
                    className="starter-prompt-card"
                    onClick={() => setInput(prompt)}
                    aria-label={`Starter prompt: ${prompt.substring(0, 50)}...`}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className="message">
              <div className={`avatar ${msg.role}`} aria-hidden="true">
                {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
              </div>
              {msg.content === '' && msg.id && msg.id.startsWith("streaming-") ? (
                <div className="message-content">
                  <div className="typing-indicator" aria-label="Assistant is typing">
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                  </div>
                </div>
              ) : (
                <div className="message-content markdown-body">
                  <ReactMarkdown>{formatText(msg.content)}</ReactMarkdown>
                  {/* Feedback buttons */}
                  {msg.role === 'assistant' && msg.id && !msg.id.startsWith("temp-") && !msg.id.startsWith("streaming-") && (
                    <div className="feedback-container" style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                      <button 
                        onClick={() => handleFeedback(msg.id, 1)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: feedbackMap[msg.id] === 1 ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
                        title="Good response"
                        aria-label="Thumbs up"
                      >
                        <ThumbsUp size={16} />
                      </button>
                      <button 
                        onClick={() => handleFeedback(msg.id, -1)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: feedbackMap[msg.id] === -1 ? '#ef4444' : 'var(--text-secondary)' }}
                        title="Bad response"
                        aria-label="Thumbs down"
                      >
                        <ThumbsDown size={16} />
                      </button>
                    </div>
                  )}
                  {/* Follow-up suggestion pills */}
                  {msg.role === 'assistant' && extractSuggestions(msg.content).length > 0 && !msg.id.startsWith("streaming-") && (
                    <div className="suggestions-container" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '16px' }}>
                      {extractSuggestions(msg.content).map((q, i) => (
                        <button 
                          key={i}
                          onClick={() => setInput(q)}
                          className="suggestion-pill"
                          style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '16px', padding: '6px 12px', fontSize: '0.85rem', cursor: 'pointer', transition: 'all 0.2s' }}
                          onMouseOver={(e) => e.currentTarget.style.borderColor = 'var(--accent-primary)'}
                          onMouseOut={(e) => e.currentTarget.style.borderColor = 'var(--border-color)'}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
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
              aria-label="Chat message input"
              autoFocus
            />
            <button 
              className="send-btn" 
              onClick={handleSend} 
              disabled={isLoading || !input.trim()}
              aria-label="Send message"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </main>

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
