import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Sparkles,
  Plus,
  Trash2,
  Edit2,
  ExternalLink,
  Eye,
  RefreshCw,
  Search,
  CheckCircle2,
  ToggleLeft,
  ToggleRight,
  Database,
  Layers,
  FileText,
  Copy,
  Check,
  Zap,
} from 'lucide-react';
import { contextApi, resumeApi, formatApiError } from '../api';
import { useToast, useAIProvider } from '../App';
import Button from '../components/Button';
import Modal from '../components/Modal';
import './ContextPage.css';

const CATEGORIES = [
  { id: 'all', label: 'All Cards', icon: Layers },
  { id: 'profile_persona', label: 'Persona & Ethos', color: '#4f46e5' },
  { id: 'achievement_metric', label: 'Metrics & Scale', color: '#059669' },
  { id: 'experience_project', label: 'Deep Work & Projects', color: '#0284c7' },
  { id: 'skills_arsenal', label: 'Tech Arsenal', color: '#d97706' },
  { id: 'education_credential', label: 'Credentials', color: '#7c3aed' },
  { id: 'proof_link', label: 'Verifiable Proof', color: '#e11d48' },
];

export default function ContextPage() {
  const addToast = useToast();
  const { aiProvider } = useAIProvider();

  // Navigation tab
  const [activeTab, setActiveTab] = useState('cards'); // 'cards' | 'sources' | 'persona'

  // Data states
  const [sources, setSources] = useState([]);
  const [items, setItems] = useState([]);
  const [profile, setProfile] = useState(null);
  const [stats, setStats] = useState(null);
  const [resumeVersions, setResumeVersions] = useState([]);

  // Filter states
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showActiveOnly, setShowActiveOnly] = useState(false);

  // Loading states
  const [loading, setLoading] = useState(true);
  const [synthesizing, setSynthesizing] = useState(false);

  // Modal states
  const [isAddSourceModalOpen, setIsAddSourceModalOpen] = useState(false);
  const [isAddItemModalOpen, setIsAddItemModalOpen] = useState(false);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [isViewSourceModalOpen, setIsViewSourceModalOpen] = useState(false);
  const [selectedSourceForView, setSelectedSourceForView] = useState(null);

  // Form states - Add Source
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceType, setSourceType] = useState('dump');
  const [sourceContent, setSourceContent] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');

  // Form states - Add/Edit Item
  const [editingItem, setEditingItem] = useState(null);
  const [itemCategory, setItemCategory] = useState('experience_project');
  const [itemTitle, setItemTitle] = useState('');
  const [itemContent, setItemContent] = useState('');
  const [itemTags, setItemTags] = useState('');

  // Preview data
  const [previewData, setPreviewData] = useState(null);
  const [copiedPreview, setCopiedPreview] = useState(false);

  // Fetch all initial data
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [sourcesRes, itemsRes, profileRes, statsRes, versionsRes] = await Promise.all([
        contextApi.listSources(),
        contextApi.listItems(),
        contextApi.getProfile().catch(() => null),
        contextApi.getStats().catch(() => null),
        resumeApi.list().catch(() => []),
      ]);
      setSources(sourcesRes || []);
      setItems(itemsRes || []);
      setProfile(profileRes || null);
      setStats(statsRes || null);
      setResumeVersions(versionsRes || []);
    } catch (err) {
      addToast(`Failed to load context: ${formatApiError(err)}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, [loadData]);

  // Handle Ingest Source
  const handleAddSource = async (e) => {
    e.preventDefault();
    if (!sourceTitle.trim() || !sourceContent.trim()) {
      addToast('Please enter both title and content', 'error');
      return;
    }
    try {
      await contextApi.addSource({
        title: sourceTitle.trim(),
        source_type: sourceType,
        content: sourceContent.trim(),
        url: sourceUrl.trim() || null,
        is_active: true,
      });
      addToast('Context source added successfully', 'success');
      setIsAddSourceModalOpen(false);
      setSourceTitle('');
      setSourceContent('');
      setSourceUrl('');
      loadData();
    } catch (err) {
      addToast(`Failed to add source: ${formatApiError(err)}`, 'error');
    }
  };

  // Handle Delete Source
  const handleDeleteSource = async (sourceId) => {
    if (!window.confirm('Are you sure you want to delete this source?')) return;
    try {
      await contextApi.deleteSource(sourceId);
      addToast('Source deleted', 'info');
      loadData();
    } catch (err) {
      addToast(`Failed to delete source: ${formatApiError(err)}`, 'error');
    }
  };

  // Handle Import from Resume
  const handleImportResume = async (versionId) => {
    try {
      await contextApi.importResume(versionId);
      addToast('Resume imported into Context Vault', 'success');
      loadData();
    } catch (err) {
      addToast(`Import failed: ${formatApiError(err)}`, 'error');
    }
  };

  // Handle AI Knowledge Distillation (Synthesize)
  const handleSynthesize = async () => {
    if (sources.length === 0) {
      addToast('Add at least one raw source or import a resume first', 'error');
      return;
    }
    setSynthesizing(true);
    try {
      const res = await contextApi.synthesize(aiProvider, {
        replace_existing: false,
      });
      addToast(
        `Synthesized ${res.extracted_items_count} verified knowledge cards using ${aiProvider === 'chatgpt' ? 'ChatGPT' : 'Gemini'}!`,
        'success'
      );
      loadData();
    } catch (err) {
      addToast(`Synthesis failed: ${formatApiError(err)}`, 'error');
    } finally {
      setSynthesizing(false);
    }
  };

  // Handle Toggle Item Active
  const handleToggleItem = async (itemId) => {
    try {
      const updated = await contextApi.toggleItem(itemId);
      setItems((prev) => prev.map((item) => (item.id === itemId ? updated : item)));
      const statsRes = await contextApi.getStats();
      setStats(statsRes);
    } catch (err) {
      addToast(`Toggle failed: ${formatApiError(err)}`, 'error');
    }
  };

  // Handle Save (Create/Update) Item
  const handleSaveItem = async (e) => {
    e.preventDefault();
    if (!itemTitle.trim() || !itemContent.trim()) {
      addToast('Title and content are required', 'error');
      return;
    }
    const tagsArray = itemTags
      .split(',')
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

    try {
      if (editingItem) {
        await contextApi.updateItem(editingItem.id, {
          category: itemCategory,
          title: itemTitle.trim(),
          content: itemContent.trim(),
          tags: tagsArray,
        });
        addToast('Knowledge card updated', 'success');
      } else {
        await contextApi.addItem({
          category: itemCategory,
          title: itemTitle.trim(),
          content: itemContent.trim(),
          tags: tagsArray,
          is_active: true,
        });
        addToast('Knowledge card added', 'success');
      }
      setIsAddItemModalOpen(false);
      setEditingItem(null);
      setItemTitle('');
      setItemContent('');
      setItemTags('');
      loadData();
    } catch (err) {
      addToast(`Failed to save item: ${formatApiError(err)}`, 'error');
    }
  };

  // Open Edit Item Modal
  const handleOpenEditItem = (item) => {
    setEditingItem(item);
    setItemCategory(item.category);
    setItemTitle(item.title);
    setItemContent(item.content);
    setItemTags((item.tags || []).join(', '));
    setIsAddItemModalOpen(true);
  };

  // Handle Delete Item
  const handleDeleteItem = async (itemId) => {
    if (!window.confirm('Delete this knowledge card?')) return;
    try {
      await contextApi.deleteItem(itemId);
      addToast('Item removed', 'info');
      loadData();
    } catch (err) {
      addToast(`Failed to delete item: ${formatApiError(err)}`, 'error');
    }
  };

  // Handle Preview Assembled Context
  const handleOpenPreview = async () => {
    try {
      const res = await contextApi.preview({ maxItems: 20 });
      setPreviewData(res);
      setIsPreviewModalOpen(true);
      setCopiedPreview(false);
    } catch (err) {
      addToast(`Failed to generate preview: ${formatApiError(err)}`, 'error');
    }
  };

  const handleCopyPreview = () => {
    if (previewData?.assembled_prompt) {
      navigator.clipboard.writeText(previewData.assembled_prompt);
      setCopiedPreview(true);
      setTimeout(() => setCopiedPreview(false), 2000);
      addToast('Assembled context prompt copied to clipboard', 'info');
    }
  };

  // Filtered knowledge cards
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (selectedCategory !== 'all' && item.category !== selectedCategory) {
        return false;
      }
      if (showActiveOnly && !item.is_active) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = item.title?.toLowerCase().includes(q);
        const matchContent = item.content?.toLowerCase().includes(q);
        const matchTags = (item.tags || []).some((t) => t.toLowerCase().includes(q));
        if (!matchTitle && !matchContent && !matchTags) return false;
      }
      return true;
    });
  }, [items, selectedCategory, showActiveOnly, searchQuery]);

  return (
    <div className="context-page">
      {/* Header */}
      <header className="context-header">
        <div className="context-header-main">
          <div className="context-badge">
            <Sparkles size={13} /> Deep Context Vault
          </div>
          <h1 className="context-title">Candidate Context Vault</h1>
          <p className="context-subtitle">
            Ingest and curate your complete professional context: AI interview transcripts, deep project histories, exact scale metrics, and GitHub repositories. All AI tools in Forma draw upon this verified vault.
          </p>
        </div>

        <div className="context-header-actions">
          <Button variant="secondary" onClick={handleOpenPreview} title="Inspect compiled AI prompt">
            <Eye size={15} /> Preview AI Context
          </Button>
          <Button
            variant="primary"
            onClick={handleSynthesize}
            disabled={synthesizing || sources.length === 0}
            title="Distill raw sources into structured cards"
          >
            {synthesizing ? (
              <>
                <RefreshCw size={15} className="spin" /> Synthesizing with {aiProvider === 'chatgpt' ? 'ChatGPT' : 'Gemini'}…
              </>
            ) : (
              <>
                <Zap size={15} /> Synthesize Context
              </>
            )}
          </Button>
        </div>
      </header>

      {/* Metrics Banner */}
      <div className="context-stats-grid">
        <div className="stat-card">
          <div className="stat-label">Active Knowledge Cards</div>
          <div className="stat-value">
            {stats ? `${stats.active_items} / ${stats.total_items}` : '0'}
          </div>
          <div className="stat-hint">Included in AI generations</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Raw Sources Ingested</div>
          <div className="stat-value">{stats ? stats.total_sources : sources.length}</div>
          <div className="stat-hint">Dumps, links, notes</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Vault Prompt Density</div>
          <div className="stat-value">
            ~{stats ? stats.estimated_tokens.toLocaleString() : '0'} <small>tokens</small>
          </div>
          <div className="stat-hint">Compact, high-density facts</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Intelligence Status</div>
          <div className="stat-value status-active">
            <span className="pulse-dot" /> Connected
          </div>
          <div className="stat-hint">
            Active for Critique, Tailor & Letters
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="context-nav-tabs">
        <button
          type="button"
          className={`nav-tab ${activeTab === 'cards' ? 'active' : ''}`}
          onClick={() => setActiveTab('cards')}
        >
          <Layers size={15} /> Knowledge Cards ({items.length})
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === 'sources' ? 'active' : ''}`}
          onClick={() => setActiveTab('sources')}
        >
          <Database size={15} /> Raw Sources ({sources.length})
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === 'persona' ? 'active' : ''}`}
          onClick={() => setActiveTab('persona')}
        >
          <Sparkles size={15} /> Executive Persona
        </button>
      </div>

      {/* TAB 1: KNOWLEDGE CARDS */}
      {activeTab === 'cards' && (
        <div className="cards-view">
          {/* Controls bar */}
          <div className="cards-controls-bar">
            <div className="search-box">
              <Search size={15} className="search-icon" />
              <input
                type="text"
                placeholder="Search knowledge by keyword, metric, tag..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="controls-actions">
              <label className="filter-toggle">
                <input
                  type="checkbox"
                  checked={showActiveOnly}
                  onChange={(e) => setShowActiveOnly(e.target.checked)}
                />
                Active only
              </label>
              <Button
                variant="secondary"
                onClick={() => {
                  setEditingItem(null);
                  setItemCategory('experience_project');
                  setItemTitle('');
                  setItemContent('');
                  setItemTags('');
                  setIsAddItemModalOpen(true);
                }}
              >
                <Plus size={15} /> Add Custom Card
              </Button>
            </div>
          </div>

          {/* Category Chips */}
          <div className="category-chips">
            {CATEGORIES.map((cat) => {
              const count =
                cat.id === 'all'
                  ? items.length
                  : items.filter((i) => i.category === cat.id).length;
              return (
                <button
                  type="button"
                  key={cat.id}
                  className={`category-chip ${selectedCategory === cat.id ? 'active' : ''}`}
                  onClick={() => setSelectedCategory(cat.id)}
                >
                  {cat.label} <span className="chip-count">{count}</span>
                </button>
              );
            })}
          </div>

          {/* Cards Grid */}
          {loading ? (
            <div className="loading-state">
              <RefreshCw size={24} className="spin" />
              <p>Loading your context vault…</p>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="empty-vault-state">
              <Database size={40} className="empty-icon" />
              <h3>No knowledge cards match your filter</h3>
              <p>
                {items.length === 0
                  ? 'Your Context Vault is empty. Ingest your background information to start making Forma smarter!'
                  : 'Try clearing your search or category filter.'}
              </p>
              {items.length === 0 && (
                <div className="empty-actions">
                  <Button
                    variant="primary"
                    onClick={() => {
                      setSourceType('dump');
                      setIsAddSourceModalOpen(true);
                    }}
                  >
                    <Plus size={15} /> Paste Information Dump
                  </Button>
                  {resumeVersions.length > 0 && (
                    <Button
                      variant="secondary"
                      onClick={() => handleImportResume(resumeVersions[0].id)}
                    >
                      <FileText size={15} /> Import from Active Resume
                    </Button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="cards-grid">
              {filteredItems.map((item) => {
                const categoryDef =
                  CATEGORIES.find((c) => c.id === item.category) || {
                    label: item.category,
                    color: '#6b7280',
                  };
                return (
                  <div
                    key={item.id}
                    className={`context-card ${item.is_active ? 'active' : 'inactive'}`}
                  >
                    <div className="card-header">
                      <span
                        className="card-category-badge"
                        style={{ backgroundColor: `${categoryDef.color}15`, color: categoryDef.color }}
                      >
                        {categoryDef.label}
                      </span>
                      <button
                        type="button"
                        className="card-toggle-btn"
                        onClick={() => handleToggleItem(item.id)}
                        title={item.is_active ? 'Active in AI tools (click to mute)' : 'Muted (click to activate)'}
                      >
                        {item.is_active ? (
                          <ToggleRight size={22} className="toggle-icon on" />
                        ) : (
                          <ToggleLeft size={22} className="toggle-icon off" />
                        )}
                      </button>
                    </div>

                    <h4 className="card-title">{item.title}</h4>
                    <p className="card-content">{item.content}</p>

                    {item.tags && item.tags.length > 0 && (
                      <div className="card-tags">
                        {item.tags.map((tag, idx) => (
                          <span
                            key={idx}
                            className="tag-pill"
                            onClick={() => setSearchQuery(tag)}
                            title={`Filter by "${tag}"`}
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="card-footer">
                      <span className="card-date">
                        {new Date(item.updated_at).toLocaleDateString()}
                      </span>
                      <div className="card-actions">
                        <button
                          type="button"
                          className="action-icon-btn"
                          onClick={() => handleOpenEditItem(item)}
                          title="Edit Card"
                        >
                          <Edit2 size={13} />
                        </button>
                        <button
                          type="button"
                          className="action-icon-btn danger"
                          onClick={() => handleDeleteItem(item.id)}
                          title="Delete Card"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: RAW SOURCES */}
      {activeTab === 'sources' && (
        <div className="sources-view">
          <div className="sources-action-bar">
            <div>
              <h3>Raw Ingestion Sources</h3>
              <p className="sources-desc">
                Paste conversational AI dumps, notes, and links. Forma’s synthesis engine distills them into searchable knowledge cards.
              </p>
            </div>
            <div className="sources-buttons">
              {resumeVersions.length > 0 && (
                <Button
                  variant="secondary"
                  onClick={() => handleImportResume(resumeVersions[0].id)}
                  title="Import your current CV as a starting source"
                >
                  <FileText size={15} /> Import Current CV
                </Button>
              )}
              <Button
                variant="primary"
                onClick={() => {
                  setSourceTitle('');
                  setSourceContent('');
                  setSourceUrl('');
                  setIsAddSourceModalOpen(true);
                }}
              >
                <Plus size={15} /> Ingest New Source
              </Button>
            </div>
          </div>

          {sources.length === 0 ? (
            <div className="empty-sources-state">
              <Database size={40} className="empty-icon" />
              <h4>No sources added yet</h4>
              <p>
                Prompt an AI: &ldquo;Give me everything worth knowing about me across my entire career, projects, and skills&rdquo; and paste it here!
              </p>
            </div>
          ) : (
            <div className="sources-list">
              {sources.map((s) => (
                <div key={s.id} className="source-row">
                  <div className="source-info">
                    <div className="source-title-line">
                      <span className={`source-badge ${s.source_type}`}>
                        {s.source_type}
                      </span>
                      <strong className="source-title">{s.title}</strong>
                      {s.url && (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noreferrer"
                          className="source-link"
                          title="Open URL"
                        >
                          <ExternalLink size={13} />
                        </a>
                      )}
                    </div>
                    <div className="source-meta">
                      <span>{s.content.length.toLocaleString()} characters</span>
                      <span>•</span>
                      <span>Added {new Date(s.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="source-snippet">
                      {s.content.length > 200 ? `${s.content.slice(0, 200)}…` : s.content}
                    </p>
                  </div>
                  <div className="source-row-actions">
                    <button
                      type="button"
                      className="source-btn"
                      onClick={() => {
                        setSelectedSourceForView(s);
                        setIsViewSourceModalOpen(true);
                      }}
                      title="View full source"
                    >
                      <Eye size={14} /> View
                    </button>
                    <button
                      type="button"
                      className="source-btn danger"
                      onClick={() => handleDeleteSource(s.id)}
                      title="Delete source"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: EXECUTIVE PERSONA */}
      {activeTab === 'persona' && (
        <div className="persona-view">
          {profile ? (
            <div className="persona-content-card">
              <div className="persona-section">
                <h3>Executive Summary & Positioning</h3>
                <p className="persona-summary">{profile.summary}</p>
              </div>

              {profile.key_differentiators && profile.key_differentiators.length > 0 && (
                <div className="persona-section">
                  <h3>Core Differentiators</h3>
                  <ul className="differentiators-list">
                    {profile.key_differentiators.map((diff, i) => (
                      <li key={i}>
                        <CheckCircle2 size={16} className="check-icon" />
                        <span>{diff}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {profile.target_roles && profile.target_roles.length > 0 && (
                <div className="persona-section">
                  <h3>Optimal Target Roles</h3>
                  <div className="target-roles-pills">
                    {profile.target_roles.map((role, i) => (
                      <span key={i} className="role-pill">
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-persona-state">
              <Sparkles size={36} className="empty-icon" />
              <h3>Executive Persona Not Synthesized Yet</h3>
              <p>
                Add raw sources into the vault and click &ldquo;Synthesize Context&rdquo; to automatically distill your executive positioning and differentiators.
              </p>
              <Button
                variant="primary"
                onClick={handleSynthesize}
                disabled={synthesizing || sources.length === 0}
              >
                Synthesize Context Now
              </Button>
            </div>
          )}
        </div>
      )}

      {/* MODAL: Ingest Source */}
      <Modal
        isOpen={isAddSourceModalOpen}
        onClose={() => setIsAddSourceModalOpen(false)}
        title="Ingest Background Source"
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsAddSourceModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleAddSource}>
              Add to Vault
            </Button>
          </>
        }
      >
        <form onSubmit={handleAddSource} className="context-modal-form">
          <div className="form-group">
            <label className="form-label">Source Title</label>
            <input
              type="text"
              placeholder="e.g. Master Bio Dump, GitHub Deep Dive, Tech Lead Case Study"
              value={sourceTitle}
              onChange={(e) => setSourceTitle(e.target.value)}
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group flex-1">
              <label className="form-label">Source Type</label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
              >
                <option value="dump">AI Information Dump</option>
                <option value="link">External Profile / Repo Link</option>
                <option value="note">Career & Project Notes</option>
              </select>
            </div>
            <div className="form-group flex-2">
              <label className="form-label">Reference URL (Optional)</label>
              <input
                type="url"
                placeholder="https://github.com/my-profile or website"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              Source Content (Paste uncompressed text, notes, or AI dump)
            </label>
            <textarea
              rows={9}
              placeholder="Paste your extensive background information, interview transcripts, project notes, or accomplishments..."
              value={sourceContent}
              onChange={(e) => setSourceContent(e.target.value)}
              required
            />
          </div>
        </form>
      </Modal>

      {/* MODAL: Add/Edit Knowledge Card */}
      <Modal
        isOpen={isAddItemModalOpen}
        onClose={() => setIsAddItemModalOpen(false)}
        title={editingItem ? 'Edit Knowledge Card' : 'Add Knowledge Card'}
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsAddItemModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSaveItem}>
              {editingItem ? 'Save Changes' : 'Create Card'}
            </Button>
          </>
        }
      >
        <form onSubmit={handleSaveItem} className="context-modal-form">
          <div className="form-group">
            <label className="form-label">Category</label>
            <select
              value={itemCategory}
              onChange={(e) => setItemCategory(e.target.value)}
            >
              <option value="profile_persona">Persona & Ethos</option>
              <option value="achievement_metric">Metrics & Scale</option>
              <option value="experience_project">Deep Work & Projects</option>
              <option value="skills_arsenal">Tech Arsenal</option>
              <option value="education_credential">Credentials</option>
              <option value="proof_link">Verifiable Proof</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Card Title</label>
            <input
              type="text"
              placeholder="e.g. Distributed Event Pipeline Scale"
              value={itemTitle}
              onChange={(e) => setItemTitle(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Content (Detailed facts, metrics, outcomes)</label>
            <textarea
              rows={4}
              placeholder="2-4 sentences with exact numbers, technologies, and challenges overcome..."
              value={itemContent}
              onChange={(e) => setItemContent(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Tags (comma-separated)</label>
            <input
              type="text"
              placeholder="python, distributed-systems, kafka, latency"
              value={itemTags}
              onChange={(e) => setItemTags(e.target.value)}
            />
          </div>
        </form>
      </Modal>

      {/* MODAL: View Full Source */}
      <Modal
        isOpen={isViewSourceModalOpen}
        onClose={() => setIsViewSourceModalOpen(false)}
        title={selectedSourceForView?.title || 'Source View'}
        wide
        footer={
          <Button variant="secondary" onClick={() => setIsViewSourceModalOpen(false)}>
            Close
          </Button>
        }
      >
        {selectedSourceForView && (
          <div className="source-detail-content">
            {selectedSourceForView.url && (
              <div className="detail-url">
                <strong>Link: </strong>
                <a href={selectedSourceForView.url} target="_blank" rel="noreferrer">
                  {selectedSourceForView.url}
                </a>
              </div>
            )}
            <pre className="source-pre">{selectedSourceForView.content}</pre>
          </div>
        )}
      </Modal>

      {/* MODAL: Preview Assembled AI Prompt */}
      <Modal
        isOpen={isPreviewModalOpen}
        onClose={() => setIsPreviewModalOpen(false)}
        title="Compiled AI Context Vault Preview"
        wide
        footer={
          <>
            <Button variant="secondary" onClick={handleCopyPreview}>
              {copiedPreview ? <Check size={14} /> : <Copy size={14} />}
              {copiedPreview ? 'Copied!' : 'Copy Markdown'}
            </Button>
            <Button variant="primary" onClick={() => setIsPreviewModalOpen(false)}>
              Done
            </Button>
          </>
        }
      >
        <div className="preview-modal-body">
          <p className="preview-explanation">
            This is the exact, bounded knowledge block synthesized from your active cards and injected into Forma&rsquo;s AI models (Critique, Tailor, Suggestions, Cover Letters).
          </p>
          <div className="preview-stats-bar">
            <span>Active Cards: {previewData?.item_count}</span>
            <span>•</span>
            <span>Estimated Token Size: ~{previewData?.estimated_tokens} tokens</span>
          </div>
          <pre className="preview-markdown">{previewData?.assembled_prompt || 'No active context cards.'}</pre>
        </div>
      </Modal>
    </div>
  );
}
