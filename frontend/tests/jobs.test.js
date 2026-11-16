import assert from 'node:assert/strict';
import test from 'node:test';

import {
  addDays,
  buildHandoff,
  daysBetween,
  describeAge,
  followUpInfo,
  lastActivityDate,
  matchesQuery,
  readHandoff,
  statusLabel,
  toISODate,
} from '../src/jobs.js';


test('day arithmetic ignores time of day and time zones', () => {
  assert.equal(daysBetween('2026-11-16', '2026-11-23'), 7);
  assert.equal(daysBetween('2026-11-16T23:59:00+00:00', '2026-11-15'), -1);
  assert.equal(daysBetween('2026-03-28', '2026-03-30'), 2); // across a DST change
  assert.equal(daysBetween('', '2026-11-15'), null);
  assert.equal(addDays('2026-12-29', 7), '2027-01-05');
  assert.equal(toISODate(new Date(2026, 0, 5, 23, 30)), '2026-01-05');
});

test('follow-ups are graded by urgency for open applications only', () => {
  const today = '2026-11-16';
  const job = (follow_up_at, status = 'applied') => ({ follow_up_at, status });

  assert.deepEqual(followUpInfo(job('2026-11-13'), today), { state: 'overdue', label: '3 days overdue' });
  assert.deepEqual(followUpInfo(job('2026-11-15'), today), { state: 'overdue', label: '1 day overdue' });
  assert.equal(followUpInfo(job('2026-11-16'), today).state, 'today');
  assert.equal(followUpInfo(job('2026-11-17'), today).label, 'Tomorrow');
  assert.equal(followUpInfo(job('2026-11-20'), today).label, 'In 4 days');
  assert.equal(followUpInfo(job('2026-12-20'), today).state, 'later');
  assert.equal(followUpInfo(job(null), today), null);
  assert.equal(followUpInfo(job('2026-11-13', 'rejected'), today), null);
});

test('ages read naturally', () => {
  assert.equal(describeAge(0), 'today');
  assert.equal(describeAge(1), 'yesterday');
  assert.equal(describeAge(9), '9 days ago');
  assert.equal(describeAge(35), '5 weeks ago');
  assert.equal(describeAge(90), '3 months ago');
});

test('last activity is the later of applying and the last status change', () => {
  assert.equal(
    lastActivityDate({ applied_at: '2026-09-02 10:00:00', status_changed_at: '2026-10-01T08:00:00+00:00' }),
    '2026-10-01',
  );
  assert.equal(lastActivityDate({ applied_at: '2026-09-02', status_changed_at: null }), '2026-09-02');
});

test('a handoff carries only what the AI pages need', () => {
  const job = { id: 4, company: 'Acme', position: 'Engineer', url: null, job_description: 'Post', notes: 'private' };
  assert.deepEqual(buildHandoff(job), {
    id: 4, company: 'Acme', position: 'Engineer', url: '', job_description: 'Post',
  });
  assert.deepEqual(readHandoff({ state: { job } }), buildHandoff(job));
  assert.equal(readHandoff({ state: null }), null);
  assert.equal(readHandoff(undefined), null);
});

test('search matches company, role, place and notes', () => {
  const job = { company: 'Acme GmbH', position: 'ML Engineer', location: 'Berlin', notes: 'referral from Sam' };
  assert.ok(matchesQuery(job, ' acme '));
  assert.ok(matchesQuery(job, 'berlin'));
  assert.ok(matchesQuery(job, 'SAM'));
  assert.ok(matchesQuery(job, ''));
  assert.ok(!matchesQuery(job, 'munich'));
  assert.equal(statusLabel('ghosted'), 'No response');
});
