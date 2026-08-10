import { NavLink } from 'react-router-dom';
import { PenLine, Layers, Briefcase, Target, Mail, Command, Building2, Bot } from 'lucide-react';
import { useAIProvider } from '../App';
import './Layout.css';

export default function Layout({ children }) {
  const { aiProvider, setAIProvider } = useAIProvider();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-brand-icon">F</div>
            <div>
              <div className="sidebar-brand-text">Forma</div>
              <div className="sidebar-brand-sub"><span className="status-pulse" /> Private workspace</div>
            </div>
          </div>
        </div>
        <nav className="sidebar-nav">
          <div className="sidebar-nav-label">Create</div>
          <NavLink to="/editor" aria-label="Resume" title="Resume" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><PenLine size={16} /></span>
            <span><strong>Resume</strong></span>
          </NavLink>
          <NavLink to="/versions" aria-label="Versions" title="Versions" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <span className="sidebar-link-icon"><Layers size={16} /></span>
            <span><strong>Versions</strong></span>
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
          </div>
          <div className="sidebar-command">
            <Command size={14} />
            <span>Everything autosaves</span>
            <kbd>⌘ S</kbd>
          </div>
        </div>
      </aside>
      <main className="layout-main">
        {children}
      </main>
    </div>
  );
}
