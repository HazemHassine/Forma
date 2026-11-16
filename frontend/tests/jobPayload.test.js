import assert from 'node:assert/strict';
import test from 'node:test';

import { formatApiError } from '../src/api.js';
import { buildJobPayload } from '../src/jobPayload.js';


test('an empty resume selection is sent as null', () => {
  const payload = buildJobPayload({
    company: ' Example GmbH ',
    position: ' Working Student ',
    url: '',
    status: 'applied',
    resume_version_id: '',
    notes: '',
    applied_at: '2026-07-28',
  });

  assert.deepEqual(payload, {
    company: 'Example GmbH',
    position: 'Working Student',
    url: null,
    status: 'applied',
    resume_version_id: null,
    notes: null,
    applied_at: '2026-07-28',
    job_description: null,
    location: null,
    salary: null,
    contact: null,
    next_step: null,
    follow_up_at: null,
  });
});

test('the job post and follow-up date are trimmed and sent', () => {
  const payload = buildJobPayload({
    company: 'Example GmbH',
    position: 'Engineer',
    url: '',
    status: 'saved',
    resume_version_id: '',
    notes: '',
    applied_at: '',
    job_description: '  Build agents.\n',
    location: ' Berlin ',
    follow_up_at: '2026-08-04',
  });

  assert.equal(payload.job_description, 'Build agents.');
  assert.equal(payload.location, 'Berlin');
  assert.equal(payload.follow_up_at, '2026-08-04');
  assert.equal(payload.applied_at, null);
});

test('a selected resume is sent as a number', () => {
  const payload = buildJobPayload({
    company: 'Example GmbH',
    position: 'Working Student',
    url: 'https://example.com/job',
    status: 'interviewing',
    resume_version_id: '11',
    notes: 'Follow up',
    applied_at: '2026-07-27',
  });

  assert.equal(payload.resume_version_id, 11);
});

test('FastAPI validation details become a readable message', () => {
  const message = formatApiError({
    detail: [{
      type: 'int_parsing',
      loc: ['body', 'resume_version_id'],
      msg: 'Input should be a valid integer',
      input: '',
    }],
  }, 422);

  assert.equal(
    message,
    'resume version id: Input should be a valid integer',
  );
});
