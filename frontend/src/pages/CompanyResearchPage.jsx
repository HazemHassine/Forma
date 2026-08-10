import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Boxes, Briefcase, Building2, Check, ChevronRight,
  CircleDollarSign, CircleHelp, Clock3, Compass, Database, ExternalLink,
  FileSearch, Globe2, HeartHandshake, Lightbulb, Link2, Loader, Newspaper,
  Plus, RefreshCw, Search, ShieldCheck, Sparkles, Target, Trash2, TrendingUp,
  Users,
} from 'lucide-react';
import { companyResearchApi } from '../api';
import { useAIProvider, useToast } from '../App';
import Button from '../components/Button';
import Modal from '../components/Modal';
import './CompanyResearchPage.css';

const EMPTY_FORM = {
  company: '',
  website_url: '',
  role: '',
  job_context: '',
  focus: '',
};

const RESEARCH_STAGES = [
  {
    title: 'Find authoritative sources',
    detail: 'Checking the company website and reliable public reporting.',
  },
  {
    title: 'Build the company picture',
    detail: 'Mapping products, markets, leadership, funding, and recent activity.',
  },
  {
    title: 'Separate signals from assumptions',
    detail: 'Cross-checking claims and recording confidence and watchouts.',
  },
  {
    title: 'Make it useful for your role',
    detail: 'Turning the findings into a focused, source-backed briefing.',
  },
];

const KNOWN_REPORT_KEYS = new Set([
  'identity',
  'executive_summary',
  'products_services',
  'business_model',
  'customers_markets',
  'financial_signals',
  'competitive_landscape',
  'leadership_ownership_funding',
  'recent_developments',
  'strategy_priorities',
  'culture_workplace',
  'risks_watchouts',
  'role_relevance',
  'follow_up_questions',
  'sources',
  'researched_at',
  'confidence',
  'confidence_notes',
]);

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function safeExternalUrl(url) {
  if (typeof url !== 'string' || !url.trim()) return null;
  try {
    const parsed = new URL(url);
    if (
      !['http:', 'https:'].includes(parsed.protocol)
      || !parsed.hostname
      || parsed.username
      || parsed.password
    ) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

function hasFindings(value) {
  if (Array.isArray(value)) return value.length > 0;
  if (value && typeof value === 'object') return Object.values(value).some(hasFindings);
  return value !== null && value !== undefined && String(value).trim() !== '';
}

function collectSourceUrls(value, keyHint = '', collected = new Set()) {
  if (Array.isArray(value)) {
    value.forEach(item => collectSourceUrls(item, keyHint, collected));
    return collected;
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, item]) => collectSourceUrls(item, key, collected));
    return collected;
  }
  if (
    typeof value === 'string'
    && ['url', 'source_url', 'source_urls', 'sources'].includes(keyHint)
  ) {
    const url = safeExternalUrl(value);
    if (url) collected.add(url);
  }
  return collected;
}

function normalizeReports(payload) {
  if (Array.isArray(payload)) return payload;
  const candidates = [payload?.reports, payload?.items, payload?.results, payload?.data];
  return candidates.find(Array.isArray) || [];
}

function unwrapEntity(payload) {
  if (!payload || typeof payload !== 'object') return null;
  if (payload.id || payload.report) return payload;
  return payload.item || payload.result || payload.data || null;
}

function reportBody(entity) {
  if (!entity || typeof entity !== 'object') return {};
  const candidate = entity.report || entity.content || entity.research || {};
  return candidate && typeof candidate === 'object' && !Array.isArray(candidate) ? candidate : {};
}

function humanizeKey(key) {
  return String(key || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, character => character.toUpperCase());
}

function formatDate(value) {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

function sourceLabel(url, index) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return `Source ${index + 1}`;
  }
}

function confidenceValue(entity, report) {
  return entity?.confidence || report?.confidence || entity?.metadata?.confidence || 'unknown';
}

function confidenceLabel(value) {
  if (typeof value === 'number') {
    const percentage = value <= 1 ? Math.round(value * 100) : Math.round(value);
    return `${percentage}% confidence`;
  }
  const label = String(value || 'unknown').trim();
  return `${label.charAt(0).toUpperCase()}${label.slice(1)} confidence`;
}

function InlineSources({ urls }) {
  const validUrls = [...new Set(asArray(urls).map(item => (
    typeof item === 'string' ? item : item?.url || item?.source_url
  )).map(safeExternalUrl).filter(Boolean))];

  if (!validUrls.length) return null;

  return (
    <div className="company-inline-sources" aria-label="Supporting sources">
      {validUrls.map((url, index) => (
        <a href={url} target="_blank" rel="noreferrer" key={url}>
          {sourceLabel(url, index)} <ExternalLink size={10} />
        </a>
      ))}
    </div>
  );
}

function StructuredValue({ value }) {
  if (value === null || value === undefined || value === '') return null;

  if (Array.isArray(value)) {
    return (
      <ul className="company-generic-list">
        {value.map((item, index) => (
          <li key={index}><StructuredValue value={item} /></li>
        ))}
      </ul>
    );
  }

  if (typeof value === 'object') {
    return (
      <dl className="company-generic-fields">
        {Object.entries(value)
          .filter(([, item]) => item !== null && item !== undefined && item !== '')
          .map(([key, item]) => (
            <div key={key}>
              <dt>{humanizeKey(key)}</dt>
              <dd><StructuredValue value={item} /></dd>
            </div>
          ))}
      </dl>
    );
  }

  return <span>{typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}</span>;
}

function ResearchItems({ items, emptyMessage = 'No reliable findings were returned for this area.' }) {
  const normalized = Array.isArray(items)
    ? items
    : items && typeof items === 'object'
      ? Object.entries(items).map(([title, detail]) => ({ title: humanizeKey(title), detail }))
      : items
        ? [items]
        : [];

  if (!normalized.length) {
    return <p className="company-report-empty-copy">{emptyMessage}</p>;
  }

  return (
    <div className="company-finding-list">
      {normalized.map((item, index) => {
        if (typeof item !== 'object' || item === null) {
          return <article key={index}><p>{String(item)}</p></article>;
        }
        const title = item.title || item.name || item.label || item.fact || item.event;
        const detail = item.detail || item.description || item.text || item.summary;
        const remaining = Object.fromEntries(Object.entries(item).filter(([key, value]) => (
          !['title', 'name', 'label', 'fact', 'event', 'detail', 'description', 'text', 'summary', 'source_urls', 'sources'].includes(key)
          && value !== null
          && value !== undefined
          && value !== ''
        )));
        return (
          <article key={`${title || 'finding'}-${index}`}>
            {title && <strong>{title}</strong>}
            {detail && (typeof detail === 'object'
              ? <StructuredValue value={detail} />
              : <p>{detail}</p>
            )}
            {!!Object.keys(remaining).length && <StructuredValue value={remaining} />}
            <InlineSources urls={item.source_urls || item.sources} />
          </article>
        );
      })}
    </div>
  );
}

function ReportSection({ icon: Icon, title, tone = 'default', wide = false, children }) {
  return (
    <section className={`company-report-section tone-${tone} ${wide ? 'wide' : ''}`}>
      <div className="company-report-section-title">
        <span><Icon size={16} /></span>
        <h3>{title}</h3>
      </div>
      {children}
    </section>
  );
}

function ResearchProgress({ activeIndex }) {
  return (
    <div className="company-progress" aria-live="polite">
      <div className="company-progress-orbit">
        <div><Building2 size={24} /></div>
        <span><Search size={15} /></span>
      </div>
      <div className="company-progress-copy">
        <span>Research in progress</span>
        <h2>{RESEARCH_STAGES[activeIndex]?.title}</h2>
        <p>{RESEARCH_STAGES[activeIndex]?.detail}</p>
      </div>
      <div className="company-progress-track">
        <span style={{ width: `${((activeIndex + 1) / RESEARCH_STAGES.length) * 100}%` }} />
      </div>
      <div className="company-progress-stages">
        {RESEARCH_STAGES.map((stage, index) => {
          const status = index < activeIndex ? 'complete' : index === activeIndex ? 'active' : 'queued';
          return (
            <div className={status} key={stage.title}>
              <span>{status === 'complete' ? <Check size={13} /> : index + 1}</span>
              <strong>{stage.title}</strong>
            </div>
          );
        })}
      </div>
      <small>Detailed web research can take several minutes. Keep this tab open; the report will be saved automatically when it finishes.</small>
    </div>
  );
}

function NewResearchForm({ form, setForm, onSubmit, error }) {
  const setField = (field, value) => setForm(previous => ({ ...previous, [field]: value }));
  const focusIdeas = ['Interview preparation', 'Cover-letter positioning', 'Competitors and strategy'];

  return (
    <div className="company-new-research">
      <div className="company-new-hero">
        <div className="company-new-icon"><FileSearch size={24} /></div>
        <div>
          <span>New research brief</span>
          <h2>Understand the company behind the role</h2>
          <p>Build a current, sourced view of the business before you write, apply, or interview.</p>
        </div>
      </div>

      {error && (
        <div className="company-error-banner" role="alert">
          <AlertTriangle size={17} />
          <div><strong>Research could not be completed</strong><span>{error}</span></div>
        </div>
      )}

      <form className="company-research-form" onSubmit={onSubmit}>
        <div className="company-form-grid">
          <div className="form-group">
            <label className="form-label" htmlFor="research-company">Company</label>
            <div className="company-input-icon">
              <Building2 size={15} />
              <input
                id="research-company"
                value={form.company}
                onChange={event => setField('company', event.target.value)}
                placeholder="e.g. Siemens"
                autoFocus
                required
              />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="research-website">Website <span>optional</span></label>
            <div className="company-input-icon">
              <Globe2 size={15} />
              <input
                id="research-website"
                type="url"
                value={form.website_url}
                onChange={event => setField('website_url', event.target.value)}
                placeholder="https://company.com"
              />
            </div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="research-role">Target role <span>optional</span></label>
          <div className="company-input-icon">
            <Briefcase size={15} />
            <input
              id="research-role"
              value={form.role}
              onChange={event => setField('role', event.target.value)}
              placeholder="e.g. Product Manager, Grid Software"
            />
          </div>
          <small className="company-field-help">A role lets the report call out the most relevant signals for your application.</small>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="research-job-context">Role or job context <span>optional</span></label>
          <textarea
            id="research-job-context"
            value={form.job_context}
            onChange={event => setField('job_context', event.target.value)}
            placeholder="Paste the job description, team context, or the parts of the opportunity you want understood."
            rows={6}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="research-focus">Research focus <span>optional</span></label>
          <textarea
            id="research-focus"
            value={form.focus}
            onChange={event => setField('focus', event.target.value)}
            placeholder="What should the research pay special attention to?"
            rows={3}
          />
          <div className="company-focus-ideas">
            {focusIdeas.map(idea => (
              <button type="button" onClick={() => setField('focus', idea)} key={idea}>
                <Plus size={11} /> {idea}
              </button>
            ))}
          </div>
        </div>

        <div className="company-form-footer">
          <div>
            <ShieldCheck size={16} />
            <span><strong>Source-backed by design.</strong> Findings preserve links, uncertainty, and confidence.</span>
          </div>
          <Button type="submit" variant="primary" disabled={!form.company.trim()}>
            <Search size={15} /> Research company
          </Button>
        </div>
      </form>
    </div>
  );
}

function CompanyReport({ entity }) {
  const report = reportBody(entity);
  const identity = report.identity && typeof report.identity === 'object' ? report.identity : {};
  const summary = report.executive_summary;
  const summaryText = typeof summary === 'string'
    ? summary
    : summary?.text || report.high_level_summary || report.summary || entity.summary;
  const summarySources = typeof summary === 'object' ? summary?.source_urls : [];
  const companyName = identity.name || identity.legal_name || entity.legal_name || entity.company || 'Company research';
  const legalName = identity.legal_name || entity.legal_name;
  const requestedCompany = entity.company && entity.company !== companyName ? entity.company : null;
  const verifiedWebsite = safeExternalUrl(identity.website || entity.website);
  const suppliedWebsite = verifiedWebsite ? null : safeExternalUrl(entity.website_url);
  const website = verifiedWebsite || suppliedWebsite;
  const confidence = confidenceValue(entity, report);
  const listedSources = asArray(report.sources)
    .map((source, index) => {
      if (typeof source === 'string') {
        return { title: sourceLabel(source, index), url: safeExternalUrl(source) };
      }
      return {
        title: source?.title || source?.name || sourceLabel(source?.url, index),
        url: safeExternalUrl(source?.url || source?.source_url),
      };
    })
    .filter(source => source.url);
  const listedUrls = new Set(listedSources.map(source => source.url));
  const fallbackSources = [...collectSourceUrls(report)]
    .filter(url => !listedUrls.has(url))
    .map((url, index) => ({ title: sourceLabel(url, index), url }));
  const sources = [...listedSources, ...fallbackSources];
  const identityFacts = [
    ['Headquarters', identity.headquarters],
    ['Founded', identity.founded],
    ['Company type', identity.company_type],
    ['Employee size', identity.employee_size],
    ['Industries', asArray(identity.industries).join(', ')],
  ].filter(([, value]) => value);
  const extraEntries = Object.entries(report).filter(([key, value]) => (
    !KNOWN_REPORT_KEYS.has(key)
    && value !== null
    && value !== undefined
    && value !== ''
    && (!Array.isArray(value) || value.length)
  ));
  const researchedAt = report.researched_at || entity.researched_at || entity.created_at;
  const isLimited = !sources.length || String(confidence).toLowerCase() === 'low';

  return (
    <article className="company-report">
      <header className="company-report-hero">
        <div className="company-report-logo">{companyName.charAt(0).toUpperCase()}</div>
        <div className="company-report-heading">
          <div className="company-report-kicker">
            <span>Research report</span>
            <span className={`company-confidence confidence-${String(confidence).toLowerCase()}`}>
              <span /> {confidenceLabel(confidence)}
            </span>
          </div>
          <h1>{companyName}</h1>
          {legalName && legalName !== companyName && <p>{legalName}</p>}
          <div className="company-report-meta-row">
            {requestedCompany && <span><Search size={12} /> Input: {requestedCompany}</span>}
            {(entity.role || report.role) && <span><Briefcase size={12} /> {entity.role || report.role}</span>}
            {researchedAt && <span><Clock3 size={12} /> Researched {formatDate(researchedAt)}</span>}
            {website && (
              <a href={website} target="_blank" rel="noreferrer">
                <Globe2 size={12} /> {verifiedWebsite ? 'Verified website' : 'Provided URL'} <ExternalLink size={10} />
              </a>
            )}
          </div>
        </div>
      </header>

      {isLimited && (
        <div className="company-limited-report" role="note">
          <AlertTriangle size={17} />
          <div>
            <strong>Limited verified evidence</strong>
            <span>
              {!sources.length
                ? 'This report contains no valid source links. Treat its findings as leads to verify, not established facts.'
                : 'The available sources leave material uncertainty. Review the confidence notes and verify important claims before using them.'}
            </span>
          </div>
        </div>
      )}

      <section className="company-executive-summary">
        <div className="company-summary-label"><Sparkles size={14} /> Executive summary</div>
        {summaryText ? <StructuredValue value={summaryText} /> : (
          <p className="company-report-empty-copy">No executive summary was returned.</p>
        )}
        <InlineSources urls={summarySources} />
      </section>

      <div className="company-report-grid">
        {!!identityFacts.length && (
          <ReportSection icon={Database} title="Company facts" tone="facts">
            <dl className="company-fact-grid">
              {identityFacts.map(([label, value]) => (
                <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
              ))}
            </dl>
            <InlineSources urls={identity.source_urls} />
          </ReportSection>
        )}

        {hasFindings(report.products_services) && (
          <ReportSection icon={Boxes} title="Products and services">
            <ResearchItems items={report.products_services} />
          </ReportSection>
        )}

        {(hasFindings(report.business_model) || hasFindings(report.customers_markets)) && (
          <ReportSection icon={CircleDollarSign} title="Business model and markets" wide>
            <div className="company-split-findings">
              <div>
                <h4>How the business works</h4>
                <ResearchItems items={report.business_model} />
              </div>
              <div>
                <h4>Customers and markets</h4>
                <ResearchItems items={report.customers_markets} />
              </div>
            </div>
          </ReportSection>
        )}

        {hasFindings(report.financial_signals) && (
          <ReportSection icon={TrendingUp} title="Financial signals" tone="money">
            <ResearchItems items={report.financial_signals} />
          </ReportSection>
        )}

        {hasFindings(report.competitive_landscape) && (
          <ReportSection icon={Compass} title="Competitive landscape" tone="strategy">
            <ResearchItems items={report.competitive_landscape} />
          </ReportSection>
        )}

        {hasFindings(report.leadership_ownership_funding) && (
          <ReportSection icon={Users} title="Leadership, ownership, and funding">
            <ResearchItems items={report.leadership_ownership_funding} />
          </ReportSection>
        )}

        {hasFindings(report.recent_developments) && (
          <ReportSection icon={Newspaper} title="Recent developments">
            <ResearchItems items={report.recent_developments} />
          </ReportSection>
        )}

        {hasFindings(report.strategy_priorities) && (
          <ReportSection icon={Compass} title="Strategy and priorities" tone="strategy">
            <ResearchItems items={report.strategy_priorities} />
          </ReportSection>
        )}

        {hasFindings(report.culture_workplace) && (
          <ReportSection icon={HeartHandshake} title="Culture and workplace signals" tone="culture">
            <ResearchItems items={report.culture_workplace} />
          </ReportSection>
        )}

        {hasFindings(report.risks_watchouts) && (
          <ReportSection icon={AlertTriangle} title="Risks and watchouts" tone="warning">
            <ResearchItems items={report.risks_watchouts} />
          </ReportSection>
        )}

        {hasFindings(report.role_relevance) && (
          <ReportSection icon={Target} title="Relevance to your role" tone="relevance">
            <ResearchItems items={report.role_relevance} />
          </ReportSection>
        )}

        {hasFindings(report.follow_up_questions) && (
          <ReportSection icon={CircleHelp} title="Open questions" wide>
            <ResearchItems items={report.follow_up_questions} />
          </ReportSection>
        )}

        {!!extraEntries.length && (
          <ReportSection icon={Lightbulb} title="Additional findings" wide>
            <StructuredValue value={Object.fromEntries(extraEntries)} />
          </ReportSection>
        )}

        <ReportSection icon={Link2} title={`Sources${sources.length ? ` · ${sources.length}` : ''}`} wide>
          {sources.length ? (
            <div className="company-source-grid">
              {sources.map((source, index) => (
                <a href={source.url} target="_blank" rel="noreferrer" key={`${source.url}-${index}`}>
                  <span>{index + 1}</span>
                  <strong>{source.title}</strong>
                  <small>{sourceLabel(source.url, index)}</small>
                  <ExternalLink size={13} />
                </a>
              ))}
            </div>
          ) : (
            <p className="company-report-empty-copy">No valid HTTP sources were included in this report.</p>
          )}
        </ReportSection>

        <ReportSection icon={ShieldCheck} title="Research metadata and confidence" tone="metadata" wide>
          <div className="company-metadata-grid">
            <div><span>Confidence</span><strong>{confidenceLabel(confidence)}</strong></div>
            <div><span>Researched</span><strong>{formatDate(researchedAt)}</strong></div>
            <div><span>Sources retained</span><strong>{sources.length}</strong></div>
            <div><span>Research focus</span><strong>{entity.focus || 'General company briefing'}</strong></div>
          </div>
          {report.confidence_notes && (
            <div className="company-confidence-notes">
              <AlertTriangle size={14} />
              <span><strong>Confidence notes</strong>{report.confidence_notes}</span>
            </div>
          )}
        </ReportSection>
      </div>
    </article>
  );
}

export default function CompanyResearchPage() {
  const addToast = useToast();
  const { aiProvider } = useAIProvider();
  const [reports, setReports] = useState([]);
  const [loadingLibrary, setLoadingLibrary] = useState(true);
  const [libraryError, setLibraryError] = useState('');
  const [historyQuery, setHistoryQuery] = useState('');
  const [showNewResearch, setShowNewResearch] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [researching, setResearching] = useState(false);
  const [researchError, setResearchError] = useState('');
  const [progressIndex, setProgressIndex] = useState(0);
  const [selectedReport, setSelectedReport] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const detailRequestRef = useRef(0);
  const researchInFlightRef = useRef(false);

  const loadLibrary = useCallback(async () => {
    setLoadingLibrary(true);
    setLibraryError('');
    try {
      const payload = await companyResearchApi.list();
      setReports(normalizeReports(payload));
    } catch (error) {
      setLibraryError(error.message || 'Could not load saved research.');
    } finally {
      setLoadingLibrary(false);
    }
  }, []);

  useEffect(() => {
    // Initial server data is loaded once when the workspace mounts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadLibrary();
  }, [loadLibrary]);

  useEffect(() => {
    if (!researching) return undefined;
    const timer = window.setInterval(() => {
      setProgressIndex(previous => Math.min(previous + 1, RESEARCH_STAGES.length - 1));
    }, 12000);
    return () => window.clearInterval(timer);
  }, [researching]);

  const filteredReports = useMemo(() => {
    const query = historyQuery.trim().toLowerCase();
    if (!query) return reports;
    return reports.filter(item => [
      item.company,
      item.legal_name,
      item.role,
      item.website,
      item.website_url,
    ].some(value => String(value || '').toLowerCase().includes(query)));
  }, [historyQuery, reports]);

  const openNew = () => {
    if (researching) return;
    detailRequestRef.current += 1;
    setShowNewResearch(true);
    setSelectedReport(null);
    setDetailLoading(false);
    setDetailError('');
    setResearchError('');
  };

  const openReport = async (summary) => {
    if (researching || !summary?.id) return;
    const requestId = detailRequestRef.current + 1;
    detailRequestRef.current = requestId;
    setShowNewResearch(false);
    setSelectedReport(summary);
    setDetailLoading(true);
    setDetailError('');
    try {
      const payload = await companyResearchApi.get(summary.id);
      if (detailRequestRef.current === requestId) {
        setSelectedReport(unwrapEntity(payload) || summary);
      }
    } catch (error) {
      if (detailRequestRef.current === requestId) {
        setDetailError(error.message || 'Could not load this research report.');
      }
    } finally {
      if (detailRequestRef.current === requestId) setDetailLoading(false);
    }
  };

  const runResearch = async (event) => {
    event.preventDefault();
    if (researchInFlightRef.current) return;
    if (!form.company.trim()) {
      setResearchError('Enter a company name to begin.');
      return;
    }

    researchInFlightRef.current = true;
    detailRequestRef.current += 1;
    setResearching(true);
    setProgressIndex(0);
    setResearchError('');
    try {
      const payload = await companyResearchApi.research(aiProvider, {
        company: form.company.trim(),
        website_url: form.website_url.trim() || null,
        role: form.role.trim() || null,
        job_context: form.job_context.trim() || null,
        focus: form.focus.trim() || null,
      });
      const entity = unwrapEntity(payload);
      if (!entity) throw new Error('The research finished without a readable report.');

      setReports(previous => {
        const withoutDuplicate = previous.filter(item => String(item.id) !== String(entity.id));
        return [entity, ...withoutDuplicate];
      });
      setSelectedReport(entity);
      setShowNewResearch(false);
      setForm(EMPTY_FORM);
      addToast(`Research for ${entity.company || 'the company'} is ready`, 'success');
    } catch (error) {
      setResearchError(error.message || 'Company research failed.');
      setShowNewResearch(true);
    } finally {
      researchInFlightRef.current = false;
      setResearching(false);
    }
  };

  const deleteReport = async () => {
    if (!deleteTarget?.id) return;
    setDeleting(true);
    try {
      await companyResearchApi.delete(deleteTarget.id);
      const remaining = reports.filter(item => String(item.id) !== String(deleteTarget.id));
      setReports(remaining);
      if (String(selectedReport?.id) === String(deleteTarget.id)) {
        detailRequestRef.current += 1;
        setSelectedReport(null);
        setShowNewResearch(true);
      }
      setDeleteTarget(null);
      addToast('Research report deleted', 'success');
    } catch (error) {
      addToast(error.message || 'Could not delete the report', 'error');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="company-research-page">
      <header className="company-page-header">
        <div>
          <div className="page-eyebrow"><Globe2 size={14} /> Company intelligence</div>
          <h1>Company researcher</h1>
          <p className="page-subtitle">Current, sourced context for stronger applications and sharper interviews.</p>
        </div>
        <Button variant="primary" onClick={openNew} disabled={researching}>
          <Plus size={15} /> New research
        </Button>
      </header>

      <div className="company-research-workspace">
        <aside className="company-library">
          <div className="company-library-header">
            <div>
              <span>Recent reports</span>
              <strong>{reports.length}</strong>
            </div>
            <button onClick={loadLibrary} disabled={loadingLibrary} aria-label="Refresh report library">
              <RefreshCw size={14} className={loadingLibrary ? 'spin' : ''} />
            </button>
          </div>

          <div className="company-library-search">
            <Search size={14} />
            <input
              value={historyQuery}
              onChange={event => setHistoryQuery(event.target.value)}
              placeholder="Search recent reports"
              aria-label="Search loaded recent company reports"
            />
          </div>

          <div className="company-library-list">
            {loadingLibrary ? (
              <div className="company-library-state"><Loader size={20} className="spin" /><span>Loading reports…</span></div>
            ) : libraryError ? (
              <div className="company-library-state error">
                <AlertTriangle size={20} />
                <span>{libraryError}</span>
                <button onClick={loadLibrary}>Try again</button>
              </div>
            ) : !filteredReports.length ? (
              <div className="company-library-state">
                <Database size={22} />
                <span>{reports.length ? 'No reports match your search.' : 'Your completed research will appear here.'}</span>
              </div>
            ) : (
              filteredReports.map(item => {
                const isSelected = !showNewResearch && String(selectedReport?.id) === String(item.id);
                const itemConfidence = confidenceValue(item, reportBody(item));
                return (
                  <div className={`company-history-card ${isSelected ? 'selected' : ''}`} key={item.id}>
                    <button className="company-history-open" onClick={() => openReport(item)}>
                      <span className="company-history-logo">{(item.legal_name || item.company || '?').charAt(0).toUpperCase()}</span>
                      <span className="company-history-copy">
                        <strong>{item.legal_name || item.company || 'Company report'}</strong>
                        <small>{item.role || (item.legal_name && item.company !== item.legal_name ? `Input: ${item.company}` : 'General research')}</small>
                        <span>
                          {formatDate(item.researched_at || item.created_at)}
                          <span className="company-history-confidence">
                            <i
                              className={`confidence-dot confidence-${String(itemConfidence).toLowerCase()}`}
                              aria-hidden="true"
                            />
                            {String(itemConfidence || 'unknown')} confidence
                          </span>
                        </span>
                      </span>
                      <ChevronRight size={14} />
                    </button>
                    <button
                      className="company-history-delete"
                      onClick={() => setDeleteTarget(item)}
                      aria-label={`Delete research for ${item.legal_name || item.company}`}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })
            )}
          </div>

          <div className="company-library-footer">
            <ShieldCheck size={13} />
            <span>Showing up to 50 recent reports. Each keeps its sources and confidence notes.</span>
          </div>
        </aside>

        <section className="company-research-canvas" aria-label="Company research workspace">
          {researching ? (
            <ResearchProgress activeIndex={progressIndex} />
          ) : showNewResearch ? (
            <NewResearchForm
              form={form}
              setForm={setForm}
              onSubmit={runResearch}
              error={researchError}
            />
          ) : detailLoading ? (
            <div className="company-canvas-state">
              <Loader size={28} className="spin" />
              <h2>Opening research report</h2>
              <p>Loading the complete findings and sources…</p>
            </div>
          ) : detailError ? (
            <div className="company-canvas-state error">
              <AlertTriangle size={28} />
              <h2>Report unavailable</h2>
              <p>{detailError}</p>
              <Button variant="secondary" onClick={() => openReport(selectedReport)}>
                <RefreshCw size={14} /> Try again
              </Button>
            </div>
          ) : selectedReport ? (
            <>
              <button className="company-mobile-back" onClick={openNew}>
                <ArrowLeft size={14} /> New research
              </button>
              <CompanyReport entity={selectedReport} />
            </>
          ) : (
            <div className="company-canvas-state">
              <Building2 size={30} />
              <h2>Select a saved report</h2>
              <p>Choose from your research library or start a new company brief.</p>
            </div>
          )}
        </section>
      </div>

      <Modal
        isOpen={!!deleteTarget}
        onClose={() => !deleting && setDeleteTarget(null)}
        title="Delete research report"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)} disabled={deleting}>Cancel</Button>
            <Button variant="danger" onClick={deleteReport} disabled={deleting}>
              {deleting ? <Loader size={14} className="spin" /> : <Trash2 size={14} />} Delete report
            </Button>
          </>
        )}
      >
        <p className="confirm-delete-text">
          Permanently delete the saved research for <strong>{deleteTarget?.legal_name || deleteTarget?.company}</strong>? The report and its source record cannot be recovered.
        </p>
      </Modal>
    </div>
  );
}
