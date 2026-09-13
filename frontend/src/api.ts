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
  
  sendMessage: async (sessionId: string, message: string, provider: string, onToken?: (chunk: string) => void): Promise<Message> => {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, llm_provider: provider })
    });
    
    if (!res.body) throw new Error("No response body");
    
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = "";
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      fullText += chunk;
      if (onToken) onToken(chunk);
    }
    
    return {
      id: "temp-" + Date.now(),
      role: 'assistant',
      content: fullText,
      created_at: new Date().toISOString()
    };
  }
};
