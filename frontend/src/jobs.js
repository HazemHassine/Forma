// Pure helpers for the application pipeline. No React or network code here so
// the date and status rules can be unit-tested directly.

export const JOB_STATUSES = [
  { id: 'saved', label: 'Saved', hint: 'Interesting, not applied yet' },
  { id: 'applied', label: 'Applied', hint: 'Sent, waiting to hear back' },
  { id: 'interviewing', label: 'Interviewing', hint: 'In conversation' },
  { id: 'offer', label: 'Offer', hint: 'Offer received' },
  { id: 'rejected', label: 'Rejected', hint: 'They said no' },
  { id: 'ghosted', label: 'No response', hint: 'Never heard back' },
  { id: 'withdrawn', label: 'Withdrawn', hint: 'You pulled out' },
];

export const ACTIVE_STATUSES = new Set(['saved', 'applied', 'interviewing', 'offer']);

const STATUS_LABELS = Object.fromEntries(JOB_STATUSES.map(status => [status.id, status.label]));

export function statusLabel(status) {
  return STATUS_LABELS[status] || status || 'Unknown';
}

export function isActive(job) {
  return ACTIVE_STATUSES.has(job.status);
}

/** Local calendar date as YYYY-MM-DD (not UTC, so "today" matches the user's day). */
export function toISODate(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseDay(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
  if (!match) return null;
  return Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

/** Whole days from `from` to `to`; negative when `to` is earlier. */
export function daysBetween(from, to) {
  const start = parseDay(from);
  const end = parseDay(to);
  if (start == null || end == null) return null;
  return Math.round((end - start) / 86400000);
}

export function addDays(isoDate, days) {
  const start = parseDay(isoDate);
  if (start == null) return null;
  return new Date(start + days * 86400000).toISOString().slice(0, 10);
}

export function formatDay(value, { withYear = false } = {}) {
  const day = parseDay(value);
  if (day == null) return '—';
  return new Date(day).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
    ...(withYear ? { year: 'numeric' } : {}),
  });
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

/** "today", "3 days ago", "5 weeks ago". */
export function describeAge(days) {
  if (days == null) return '';
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 14) return `${plural(days, 'day')} ago`;
  if (days < 60) return `${plural(Math.round(days / 7), 'week')} ago`;
  return `${plural(Math.round(days / 30), 'month')} ago`;
}

/** How urgent a follow-up date is relative to today. */
export function followUpInfo(job, today = toISODate()) {
  if (!job.follow_up_at || !isActive(job)) return null;
  const delta = daysBetween(today, job.follow_up_at);
  if (delta == null) return null;
  if (delta < 0) return { state: 'overdue', label: `${plural(-delta, 'day')} overdue` };
  if (delta === 0) return { state: 'today', label: 'Today' };
  if (delta === 1) return { state: 'soon', label: 'Tomorrow' };
  if (delta <= 7) return { state: 'soon', label: `In ${delta} days` };
  return { state: 'later', label: formatDay(job.follow_up_at) };
}

/** The most recent date something happened to an application. */
export function lastActivityDate(job) {
  const dates = [job.applied_at, job.status_changed_at]
    .map(value => String(value || '').slice(0, 10))
    .filter(value => parseDay(value) != null);
  return dates.sort().at(-1) || null;
}

/**
 * What the tailoring, cover letter, research and review pages need to start
 * from an application without the user pasting the job post again.
 */
export function buildHandoff(job) {
  return {
    id: job.id ?? null,
    company: job.company || '',
    position: job.position || '',
    url: job.url || '',
    job_description: job.job_description || '',
  };
}

/** Read a handoff out of react-router location state, tolerating anything. */
export function readHandoff(location) {
  const job = location?.state?.job;
  if (!job || typeof job !== 'object') return null;
  return buildHandoff(job);
}

export function matchesQuery(job, query) {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return [job.company, job.position, job.location, job.notes, job.contact, job.next_step]
    .some(value => String(value || '').toLowerCase().includes(needle));
}
