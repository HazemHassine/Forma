import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Check, ChevronDown, Clipboard, Download,
  ExternalLink, FileSearch, FileText, HelpCircle, Lightbulb,
  Link2, ListChecks, Loader, Mail, MessageSquare, Plus, Save, Search,
  ShieldCheck, Sparkles, Target, Trash2,
} from 'lucide-react';
import { coverLetterApi, resumeApi } from '../api';
import { useToast } from '../App';
import Button from '../components/Button';
import Modal from '../components/Modal';
import './CoverLettersPage.css';

const EMPTY_FORM = {
  resume_version_id: '',
  company: '',
  position: '',
  source_url: '',
  job_post: '',
  instructions: '',
};

const WORKFLOW_STEPS = [
  { number: 1, label: 'Job details' },
  { number: 2, label: 'Analysis' },
  { number: 3, label: 'Research & clarify' },
  { number: 4, label: 'Draft' },
];

const PROGRESS_PHASES = [
  {
    id: 'analyzing',
    label: 'Analyze the role and resume',
    detail: 'Extracting requirements and matching only verified resume evidence.',
  },
  {
    id: 'researching',
    label: 'Research the company',
    detail: 'Looking for useful, attributable context from public sources.',
  },
  {
    id: 'drafting',
    label: 'Write the evidence-backed draft',
    detail: 'Using the approved strategy, research, and your answers.',
  },
];

function safeExternalUrl(url) {
  return /^https?:\/\//i.test(url || '') ? url : null;
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function findAngle(analysis, angleId) {
  const angles = asArray(analysis?.angles);
  if (angleId === null || angleId === undefined) return null;
  return angles.find(angle => String(angle.id) === String(angleId)) || null;
}

function StructuredAnalysisRecord({ analysis, compact = false }) {
  if (!analysis) return null;

  return (
    <details className={`cover-analysis-json ${compact ? 'compact' : ''}`}>
      <summary>
        <span>
          <strong>Complete structured analysis</strong>
          <small>All analysis fields used as the public decision record</small>
        </span>
        <ChevronDown size={16} />
      </summary>
      <pre>{JSON.stringify(analysis, null, 2)}</pre>
    </details>
  );
}

function WorkflowStepper({ currentStep }) {
  return (
    <ol className="cover-wizard-steps" aria-label="Cover letter creation progress">
      {WORKFLOW_STEPS.map(step => {
        const isComplete = step.number < currentStep;
        const isActive = step.number === currentStep;
        return (
          <li
            className={`cover-wizard-step ${isComplete ? 'complete' : ''} ${isActive ? 'active' : ''}`}
            key={step.number}
            aria-current={isActive ? 'step' : undefined}
          >
            <span className="cover-step-number">{isComplete ? <Check size={13} /> : step.number}</span>
            <span>{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function WorkflowProgress({ phase }) {
  const currentIndex = PROGRESS_PHASES.findIndex(item => item.id === phase);
  return (
    <div className="cover-workflow-progress" aria-live="polite">
      <div className="cover-progress-hero">
        <div className="cover-progress-spinner"><Loader size={24} className="spin" /></div>
        <div>
          <span>Working in clear stages</span>
          <h3>{PROGRESS_PHASES[currentIndex]?.label || 'Preparing your draft'}</h3>
          <p>{PROGRESS_PHASES[currentIndex]?.detail}</p>
        </div>
      </div>
      <div className="cover-progress-list">
        {PROGRESS_PHASES.map((item, index) => {
          const status = index < currentIndex ? 'complete' : index === currentIndex ? 'active' : 'queued';
          return (
            <div className={`cover-progress-item ${status}`} key={item.id}>
              <span className="cover-progress-status">
                {status === 'complete' ? <Check size={14} /> : status === 'active' ? <Loader size={14} className="spin" /> : index + 1}
              </span>
              <div>
                <strong>{item.label}</strong>
                <small>{status === 'complete' ? 'Completed' : status === 'active' ? 'In progress' : 'Up next'}</small>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DraftDecisionSummary({ context }) {
  if (!context) return null;

  const analysis = context.analysis || {};
  const research = context.research || {};
  const evidence = asArray(analysis.evidence_matches);
  const gaps = asArray(analysis.gaps);
  const observations = asArray(analysis.observations);
  const paragraphPlan = asArray(analysis.paragraph_plan);
  const excludedClaims = asArray(analysis.excluded_claims);
  const insights = asArray(research.insights);
  const sources = asArray(research.sources);
  const selectedAngle = findAngle(
    analysis,
    context.selected_angle_id ?? analysis.recommended_angle_id,
  );
  const answers = Array.isArray(context.answers)
    ? context.answers.filter(item => item.answer?.trim())
    : [];

  return (
    <details className="cover-decision-panel">
      <summary>
        <span className="cover-decision-summary-icon"><Lightbulb size={15} /></span>
        <span>
          <strong>How this draft was built</strong>
          <small>Decision summary and supporting evidence</small>
        </span>
        <ChevronDown className="cover-decision-chevron" size={17} />
      </summary>
      <div className="cover-decision-body">
        <p className="cover-decision-explainer">
          This public decision record shows the structured analysis, evidence, choices, and context used in the letter. It does not expose hidden chain-of-thought.
        </p>
        <section className="cover-decision-angle">
          <h3><Sparkles size={14} /> Selected letter angle</h3>
          {selectedAngle ? (
            <>
            <strong>{selectedAngle.title}</strong>
            <p>{selectedAngle.approach}</p>
            {!!asArray(selectedAngle.supporting_evidence).length && (
              <ul>
                {selectedAngle.supporting_evidence.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            )}
            {selectedAngle.caution && <small>Caution: {selectedAngle.caution}</small>}
            </>
          ) : (
            <>
              <strong>Original evidence-backed strategy</strong>
              <p>{analysis.strategy || 'No separate letter angle was recorded for this older draft.'}</p>
            </>
          )}
        </section>
        {analysis.strategy && (
          <section>
            <h3><Target size={14} /> Draft strategy</h3>
            <p>{analysis.strategy}</p>
          </section>
        )}
        <section>
          <h3><Lightbulb size={14} /> Analysis observations</h3>
          {observations.length ? (
            <ul>
              {observations.map((observation, index) => (
                <li key={`${observation.title}-${index}`}>
                  <strong>{observation.title}</strong>
                  <span>{observation.detail}</span>
                  {observation.impact && <small>{observation.impact}</small>}
                </li>
              ))}
            </ul>
          ) : (
            <p>No separate observations were recorded for this older analysis.</p>
          )}
        </section>
        {!!evidence.length && (
          <section>
            <h3><ListChecks size={14} /> Resume evidence</h3>
            <ul>
              {evidence.map((item, index) => (
                <li key={`${item.requirement}-${index}`}>
                  <strong>{item.requirement}</strong>
                  <span>{item.resume_evidence}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        {!!gaps.length && (
          <section className="cover-decision-gaps">
            <h3><AlertTriangle size={14} /> Gaps kept honest</h3>
            <ul>{gaps.map((gap, index) => <li key={`${gap}-${index}`}>{gap}</li>)}</ul>
          </section>
        )}
        <section>
          <h3><FileText size={14} /> Paragraph plan</h3>
          {paragraphPlan.length ? (
            <ol className="cover-decision-plan">
              {paragraphPlan.map((item, index) => (
                <li key={`${item.paragraph}-${index}`}>
                  <strong>Paragraph {item.paragraph ?? index + 1}: {item.purpose}</strong>
                  {item.evidence && <span>{item.evidence}</span>}
                </li>
              ))}
            </ol>
          ) : (
            <p>No paragraph plan was saved for this older analysis.</p>
          )}
        </section>
        <section className="cover-decision-gaps">
          <h3><AlertTriangle size={14} /> Excluded claims and uncertainties</h3>
          {excludedClaims.length ? (
            <ul>
              {excludedClaims.map((item, index) => (
                <li key={`${item.claim}-${index}`}>
                  <strong>{item.claim}</strong>
                  {item.reason && <span>{item.reason}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p>No separate excluded-claims record was saved. Evidence gaps were still kept out of the draft.</p>
          )}
        </section>
        {(insights.length > 0 || sources.length > 0) && (
          <section>
            <h3><Search size={14} /> Company research used</h3>
            {!!insights.length && (
              <ul>
                {insights.map((insight, index) => {
                  const url = safeExternalUrl(insight.source_url);
                  return (
                    <li key={`${insight.fact}-${index}`}>
                      <span>{insight.fact}</span>
                      {url && (
                        <a href={url} target="_blank" rel="noreferrer">
                          {insight.source_title || 'View source'} <ExternalLink size={11} />
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {!insights.length && (
              <div className="cover-source-links">
                {sources.map((source, index) => {
                  const url = safeExternalUrl(source.url);
                  return url ? (
                    <a href={url} target="_blank" rel="noreferrer" key={`${source.url}-${index}`}>
                      {source.title || 'Research source'} <ExternalLink size={11} />
                    </a>
                  ) : null;
                })}
              </div>
            )}
          </section>
        )}
        {!!answers.length && (
          <section>
            <h3><MessageSquare size={14} /> Your clarifications</h3>
            <dl>
              {answers.map((answer, index) => (
                <div key={`${answer.question_id}-${index}`}>
                  <dt>{answer.question}</dt>
                  <dd>{answer.answer}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}
        <StructuredAnalysisRecord analysis={analysis} compact />
      </div>
    </details>
  );
}

export default function CoverLettersPage() {
  const addToast = useToast();
  const [letters, setLetters] = useState([]);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [previewKey, setPreviewKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [deleteLetter, setDeleteLetter] = useState(null);
  const [wizardStep, setWizardStep] = useState(1);
  const [busyPhase, setBusyPhase] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [research, setResearch] = useState(null);
  const [selectedAngleId, setSelectedAngleId] = useState(null);
  const [selectedInsights, setSelectedInsights] = useState([]);
  const [answers, setAnswers] = useState({});

  const workflowBusy = Boolean(busyPhase);

  const load = useCallback(async () => {
    try {
      const [letterData, versionData] = await Promise.all([
        coverLetterApi.list(),
        resumeApi.list(),
      ]);
      setLetters(letterData);
      setVersions(versionData);
      const current = versionData.find(item => item.is_current) || versionData[0];
      setForm(previous => ({
        ...previous,
        resume_version_id: previous.resume_version_id || String(current?.id || ''),
      }));
    } catch (error) {
      addToast(error.message || 'Failed to load cover letters', 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    // Initial data is loaded once and then refreshed after mutations.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const setFormField = (field, value) => {
    setForm(previous => ({ ...previous, [field]: value }));
  };

  const openCreate = () => {
    setWizardStep(1);
    setAnalysis(null);
    setResearch(null);
    setSelectedAngleId(null);
    setSelectedInsights([]);
    setAnswers({});
    setShowCreate(true);
  };

  const closeCreate = () => {
    if (workflowBusy) return;
    setShowCreate(false);
    setWizardStep(1);
    setAnalysis(null);
    setResearch(null);
    setSelectedAngleId(null);
    setSelectedInsights([]);
    setAnswers({});
  };

  const resetWorkflow = () => {
    setWizardStep(1);
    setBusyPhase(null);
    setAnalysis(null);
    setResearch(null);
    setSelectedAngleId(null);
    setSelectedInsights([]);
    setAnswers({});
    setForm(previous => ({ ...EMPTY_FORM, resume_version_id: previous.resume_version_id }));
  };

  const pasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (!text.trim()) throw new Error('Clipboard is empty');
      setFormField('job_post', text);
      addToast('Job post pasted', 'success');
    } catch (error) {
      addToast(error.message || 'Clipboard access was blocked', 'error');
    }
  };

  const buildBasePayload = () => ({
    resume_version_id: Number(form.resume_version_id),
    company: form.company.trim() || null,
    position: form.position.trim() || null,
    source_url: form.source_url.trim() || null,
    job_post: form.job_post.trim(),
    instructions: form.instructions.trim() || null,
  });

  const analyzeJob = async () => {
    if (!form.resume_version_id) return addToast('Choose a resume version', 'warning');
    if (form.job_post.trim().length < 80) return addToast('Paste the complete job post', 'warning');

    const payload = buildBasePayload();
    setWizardStep(2);
    setBusyPhase('analyzing');
    setAnalysis(null);
    setResearch(null);
    setSelectedAngleId(null);
    setSelectedInsights([]);
    setAnswers({});
    try {
      const analyzed = await coverLetterApi.analyze(payload);
      setAnalysis(analyzed);
      const analyzedAngles = asArray(analyzed.angles);
      const recommendedAngle = findAngle(analyzed, analyzed.recommended_angle_id);
      setSelectedAngleId(recommendedAngle?.id ?? analyzedAngles[0]?.id ?? null);

      const detectedCompany = analyzed.company || payload.company || '';
      const detectedPosition = analyzed.position || payload.position || '';
      setForm(previous => ({
        ...previous,
        company: detectedCompany,
        position: detectedPosition,
      }));

      setWizardStep(2);
    } catch (error) {
      setWizardStep(1);
      addToast(error.message || 'Job analysis failed', 'error');
    } finally {
      setBusyPhase(null);
    }
  };

  const researchCompany = async () => {
    if (!analysis) return addToast('Analyze the job before researching', 'warning');

    setWizardStep(3);
    setBusyPhase('researching');
    let researched;
    try {
      researched = await coverLetterApi.research({
        company: analysis.company || form.company.trim() || null,
        position: analysis.position || form.position.trim() || null,
        role_summary: analysis.role_summary || null,
        source_url: form.source_url.trim() || null,
      });
    } catch {
      researched = {
        status: 'limited',
        summary: 'Company research could not be completed. The draft can still use the job post and verified resume evidence.',
        insights: [],
        sources: [],
      };
      addToast('Company research was limited. You can still clarify anything useful and continue.', 'warning');
    } finally {
      setBusyPhase(null);
    }

    setResearch(researched);
    setSelectedInsights(asArray(researched?.insights).map((_, index) => index));
  };

  const toggleInsight = index => {
    setSelectedInsights(previous => (
      previous.includes(index)
        ? previous.filter(item => item !== index)
        : [...previous, index]
    ));
  };

  const generate = async () => {
    if (!analysis) return addToast('Analyze the job before drafting', 'warning');

    const questions = Array.isArray(analysis.questions) ? analysis.questions : [];
    const submittedAnswers = questions
      .map((question, index) => {
        const questionId = question.id ?? `question-${index}`;
        return {
          question_id: questionId,
          question: question.question,
          answer: (answers[questionId] || '').trim(),
        };
      })
      .filter(item => item.answer);

    const allInsights = Array.isArray(research?.insights) ? research.insights : [];
    const includedInsights = allInsights.filter((_, index) => selectedInsights.includes(index));
    const includedSourceUrls = new Set(includedInsights.map(item => item.source_url).filter(Boolean));
    const includedSourceTitles = new Set(includedInsights.map(item => item.source_title).filter(Boolean));
    const selectedResearch = {
      ...(research || {
        status: 'limited',
        summary: 'No external company research was available.',
        sources: [],
      }),
      insights: includedInsights,
      sources: (research?.sources || []).filter(source => (
        includedSourceUrls.has(source.url) || includedSourceTitles.has(source.title)
      )),
    };

    setWizardStep(4);
    setBusyPhase('drafting');
    try {
      const letter = await coverLetterApi.generate({
        ...buildBasePayload(),
        analysis,
        research: selectedResearch,
        answers: submittedAnswers,
        selected_angle_id: selectedAngleId,
      });
      setLetters(previous => [letter, ...previous]);
      setSelected(letter);
      setShowCreate(false);
      resetWorkflow();
      addToast('Cover letter created and saved', 'success');
    } catch (error) {
      setWizardStep(3);
      addToast(error.message || 'Generation failed', 'error');
    } finally {
      setBusyPhase(null);
    }
  };

  const updateContent = (field, value) => {
    setSelected(previous => ({
      ...previous,
      content: { ...previous.content, [field]: value },
    }));
  };

  const updateParagraph = (index, value) => {
    setSelected(previous => {
      const paragraphs = [...previous.content.paragraphs];
      paragraphs[index] = value;
      return { ...previous, content: { ...previous.content, paragraphs } };
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      const updated = await coverLetterApi.update(selected.id, selected.content);
      const merged = {
        ...updated,
        generation_context: updated.generation_context ?? selected.generation_context,
      };
      setSelected(merged);
      setLetters(previous => previous.map(item => item.id === merged.id ? merged : item));
      setPreviewKey(key => key + 1);
      addToast('Cover letter saved', 'success');
    } catch (error) {
      addToast(error.message || 'Save failed', 'error');
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await coverLetterApi.delete(deleteLetter.id);
      setLetters(previous => previous.filter(item => item.id !== deleteLetter.id));
      if (selected?.id === deleteLetter.id) setSelected(null);
      setDeleteLetter(null);
      addToast('Cover letter deleted', 'success');
    } catch (error) {
      addToast(error.message || 'Delete failed', 'error');
    }
  };

  const questions = Array.isArray(analysis?.questions) ? analysis.questions : [];
  const keyRequirements = Array.isArray(analysis?.key_requirements) ? analysis.key_requirements : [];
  const evidenceMatches = Array.isArray(analysis?.evidence_matches) ? analysis.evidence_matches : [];
  const gaps = Array.isArray(analysis?.gaps) ? analysis.gaps : [];
  const observations = asArray(analysis?.observations);
  const angles = asArray(analysis?.angles);
  const paragraphPlan = asArray(analysis?.paragraph_plan);
  const excludedClaims = asArray(analysis?.excluded_claims);
  const selectedAngle = findAngle(analysis, selectedAngleId);
  const researchInsights = Array.isArray(research?.insights) ? research.insights : [];

  const createFooter = wizardStep === 1 ? (
    <>
      <Button variant="secondary" onClick={closeCreate} disabled={workflowBusy}>Cancel</Button>
      <Button variant="primary" onClick={analyzeJob} disabled={workflowBusy || !form.job_post.trim()}>
        {busyPhase === 'analyzing' ? (
          <><Loader size={15} className="spin" /> Analyzing role…</>
        ) : (
          <><Search size={15} /> Analyze role</>
        )}
      </Button>
    </>
  ) : wizardStep === 2 ? (
    <>
      <Button variant="secondary" onClick={() => setWizardStep(1)} disabled={workflowBusy}>
        <ArrowLeft size={14} /> Back
      </Button>
      <Button variant="primary" onClick={researchCompany} disabled={workflowBusy}>
        {busyPhase === 'analyzing' ? (
          <><Loader size={15} className="spin" /> Analyzing role…</>
        ) : (
          <><Search size={15} /> Continue · Research company</>
        )}
      </Button>
    </>
  ) : wizardStep === 3 ? (
    <>
      <Button variant="secondary" onClick={() => setWizardStep(2)} disabled={workflowBusy}>
        <ArrowLeft size={14} /> Back to analysis
      </Button>
      <Button variant="primary" onClick={generate} disabled={workflowBusy}>
        {busyPhase === 'researching' ? (
          <><Loader size={15} className="spin" /> Researching company…</>
        ) : (
          <><Sparkles size={15} /> Build draft</>
        )}
      </Button>
    </>
  ) : (
    <Button variant="primary" disabled>
      <Loader size={15} className="spin" /> Building the draft…
    </Button>
  );

  if (selected) {
    return (
      <div className="cover-editor-page">
        <div className="cover-editor-topbar">
          <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
            <ArrowLeft size={15} /> Library
          </Button>
          <div className="cover-editor-title">
            <span>{selected.company}</span>
            <strong>{selected.position}</strong>
          </div>
          <div className="cover-editor-actions">
            <Button variant="secondary" size="sm" onClick={() => window.open(coverLetterApi.getDownloadUrl(selected.id), '_blank')}>
              <Download size={14} /> PDF
            </Button>
            <Button variant="primary" size="sm" onClick={save} disabled={saving}>
              {saving ? <Loader size={14} className="spin" /> : <Save size={14} />} Save changes
            </Button>
          </div>
        </div>
        <div className="cover-editor-split">
          <div className="cover-form-pane">
            <div className="cover-form-intro">
              <div className="truth-badge"><ShieldCheck size={14} /> Evidence-only draft</div>
              <h2>Edit the letter</h2>
              <p>The PDF updates when you save. Every field remains under your control.</p>
            </div>
            <DraftDecisionSummary context={selected.generation_context} />
            <div className="cover-fields-grid">
              <label>Company<input value={selected.content.company} onChange={e => updateContent('company', e.target.value)} /></label>
              <label>Position<input value={selected.content.position} onChange={e => updateContent('position', e.target.value)} /></label>
              <label>Recipient<input value={selected.content.recipient} onChange={e => updateContent('recipient', e.target.value)} /></label>
              <label>Date<input value={selected.content.date} onChange={e => updateContent('date', e.target.value)} /></label>
            </div>
            <label className="cover-field">Subject<input value={selected.content.subject} onChange={e => updateContent('subject', e.target.value)} /></label>
            <div className="paragraph-editor">
              {selected.content.paragraphs.map((paragraph, index) => (
                <label key={index}>
                  <span>Paragraph {index + 1}</span>
                  <textarea value={paragraph} onChange={e => updateParagraph(index, e.target.value)} rows={7} />
                </label>
              ))}
            </div>
            <label className="cover-field">Sign-off<input value={selected.content.sign_off} onChange={e => updateContent('sign_off', e.target.value)} /></label>
          </div>
          <div className="cover-preview-pane">
            <iframe
              key={previewKey}
              src={coverLetterApi.getPreviewUrl(selected.id, previewKey)}
              title="Cover letter preview"
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="cover-page">
      <div className="cover-page-header">
        <div>
          <div className="page-eyebrow"><Mail size={14} /> Correspondence</div>
          <h1>Cover letters</h1>
          <p className="page-subtitle">Specific, truthful letters that sound like you wrote them.</p>
        </div>
        <Button variant="primary" onClick={openCreate}><Plus size={15} /> New cover letter</Button>
      </div>

      {loading ? (
        <div className="cover-empty"><Loader size={32} className="spin" /><span>Loading letters…</span></div>
      ) : letters.length === 0 ? (
        <div className="cover-empty">
          <div className="cover-empty-icon"><FileText size={30} /></div>
          <h2>No cover letters yet</h2>
          <p>Paste a job post to create the first one.</p>
          <Button variant="primary" onClick={openCreate}><Sparkles size={15} /> Create a letter</Button>
        </div>
      ) : (
        <div className="cover-grid">
          {letters.map(letter => (
            <article className="cover-card" key={letter.id} onClick={() => setSelected(letter)}>
              <div className="cover-card-icon"><Mail size={18} /></div>
              <div className="cover-card-copy">
                <span>{letter.company}</span>
                <h2>{letter.position}</h2>
                <p>Based on {letter.resume_version_name}</p>
                <small>{new Date(letter.created_at).toLocaleDateString()}</small>
              </div>
              <button
                className="cover-delete"
                aria-label={`Delete cover letter for ${letter.position}`}
                onClick={event => { event.stopPropagation(); setDeleteLetter(letter); }}
              >
                <Trash2 size={15} />
              </button>
            </article>
          ))}
        </div>
      )}

      <Modal
        isOpen={showCreate}
        onClose={closeCreate}
        title="Build a cover letter"
        wide
        footer={createFooter}
      >
        <div className="cover-wizard-shell">
          <WorkflowStepper currentStep={wizardStep} />

          {wizardStep === 1 && !workflowBusy && (
            <div className="cover-wizard-stage">
              <div className="cover-stage-heading">
                <div className="cover-stage-icon"><FileSearch size={19} /></div>
                <div>
                  <h3>Start with the role</h3>
                  <p>We will analyze the post, match it to your resume, then research useful company context.</p>
                </div>
              </div>
              <div className="cover-create-note">
                <ShieldCheck size={17} />
                <span><strong>Truth guardrails stay on.</strong> Candidate claims must come from your selected resume or your own answers.</span>
              </div>
              <div className="cover-wizard-form-grid">
                <div className="form-group">
                  <label className="form-label">Resume source</label>
                  <select value={form.resume_version_id} onChange={e => setFormField('resume_version_id', e.target.value)}>
                    {versions.map(version => (
                      <option value={version.id} key={version.id}>
                        {version.name}{version.is_current ? ' (Current)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Job post URL <span>optional</span></label>
                  <div className="cover-input-with-icon">
                    <Link2 size={14} />
                    <input
                      type="url"
                      value={form.source_url}
                      onChange={e => setFormField('source_url', e.target.value)}
                      placeholder="https://company.com/jobs/…"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Company <span>optional</span></label>
                  <input value={form.company} onChange={e => setFormField('company', e.target.value)} placeholder="We can detect this" />
                </div>
                <div className="form-group">
                  <label className="form-label">Position <span>optional</span></label>
                  <input value={form.position} onChange={e => setFormField('position', e.target.value)} placeholder="We can detect this" />
                </div>
              </div>
              <div className="form-group">
                <div className="cover-label-row">
                  <label className="form-label">Job post</label>
                  <button type="button" onClick={pasteFromClipboard}><Clipboard size={13} /> Paste clipboard</button>
                </div>
                <textarea
                  className="job-post-input"
                  value={form.job_post}
                  onChange={e => setFormField('job_post', e.target.value)}
                  placeholder="Paste the complete job description."
                  rows={11}
                />
                <div className="cover-input-meta">
                  {form.job_post.trim() ? `${form.job_post.trim().split(/\s+/).length} words` : 'A complete post produces a more specific analysis'}
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Personal direction <span>optional</span></label>
                <textarea
                  value={form.instructions}
                  onChange={e => setFormField('instructions', e.target.value)}
                  placeholder="Anything true you want emphasized, explained, or avoided."
                  rows={3}
                />
              </div>
            </div>
          )}

          {wizardStep === 2 && workflowBusy && <WorkflowProgress phase="analyzing" />}

          {wizardStep === 2 && !workflowBusy && (
            <div className="cover-wizard-stage">
              <div className="cover-stage-heading">
                <div className="cover-stage-icon"><ListChecks size={19} /></div>
                <div>
                  <h3>Inspect the analysis</h3>
                  <p>Review what was found, compare possible letter angles, and choose the direction before any company research begins.</p>
                </div>
              </div>
              <div className="cover-decision-note">
                <Lightbulb size={16} />
                <span><strong>Public decision record, not hidden chain-of-thought.</strong> This is the complete structured output the drafting process can use: observations, evidence, choices, uncertainties, and outline.</span>
              </div>

              <div className="cover-review-grid">
                <section className="cover-review-card">
                  <div className="cover-review-card-title"><Target size={15} /><h4>Role at a glance</h4></div>
                  <p>{analysis?.role_summary || `${analysis?.position || form.position} at ${analysis?.company || form.company}`}</p>
                </section>
                <section className="cover-review-card">
                  <div className="cover-review-card-title"><Lightbulb size={15} /><h4>Draft strategy</h4></div>
                  <p>{analysis?.strategy || 'Lead with the strongest verified experience and keep unsupported requirements out of the letter.'}</p>
                </section>

                <section className="cover-review-card cover-review-wide">
                  <div className="cover-review-card-title"><Lightbulb size={15} /><h4>Analysis observations</h4></div>
                  {observations.length ? (
                    <div className="cover-observation-list">
                      {observations.map((observation, index) => (
                        <article key={`${observation.title}-${index}`}>
                          <strong>{observation.title}</strong>
                          <p>{observation.detail}</p>
                          {observation.impact && <small><span>Why it matters</span>{observation.impact}</small>}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="cover-muted-copy">This older analysis did not include separate observations. The role summary, evidence, and strategy are still available below.</p>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide">
                  <div className="cover-review-card-title"><ListChecks size={15} /><h4>What the role needs</h4></div>
                  {keyRequirements.length ? (
                    <div className="cover-requirements">
                      {keyRequirements.map((item, index) => (
                        <div key={`${item.requirement}-${index}`}>
                          <span>{item.requirement}</span>
                          {item.importance && <small className={`importance-${item.importance.toLowerCase()}`}>{item.importance}</small>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="cover-muted-copy">No distinct requirements were extracted.</p>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide">
                  <div className="cover-review-card-title"><ShieldCheck size={15} /><h4>Evidence from your resume</h4></div>
                  {evidenceMatches.length ? (
                    <div className="cover-evidence-list">
                      {evidenceMatches.map((item, index) => (
                        <article key={`${item.requirement}-${index}`}>
                          <strong>{item.requirement}</strong>
                          <p>{item.resume_evidence}</p>
                          {item.relevance && <small>{item.relevance}</small>}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="cover-muted-copy">No direct evidence matches were found. The draft will avoid unsupported claims.</p>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide cover-gap-card">
                  <div className="cover-review-card-title"><AlertTriangle size={15} /><h4>Gaps kept honest</h4></div>
                  {gaps.length ? (
                    <ul>{gaps.map((gap, index) => <li key={`${gap}-${index}`}>{gap}</li>)}</ul>
                  ) : (
                    <p className="cover-muted-copy">No material resume-to-role gaps were recorded.</p>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide">
                  <div className="cover-review-card-title"><Sparkles size={15} /><h4>Choose a letter angle</h4></div>
                  <p className="cover-section-intro">Each angle is a different truthful way to organize the same verified evidence. The recommended option is preselected, but the choice is yours.</p>
                  {angles.length ? (
                    <div className="cover-angle-list" role="radiogroup" aria-label="Letter angle">
                      {angles.map((angle, index) => {
                        const isSelected = String(selectedAngleId) === String(angle.id);
                        const isRecommended = String(analysis?.recommended_angle_id) === String(angle.id);
                        return (
                          <label className={`cover-angle-choice ${isSelected ? 'selected' : ''}`} key={angle.id ?? index}>
                            <input
                              type="radio"
                              name="cover-letter-angle"
                              value={angle.id}
                              checked={isSelected}
                              onChange={() => setSelectedAngleId(angle.id)}
                            />
                            <span className="cover-angle-copy">
                              <span className="cover-angle-heading">
                                <strong>{angle.title}</strong>
                                {isRecommended && <small className="cover-recommended-badge"><Check size={11} /> Recommended</small>}
                              </span>
                              <p>{angle.approach}</p>
                              {!!asArray(angle.supporting_evidence).length && (
                                <span className="cover-angle-evidence">
                                  <b>Supporting evidence</b>
                                  <ul>
                                    {angle.supporting_evidence.map((item, evidenceIndex) => (
                                      <li key={`${item}-${evidenceIndex}`}>{item}</li>
                                    ))}
                                  </ul>
                                </span>
                              )}
                              {angle.caution && (
                                <span className="cover-angle-caution"><AlertTriangle size={12} /> {angle.caution}</span>
                              )}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="cover-legacy-angle">
                      <Target size={15} />
                      <span>
                        <strong>Using the original draft strategy</strong>
                        <small>This older analysis has no separate angle options. You can continue with its evidence-backed strategy.</small>
                      </span>
                    </div>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide">
                  <div className="cover-review-card-title"><FileText size={15} /><h4>Four-paragraph outline</h4></div>
                  {paragraphPlan.length ? (
                    <ol className="cover-paragraph-plan">
                      {paragraphPlan.map((item, index) => (
                        <li key={`${item.paragraph}-${index}`}>
                          <span>{item.paragraph ?? index + 1}</span>
                          <div>
                            <strong>{item.purpose}</strong>
                            {item.evidence && <p>{item.evidence}</p>}
                          </div>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="cover-muted-copy">This older analysis did not save a paragraph-by-paragraph outline. The generator will still use the original strategy.</p>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide cover-gap-card">
                  <div className="cover-review-card-title"><AlertTriangle size={15} /><h4>Excluded claims and uncertainties</h4></div>
                  {excludedClaims.length ? (
                    <div className="cover-excluded-list">
                      {excludedClaims.map((item, index) => (
                        <article key={`${item.claim}-${index}`}>
                          <strong>{item.claim}</strong>
                          {item.reason && <p>{item.reason}</p>}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="cover-muted-copy">No additional excluded claims were recorded. Any evidence gaps above will still remain outside the draft.</p>
                  )}
                </section>
              </div>

              <StructuredAnalysisRecord analysis={analysis} />
            </div>
          )}

          {wizardStep === 3 && workflowBusy && <WorkflowProgress phase="researching" />}

          {wizardStep === 3 && !workflowBusy && (
            <div className="cover-wizard-stage">
              <div className="cover-stage-heading">
                <div className="cover-stage-icon"><Search size={19} /></div>
                <div>
                  <h3>Research and clarify</h3>
                  <p>Choose which attributable company context to use and answer only the questions that improve the letter.</p>
                </div>
              </div>

              <div className="cover-review-grid">
                <section className="cover-review-card cover-review-wide cover-selected-angle">
                  <div className="cover-review-card-title"><Sparkles size={15} /><h4>Selected letter angle</h4></div>
                  {selectedAngle ? (
                    <>
                      <strong>{selectedAngle.title}</strong>
                      <p>{selectedAngle.approach}</p>
                      {selectedAngle.caution && <small><AlertTriangle size={12} /> {selectedAngle.caution}</small>}
                    </>
                  ) : (
                    <>
                      <strong>Original evidence-backed strategy</strong>
                      <p>{analysis?.strategy || 'Use the strongest verified resume evidence and avoid unsupported claims.'}</p>
                    </>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide">
                  <div className="cover-review-card-title">
                    <Search size={15} />
                    <h4>Company research</h4>
                    <span className={`research-status ${research?.status || 'limited'}`}>{research?.status || 'limited'}</span>
                  </div>
                  {research?.summary && <p className="cover-research-summary">{research.summary}</p>}
                  {research?.status === 'limited' && (
                    <div className="cover-limited-note">
                      <AlertTriangle size={14} />
                      <span>Research was limited. You can safely continue using the job post and resume evidence.</span>
                    </div>
                  )}
                  {researchInsights.length ? (
                    <div className="cover-research-list">
                      {researchInsights.map((insight, index) => {
                        const sourceUrl = safeExternalUrl(insight.source_url);
                        const isSelected = selectedInsights.includes(index);
                        return (
                          <label className={`cover-research-choice ${isSelected ? 'selected' : ''}`} key={`${insight.fact}-${index}`}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleInsight(index)}
                            />
                            <span>
                              <strong>{insight.fact}</strong>
                              {insight.relevance && <small>{insight.relevance}</small>}
                              {sourceUrl && (
                                <a href={sourceUrl} target="_blank" rel="noreferrer">
                                  {insight.source_title || 'View source'} <ExternalLink size={11} />
                                </a>
                              )}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="cover-muted-copy">No external facts will be added to the draft.</p>
                  )}
                </section>

                <section className="cover-review-card cover-review-wide">
                  <div className="cover-review-card-title"><HelpCircle size={15} /><h4>Clarify what matters</h4></div>
                  {questions.length ? (
                    <div className="cover-question-list">
                      {questions.map((question, index) => {
                        const questionId = question.id ?? `question-${index}`;
                        return (
                          <label key={questionId}>
                            <span>{question.question}</span>
                            {question.why && <small>{question.why}</small>}
                            <textarea
                              value={answers[questionId] || ''}
                              onChange={event => setAnswers(previous => ({ ...previous, [questionId]: event.target.value }))}
                              placeholder={question.placeholder || 'Optional — leave blank to skip'}
                              rows={3}
                            />
                          </label>
                        );
                      })}
                      <p className="cover-skip-note">Not sure? Leave any answer blank. The draft will not guess.</p>
                    </div>
                  ) : (
                    <div className="cover-no-questions">
                      <Check size={16} />
                      <span><strong>Nothing material to clarify.</strong> The role and available evidence are clear enough to draft responsibly.</span>
                    </div>
                  )}
                </section>
              </div>
            </div>
          )}

          {wizardStep === 4 && <WorkflowProgress phase="drafting" />}
        </div>
      </Modal>

      <Modal
        isOpen={!!deleteLetter}
        onClose={() => setDeleteLetter(null)}
        title="Delete cover letter"
        footer={<><Button variant="secondary" onClick={() => setDeleteLetter(null)}>Cancel</Button><Button variant="danger" onClick={remove}>Delete</Button></>}
      >
        <p className="confirm-delete-text">Permanently delete the letter for <strong>{deleteLetter?.position}</strong> at <strong>{deleteLetter?.company}</strong>?</p>
      </Modal>
    </div>
  );
}
