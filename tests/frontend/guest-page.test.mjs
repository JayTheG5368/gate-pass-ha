import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../../custom_components/gate_pass/server.py', import.meta.url), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];

async function page(remaining, scheduled = false) {
  const elements = new Map();
  const timers = [];
  let statusCalls = 0;
  let openCalls = 0;
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      textContent: '', disabled: true, handlers: {},
      addEventListener(type, fn) { this.handlers[type] = fn; },
      setAttribute() {}, close() {}, showModal() {},
    });
    return elements.get(id);
  };
  vm.runInNewContext(script, {
    document: { getElementById: element, documentElement: { dataset: {} } },
    window: { matchMedia: () => ({ matches: false, addEventListener() {} }) },
    location: { pathname: '/gate-pass/guest/one/pass/secret' },
    setTimeout: (fn) => timers.push(fn),
    fetch: async (url) => {
      if (url.endsWith('/open')) {
        openCalls++;
        return { ok: true, json: async () => ({ success: true, remaining_uses: remaining }) };
      }
      statusCalls++;
      const future = scheduled && statusCalls === 1;
      return {
        ok: !future, status: future ? 425 : 200,
        json: async () => ({
          valid_from: new Date(Date.now() + 1000).toISOString(),
          expires_at: new Date(Date.now() + 3600000).toISOString(),
          action_label: 'Open', access_name: 'Garage', label: 'Guest', remaining_uses: remaining,
        }),
      };
    },
  });
  await new Promise(setImmediate);
  return { element, timers, opens: () => openCalls };
}

for (const remaining of [1, null, 0]) {
  test(`successful use with ${remaining} remaining`, async () => {
    const browser = await page(remaining);
    const button = browser.element('openButton');
    assert.equal(button.disabled, false);
    await browser.element('confirmButton').handlers.click();
    assert.equal(button.disabled, remaining === 0);
    assert.match(browser.element('status').textContent, /wurde ausgeführt/);
    if (remaining !== 0) {
      await browser.element('confirmButton').handlers.click();
      assert.equal(browser.opens(), 2);
    }
  });
}

test('scheduled pass refreshes and enables itself once active', async () => {
  const browser = await page(1, true);
  assert.equal(browser.element('openButton').disabled, true);
  assert.equal(browser.timers.length, 1);
  await browser.timers[0]();
  assert.equal(browser.element('openButton').disabled, false);
});
