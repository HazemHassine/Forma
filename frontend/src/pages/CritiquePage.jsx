import { useState, useEffect, useCallback } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Info,
  Check,
  Copy,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Trash2,
  FileText,
  Briefcase,
} from 'lucide-react';
import { resumeApi, critiqueApi, formatApiError } from '../api';
import { useToast, useAIProvider } from '../App';
import Button from '../components/Button';
import './CritiquePage.css';

export default function CritiquePage() {
  const toast = useToast();
  const { aiProvider } = useAIProvider();

  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState(null);
  const [targetRole, setTargetRole] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [showRoleInputs, setShowRoleInputs] = useState(false);

  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const [history, setHistory] = useState([]);
  const [currentCritique, setCurrentCritique] = useState(null);

  const [activeSeverityFilter, setActiveSeverityFilter] = useState('all');
  const [activeCategoryFilter, setActiveCategoryFilter] = useState('all');
  const [copiedIssueId, setCopiedIssueId] = useState(null);

  // Load resume versions on mount
  useEffect(() => {
    setLoading(true);
    resumeApi.listVersions()
      .then(data => {
        setVersions(data);
        const current = data.find(v => v.is_current) || data[0];
        if (current) {
          setSelectedVersionId(current.id);
        }
      })
      .catch(err => {
        toast.addToast(`Failed to load versions: ${formatApiError(err)}`, 'error');
      })
      .finally(() => setLoading(false));
  }, [toast]);

  // Load critique history when selected version changes
  const loadHistory = useCallback(async (versionId) => {
    if (!versionId) return;
    try {
      const list = await critiqueApi.listForVersion(versionId);
      setHistory(list);
      if (list.length > 0) {
        // Fetch full report of most recent critique
        const latest = await critiqueApi.get(list[0].id);
        setCurrentCritique(latest);
      } else {
        setCurrentCritique(null);
      }
    } catch (err) {
      toast.addToast(`Failed to load reviews: ${formatApiError(err)}`, 'error');
    }
  }, [toast]);

  useEffect(() => {
    if (selectedVersionId) {
      loadHistory(selectedVersionId);
    }
  }, [selectedVersionId, loadHistory]);

  const handleRunCritique = async () => {
    if (!selectedVersionId) {
      toast.addToast('Please select a resume version', 'error');
      return;
    }

    setAnalyzing(true);
    try {
      const response = await critiqueApi.create(aiProvider, {
        resume_version_id: selectedVersionId,
        target_role: targetRole.trim() || null,
        job_description: jobDescription.trim() || null,
      });
      setCurrentCritique(response);
      toast.addToast('Review completed', 'success');
      // Refresh history list
      loadHistory(selectedVersionId);
    } catch (err) {
      toast.addToast(formatApiError(err) || 'Review failed', 'error');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSelectHistoricalCritique = async (critiqueId) => {
    try {
      const full = await critiqueApi.get(critiqueId);
      setCurrentCritique(full);
    } catch (err) {
      toast.addToast(`Failed to load review: ${formatApiError(err)}`, 'error');
    }
  };

  const handleDeleteCritique = async (critiqueId) => {
    if (!window.confirm('Delete this review?')) return;
    try {
      await critiqueApi.delete(critiqueId);
      toast.addToast('Review deleted', 'info');
      loadHistory(selectedVersionId);
    } catch (err) {
      toast.addToast(`Delete failed: ${formatApiError(err)}`, 'error');
    }
  };

  const handleCopyFix = (issueId, text) => {
    navigator.clipboard.writeText(text);
    setCopiedIssueId(issueId);
    setTimeout(() => {
      setCopiedIssueId(null);
    }, 2000);
  };

  const report = currentCritique?.report;
  const issues = report?.issues || [];

  const filteredIssues = issues.filter(issue => {
    if (activeSeverityFilter !== 'all' && issue.severity !== activeSeverityFilter) {
      return false;
    }
    if (activeCategoryFilter !== 'all' && issue.category !== activeCategoryFilter) {
      return false;
    }
    return true;
  });

  const getScoreColorClass = (score) => {
    if (score >= 80) return 'score-green';
    if (score >= 65) return 'score-amber';
    return 'score-red';
  };

  return (
    <div className="critique-page">
      <header className="critique-header">
        <div>
          <h1 className="critique-title">Resume review</h1>
          <p className="critique-subtitle">
            Find passive phrasing, unquantified bullets, buzzwords, and structure issues.
          </p>
        </div>
      </header>

      {/* Control Panel */}
      <section className="critique-controls-panel">
        <div className="critique-controls-row">
          <div className="control-group">
            <label htmlFor="version-select">Resume version</label>
            <select
              id="version-select"
              value={selectedVersionId || ''}
              onChange={e => setSelectedVersionId(Number(e.target.value))}
              disabled={analyzing}
            >
              {versions.map(v => (
                <option key={v.id} value={v.id}>
                  {v.name} {v.is_current ? '(Current)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="control-actions">
            <button
              type="button"
              className="role-toggle-btn"
              onClick={() => setShowRoleInputs(!showRoleInputs)}
            >
              <Briefcase size={14} />
              <span>{showRoleInputs ? 'Hide job target' : '+ Add target job post'}</span>
              {showRoleInputs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            <Button
              variant="primary"
              onClick={handleRunCritique}
              disabled={analyzing || !selectedVersionId}
            >
              {analyzing ? (
                <>
                  <RefreshCw size={14} className="spin" /> Reviewing...
                </>
              ) : (
                'Run review'
              )}
            </Button>
          </div>
        </div>

        {/* Optional Target Job Post */}
        {showRoleInputs && (
          <div className="critique-target-inputs">
            <div className="target-input-field">
              <label htmlFor="target-role">Target role (optional)</label>
              <input
                id="target-role"
                type="text"
                placeholder="e.g. Senior Backend Engineer"
                value={targetRole}
                onChange={e => setTargetRole(e.target.value)}
                disabled={analyzing}
              />
            </div>
            <div className="target-input-field">
              <label htmlFor="job-description">Target job description (optional)</label>
              <textarea
                id="job-description"
                rows={4}
                placeholder="Paste the job description to test for specific qualification gaps and keyword alignment..."
                value={jobDescription}
                onChange={e => setJobDescription(e.target.value)}
                disabled={analyzing}
              />
            </div>
          </div>
        )}

        {/* Past Reviews Dropdown */}
        {history.length > 0 && (
          <div className="critique-history-bar">
            <span className="history-label">Previous reviews:</span>
            <select
              value={currentCritique?.id || ''}
              onChange={e => handleSelectHistoricalCritique(Number(e.target.value))}
            >
              {history.map(item => (
                <option key={item.id} value={item.id}>
                  Score: {item.overall_score}/100 — {new Date(item.created_at).toLocaleDateString()} {item.target_role ? `(${item.target_role})` : ''}
                </option>
              ))}
            </select>
            {currentCritique && (
              <button
                type="button"
                className="delete-review-btn"
                title="Delete this review"
                onClick={() => handleDeleteCritique(currentCritique.id)}
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        )}
      </section>

      {/* Empty State */}
      {!analyzing && !currentCritique && (
        <div className="critique-empty-state">
          <div className="empty-icon"><FileText size={36} /></div>
          <h3>No review generated yet</h3>
          <p>Select your resume and click "Run review" to analyze bullet points, clarity, and metrics.</p>
        </div>
      )}

      {/* Active Review Results */}
      {currentCritique && report && (
        <div className="critique-results">
          {/* Top Score Banner */}
          <section className="critique-score-banner">
            <div className={`score-badge ${getScoreColorClass(report.overall_score)}`}>
              <span className="score-number">{report.overall_score}</span>
              <span className="score-out-of">/100</span>
            </div>

            <div className="score-summary-content">
              <h2 className="verdict-heading">{report.verdict}</h2>
              <p className="summary-text">{report.summary}</p>
            </div>
          </section>

          {/* Categories Grid */}
          <section className="critique-categories-grid">
            {report.category_scores.map(cat => (
              <div key={cat.category} className="category-card">
                <div className="category-header">
                  <span className="category-label">{cat.label}</span>
                  <span className={`category-score-val ${getScoreColorClass(cat.score)}`}>
                    {cat.score}%
                  </span>
                </div>
                <div className="category-progress-track">
                  <div
                    className={`category-progress-bar ${getScoreColorClass(cat.score)}`}
                    style={{ width: `${cat.score}%` }}
                  />
                </div>
                <p className="category-summary">{cat.summary}</p>
              </div>
            ))}
          </section>

          {/* Strengths List */}
          {report.strengths?.length > 0 && (
            <section className="critique-strengths-card">
              <h3 className="section-subtitle">What is working well</h3>
              <ul className="strengths-list">
                {report.strengths.map((str, idx) => (
                  <li key={idx}>
                    <Check size={14} className="check-icon" />
                    <span>{str}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Issues Section */}
          <section className="critique-issues-section">
            <div className="issues-header-bar">
              <h3 className="section-subtitle">Identified issues ({issues.length})</h3>

              {/* Severity Filter Tabs */}
              <div className="severity-tabs">
                <button
                  type="button"
                  className={`tab-btn ${activeSeverityFilter === 'all' ? 'active' : ''}`}
                  onClick={() => setActiveSeverityFilter('all')}
                >
                  All ({issues.length})
                </button>
                <button
                  type="button"
                  className={`tab-btn tab-critical ${activeSeverityFilter === 'critical' ? 'active' : ''}`}
                  onClick={() => setActiveSeverityFilter('critical')}
                >
                  <AlertCircle size={13} /> Critical ({report.critical_count})
                </button>
                <button
                  type="button"
                  className={`tab-btn tab-warning ${activeSeverityFilter === 'warning' ? 'active' : ''}`}
                  onClick={() => setActiveSeverityFilter('warning')}
                >
                  <AlertTriangle size={13} /> Warning ({report.warning_count})
                </button>
                <button
                  type="button"
                  className={`tab-btn tab-suggestion ${activeSeverityFilter === 'suggestion' ? 'active' : ''}`}
                  onClick={() => setActiveSeverityFilter('suggestion')}
                >
                  <Info size={13} /> Suggestion ({report.suggestion_count})
                </button>
              </div>
            </div>

            {/* Category Filter Pills */}
            <div className="category-filter-pills">
              {['all', 'impact', 'brevity', 'style', 'structure', 'ats'].map(cat => (
                <button
                  key={cat}
                  type="button"
                  className={`pill-btn ${activeCategoryFilter === cat ? 'active' : ''}`}
                  onClick={() => setActiveCategoryFilter(cat)}
                >
                  {cat === 'all' ? 'All categories' : cat.charAt(0).toUpperCase() + cat.slice(1)}
                </button>
              ))}
            </div>

            {/* Issues List */}
            <div className="issues-list">
              {filteredIssues.length === 0 ? (
                <div className="no-issues-match">
                  No issues match the selected filters.
                </div>
              ) : (
                filteredIssues.map(issue => (
                  <article key={issue.id} className={`issue-card severity-${issue.severity}`}>
                    <div className="issue-card-top">
                      <div className="issue-badges">
                        <span className={`severity-badge badge-${issue.severity}`}>
                          {issue.severity === 'critical' && <AlertCircle size={12} />}
                          {issue.severity === 'warning' && <AlertTriangle size={12} />}
                          {issue.severity === 'suggestion' && <Info size={12} />}
                          {issue.severity}
                        </span>
                        <span className="location-badge">{issue.location_label}</span>
                        <span className="category-tag">{issue.category}</span>
                      </div>
                    </div>

                    <h4 className="issue-problem">{issue.problem}</h4>
                    <p className="issue-why">{issue.why_it_hurts}</p>

                    <div className="issue-diff-comparison">
                      <div className="diff-block original-block">
                        <span className="diff-label">Current text</span>
                        <p className="diff-text">{issue.original_text}</p>
                      </div>

                      <div className="diff-block fix-block">
                        <div className="fix-header">
                          <span className="diff-label">Suggested rewrite</span>
                          <button
                            type="button"
                            className="copy-fix-btn"
                            onClick={() => handleCopyFix(issue.id, issue.suggested_fix)}
                            title="Copy rewrite"
                          >
                            {copiedIssueId === issue.id ? (
                              <>
                                <Check size={12} /> Copied
                              </>
                            ) : (
                              <>
                                <Copy size={12} /> Copy
                              </>
                            )}
                          </button>
                        </div>
                        <p className="diff-text">{issue.suggested_fix}</p>
                      </div>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
