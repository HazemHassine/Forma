import { useState, useEffect } from 'react';
import { resumeApi, aiApi } from '../api';
import { useAIProvider, useToast } from '../App';
import { useNavigate } from 'react-router-dom';
import { Target, Sparkles, Check, X, Loader, MessageSquare, Send, ChevronRight, FileText, ArrowRight, ShieldCheck, Save, Clock3 } from 'lucide-react';
import Button from '../components/Button';
import { diffWords } from 'diff';
import './OptimizePage.css';

// --- Diff Helpers ---
function DiffText({ original, optimized }) {
  if (!original && !optimized) return null;
  if (original === optimized) return <span className="diff-unchanged">{original}</span>;

  const parts = diffWords(original || '', optimized || '');
  return (
    <span className="diff-text">
      {parts.map((part, i) => {
        if (part.added) return <span key={i} className="diff-added">{part.value}</span>;
        if (part.removed) return <span key={i} className="diff-removed">{part.value}</span>;
        return <span key={i} className="diff-unchanged">{part.value}</span>;
      })}
    </span>
  );
}

function DiffBullets({ originalBullets, optimizedBullets }) {
  const maxLen = Math.max((originalBullets || []).length, (optimizedBullets || []).length);
  return (
    <ul className="diff-bullets">
      {Array.from({ length: maxLen }, (_, i) => {
        const orig = (originalBullets || [])[i] || '';
        const opt = (optimizedBullets || [])[i] || '';
        if (!orig && opt) return <li key={i} className="diff-bullet-new"><span className="diff-added">{opt}</span></li>;
        if (orig && !opt) return <li key={i} className="diff-bullet-removed"><span className="diff-removed">{orig}</span></li>;
        return <li key={i}><DiffText original={orig} optimized={opt} /></li>;
      })}
    </ul>
  );
}

// --- Sidebar Item Component ---
function DiffSectionCard({
  title, icon, originalContent, optimizedContent, sectionType,
  onReject, onRegenerate
}) {
  const [comment, setComment] = useState('');
  const [showComment, setShowComment] = useState(false);
  const [loading, setLoading] = useState(false);

  const isChanged = JSON.stringify(originalContent) !== JSON.stringify(optimizedContent);
  if (!isChanged) return null;

  const handleRegenerate = async () => {
    if (!comment.trim()) return;
    setLoading(true);
    await onRegenerate(sectionType, optimizedContent, comment);
    setLoading(false);
    setComment('');
    setShowComment(false);
  };

  return (
    <div className="diff-card">
      <div className="diff-card-header">
        <div className="diff-card-title">{icon} {title}</div>
      </div>

      <div className="diff-card-body">
        {typeof originalContent === 'string' ? (
          <DiffText original={originalContent} optimized={optimizedContent} />
        ) : (
          <DiffBullets originalBullets={originalContent} optimizedBullets={optimizedContent} />
        )}
      </div>

      <div className="diff-card-actions">
        <button className="diff-btn reject" onClick={onReject} title="Revert to original">
          <X size={14} /> Revert
        </button>
        <button className="diff-btn comment" onClick={() => setShowComment(!showComment)}>
          <MessageSquare size={14} /> Adjust
        </button>
      </div>

      {showComment && (
        <div className="diff-card-comment-area">
          <textarea
            placeholder="Tell AI what to change... e.g., 'Make it more professional'"
            value={comment}
            onChange={e => setComment(e.target.value)}
            rows={2}
          />
          <button
            className="diff-btn-submit"
            onClick={handleRegenerate}
            disabled={loading || !comment.trim()}
          >
            {loading ? <Loader size={14} className="spin" /> : <Send size={14} />}
          </button>
        </div>
      )}
    </div>
  );
}

// --- Main Page ---
export default function OptimizePage() {
  const addToast = useToast();
  const { aiProvider } = useAIProvider();
  const navigate = useNavigate();

  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState(null);
  const [jobDescription, setJobDescription] = useState('');
  const [targetRole, setTargetRole] = useState('');
  const [company, setCompany] = useState('');
  const [instructions, setInstructions] = useState('');

  // States
  const [loading, setLoading] = useState(false);
  const [draftVersionId, setDraftVersionId] = useState(null);
  const [draftName, setDraftName] = useState('');
  const [processingDraft, setProcessingDraft] = useState(false);
  const [jobDescCache, setJobDescCache] = useState('');
  const [insights, setInsights] = useState(null);

  // Data Tracking
  const [originalData, setOriginalData] = useState(null);
  const [draftData, setDraftData] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // PDF key for forcing iframe reload
  const [pdfKey, setPdfKey] = useState(0);

  useEffect(() => {
    resumeApi.list().then(data => {
      const realVersions = data;
      setVersions(realVersions);
      const current = realVersions.find(v => v.is_current);
      if (current) setSelectedVersionId(current.id);
      else if (realVersions.length > 0) setSelectedVersionId(realVersions[0].id);
    });
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem('activeTailoringDraft');
    if (!saved) return;
    try {
      const session = JSON.parse(saved);
      Promise.all([
        resumeApi.get(session.sourceVersionId),
        resumeApi.get(session.draftVersionId),
      ]).then(([source, draft]) => {
        setSelectedVersionId(session.sourceVersionId);
        setOriginalData(source.data);
        setDraftData(draft.data);
        setDraftVersionId(draft.id);
        setDraftName(session.finalName || draft.name.replace(/^Draft · /, ''));
        setJobDescription(session.jobDescription || '');
        setJobDescCache(session.jobDescription || '');
        addToast('Recovered your autosaved tailoring draft.', 'info');
      }).catch(() => localStorage.removeItem('activeTailoringDraft'));
    } catch {
      localStorage.removeItem('activeTailoringDraft');
    }
  }, [addToast]);

  const handleOptimize = async () => {
    if (!selectedVersionId) return addToast('Select a version', 'warning');
    if (!jobDescription.trim()) return addToast('Paste a job description', 'warning');

    setLoading(true);
    try {
      const data = await aiApi.optimize(aiProvider, selectedVersionId, jobDescription, {
        targetRole,
        company,
        instructions,
      });

      const merged = JSON.parse(JSON.stringify(data.original));
      merged.about_me = data.optimized.about_me;
      data.original.work_experience?.forEach((_, i) => {
        if (data.optimized.work_experience?.[i]) {
          merged.work_experience[i].bullets = data.optimized.work_experience[i].bullets;
        }
      });
      data.original.projects?.forEach((_, i) => {
        if (data.optimized.projects?.[i]) {
          merged.projects[i].description = data.optimized.projects[i].description;
          merged.projects[i].bullets = data.optimized.projects[i].bullets;
        }
      });
      data.original.research?.forEach((_, i) => {
        if (data.optimized.research?.[i]) {
          merged.research[i].description = data.optimized.research[i].description;
        }
      });

      const version = versions.find(v => v.id === selectedVersionId);
      const baseName = version?.name || 'Resume';
      const targetLabel = [targetRole.trim(), company.trim()].filter(Boolean).join(' · ');
      const proposedName = targetLabel || `${baseName} · Tailored`;
      const newDraftName = `Draft · ${proposedName}`;

      const draft = await resumeApi.create({
        name: newDraftName,
        description: `Recoverable tailoring draft based on "${baseName}"${targetLabel ? ` for ${targetLabel}` : ''}.`,
        data: merged,
      });

      setOriginalData(data.original);
      setDraftData(merged);
      setDraftName(proposedName);
      setDraftVersionId(draft.id);
      setJobDescCache(jobDescription);
      setInsights({
        matchSummary: data.match_summary,
        strengths: data.strengths || [],
        gaps: data.gaps || [],
        keywords: data.keywords_used || [],
      });
      localStorage.setItem('activeTailoringDraft', JSON.stringify({
        draftVersionId: draft.id,
        sourceVersionId: selectedVersionId,
        jobDescription,
        finalName: proposedName,
      }));
      addToast('Tailored draft created. Your source version is unchanged.', 'success');
    } catch (err) {
      addToast(err.message || 'Optimization failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const updateDraftOnServer = async (newData) => {
    try {
      await resumeApi.update(draftVersionId, { data: newData });
      setDraftData(newData);
      setPdfKey(prev => prev + 1); // Refresh right iframe
    } catch {
      addToast('Failed to update PDF', 'error');
    }
  };

  // Section-level actions
  const handleRejectSection = (path) => {
    const newData = JSON.parse(JSON.stringify(draftData));
    const [section, index, field] = path.split('.');

    if (section === 'about_me') {
      newData.about_me = originalData.about_me;
    } else if (field) {
      newData[section][index][field] = originalData[section][index][field];
    } else {
      newData[section][index] = originalData[section][index];
    }
    updateDraftOnServer(newData);
  };

  const handleRegenerateSection = async (path, sectionType, currentContent, feedback) => {
    try {
      let contentString = currentContent;
      if (Array.isArray(currentContent)) contentString = currentContent.join('\n');

      const response = await aiApi.suggest(aiProvider, {
        section_type: sectionType,
        current_content: contentString,
        job_description: jobDescCache,
        feedback: feedback
      });

      const newData = JSON.parse(JSON.stringify(draftData));
      const [section, index, field] = path.split('.');

      if (section === 'about_me') {
        newData.about_me = response.suggestion;
      } else if (field === 'bullets' || sectionType === 'work_experience' || sectionType === 'project') {
        newData[section][index].bullets = response.suggestion.split('\n').map(s => s.replace(/^- /, '').trim()).filter(Boolean);
      } else if (field) {
        newData[section][index][field] = response.suggestion;
      }

      await updateDraftOnServer(newData);
      addToast('Section updated!', 'success');
    } catch (err) {
      addToast('Failed to regenerate: ' + err.message, 'error');
    }
  };

  // Global actions
  const handleAcceptAll = async () => {
    setProcessingDraft(true);
    try {
      await resumeApi.update(draftVersionId, { name: draftName });
      localStorage.removeItem('activeTailoringDraft');
      addToast('Saved as a new resume version. Your source is unchanged.', 'success');
      navigate(`/editor/${draftVersionId}`);
    } catch {
      addToast('Failed to accept draft.', 'error');
      setProcessingDraft(false);
    }
  };

  const handleKeepForLater = () => {
    addToast('Draft kept safely in Versions. You can continue it from the editor.', 'info');
    navigate('/versions');
  };

  if (draftVersionId && originalData && draftData) {
    const changesExist = JSON.stringify(originalData) !== JSON.stringify(draftData);

    return (
      <div className="optimize-page comparison-mode">
        {/* Background PDFs */}
        <div className="optimize-split-panes">
          <div className="optimize-pane">
            <div className="optimize-pane-header">
              <span className="pane-label">Original</span>
              <span className="pane-version">{versions.find(v => v.id === selectedVersionId)?.name}</span>
            </div>
            <iframe
              src={`${resumeApi.getPreviewUrl(selectedVersionId)}#toolbar=0&navpanes=0`}
              className="optimize-pdf-iframe"
            />
          </div>
          <div className="optimize-pane draft-pane">
            <div className="optimize-pane-header highlight">
              <span className="pane-label highlight"><Sparkles size={14}/> Optimized Draft</span>
              <span className="pane-version">{draftName}</span>
            </div>
            <iframe
              key={`pdf-${pdfKey}`}
              src={`${resumeApi.getPreviewUrl(draftVersionId)}#toolbar=0&navpanes=0&t=${pdfKey}`}
              className="optimize-pdf-iframe"
            />
          </div>
        </div>

        {/* Floating Sidebar */}
        <div className={`diff-sidebar-container ${sidebarOpen ? 'open' : 'closed'}`}>
          <button className="diff-sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? <ChevronRight size={20} /> : <div className="sidebar-pill"><Sparkles size={14} /> Review Changes</div>}
          </button>

          <div className="diff-sidebar">
            <div className="diff-sidebar-header">
              <div className="review-eyebrow"><ShieldCheck size={14} /> Source protected</div>
              <h3>Review tailored draft</h3>
              <p>Revert or refine any section. Changes auto-save only to this new draft.</p>
              <input
                className="draft-name-input"
                aria-label="New version name"
                value={draftName}
                onChange={e => setDraftName(e.target.value)}
              />
            </div>

            <div className="diff-sidebar-content">
              {insights && (
                <div className="tailoring-brief">
                  <strong>Tailoring brief</strong>
                  {insights.matchSummary && <p>{insights.matchSummary}</p>}
                  {!!insights.strengths.length && <div><span>Strong matches</span><ul>{insights.strengths.map(item => <li key={item}>{item}</li>)}</ul></div>}
                  {!!insights.gaps.length && <div className="gap-list"><span>Gaps kept honest</span><ul>{insights.gaps.map(item => <li key={item}>{item}</li>)}</ul></div>}
                  {!!insights.keywords.length && <div className="keyword-list">{insights.keywords.map(item => <span key={item}>{item}</span>)}</div>}
                </div>
              )}
              {!changesExist && (
                <div className="no-changes-msg">
                  <Check size={24} className="success-icon" />
                  <p>All changes reverted!</p>
                </div>
              )}

              {/* About Me */}
              <DiffSectionCard
                title="About Me"
                icon={<FileText size={16} />}
                originalContent={originalData.about_me}
                optimizedContent={draftData.about_me}
                sectionType="about_me"
                onReject={() => handleRejectSection('about_me')}
                onRegenerate={(type, content, fb) => handleRegenerateSection('about_me', type, content, fb)}
              />

              {/* Work Experience */}
              {draftData.work_experience?.map((exp, i) => (
                <DiffSectionCard
                  key={`we-${i}`}
                  title={`${exp.company} - ${exp.role}`}
                  icon={<ArrowRight size={16} />}
                  originalContent={originalData.work_experience[i]?.bullets}
                  optimizedContent={exp.bullets}
                  sectionType="work_experience"
                  onReject={() => handleRejectSection(`work_experience.${i}.bullets`)}
                  onRegenerate={(type, content, fb) => handleRegenerateSection(`work_experience.${i}.bullets`, type, content, fb)}
                />
              ))}

              {/* Projects */}
              {draftData.projects?.map((proj, i) => (
                <div key={`proj-${i}`}>
                  <DiffSectionCard
                    title={`Project: ${proj.name} (Desc)`}
                    icon={<ArrowRight size={16} />}
                    originalContent={originalData.projects[i]?.description}
                    optimizedContent={proj.description}
                    sectionType="about_me" // trick backend to just rewrite text
                    onReject={() => handleRejectSection(`projects.${i}.description`)}
                    onRegenerate={(type, content, fb) => handleRegenerateSection(`projects.${i}.description`, type, content, fb)}
                  />
                  <DiffSectionCard
                    title={`Project: ${proj.name} (Bullets)`}
                    icon={<ArrowRight size={16} />}
                    originalContent={originalData.projects[i]?.bullets}
                    optimizedContent={proj.bullets}
                    sectionType="project"
                    onReject={() => handleRejectSection(`projects.${i}.bullets`)}
                    onRegenerate={(type, content, fb) => handleRegenerateSection(`projects.${i}.bullets`, type, content, fb)}
                  />
                </div>
              ))}

              {draftData.research?.map((item, i) => (
                <DiffSectionCard
                  key={`research-${i}`}
                  title={`Research: ${item.title}`}
                  icon={<ArrowRight size={16} />}
                  originalContent={originalData.research[i]?.description}
                  optimizedContent={item.description}
                  sectionType="about_me"
                  onReject={() => handleRejectSection(`research.${i}.description`)}
                  onRegenerate={(type, content, fb) => handleRegenerateSection(`research.${i}.description`, type, content, fb)}
                />
              ))}
            </div>

            <div className="diff-sidebar-footer">
              <Button variant="secondary" className="w-full mb-2" onClick={handleKeepForLater} disabled={processingDraft}>
                <Clock3 size={16} /> Keep draft for later
              </Button>
              <Button variant="success" className="w-full" onClick={handleAcceptAll} disabled={processingDraft || !draftName.trim()}>
                {processingDraft ? <Loader size={16} className="spin" /> : <Save size={16} />}
                Save as new version
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Initial Form
  return (
    <div className="optimize-page">
      <div className="optimize-header">
        <div className="optimize-header-text">
          <div className="optimize-kicker"><Sparkles size={14} /> {aiProvider === 'chatgpt' ? 'ChatGPT' : 'Gemini'} tailoring workspace</div>
          <h1><Target size={24} /> Turn a job post into a focused CV</h1>
          <p>Choose a trusted source, add the role context, then review every evidence-backed change before saving a new version.</p>
        </div>
      </div>
      <div className="optimize-input-section">
        <div className="optimize-input-row">
          <div className="optimize-version-select">
            <label>Base Resume Version</label>
            <select value={selectedVersionId || ''} onChange={e => setSelectedVersionId(parseInt(e.target.value))}>
              {versions.map(v => <option key={v.id} value={v.id}>{v.name} {v.is_current ? '(Current)' : ''}</option>)}
            </select>
          </div>
          <div className="optimize-version-select">
            <label>Target role <span>optional</span></label>
            <input value={targetRole} onChange={e => setTargetRole(e.target.value)} placeholder="e.g. AI Software Engineer" />
          </div>
        </div>
        <div className="optimize-input-row">
          <div className="optimize-version-select">
            <label>Company <span>optional</span></label>
            <input value={company} onChange={e => setCompany(e.target.value)} placeholder="e.g. Acme" />
          </div>
          <div className="source-safety-note"><ShieldCheck size={18} /><span><strong>Your source stays untouched.</strong> Tailoring always creates a separate, recoverable draft.</span></div>
        </div>
        <div className="optimize-jd-area">
          <label>Job Description</label>
          <textarea value={jobDescription} onChange={e => setJobDescription(e.target.value)} placeholder="Paste the job description..." rows={10} />
          <div className="jd-meta"><span>{jobDescription.trim() ? `${jobDescription.trim().split(/\s+/).length} words` : 'Paste the complete post for better matching'}</span></div>
        </div>
        <div className="optimize-jd-area">
          <label>What should the AI prioritize? <span>optional</span></label>
          <textarea value={instructions} onChange={e => setInstructions(e.target.value)} placeholder="For example: emphasize backend and RAG work; keep the tone technical and concise." rows={3} />
        </div>
        <Button variant="primary" size="lg" onClick={handleOptimize} disabled={loading || !jobDescription.trim()} className="optimize-btn">
          {loading ? <><Loader size={18} className="spin" /> Mapping evidence to the role...</> : <><Sparkles size={18} /> Create tailored draft</>}
        </Button>
      </div>
    </div>
  );
}
