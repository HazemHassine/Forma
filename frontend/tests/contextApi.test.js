import assert from 'node:assert/strict';
import test from 'node:test';
import { contextApi, aiApi, critiqueApi } from '../src/api.js';

test('contextApi builds correct URLs and query strings', async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];

  globalThis.fetch = async (url, opts) => {
    requests.push({ url, method: opts?.method || 'GET', body: opts?.body ? JSON.parse(opts.body) : null });
    return new Response(JSON.stringify({ ok: true, id: 123 }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };

  try {
    await contextApi.listSources(true);
    await contextApi.addSource({ title: 'Dump', content: 'Extensive career notes' });
    await contextApi.listItems({ category: 'achievement_metric', activeOnly: true, query: 'redis' });
    await contextApi.toggleItem(42);
    await contextApi.preview({ targetRole: 'Staff Engineer', company: 'Acme', maxItems: 15 });
    await contextApi.synthesize('gemini', { replace_existing: false });
    await contextApi.importResume(99);

    assert.equal(requests[0].url, '/api/context/sources?active_only=true');
    assert.equal(requests[0].method, 'GET');

    assert.equal(requests[1].url, '/api/context/sources');
    assert.equal(requests[1].method, 'POST');
    assert.equal(requests[1].body.title, 'Dump');

    assert.equal(requests[2].url, '/api/context/items?category=achievement_metric&active_only=true&query=redis');

    assert.equal(requests[3].url, '/api/context/items/42/toggle');
    assert.equal(requests[3].method, 'POST');

    assert.equal(requests[4].url, '/api/context/preview?target_role=Staff+Engineer&company=Acme&max_items=15');

    assert.equal(requests[5].url, '/api/context/gemini/synthesize');
    assert.equal(requests[5].method, 'POST');

    assert.equal(requests[6].url, '/api/context/import-resume/99');
    assert.equal(requests[6].method, 'POST');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('aiApi and critiqueApi default to including context', async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];

  globalThis.fetch = async (url, opts) => {
    requests.push({ url, body: JSON.parse(opts.body) });
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };

  try {
    await aiApi.suggest('chatgpt', {
      section_type: 'about_me',
      current_content: 'Original',
    });
    await aiApi.optimize('chatgpt', 1, 'Job description here', { targetRole: 'Backend' });
    await critiqueApi.create('chatgpt', { resume_version_id: 1 });

    assert.equal(requests[0].body.include_context, true);
    assert.equal(requests[1].body.include_context, true);
    assert.equal(requests[2].body.include_context, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
