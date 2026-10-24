import test from 'node:test'; import assert from 'node:assert/strict';
import { buildEvent, originOk, FUNNEL, send } from '../lib/mixpanel.js';
test('rejects non-funnel events', () => assert.equal(buildEvent({ event: 'x', distinct_id: 'abcdefgh1' }, 't').error, 'event_not_allowed'));
test('drops PII props, keeps allowed', () => { const e = buildEvent({ event: 'scorecard_completed', distinct_id: 'abcdefgh1', props: { score_band: 'B', email: 'a@b.com', name: 'X' } }, 'tok').event; assert.equal(e.properties.score_band, 'B'); assert.equal(e.properties.email, undefined); assert.equal(e.properties.name, undefined); assert.equal(e.properties.token, 'tok'); });
test('origin allow-list', () => { assert.ok(originOk('https://www.impactquadrant.com')); assert.ok(!originOk('https://evil.com')); });
test('funnel order', () => assert.deepEqual(FUNNEL.slice(0, 1).concat(FUNNEL.slice(-1)), ['scorecard_viewed', 'checkout_completed']));
test('send posts batch', async () => { let got; const ok = await send({ event: 'pricing_viewed', properties: {} }, async (u, o) => { got = [u, JSON.parse(o.body)]; return { ok: true }; }); assert.ok(ok); assert.match(got[0], /api\.mixpanel\.com\/track/); assert.equal(got[1].length, 1); });
test('track snippet has no token', async () => { const fs = await import('node:fs'); const s = fs.readFileSync(new URL('../../wix/mixpanel-funnel-embed.html', import.meta.url), 'utf8'); assert.ok(!/MIXPANEL_TOKEN|mixpanel\.com/i.test(s)); assert.match(s, /\/api\/track/); });
