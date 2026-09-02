import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Save, Download, FilePenLine, Palette, Check } from 'lucide-react';
import { resumeApi } from '../api';
import { useToast } from '../App';
import ResumeEditor from '../components/ResumeEditor';
import ResumePreview from '../components/ResumePreview';
import Button from '../components/Button';
import './EditorPage.css';

const EMPTY_RESUME = {
  personal_info: { name: '', title: '', address: '', phone: '', email: '', github: '', linkedin: '', photo_path: '' },
  about_me: '',
  education: [],
  work_experience: [],
  projects: [],
  research: [],
  skills: [],
  certificates: [],
  languages: [],
  references: '',
};

const FALLBACK_TEMPLATES = [
  { id: 'modern', name: 'Modern', description: 'Balanced two-column layout', accent: '#1f4e79' },
  { id: 'classic', name: 'Classic', description: 'Traditional serif styling', accent: '#5b4636' },
  { id: 'minimal', name: 'Minimal', description: 'Clean and understated', accent: '#222222' },
  { id: 'executive', name: 'Executive', description: 'Confident navy and gold', accent: '#13233f' },
  { id: 'creative', name: 'Creative', description: 'Warm editorial character', accent: '#bb4d3e' },
  { id: 'technical', name: 'Technical', description: 'Compact and precise', accent: '#146b52' },
];

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const addToast = useToast();

  const [versions, setVersions] = useState([]);
  const [currentId, setCurrentId] = useState(id || null);
  const [resumeData, setResumeData] = useState(id ? null : EMPTY_RESUME);
  const [resumeName, setResumeName] = useState(id ? '' : 'New Resume');
  const [templateId, setTemplateId] = useState('modern');
  const [templates, setTemplates] = useState(FALLBACK_TEMPLATES);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [loading, setLoading] = useState(Boolean(id));
  const [saveState, setSaveState] = useState('idle'); // idle | saving | saved
  const saveTimerRef = useRef(null);
  const dividerRef = useRef(null);
  const splitRef = useRef(null);
  const [leftWidth, setLeftWidth] = useState(50);

  // Load versions list
  useEffect(() => {
    resumeApi.templates().then(setTemplates).catch(() => {});
  }, []);

  useEffect(() => {
    resumeApi.list().then(data => {
      setVersions(data);
      if (!id && data.length > 0) {
        const current = data.find(v => v.is_current) || data[0];
        setLoading(true);
        setCurrentId(current.id);
      }
    }).catch(err => {
      addToast(err.message || 'Failed to load resume versions', 'error');
      setLoading(false);
    });
  }, [id, addToast]);

  // Load selected resume
  useEffect(() => {
    if (!currentId) return;

    resumeApi.get(currentId).then(data => {
      setResumeData(data.data || EMPTY_RESUME);
      setResumeName(data.name || 'Untitled');
      setTemplateId(data.template_id || 'modern');
      setLoading(false);
    }).catch(err => {
      addToast(err.message || 'Failed to load resume', 'error');
      setResumeData(EMPTY_RESUME);
      setLoading(false);
    });
  }, [currentId, addToast]);

  // Auto-save
  const handleDataChange = useCallback((newData) => {
    setResumeData(newData);
    setSaveState('idle');

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      if (!currentId) return;
      setSaveState('saving');
      try {
        await resumeApi.update(currentId, { data: newData });
        setSaveState('saved');
        setTimeout(() => setSaveState(prev => prev === 'saved' ? 'idle' : prev), 2000);
      } catch (err) {
        setSaveState('idle');
        addToast(err.message || 'Autosave failed. Your changes are still in this browser.', 'error');
      }
    }, 1500);
  }, [currentId, addToast]);

  const handleSave = async () => {
    if (!currentId || !resumeData) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setSaveState('saving');
    try {
      await resumeApi.update(currentId, { data: resumeData });
      setSaveState('saved');
      addToast('Resume saved', 'success');
      setTimeout(() => setSaveState(prev => prev === 'saved' ? 'idle' : prev), 2000);
    } catch (err) {
      addToast(err.message || 'Failed to save', 'error');
      setSaveState('idle');
    }
  };

  const handleVersionChange = (e) => {
    const newId = e.target.value;
    setLoading(true);
    setCurrentId(newId);
    navigate(`/editor/${newId}`);
  };

  const handleDownload = () => {
    if (currentId) {
      window.open(resumeApi.getDownloadUrl(currentId), '_blank');
    }
  };

  const handleTemplateChange = async (nextTemplateId) => {
    if (!currentId || nextTemplateId === templateId) {
      setTemplateOpen(false);
      return;
    }
    const previousTemplateId = templateId;
    setTemplateId(nextTemplateId);
    setTemplateOpen(false);
    setSaveState('saving');
    try {
      await resumeApi.update(currentId, { template_id: nextTemplateId });
      setSaveState('saved');
      addToast(`Template changed to ${templates.find(item => item.id === nextTemplateId)?.name || nextTemplateId}`, 'success');
      setTimeout(() => setSaveState(prev => prev === 'saved' ? 'idle' : prev), 2000);
    } catch (err) {
      setTemplateId(previousTemplateId);
      setSaveState('idle');
      addToast(err.message || 'Failed to change template', 'error');
    }
  };

  // Resizable divider
  const handleDividerMouseDown = (e) => {
    e.preventDefault();
    const startX = e.clientX;
    const container = splitRef.current;
    if (!container) return;
    const containerWidth = container.offsetWidth;
    const startLeft = leftWidth;

    const div = dividerRef.current;
    div?.classList.add('dragging');

    const onMouseMove = (me) => {
      const delta = me.clientX - startX;
      const newPercent = startLeft + (delta / containerWidth) * 100;
      setLeftWidth(Math.max(25, Math.min(75, newPercent)));
    };

    const onMouseUp = () => {
      div?.classList.remove('dragging');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  if (loading) {
    return (
      <div className="editor-page">
        <div className="editor-loading">
          <div className="preview-spinner"></div>
          <span>Loading resume...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="editor-page">
      <div className="editor-topbar">
        <div className="editor-topbar-left">
          <div className="editor-context-icon"><FilePenLine size={17} /></div>
          <div className="editor-context-copy"><span>Editing resume</span><strong>{resumeName}</strong></div>
          <select className="version-selector" value={currentId || ''} onChange={handleVersionChange}>
            {!currentId && <option value="">New Resume</option>}
            {versions.map(v => (
              <option key={v.id} value={v.id}>{v.name}{v.is_current ? ' ★' : ''}</option>
            ))}
          </select>
          <div className={`save-indicator ${saveState}`}>
            <span className="save-dot"></span>
            {saveState === 'saving' && 'Saving...'}
            {saveState === 'saved' && 'Saved'}
            {saveState === 'idle' && ''}
          </div>
        </div>
        <div className="editor-topbar-right">
          <div className="template-picker">
            <Button variant="secondary" size="sm" onClick={() => setTemplateOpen(open => !open)} disabled={!currentId}>
              <Palette size={14} /> {templates.find(item => item.id === templateId)?.name || 'Template'}
            </Button>
            {templateOpen && (
              <div className="template-menu">
                <div className="template-menu-heading">
                  <strong>Choose a template</strong>
                  <span>Your content stays exactly the same.</span>
                </div>
                <div className="template-menu-grid">
                  {templates.map(template => (
                    <button
                      type="button"
                      key={template.id}
                      className={`template-option ${template.id === templateId ? 'selected' : ''}`}
                      onClick={() => handleTemplateChange(template.id)}
                    >
                      <span className="template-swatch" style={{ '--template-accent': template.accent }}>
                        <i></i><i></i><i></i>
                      </span>
                      <span><strong>{template.name}</strong><small>{template.description}</small></span>
                      {template.id === templateId && <Check size={14} />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          <Button variant="secondary" size="sm" onClick={handleSave} disabled={!currentId}>
            <Save size={14} /> Save
          </Button>
          <Button variant="secondary" size="sm" onClick={handleDownload} disabled={!currentId}>
            <Download size={14} /> PDF
          </Button>
        </div>
      </div>

      <div className="editor-split" ref={splitRef}>
        <div className="editor-pane editor-pane-left" style={{ width: `${leftWidth}%` }}>
          <ResumeEditor data={resumeData} onChange={handleDataChange} />
        </div>
        <div className="editor-divider" ref={dividerRef} onMouseDown={handleDividerMouseDown}></div>
        <div className="editor-pane editor-pane-right" style={{ width: `${100 - leftWidth}%` }}>
          <ResumePreview key={`${currentId}-${templateId}`} resumeId={currentId} renderingKey={templateId} />
        </div>
      </div>
    </div>
  );
}
