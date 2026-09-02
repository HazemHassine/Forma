import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { aiApi } from '../api';
import Modal from './Modal';
import Button from './Button';
import { useAIProvider, useToast } from '../App';
import './AISuggest.css';

export default function AISuggest({ sectionType, currentContent, onAccept }) {
  const [isOpen, setIsOpen] = useState(false);
  const [jobDescription, setJobDescription] = useState('');
  const [suggestion, setSuggestion] = useState('');
  const [includeContext, setIncludeContext] = useState(true);
  const [loading, setLoading] = useState(false);
  const addToast = useToast();
  const { aiProvider } = useAIProvider();

  const handleOpen = () => {
    setSuggestion('');
    setIsOpen(true);
  };

  const handleGenerate = async () => {
    setLoading(true);
    setSuggestion('');
    try {
      const result = await aiApi.suggest(aiProvider, {
        section_type: sectionType,
        current_content: typeof currentContent === 'string' ? currentContent : JSON.stringify(currentContent),
        job_description: jobDescription || undefined,
        include_context: includeContext,
      });
      setSuggestion(result.suggestion);
    } catch (err) {
      addToast(err.message || 'Failed to get AI suggestion', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = () => {
    onAccept(suggestion);
    setIsOpen(false);
    addToast('AI suggestion applied', 'success');
  };

  return (
    <>
      <button className="ai-suggest-btn" onClick={handleOpen} type="button">
        <Sparkles size={12} className="sparkle" /> AI Suggest
      </button>
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title={`${aiProvider === 'chatgpt' ? 'ChatGPT' : 'Gemini'} suggestion`}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsOpen(false)}>Cancel</Button>
            {suggestion && (
              <Button variant="primary" onClick={handleAccept}>Accept Suggestion</Button>
            )}
          </>
        }
      >
        <div className="ai-modal-content">
          {currentContent && (
            <div className="form-group">
              <label className="form-label">Current Content</label>
              <div className="ai-current-content">
                {typeof currentContent === 'string' ? currentContent : JSON.stringify(currentContent, null, 2)}
              </div>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Job Description (Optional)</label>
            <textarea
              value={jobDescription}
              onChange={e => setJobDescription(e.target.value)}
              placeholder="Paste a job description to tailor the suggestion..."
              rows={3}
            />
          </div>

          <div className="ai-context-vault-option">
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12.5px', color: '#4f46e5', cursor: 'pointer', marginBottom: '14px' }}>
              <input
                type="checkbox"
                checked={includeContext}
                onChange={e => setIncludeContext(e.target.checked)}
                disabled={loading}
                style={{ cursor: 'pointer', accentColor: '#4f46e5' }}
              />
              <Sparkles size={12} />
              <span>Reference Candidate Context Vault</span>
            </label>
          </div>

          {!loading && !suggestion && (
            <Button variant="primary" onClick={handleGenerate}>
              <Sparkles size={14} /> Generate Suggestion
            </Button>
          )}

          {loading && (
            <div className="ai-suggestion-box loading">
              <div className="ai-loading-dots">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}

          {suggestion && (
            <div className="form-group">
              <label className="form-label">Suggestion</label>
              <div className="ai-suggestion-box">{suggestion}</div>
            </div>
          )}
        </div>
      </Modal>
    </>
  );
}
