import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus, Home, CalendarClock, Hourglass, Bookmark, Check, Target, Mail, ArrowRight,
  CircleCheck, Circle, Loader, Inbox,
} from 'lucide-react';
import { jobApi, resumeApi, contextApi, systemApi } from '../api';
import { useAIProvider, useToast } from '../App';
import Button from '../components/Button';
import Modal from '../components/Modal';
import {
  JOB_STATUSES, addDays, buildHandoff, daysBetween, describeAge, followUpInfo,
  formatDay, lastActivityDate, toISODate,
} from '../jobs';
import './DashboardPage.css';

const SNOOZE_DAYS = 7;

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function AttentionRow({ job, reason, tone, children }) {
  return (
    <li className="dash-row">
      <Link to={`/jobs?open=${job.id}`} className="dash-row-main">
        <span className="dash-row-title">{job.company} <em>{job.position}</em></span>
        <span className={`dash-row-reason tone-${tone}`}>{reason}</span>
        {job.next_step && <span className="dash-row-step">Next: {job.next_step}</span>}
      </Link>
      <div className="dash-row-actions">{children}</div>
    </li>
  );
}

export default function DashboardPage() {
  const addToast = useToast();
  const navigate = useNavigate();
  const { aiProvider } = useAIProvider();
  const [overview, setOverview] = useState(null);
  const [setup, setSetup] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [confirmCloseOut, setConfirmCloseOut] = useState(false);
  const [busy, setBusy] = useState(false);
  const today = toISODate();

  const load = useCallback(async () => {
    try {
      setOverview(await jobApi.overview());
      setLoadError('');
    } catch (err) {
      setLoadError(err.message || 'Could not load your applications.');
    }
  }, []);

  useEffect(() => {
    // Initial server data is loaded once and refreshed after each action.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    Promise.all([
      resumeApi.list().catch(() => []),
      contextApi.getStats().catch(() => null),
      systemApi.status().catch(() => null),
    ]).then(([versions, contextStats, status]) => setSetup({ versions, contextStats, status }));
  }, [load]);

  const act = async (work, message) => {
    setBusy(true);
    try {
      await work();
      if (message) addToast(message, 'success');
      await load();
    } catch (err) {
      addToast(err.message || 'That did not work', 'error');
    } finally {
      setBusy(false);
    }
  };

  const followedUp = (job) => act(async () => {
    await jobApi.addNote(job.id, 'Followed up');
    await jobApi.update(job.id, { follow_up_at: addDays(today, SNOOZE_DAYS) });
  }, `Logged. Next check on ${job.company} in a week.`);

  const snooze = (job) => act(
    () => jobApi.update(job.id, { follow_up_at: addDays(today, SNOOZE_DAYS) }),
    `Will remind you about ${job.company} in a week.`,
  );

  const setStatus = (job, status, message) => act(() => jobApi.update(job.id, { status }), message);

  const closeOutStale = () => act(async () => {
    await jobApi.bulkStatus(overview.stale.map(job => job.id), 'ghosted');
    setConfirmCloseOut(false);
  }, 'Old applications closed as no response.');

  if (!overview) {
    return (
      <div className="dash-page">
        <div className="dash-loading">
          {loadError
            ? <><Inbox size={32} /><p>{loadError}</p><Button variant="secondary" onClick={load}>Try again</Button></>
            : <><Loader size={28} className="dash-spin" /><p>Loading your search…</p></>}
        </div>
      </div>
    );
  }

  const { due, upcoming, stale, saved, weekly, counts } = overview;
  const attentionCount = due.length + stale.length;
  const maxWeek = Math.max(1, ...weekly.map(week => week.count));
  const pipeline = JOB_STATUSES.filter(status => counts[status.id]);
  const maxStatus = Math.max(1, ...pipeline.map(status => counts[status.id]));

  const selectedAI = setup?.status?.ai?.[aiProvider];
  const checklist = setup && [
    {
      done: setup.versions.some(version => version.name !== 'Starter Resume'),
      label: 'Replace the starter resume with yours',
      to: '/editor',
    },
    {
      done: (setup.contextStats?.active_items || 0) > 0,
      label: 'Add your background to the Context Vault',
      hint: 'Tailoring and cover letters draw facts from it.',
      to: '/context',
    },
    {
      done: Boolean(selectedAI?.configured),
      label: `Add an API key for ${aiProvider === 'chatgpt' ? 'ChatGPT' : 'Gemini'}`,
      hint: 'Set it in backend/.env, then restart the backend.',
    },
    {
      done: overview.total > 0,
      label: 'Track your first application',
      to: '/jobs?new=applied',
    },
  ];
  const setupRemaining = checklist ? checklist.filter(item => !item.done) : [];

  return (
    <div className="dash-page">
      <div className="dash-header">
        <div>
          <div className="page-eyebrow"><Home size={14} /> {formatDay(today, { withYear: true })}</div>
          <h1 className="jobs-title">{greeting()}</h1>
          <p className="page-subtitle">
            {overview.total === 0
              ? 'Start by saving a role you like. Everything else in Forma can work from it.'
              : attentionCount > 0
                ? `${attentionCount} application${attentionCount === 1 ? '' : 's'} could use a nudge today.`
                : 'Nothing is waiting on you. A good day to send a new application.'}
          </p>
        </div>
        <div className="dash-header-actions">
          <Button variant="secondary" onClick={() => navigate('/jobs?new=saved')}><Bookmark size={14} /> Save a job</Button>
          <Button variant="primary" onClick={() => navigate('/jobs?new=applied')}><Plus size={14} /> Log an application</Button>
        </div>
      </div>

      <div className="dash-tiles">
        <div className="dash-tile">
          <div className="dash-tile-value">{overview.active}</div>
          <div className="dash-tile-label">Open applications</div>
        </div>
        <div className="dash-tile">
          <div className="dash-tile-value">{overview.applied_this_week}</div>
          <div className="dash-tile-label">Sent this week</div>
        </div>
        <div className="dash-tile">
          <div className="dash-tile-value">{overview.response_rate == null ? '—' : `${overview.response_rate}%`}</div>
          <div className="dash-tile-label">Heard back</div>
        </div>
        <div className="dash-tile">
          <div className="dash-tile-value">{overview.interview_rate == null ? '—' : `${overview.interview_rate}%`}</div>
          <div className="dash-tile-label">Reached an interview</div>
        </div>
      </div>

      <div className="dash-grid">
        <div className="dash-column">
          <section className="dash-card">
            <div className="dash-card-head">
              <h2><CalendarClock size={15} /> Needs attention</h2>
              {stale.length >= 2 && (
                <button type="button" className="dash-text-button" onClick={() => setConfirmCloseOut(true)}>
                  Close all {stale.length} silent ones
                </button>
              )}
            </div>
            {attentionCount === 0 ? (
              <p className="dash-empty">
                <Check size={15} /> No follow-ups due and nothing has gone quiet.
              </p>
            ) : (
              <ul className="dash-list">
                {due.map(job => (
                  <AttentionRow
                    key={`due-${job.id}`}
                    job={job}
                    tone={followUpInfo(job, today)?.state === 'today' ? 'today' : 'overdue'}
                    reason={followUpInfo(job, today)?.state === 'today'
                      ? 'Follow-up due today'
                      : `Follow-up ${followUpInfo(job, today)?.label || 'due'}`}
                  >
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => followedUp(job)}><Check size={12} /> Done</Button>
                    <Button variant="ghost" size="sm" disabled={busy} onClick={() => snooze(job)}>Later</Button>
                  </AttentionRow>
                ))}
                {stale.map(job => (
                  <AttentionRow
                    key={`stale-${job.id}`}
                    job={job}
                    tone="stale"
                    reason={`No reply since ${describeAge(daysBetween(lastActivityDate(job), today))}`}
                  >
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => followedUp(job)}><Check size={12} /> Followed up</Button>
                    <Button variant="ghost" size="sm" disabled={busy} onClick={() => setStatus(job, 'ghosted', `${job.company} closed as no response.`)}>No response</Button>
                  </AttentionRow>
                ))}
              </ul>
            )}
            {upcoming.length > 0 && (
              <>
                <div className="dash-subhead"><Hourglass size={13} /> Coming up this week</div>
                <ul className="dash-list compact">
                  {upcoming.map(job => (
                    <li key={job.id} className="dash-row">
                      <Link to={`/jobs?open=${job.id}`} className="dash-row-main">
                        <span className="dash-row-title">{job.company} <em>{job.position}</em></span>
                        <span className="dash-row-reason">{followUpInfo(job, today)?.label}{job.next_step ? ` · ${job.next_step}` : ''}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2><Bookmark size={15} /> Saved, ready to apply</h2>
              {saved.length > 0 && <Link to="/jobs?status=saved" className="dash-text-button">See all</Link>}
            </div>
            {saved.length === 0 ? (
              <p className="dash-empty">
                Save roles as you find them, with the job post pasted in. Tailoring and the cover letter then start in one click.
              </p>
            ) : (
              <ul className="dash-list">
                {saved.slice(0, 6).map(job => (
                  <li key={job.id} className="dash-row">
                    <Link to={`/jobs?open=${job.id}`} className="dash-row-main">
                      <span className="dash-row-title">{job.company} <em>{job.position}</em></span>
                      <span className="dash-row-reason">
                        Saved {describeAge(daysBetween(job.applied_at, today))}
                        {!job.job_description && ' · job post not pasted yet'}
                      </span>
                    </Link>
                    <div className="dash-row-actions">
                      {job.job_description && (
                        <>
                          <Button variant="secondary" size="sm" onClick={() => navigate('/optimize', { state: { job: buildHandoff(job) } })}><Target size={12} /> Tailor</Button>
                          <Button variant="secondary" size="sm" onClick={() => navigate('/cover-letters', { state: { job: buildHandoff(job) } })}><Mail size={12} /> Letter</Button>
                        </>
                      )}
                      <Button variant="ghost" size="sm" disabled={busy} onClick={() => act(
                        () => jobApi.update(job.id, { status: 'applied', follow_up_at: addDays(today, SNOOZE_DAYS) }),
                        `Applied to ${job.company}. Follow-up set for next week.`,
                      )}>Mark applied</Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <div className="dash-column">
          {setupRemaining.length > 0 && (
            <section className="dash-card">
              <div className="dash-card-head"><h2>Get set up</h2></div>
              <ul className="dash-checklist">
                {checklist.map(item => (
                  <li key={item.label} className={item.done ? 'done' : ''}>
                    {item.done ? <CircleCheck size={16} /> : <Circle size={16} />}
                    <div>
                      {item.to && !item.done
                        ? <Link to={item.to}>{item.label} <ArrowRight size={12} /></Link>
                        : <span>{item.label}</span>}
                      {item.hint && !item.done && <small>{item.hint}</small>}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="dash-card">
            <div className="dash-card-head">
              <h2>Applications sent per week</h2>
            </div>
            <div className="dash-weeks" role="img" aria-label={`Applications sent in each of the last ${weekly.length} weeks: ${weekly.map(week => week.count).join(', ')}`}>
              {weekly.map((week, index) => (
                <div key={week.week_start} className={`dash-week ${index === weekly.length - 1 ? 'current' : ''}`} title={`Week of ${formatDay(week.week_start)}: ${week.count}`}>
                  <span className="dash-week-count">{week.count || ''}</span>
                  <span className="dash-week-bar" style={{ height: `${Math.max(week.count ? 8 : 2, (week.count / maxWeek) * 100)}%` }} />
                  <span className="dash-week-label">{index === weekly.length - 1 ? 'Now' : formatDay(week.week_start)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="dash-card">
            <div className="dash-card-head">
              <h2>Pipeline</h2>
              <Link to="/jobs" className="dash-text-button">Open applications</Link>
            </div>
            {pipeline.length === 0 ? (
              <p className="dash-empty">No applications yet.</p>
            ) : (
              <ul className="dash-pipeline">
                {pipeline.map(status => (
                  <li key={status.id}>
                    <Link to={`/jobs?status=${status.id}`}>
                      <span className="dash-pipeline-label">{status.label}</span>
                      <span className="dash-pipeline-track">
                        <span className={`dash-pipeline-bar bar-${status.id}`} style={{ width: `${(counts[status.id] / maxStatus) * 100}%` }} />
                      </span>
                      <span className="dash-pipeline-count">{counts[status.id]}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      <Modal
        isOpen={confirmCloseOut}
        onClose={() => setConfirmCloseOut(false)}
        title="Close silent applications"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmCloseOut(false)}>Cancel</Button>
            <Button variant="primary" disabled={busy} onClick={closeOutStale}>Mark {stale.length} as no response</Button>
          </>
        }
      >
        <p className="confirm-delete-text">
          These {stale.length} applications have had no reply for {overview.stale_after_days}+ days and have no follow-up planned.
          They will move to <strong>No response</strong>. Nothing is deleted, and you can change any of them back.
        </p>
        <ul className="dash-closeout-list">
          {stale.map(job => (
            <li key={job.id}>{job.company} · {job.position} <span>applied {formatDay(job.applied_at, { withYear: true })}</span></li>
          ))}
        </ul>
      </Modal>
    </div>
  );
}
