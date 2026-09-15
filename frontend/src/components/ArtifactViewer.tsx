import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Code, X, FileText, Globe, Copy, Check } from 'lucide-react';

interface ArtifactViewerProps {
  content: string;
  onClose: () => void;
}

export const ArtifactViewer: React.FC<ArtifactViewerProps> = ({ content, onClose }) => {
  const isHtml = content.trim().startsWith('<') || content.includes('<html>') || content.includes('<!DOCTYPE');
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'preview' | 'source'>('preview');

  useEffect(() => {
    if (isHtml && iframeRef.current && viewMode === 'preview') {
      // Security: Use srcdoc with a fully sandboxed iframe
      // sandbox="" blocks ALL capabilities (scripts, forms, popups, same-origin)
      // This is the strictest possible sandbox — only layout/CSS rendering is allowed.
      const blob = new Blob([content], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      iframeRef.current.src = url;

      return () => URL.revokeObjectURL(url);
    }
  }, [content, isHtml, viewMode]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="artifact-pane">
      <div className="artifact-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {isHtml ? <Globe size={16} /> : <FileText size={16} />}
          <span>{isHtml ? 'HTML Artifact' : 'Markdown Essay'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {isHtml && (
            <div className="provider-toggle" style={{ marginRight: '0.5rem' }}>
              <button 
                className={`provider-btn ${viewMode === 'preview' ? 'active' : ''}`}
                onClick={() => setViewMode('preview')}
                style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}
              >
                Preview
              </button>
              <button 
                className={`provider-btn ${viewMode === 'source' ? 'active' : ''}`}
                onClick={() => setViewMode('source')}
                style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}
              >
                Source
              </button>
            </div>
          )}
          <button 
            onClick={handleCopy}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}
            title="Copy to clipboard"
          >
            {copied ? <Check size={16} color="var(--accent-primary)" /> : <Copy size={16} />}
          </button>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>
      </div>
      <div className="artifact-content">
        {isHtml && viewMode === 'preview' ? (
          <iframe 
            ref={iframeRef} 
            className="artifact-iframe" 
            sandbox=""
            title="Artifact Preview"
            style={{ width: '100%', height: '100%', border: 'none', borderRadius: '8px', background: 'white' }}
          />
        ) : isHtml && viewMode === 'source' ? (
          <pre style={{ 
            background: 'var(--bg-tertiary)', 
            padding: '1rem', 
            borderRadius: '8px', 
            overflow: 'auto',
            fontSize: '0.85rem',
            color: 'var(--text-secondary)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}>
            <code>{content}</code>
          </pre>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>
      {/* Security notice */}
      <div style={{ 
        padding: '0.5rem 1.5rem', 
        borderTop: '1px solid var(--border-color)', 
        fontSize: '0.75rem', 
        color: 'var(--text-secondary)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem'
      }}>
        🔒 {isHtml 
          ? 'Sandboxed iframe: scripts, forms, and same-origin access are blocked.' 
          : 'Rendered as sanitized Markdown.'}
      </div>
    </div>
  );
};
