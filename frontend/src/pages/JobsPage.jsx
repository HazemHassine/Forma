import { useState, useEffect, useCallback } from 'react';
import { Plus, PenLine, Trash2, Briefcase, Loader, Activity } from 'lucide-react';
import { jobApi, resumeApi } from '../api';
import { useToast } from '../App';
import Button from '../components/Button';
import Modal from '../components/Modal';
import { buildJobPayload } from '../jobPayload';
import './JobsPage.css';

const STATUS_OPTIONS = ['applied', 'interviewing', 'offer', 'rejected'];

const EMPTY_JOB = {
  company: '',
  position: '',
  url: '',
  status: 'applied',
  resume_version_id: '',
  notes: '',
  applied_at: new Date().toISOString().split('T')[0],
};

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState({ applied: 0, interviewing: 0, offer: 0, rejected: 0 });
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [sortField, setSortField] = useState('applied_at');
  const [sortDir, setSortDir] = useState('desc');
  const [showModal, setShowModal] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [formData, setFormData] = useState(EMPTY_JOB);
  const [showDeleteModal, setShowDeleteModal] = useState(null);
  const addToast = useToast();

  const loadData = useCallback(async () => {
    try {
      const [jobsData, statsData, versionsData] = await Promise.all([
        jobApi.list(),
        jobApi.stats().catch(() => ({ applied: 0, interviewing: 0, offer: 0, rejected: 0 })),
        resumeApi.list().catch(() => []),
      ]);
      setJobs(jobsData);
      setStats(statsData);
      setVersions(versionsData);
    } catch (err) {
      addToast(err.message || 'Failed to load jobs', 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    // Initial server data is loaded once and refreshed after mutations.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, [loadData]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const filtered = jobs
    .filter(j => filterStatus === 'all' || j.status === filterStatus)
    .sort((a, b) => {
      const av = a[sortField] || '';
      const bv = b[sortField] || '';
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });

  const openCreateModal = () => {
    setEditingJob(null);
    setFormData({ ...EMPTY_JOB, applied_at: new Date().toISOString().split('T')[0] });
    setShowModal(true);
  };

  const openEditModal = (job) => {
    setEditingJob(job);
    setFormData({
      company: job.company || '',
      position: job.position || '',
      url: job.url || '',
      status: job.status || 'applied',
      resume_version_id: job.resume_version_id ?? '',
      notes: job.notes || '',
      applied_at: job.applied_at ? job.applied_at.slice(0, 10) : '',
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formData.company.trim() || !formData.position.trim()) {
      addToast('Company and position are required', 'warning');
      return;
    }
    const payload = buildJobPayload(formData);
    try {
      if (editingJob) {
        await jobApi.update(editingJob.id, payload);
        addToast('Job updated', 'success');
      } else {
        await jobApi.create(payload);
        addToast('Job created', 'success');
      }
      setShowModal(false);
      loadData();
    } catch (err) {
      addToast(err.message || 'Failed to save job', 'error');
    }
  };

  const handleDelete = async () => {
    if (!showDeleteModal) return;
    try {
      await jobApi.delete(showDeleteModal.id);
      setShowDeleteModal(null);
      addToast('Job deleted', 'success');
      loadData();
    } catch (err) {
      addToast(err.message || 'Failed to delete', 'error');
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="jobs-page">
      <div className="jobs-header">
        <div>
          <div className="page-eyebrow"><Activity size={14} /> Application pipeline</div>
          <h1 className="jobs-title">Applications</h1>
          <p className="page-subtitle">Track every opportunity and the exact resume you sent.</p>
        </div>
        <Button variant="primary" onClick={openCreateModal}><Plus size={14} /> New Application</Button>
      </div>

      <div className="jobs-stats">
        <div className="stat-card stat-applied">
          <div className="stat-card-value">{stats.applied || 0}</div>
          <div className="stat-card-label">Applied</div>
        </div>
        <div className="stat-card stat-interviewing">
          <div className="stat-card-value">{stats.interviewing || 0}</div>
          <div className="stat-card-label">Interviewing</div>
        </div>
        <div className="stat-card stat-offer">
          <div className="stat-card-value">{stats.offer || 0}</div>
          <div className="stat-card-label">Offers</div>
        </div>
        <div className="stat-card stat-rejected">
          <div className="stat-card-value">{stats.rejected || 0}</div>
          <div className="stat-card-label">Rejected</div>
        </div>
      </div>

      <div className="jobs-toolbar">
        <select className="jobs-filter-select" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="all">All Statuses</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="jobs-empty">
          <div className="jobs-empty-icon"><Loader size={40} /></div>
          <div>Loading applications...</div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="jobs-empty">
          <div className="jobs-empty-icon"><Briefcase size={40} /></div>
          <div>{jobs.length === 0 ? 'No job applications yet. Track your first one!' : 'No jobs match the current filter.'}</div>
        </div>
      ) : (
        <div className="jobs-table-wrapper">
          <table className="jobs-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('company')}>Company {sortField === 'company' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th onClick={() => handleSort('position')}>Position {sortField === 'position' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th onClick={() => handleSort('status')}>Status {sortField === 'status' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th>Resume Version</th>
                <th onClick={() => handleSort('applied_at')}>Applied {sortField === 'applied_at' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(job => (
                <tr key={job.id} onClick={() => openEditModal(job)}>
                  <td><span className="job-company">{job.company}</span></td>
                  <td><span className="job-position">{job.position}</span></td>
                  <td><span className={`status-badge status-${job.status}`}>{job.status}</span></td>
                  <td><span className="job-version-name">{job.resume_version_name || '—'}</span></td>
                  <td><span className="job-date">{formatDate(job.applied_at)}</span></td>
                  <td>
                    <div className="job-actions" onClick={e => e.stopPropagation()}>
                      <Button variant="ghost" size="sm" onClick={() => openEditModal(job)}><PenLine size={12} /> Edit</Button>
                      <Button variant="danger" size="sm" onClick={() => setShowDeleteModal(job)}><Trash2 size={12} /></Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add/Edit Job Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingJob ? 'Edit Application' : 'New Application'}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowModal(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSave}>{editingJob ? 'Update' : 'Create'}</Button>
          </>
        }
      >
        <div className="job-modal-row">
          <div className="form-group">
            <label className="form-label">Company</label>
            <input
              value={formData.company}
              onChange={e => setFormData(prev => ({ ...prev, company: e.target.value }))}
              placeholder="Google"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label className="form-label">Position</label>
            <input
              value={formData.position}
              onChange={e => setFormData(prev => ({ ...prev, position: e.target.value }))}
              placeholder="Software Engineer"
            />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">URL</label>
          <input
            value={formData.url}
            onChange={e => setFormData(prev => ({ ...prev, url: e.target.value }))}
            placeholder="https://careers.google.com/..."
          />
        </div>
        <div className="job-modal-row">
          <div className="form-group">
            <label className="form-label">Status</label>
            <select value={formData.status} onChange={e => setFormData(prev => ({ ...prev, status: e.target.value }))}>
              {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Resume Version</label>
            <select value={formData.resume_version_id} onChange={e => setFormData(prev => ({ ...prev, resume_version_id: e.target.value }))}>
              <option value="">None</option>
              {versions.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Applied Date</label>
          <input
            type="date"
            value={formData.applied_at}
            onChange={e => setFormData(prev => ({ ...prev, applied_at: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Notes</label>
          <textarea
            value={formData.notes}
            onChange={e => setFormData(prev => ({ ...prev, notes: e.target.value }))}
            placeholder="Any notes about this application..."
            rows={3}
          />
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
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
          Are you sure you want to delete the application for <strong>{showDeleteModal?.position}</strong> at <strong>{showDeleteModal?.company}</strong>?
        </p>
      </Modal>
    </div>
  );
}
