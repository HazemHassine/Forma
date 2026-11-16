import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Plus, Trash2, Briefcase, Loader, Activity, Search, ExternalLink, Target, Mail,
  Building2, SearchCheck, FileText, CalendarClock, MapPin, Send,
} from 'lucide-react';
import { jobApi, resumeApi } from '../api';
import { useToast } from '../App';
import Button from '../components/Button';
import Modal from '../components/Modal';
import { buildJobPayload } from '../jobPayload';
import {
  JOB_STATUSES, addDays, buildHandoff, describeAge, daysBetween, followUpInfo,
  formatDay, isActive, matchesQuery, statusLabel, toISODate,
} from '../jobs';
import './JobsPage.css';

const FOLLOW_UP_AFTER_DAYS = 7;

function emptyJob(status = 'applied') {
  const today = toISODate();
  return {
    company: '',
    position: '',
    url: '',
    status,
    resume_version_id: '',
    notes: '',
    applied_at: today,
    job_description: '',
    location: '',
    salary: '',
    contact: '',
    next_step: '',
    follow_up_at: status === 'applied' ? addDays(today, FOLLOW_UP_AFTER_DAYS) : '',
  };
}

function jobToForm(job) {
  return {
    company: job.company || '',
    position: job.position || '',
    url: job.url || '',
    status: job.status || 'applied',
    resume_version_id: job.resume_version_id ?? '',
    notes: job.notes || '',
    applied_at: job.applied_at ? job.applied_at.slice(0, 10) : '',
    job_description: job.job_description || '',
    location: job.location || '',
    salary: job.salary || '',
    contact: job.contact || '',
    next_step: job.next_step || '',
    follow_up_at: job.follow_up_at || '',
  };
}

function eventText(event) {
  if (event.kind === 'created') return `Added as ${statusLabel(event.detail).toLowerCase()}`;
  if (event.kind === 'status') {
    const [from, to] = String(event.detail || '').split(' → ');
    return to ? `${statusLabel(from)} → ${statusLabel(to)}` : event.detail;
  }
  return event.detail;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [sortField, setSortField] = useState('applied_at');
  const [sortDir, setSortDir] = useState('desc');
  const [showModal, setShowModal] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [formData, setFormData] = useState(emptyJob);
  const [saving, setSaving] = useState(false);
  const [events, setEvents] = useState([]);
  const [noteDraft, setNoteDraft] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(null);
  const addToast = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const today = toISODate();

  const loadData = useCallback(async () => {
    try {
      const [jobsData, versionsData] = await Promise.all([
        jobApi.list(),
        resumeApi.list().catch(() => []),
      ]);
      setJobs(jobsData);
      setVersions(versionsData);
      return jobsData;
    } catch (err) {
      addToast(err.message || 'Failed to load applications', 'error');
      return null;
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  const openCreateModal = useCallback((status = 'applied') => {
    setEditingJob(null);
    setFormData(emptyJob(status));
    setEvents([]);
    setNoteDraft('');
    setShowModal(true);
  }, []);

  const openEditModal = useCallback((job) => {
    setEditingJob(job);
    setFormData(jobToForm(job));
    setEvents([]);
    setNoteDraft('');
    setShowModal(true);
    jobApi.events(job.id).then(setEvents).catch(() => setEvents([]));
  }, []);

  useEffect(() => {
    // Initial load; also honours links such as /jobs?open=12 or /jobs?new=saved.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData().then((loaded) => {
      const openId = Number(searchParams.get('open'));
      const newStatus = searchParams.get('new');
      const status = searchParams.get('status');
      if (status) setFilter(status);
      if (openId && loaded) {
        const job = loaded.find(item => item.id === openId);
        if (job) openEditModal(job);
      } else if (newStatus) {
        openCreateModal(newStatus === 'saved' ? 'saved' : 'applied');
      }
      if (openId || newStatus) setSearchParams({}, { replace: true });
    });
    // Runs once on mount: later URL changes are made by this component itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = useMemo(() => {
    const result = { all: jobs.length, active: 0 };
    for (const job of jobs) {
      result[job.status] = (result[job.status] || 0) + 1;
      if (isActive(job)) result.active += 1;
    }
    return result;
  }, [jobs]);

  const filtered = useMemo(() => {
    const rows = jobs.filter(job => (
      (filter === 'all' || (filter === 'active' ? isActive(job) : job.status === filter))
      && matchesQuery(job, query)
    ));
    const direction = sortDir === 'asc' ? 1 : -1;
    return rows.sort((a, b) => {
      // Applications without a follow-up date always sort after those with one.
      if (sortField === 'follow_up_at' && Boolean(a.follow_up_at) !== Boolean(b.follow_up_at)) {
        return a.follow_up_at ? -1 : 1;
      }
      const av = String(a[sortField] || '').toLowerCase();
      const bv = String(b[sortField] || '').toLowerCase();
      return (av < bv ? -1 : av > bv ? 1 : 0) * direction;
    });
  }, [jobs, filter, query, sortField, sortDir]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };
  const sortMark = (field) => (sortField === field ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '');

  const setField = (field, value) => setFormData(prev => ({ ...prev, [field]: value }));

  const changeFormStatus = (status) => {
    setFormData(prev => {
      const next = { ...prev, status };
      // Applying starts the clock: suggest a follow-up if none is planned.
      if (status === 'applied' && prev.status === 'saved') {
        next.applied_at = today;
        if (!prev.follow_up_at) next.follow_up_at = addDays(today, FOLLOW_UP_AFTER_DAYS);
      }
      return next;
    });
  };

  /** Save the open form. Returns the saved job, or null when it failed. */
  const saveForm = async () => {
    if (!formData.company.trim() || !formData.position.trim()) {
      addToast('Company and position are required', 'warning');
      return null;
    }
    setSaving(true);
    try {
      const payload = buildJobPayload(formData);
      const saved = editingJob
        ? await jobApi.update(editingJob.id, payload)
        : await jobApi.create(payload);
      return saved;
    } catch (err) {
      addToast(err.message || 'Failed to save application', 'error');
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    const saved = await saveForm();
    if (!saved) return;
    addToast(editingJob ? 'Application updated' : 'Application added', 'success');
    setShowModal(false);
    loadData();
  };

  /** Save first, then open an AI page already filled in for this application. */
  const prepare = async (path) => {
    const saved = await saveForm();
    if (!saved) return;
    navigate(path, { state: { job: buildHandoff(saved) } });
  };

  const quickStatus = async (job, status) => {
    try {
      await jobApi.update(job.id, { status });
      addToast(`${job.company}: ${statusLabel(status)}`, 'success');
      loadData();
    } catch (err) {
      addToast(err.message || 'Failed to update status', 'error');
    }
  };

  const addNote = async () => {
    const detail = noteDraft.trim();
    if (!detail || !editingJob) return;
    try {
      const event = await jobApi.addNote(editingJob.id, detail);
      setEvents(prev => [event, ...prev]);
      setNoteDraft('');
    } catch (err) {
      addToast(err.message || 'Failed to add note', 'error');
    }
  };

  const handleDelete = async () => {
    if (!showDeleteModal) return;
    try {
      await jobApi.delete(showDeleteModal.id);
      setShowDeleteModal(null);
      setShowModal(false);
      addToast('Application deleted', 'success');
      loadData();
    } catch (err) {
      addToast(err.message || 'Failed to delete', 'error');
    }
  };

  const chips = [
    { id: 'all', label: 'All' },
    { id: 'active', label: 'Active' },
    ...JOB_STATUSES.map(status => ({ id: status.id, label: status.label })),
  ].filter(chip => chip.id === 'all' || chip.id === 'active' || counts[chip.id] || filter === chip.id);

  const hasJobPost = formData.job_description.trim().length > 0;

  return (
    <div className="jobs-page">
      <div className="jobs-header">
        <div>
          <div className="page-eyebrow"><Activity size={14} /> Application pipeline</div>
          <h1 className="jobs-title">Applications</h1>
          <p className="page-subtitle">
            One place per role: the job post, the resume you sent, when to follow up, and what happened.
          </p>
        </div>
        <div className="jobs-header-actions">
          <Button variant="secondary" onClick={() => openCreateModal('saved')}><Plus size={14} /> Save a job for later</Button>
          <Button variant="primary" onClick={() => openCreateModal('applied')}><Plus size={14} /> Log an application</Button>
        </div>
      </div>

      <div className="jobs-toolbar">
        <div className="jobs-chips" role="tablist" aria-label="Filter by status">
          {chips.map(chip => (
            <button
              key={chip.id}
              type="button"
              role="tab"
              aria-selected={filter === chip.id}
              className={`jobs-chip ${filter === chip.id ? 'active' : ''}`}
              onClick={() => setFilter(chip.id)}
            >
              {chip.label} <span>{counts[chip.id] || 0}</span>
            </button>
          ))}
        </div>
        <label className="jobs-search">
          <Search size={14} />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search company, role, notes…"
            aria-label="Search applications"
          />
        </label>
      </div>

      {loading ? (
        <div className="jobs-empty">
          <div className="jobs-empty-icon"><Loader size={40} /></div>
          <div>Loading applications...</div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="jobs-empty">
          <div className="jobs-empty-icon"><Briefcase size={40} /></div>
          <div>
            {jobs.length === 0
              ? 'Nothing tracked yet. Save a job you like, or log one you already applied to.'
              : 'No applications match this filter.'}
          </div>
        </div>
      ) : (
        <div className="jobs-table-wrapper">
          <table className="jobs-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('company')}>Role{sortMark('company')}</th>
                <th onClick={() => handleSort('status')}>Status{sortMark('status')}</th>
                <th onClick={() => handleSort('follow_up_at')}>Follow-up{sortMark('follow_up_at')}</th>
                <th>Prepared</th>
                <th onClick={() => handleSort('applied_at')}>Applied{sortMark('applied_at')}</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {filtered.map(job => {
                const followUp = followUpInfo(job, today);
                const age = daysBetween(job.applied_at, today);
                return (
                  <tr key={job.id} onClick={() => openEditModal(job)}>
                    <td>
                      <div className="job-company">{job.company}</div>
                      <div className="job-position">
                        {job.position}
                        {job.location && <span className="job-location"><MapPin size={11} /> {job.location}</span>}
                      </div>
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <select
                        className={`status-select status-${job.status}`}
                        value={job.status}
                        onChange={e => quickStatus(job, e.target.value)}
                        aria-label={`Status for ${job.company}`}
                      >
                        {JOB_STATUSES.map(status => (
                          <option key={status.id} value={status.id}>{status.label}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      {followUp ? (
                        <div className={`job-followup followup-${followUp.state}`}>
                          <CalendarClock size={12} /> {followUp.label}
                        </div>
                      ) : <span className="job-muted">—</span>}
                      {job.next_step && isActive(job) && <div className="job-next-step">{job.next_step}</div>}
                    </td>
                    <td>
                      <div className="job-prepared">
                        <span className={job.job_description ? 'on' : ''} title={job.job_description ? 'Job post saved' : 'No job post saved'}><FileText size={14} /></span>
                        <span className={job.resume_version_id ? 'on' : ''} title={job.resume_version_name ? `Resume: ${job.resume_version_name}` : 'No resume version linked'}><Target size={14} /></span>
                        <span className={job.has_cover_letter ? 'on' : ''} title={job.has_cover_letter ? 'Cover letter written for this company' : 'No cover letter yet'}><Mail size={14} /></span>
                        <span className={job.has_research ? 'on' : ''} title={job.has_research ? 'Company research saved' : 'No company research yet'}><Building2 size={14} /></span>
                      </div>
                    </td>
                    <td>
                      <div className="job-date">{job.status === 'saved' ? 'Not yet' : formatDay(job.applied_at, { withYear: true })}</div>
                      {job.status !== 'saved' && <div className="job-age">{describeAge(age)}</div>}
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="job-actions">
                        {job.url && (
                          <a className="job-link" href={job.url} target="_blank" rel="noreferrer" title="Open job post" aria-label={`Open job post for ${job.company}`}>
                            <ExternalLink size={14} />
                          </a>
                        )}
                        <button className="job-link danger" type="button" onClick={() => setShowDeleteModal(job)} title="Delete" aria-label={`Delete ${job.company}`}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingJob ? `${editingJob.company} · ${editingJob.position}` : formData.status === 'saved' ? 'Save a job for later' : 'Log an application'}
        wide
        footer={
          <>
            {editingJob && (
              <Button variant="danger" onClick={() => setShowDeleteModal(editingJob)} className="job-modal-delete"><Trash2 size={13} /> Delete</Button>
            )}
            <Button variant="secondary" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSave} disabled={saving}>{editingJob ? 'Save changes' : 'Add'}</Button>
          </>
        }
      >
        <div className="job-modal-row">
          <div className="form-group">
            <label className="form-label" htmlFor="job-company">Company</label>
            <input id="job-company" value={formData.company} onChange={e => setField('company', e.target.value)} placeholder="Acme GmbH" autoFocus={!editingJob} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="job-position">Position</label>
            <input id="job-position" value={formData.position} onChange={e => setField('position', e.target.value)} placeholder="Software Engineer" />
          </div>
        </div>
        <div className="job-modal-row">
          <div className="form-group">
            <label className="form-label" htmlFor="job-status">Status</label>
            <select id="job-status" value={formData.status} onChange={e => changeFormStatus(e.target.value)}>
              {JOB_STATUSES.map(status => <option key={status.id} value={status.id}>{status.label} — {status.hint}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="job-applied">{formData.status === 'saved' ? 'Saved on' : 'Applied on'}</label>
            <input id="job-applied" type="date" value={formData.applied_at} onChange={e => setField('applied_at', e.target.value)} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="job-url">Link to the job post</label>
          <input id="job-url" value={formData.url} onChange={e => setField('url', e.target.value)} placeholder="https://…" />
        </div>
        <div className="job-modal-row">
          <div className="form-group">
            <label className="form-label" htmlFor="job-location">Location</label>
            <input id="job-location" value={formData.location} onChange={e => setField('location', e.target.value)} placeholder="Berlin · hybrid" />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="job-salary">Salary</label>
            <input id="job-salary" value={formData.salary} onChange={e => setField('salary', e.target.value)} placeholder="65–75k" />
          </div>
        </div>

        <div className="job-modal-section">
          <div className="job-modal-section-title"><CalendarClock size={14} /> Next step</div>
          <div className="job-modal-row">
            <div className="form-group">
              <label className="form-label" htmlFor="job-next-step">What happens next</label>
              <input id="job-next-step" value={formData.next_step} onChange={e => setField('next_step', e.target.value)} placeholder="Email the recruiter, prepare for the tech screen…" />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="job-follow-up">Follow up on</label>
              <input id="job-follow-up" type="date" value={formData.follow_up_at} onChange={e => setField('follow_up_at', e.target.value)} />
              <div className="job-date-shortcuts">
                <button type="button" onClick={() => setField('follow_up_at', addDays(today, 3))}>+3 days</button>
                <button type="button" onClick={() => setField('follow_up_at', addDays(today, 7))}>+1 week</button>
                <button type="button" onClick={() => setField('follow_up_at', addDays(today, 14))}>+2 weeks</button>
                {formData.follow_up_at && <button type="button" onClick={() => setField('follow_up_at', '')}>Clear</button>}
              </div>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="job-contact">Contact</label>
            <input id="job-contact" value={formData.contact} onChange={e => setField('contact', e.target.value)} placeholder="Name, role, email" />
          </div>
        </div>

        <div className="job-modal-section">
          <div className="job-modal-section-title"><FileText size={14} /> Job post</div>
          <textarea
            value={formData.job_description}
            onChange={e => setField('job_description', e.target.value)}
            placeholder="Paste the full job post once. Tailoring, the cover letter, research and review all start from it, and you keep a copy after the listing is taken down."
            rows={6}
            aria-label="Job post"
          />
          <div className="job-prepare">
            <span className="job-prepare-label">
              {hasJobPost ? 'Use this post to:' : 'Paste the job post to start from it in:'}
            </span>
            <Button variant="secondary" size="sm" disabled={saving || !hasJobPost} onClick={() => prepare('/optimize')}><Target size={13} /> Tailor resume</Button>
            <Button variant="secondary" size="sm" disabled={saving || !hasJobPost} onClick={() => prepare('/cover-letters')}><Mail size={13} /> Cover letter</Button>
            <Button variant="secondary" size="sm" disabled={saving || !hasJobPost} onClick={() => prepare('/critique')}><SearchCheck size={13} /> Review fit</Button>
            <Button variant="secondary" size="sm" disabled={saving || !formData.company.trim()} onClick={() => prepare('/company-research')}><Building2 size={13} /> Research company</Button>
          </div>
        </div>

        <div className="job-modal-row">
          <div className="form-group">
            <label className="form-label" htmlFor="job-resume">Resume version sent</label>
            <select id="job-resume" value={formData.resume_version_id} onChange={e => setField('resume_version_id', e.target.value)}>
              <option value="">None</option>
              {versions.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="job-notes">Notes</label>
            <textarea id="job-notes" value={formData.notes} onChange={e => setField('notes', e.target.value)} placeholder="Referral, impressions, things to remember…" rows={2} />
          </div>
        </div>

        {editingJob && (
          <div className="job-modal-section">
            <div className="job-modal-section-title"><Activity size={14} /> Activity</div>
            <div className="job-note-input">
              <input
                value={noteDraft}
                onChange={e => setNoteDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') addNote(); }}
                placeholder="Log what happened: called back, sent thank-you, tech screen booked…"
                aria-label="Add a note"
              />
              <Button variant="secondary" size="sm" onClick={addNote} disabled={!noteDraft.trim()}><Send size={13} /> Log</Button>
            </div>
            {events.length > 0 && (
              <ul className="job-events">
                {events.map(event => (
                  <li key={event.id} className={`job-event job-event-${event.kind}`}>
                    <span className="job-event-date">{formatDay(event.created_at)}</span>
                    <span>{eventText(event)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Modal>

      <Modal
        isOpen={!!showDeleteModal}
        onClose={() => setShowDeleteModal(null)}
        title="Delete Application"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowDeleteModal(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete}>Delete</Button>
          </>
        }
      >
        <p className="confirm-delete-text">
          Delete the application for <strong>{showDeleteModal?.position}</strong> at <strong>{showDeleteModal?.company}</strong>, including its activity log? This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
