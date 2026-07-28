import { useState, useCallback } from 'react';
import { RefreshCw, Download, FileText } from 'lucide-react';
import { resumeApi } from '../api';
import Button from './Button';
import './ResumePreview.css';

export default function ResumePreview({ resumeId }) {
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRefresh = useCallback(() => {
    setLoading(true);
    setRefreshKey(k => k + 1);
  }, []);

  const handleLoad = () => {
    setLoading(false);
  };

  const handleDownload = () => {
    window.open(resumeApi.getDownloadUrl(resumeId), '_blank');
  };

  if (!resumeId) {
    return (
      <div className="preview-container">
        <div className="preview-toolbar">
          <span className="preview-toolbar-title">Preview</span>
        </div>
        <div className="preview-frame-wrapper">
          <div className="preview-empty">
            <div className="preview-empty-icon"><FileText size={40} /></div>
            <div className="preview-empty-text">Save your resume to see a preview</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="preview-container">
      <div className="preview-toolbar">
        <span className="preview-toolbar-title">Preview</span>
        <div className="preview-toolbar-actions">
          <Button variant="ghost" size="sm" onClick={handleRefresh}><RefreshCw size={14} /> Refresh</Button>
          <Button variant="secondary" size="sm" onClick={handleDownload}><Download size={14} /> Download</Button>
        </div>
      </div>
      <div className="preview-frame-wrapper">
        {loading && (
          <div className="preview-loading">
            <div className="preview-spinner"></div>
            <span className="preview-loading-text">Rendering PDF...</span>
          </div>
        )}
        <iframe
          key={refreshKey}
          className="preview-iframe"
          src={`${resumeApi.getPreviewUrl(resumeId)}?t=${refreshKey}`}
          onLoad={handleLoad}
          title="Resume Preview"
          style={{ opacity: loading ? 0 : 1, transition: 'opacity 0.3s' }}
        />
      </div>
    </div>
  );
}
