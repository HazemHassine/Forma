import assert from 'node:assert/strict';
import test from 'node:test';

import { aiApi, companyResearchApi, coverLetterApi } from '../src/api.js';

test('AI suggestions use the selected provider route', async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl;
  globalThis.fetch = async (url) => {
    requestedUrl = url;
    return new Response(JSON.stringify({ suggestion: 'Improved' }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };

  try {
    const result = await aiApi.suggest('chatgpt', {
      section_type: 'about_me',
      current_content: 'Original',
    });
    assert.equal(requestedUrl, '/api/ai/chatgpt/suggest');
    assert.equal(result.suggestion, 'Improved');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('unknown AI providers are rejected before a request is sent', () => {
  assert.throws(
    () => aiApi.suggest('unknown', {}),
    /Unsupported AI provider/,
  );
});

test('Gemini is used by every cover-letter and research mutation route', async () => {
  const originalFetch = globalThis.fetch;
  const requestedUrls = [];
  globalThis.fetch = async (url) => {
    requestedUrls.push(url);
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };

  try {
    await coverLetterApi.analyze('gemini', {});
    await coverLetterApi.research('gemini', {});
    await coverLetterApi.generate('gemini', {});
    await companyResearchApi.research('gemini', {});
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.deepEqual(requestedUrls, [
    '/api/cover-letters/gemini/analyze',
    '/api/cover-letters/gemini/research',
    '/api/cover-letters/gemini/generate',
    '/api/company-research/gemini/research',
  ]);
  assert.equal(requestedUrls.some(url => url.includes('chatgpt')), false);
});
