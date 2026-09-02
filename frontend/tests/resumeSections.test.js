import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEFAULT_SECTION_ORDER,
  SECTION_DEFINITIONS,
} from '../src/constants/resumeSections.js';

test('DEFAULT_SECTION_ORDER contains all 9 standard sections', () => {
  assert.equal(DEFAULT_SECTION_ORDER.length, 9);
  assert.deepEqual(DEFAULT_SECTION_ORDER, [
    'about_me',
    'work_experience',
    'education',
    'projects',
    'research',
    'skills',
    'certificates',
    'languages',
    'references',
  ]);
});

test('SECTION_DEFINITIONS has titles and descriptions for every section', () => {
  assert.equal(SECTION_DEFINITIONS.length, 9);
  const ids = SECTION_DEFINITIONS.map(s => s.id);
  assert.deepEqual(ids, DEFAULT_SECTION_ORDER);

  for (const def of SECTION_DEFINITIONS) {
    assert.ok(def.title && def.title.length > 0);
    assert.ok(def.description && def.description.length > 0);
  }
});

test('filtering section order removes a section cleanly', () => {
  const removedId = 'research';
  const newOrder = DEFAULT_SECTION_ORDER.filter(id => id !== removedId);
  assert.equal(newOrder.length, 8);
  assert.ok(!newOrder.includes(removedId));
});

test('reordering sections moves section to desired index', () => {
  const order = [...DEFAULT_SECTION_ORDER];
  // Move 'work_experience' (index 1) to before 'about_me' (index 0)
  const [moved] = order.splice(1, 1);
  order.splice(0, 0, moved);

  assert.equal(order[0], 'work_experience');
  assert.equal(order[1], 'about_me');
  assert.equal(order.length, 9);
});
