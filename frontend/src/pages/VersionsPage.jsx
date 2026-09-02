import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, PenLine, Copy, Download, Star, Trash2, Layers, Loader, GitBranch, TextCursorInput } from 'lucide-react';
import { resumeApi } from '../api';
import { useToast } from '../App';
import Button from '../components/Button';
import Modal from '../components/Modal';
import './VersionsPage.css';

export default function VersionsPage() {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewModal, setShowNewModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(null);
  const [renameVersion, setRenameVersion] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [renaming, setRenaming] = useState(false);
  const [newForm, setNewForm] = useState({ name: '', description: '', baseVersionId: '' });
  const navigate = useNavigate();
  const addToast = useToast();

  const loadVersions = useCallback(async () => {
    try {
      const data = await resumeApi.list();
      setVersions(data);
      setNewForm(prev => ({
        ...prev,
        baseVersionId: prev.baseVersionId || String(data.find(v => v.is_current)?.id || data[0]?.id || ''),
      }));
    } catch (err) {
      addToast(err.message || 'Failed to load versions', 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    // Loading is intentionally initiated on mount and after version mutations.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadVersions();
  }, [loadVersions]);

  const handleCreate = async () => {
    if (!newForm.name.trim()) {
      addToast('Please enter a version name', 'warning');
      return;
    }
    try {
      let result;
      if (newForm.baseVersionId) {
        result = await resumeApi.duplicate(Number(newForm.baseVersionId), newForm.name);
        if (newForm.description.trim()) {
          result = await resumeApi.update(result.id, { description: newForm.description });
        }
      } else {
        result = await resumeApi.create({
          name: newForm.name,
          description: newForm.description,
          data: {
            personal_info: { name: '', title: '', address: '', phone: '', email: '', github: '', linkedin: '' },
            about_me: '', education: [], work_experience: [], projects: [], research: [],
            skills: [], certificates: [], languages: [], references: '',
          },
        });
      }
      setShowNewModal(false);
      setNewForm(prev => ({ name: '', description: '', baseVersionId: prev.baseVersionId }));
      addToast('Version created successfully', 'success');
      loadVersions();
      navigate(`/editor/${result.id}`);
    } catch (err) {
      addToast(err.message || 'Failed to create version', 'error');
    }
  };

  const handleDuplicate = async (version) => {
    try {
      await resumeApi.duplicate(version.id, `${version.name} (Copy)`);
      addToast('Version duplicated', 'success');
      loadVersions();
    } catch (err) {
      addToast(err.message || 'Failed to duplicate', 'error');
    }
  };

  const handleDelete = async () => {
    if (!showDeleteModal) return;
    try {
      await resumeApi.delete(showDeleteModal.id);
      setShowDeleteModal(null);
      addToast('Version deleted', 'success');
      loadVersions();
    } catch (err) {
      addToast(err.message || 'Failed to delete', 'error');
    }
  };

  const handleSetCurrent = async (id) => {
    try {
      await resumeApi.setCurrent(id);
      addToast('Set as current version', 'success');
      loadVersions();
    } catch (err) {
      addToast(err.message || 'Failed to set current', 'error');
    }
  };

  const openRename = (version) => {
    setRenameVersion(version);
    setRenameValue(version.name);
  };

  const handleRename = async () => {
    const name = renameValue.trim();
    if (!name) {
      addToast('Version name cannot be empty', 'warning');
      return;
    }
    setRenaming(true);
    try {
      await resumeApi.update(renameVersion.id, { name });
      setVersions(previous => previous.map(version => (
        version.id === renameVersion.id ? { ...version, name } : version
      )));
      setRenameVersion(null);
      setRenameValue('');
      addToast('Version renamed', 'success');
    } catch (err) {
      addToast(err.message || 'Failed to rename version', 'error');
    } finally {
      setRenaming(false);
    }
  };

  const handleDownload = (id) => {
    window.open(resumeApi.getDownloadUrl(id), '_blank');
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="versions-page">
      <div className="versions-header">
        <div>
          <div className="page-eyebrow"><GitBranch size={14} /> Resume library</div>
          <h1 className="versions-title">Versions</h1>
          <p className="page-subtitle">Keep your master resume safe and organize every tailored variation.</p>
        </div>
        <Button variant="primary" onClick={() => setShowNewModal(true)}><Plus size={14} /> New Version</Button>
      </div>

      <div className="versions-grid">
        {loading ? (
          <div className="version-empty">
            <div className="version-empty-icon"><Loader size={40} /></div>
            <div className="version-empty-text">Loading versions...</div>
          </div>
        ) : versions.length === 0 ? (
          <div className="version-empty">
            <div className="version-empty-icon"><Layers size={40} /></div>
            <div className="version-empty-text">No resume versions yet. Create your first one!</div>
          </div>
        ) : (
          versions.map(v => (
            <div className="version-card" key={v.id}>
              <div className="version-card-top">
                <span className="version-card-name">{v.name}</span>
                <div className="version-card-badges">
                  {v.name.startsWith('Draft ·') && <span className="version-card-badge draft">Draft</span>}
                  {v.is_current && <span className="version-card-badge">Current</span>}
                  <span className="version-card-badge template">{v.template_id || 'modern'}</span>
                </div>
              </div>
              {v.description && <div className="version-card-desc">{v.description}</div>}
              <div className="version-card-date">Created {formatDate(v.created_at)}</div>
              <div className="version-card-actions">
                <Button variant="primary" size="sm" onClick={() => navigate(`/editor/${v.id}`)}><PenLine size={12} /> Edit</Button>
                <Button variant="secondary" size="sm" onClick={() => openRename(v)}><TextCursorInput size={12} /> Rename</Button>
                <Button variant="secondary" size="sm" onClick={() => handleDuplicate(v)}><Copy size={12} /> Duplicate</Button>
                <Button variant="secondary" size="sm" onClick={() => handleDownload(v.id)}><Download size={12} /> PDF</Button>
                {!v.is_current && (
                  <Button variant="ghost" size="sm" onClick={() => handleSetCurrent(v.id)}><Star size={12} /> Set Current</Button>
                )}
                <Button variant="danger" size="sm" onClick={() => setShowDeleteModal(v)}><Trash2 size={12} /> Delete</Button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* New Version Modal */}
      <Modal
        isOpen={showNewModal}
        onClose={() => setShowNewModal(false)}
        title="New Resume Version"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowNewModal(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleCreate}>Create</Button>
          </>
        }
      >
        {versions.length > 0 && (
          <div className="form-group">
            <label className="form-label">Start From</label>
            <select
              value={newForm.baseVersionId}
              onChange={e => setNewForm(prev => ({ ...prev, baseVersionId: e.target.value }))}
            >
              {versions.map(v => <option key={v.id} value={v.id}>{v.name}{v.is_current ? ' (Current)' : ''}</option>)}
            </select>
            <div className="form-hint">Creates an independent copy. The source version stays unchanged.</div>
          </div>
        )}
        <div className="form-group">
          <label className="form-label">Version Name</label>
          <input
            value={newForm.name}
            onChange={e => setNewForm(prev => ({ ...prev, name: e.target.value }))}
            placeholder="e.g., Software Engineer - Google"
            autoFocus
          />
        </div>
        <div className="form-group">
          <label className="form-label">Description</label>
          <textarea
            value={newForm.description}
            onChange={e => setNewForm(prev => ({ ...prev, description: e.target.value }))}
            placeholder="Optional description..."
            rows={3}
          />
        </div>
      </Modal>

      <Modal
        isOpen={!!renameVersion}
        onClose={() => !renaming && setRenameVersion(null)}
        title="Rename Version"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRenameVersion(null)} disabled={renaming}>Cancel</Button>
            <Button variant="primary" onClick={handleRename} disabled={renaming || !renameValue.trim()}>
              {renaming ? <><Loader size={14} className="spin" /> Renaming…</> : 'Rename'}
            </Button>
          </>
        }
      >
        <div className="form-group">
          <label className="form-label">Version Name</label>
          <input
            value={renameValue}
            onChange={event => setRenameValue(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && renameValue.trim() && !renaming) handleRename();
            }}
            autoFocus
            maxLength={120}
          />
          <div className="form-hint">Only the label changes. Resume content and linked applications stay untouched.</div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!showDeleteModal}
        onClose={() => setShowDeleteModal(null)}
        title="Delete Version"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowDeleteModal(null)}>Cancel</Button>
            <Button variant="danger" onClick={handleDelete}>Delete</Button>
          </>
        }
      >
        <p className="confirm-delete-text">
          Are you sure you want to permanently delete <strong>{showDeleteModal?.name}</strong>? Download or duplicate it first if you may need it later. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
