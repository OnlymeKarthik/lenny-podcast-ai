const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

export const api = {
  getSessions: async (): Promise<Session[]> => {
    const res = await fetch(`${API_BASE}/sessions`);
    return res.json();
  },
  
  createSession: async (title: string = "New Chat"): Promise<Session> => {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });
    return res.json();
  },
  
  getSession: async (id: string): Promise<Session> => {
    const res = await fetch(`${API_BASE}/sessions/${id}`);
    return res.json();
  },
  
  sendMessage: async (sessionId: string, message: string, provider: string): Promise<Message> => {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, llm_provider: provider })
    });
    return res.json();
  }
};
