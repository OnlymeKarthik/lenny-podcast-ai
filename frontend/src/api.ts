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

/**
 * Helper to handle HTTP errors consistently.
 * Throws with the server error message or a generic one.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || err.message || detail;
    } catch { /* ignore parse errors */ }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  getSessions: async (): Promise<Session[]> => {
    const res = await fetch(`${API_BASE}/sessions`);
    return handleResponse<Session[]>(res);
  },
  
  createSession: async (title: string = "New Chat"): Promise<Session> => {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    });
    return handleResponse<Session>(res);
  },
  
  getSession: async (id: string): Promise<Session> => {
    const res = await fetch(`${API_BASE}/sessions/${id}`);
    return handleResponse<Session>(res);
  },

  deleteSession: async (id: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/sessions/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Failed to delete session`);
  },
  
  sendMessage: async (
    sessionId: string,
    message: string,
    provider: string,
    onToken?: (chunk: string) => void
  ): Promise<Message> => {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, llm_provider: provider })
    });
    
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        detail = err.detail || err.message || detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    
    if (!res.body) throw new Error("No response body — streaming not supported");
    
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
  },
  
  submitFeedback: async (msgId: string, feedback: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/messages/${msgId}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback })
    });
    if (!res.ok) {
      console.warn("Feedback submission failed:", res.status);
    }
  }
};
