import { useCallback, useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { PenLine, Layers, Briefcase, Target, Mail, Command, Building2, Bot, Database, CircleAlert, SearchCheck, Sparkles, Home, RefreshCw } from 'lucide-react';
import { useAIProvider } from '../App';
import { systemApi } from '../api';
import './Layout.css';

export default function Layout({ children }) {
  const { aiProvider, setAIProvider } = useAIProvider();
  const [systemStatus, setSystemStatus] = useState(null);
  const [statusError, setStatusError] = useState(false);

  const [checking, setChecking] = useState(false);

  const checkStatus = useCallback(() => {
    setChecking(true);
    return systemApi.status()
      .then(status => {
        setSystemStatus(previous => {
          // The database came back: reload so every page fetches real data.
          if (previous?.database_status === 'unavailable' && status.database_status === 'connected') {
            window.location.reload();
          }
          return status;
        });
        setStatusError(false);
      })
      .catch(() => setStatusError(true))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    checkStatus();
  }, [checkStatus]);

  const databaseDown = systemStatus?.database_status === 'unavailable';

  useEffect(() => {
    // While something is wrong, keep checking so recovery needs no restart.
    if (!databaseDown && !statusError) return undefined;
    const timer = window.setInterval(checkStatus, 30000);
    return () => window.clearInterval(timer);
  }, [databaseDown, statusError, checkStatus]);

  const selectedAI = systemStatus?.ai?.[aiProvider];

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-brand-icon">F</div>
            <div>
              <div className="sidebar-brand-text">Forma</div>
            </div>
          </div>
        </div>
        <nav className="sidebar-nav">
          <NavLink to="/" end aria-label="Home" title="Home" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Home size={16} /></span>
            <span><strong>Home</strong></span>
          </NavLink>
          <div className="sidebar-nav-label sidebar-nav-label-spaced">Create</div>
          <NavLink to="/editor" aria-label="Resume" title="Resume" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><PenLine size={16} /></span>
            <span><strong>Resume</strong></span>
          </NavLink>
          <NavLink to="/versions" aria-label="Versions" title="Versions" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Layers size={16} /></span>
            <span><strong>Versions</strong></span>
          </NavLink>
          <NavLink to="/context" aria-label="Context Vault" title="Context Vault" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Sparkles size={16} /></span>
            <span><strong>Context Vault</strong><small className="nav-new">AI</small></span>
          </NavLink>
          <div className="sidebar-nav-label sidebar-nav-label-spaced">Workflow</div>
          <NavLink to="/jobs" aria-label="Applications" title="Applications" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Briefcase size={16} /></span>
            <span><strong>Applications</strong></span>
          </NavLink>
          <NavLink to="/optimize" aria-label="Tailor resume" title="Tailor resume" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Target size={16} /></span>
            <span><strong>Tailor</strong><small className="nav-new">AI</small></span>
          </NavLink>
          <NavLink to="/critique" aria-label="Review" title="Review" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><SearchCheck size={16} /></span>
            <span><strong>Critique</strong><small className="nav-new">AI</small></span>
          </NavLink>
          <NavLink to="/cover-letters" aria-label="Cover letters" title="Cover letters" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Mail size={16} /></span>
            <span><strong>Cover letters</strong></span>
          </NavLink>
          <NavLink to="/company-research" aria-label="Company researcher" title="Company researcher" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Building2 size={16} /></span>
            <span><strong>Company researcher</strong><small className="nav-new">AI</small></span>
          </NavLink>
        </nav>
        <div className="sidebar-footer">
          <div className={`system-status ${statusError || databaseDown ? 'error' : ''}`}>
            {statusError || databaseDown ? <CircleAlert size={14} /> : <Database size={14} />}
            <span>
              {statusError
                ? 'Backend unavailable'
                : databaseDown
                  ? `${systemStatus.database === 'supabase' ? 'Supabase' : 'Database'} unreachable`
                : systemStatus
                  ? `${systemStatus.database === 'supabase' ? 'Supabase' : 'Local data'} connected`
                  : 'Checking backend…'}
            </span>
          </div>
          <div className="provider-selector">
            <label htmlFor="ai-provider"><Bot size={14} /> AI provider</label>
            <select
              id="ai-provider"
              value={aiProvider}
              onChange={event => setAIProvider(event.target.value)}
              aria-label="AI provider"
            >
              <option value="gemini">Gemini</option>
              <option value="chatgpt">ChatGPT</option>
            </select>
            {selectedAI && !selectedAI.configured && (
              <div className="provider-warning">Add its API key in backend/.env</div>
            )}
          </div>
          <div className="sidebar-command">
            <Command size={14} />
            <span>Everything autosaves</span>
            <kbd>⌘ S</kbd>
          </div>
        </div>
      </aside>
      <main className="layout-main">
        {(databaseDown || statusError) && (
          <div className="system-banner" role="alert">
            <CircleAlert size={18} />
            <div>
              <strong>
                {statusError ? 'Forma cannot reach its backend' : 'Your data is not reachable right now'}
              </strong>
              <p>
                {statusError
                  ? 'Check that the backend is running (docker compose ps, then docker compose logs backend).'
                  : systemStatus.database_error}
              </p>
            </div>
            <button type="button" onClick={checkStatus} disabled={checking}>
              <RefreshCw size={13} className={checking ? 'spinning' : ''} /> {checking ? 'Checking…' : 'Check again'}
            </button>
          </div>
        )}
        <div className="layout-content">
          {children}
        </div>
      </main>
    </div>
  );
}
