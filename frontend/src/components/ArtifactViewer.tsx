import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Code, X } from 'lucide-react';

interface ArtifactViewerProps {
  content: string;
  onClose: () => void;
}

export const ArtifactViewer: React.FC<ArtifactViewerProps> = ({ content, onClose }) => {
  const isHtml = content.trim().startsWith('<') || content.includes('<html>') || content.includes('<!DOCTYPE');
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (isHtml && iframeRef.current) {
      // Sandbox restricts execution of scripts (no allow-scripts), but allows rendering layout.
      const blob = new Blob([content], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      iframeRef.current.src = url;

      return () => URL.revokeObjectURL(url);
    }
  }, [content, isHtml]);

  return (
    <div className="artifact-pane">
      <div className="artifact-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Code size={16} />
          <span>{isHtml ? 'Web Component' : 'Markdown Essay'}</span>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>
          <X size={16} />
        </button>
      </div>
      <div className="artifact-content">
        {isHtml ? (
          <iframe 
            ref={iframeRef} 
            className="artifact-iframe" 
            sandbox="allow-same-origin" // Important: Scripts are NOT allowed
            title="Artifact Preview"
          />
        ) : (
          <div className="markdown-body">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};
