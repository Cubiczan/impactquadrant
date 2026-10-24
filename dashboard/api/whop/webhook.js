// POST /api/whop/webhook — ImpactQuadrant agent automation from Whop payment and membership events.
// Verifies the Standard Webhooks signature with WHOP_WEBHOOK_SECRET (rejects if unset), then queues
// onboarding tasks for owner approval in Vercel Blob. Never moves money, never sends messages.
import { verifySignature, planActions } from '../../lib/whop-events.js';
import { buildCio, sendCio, buildClickup, sendClickup } from '../../lib/integrations.js';
export const config = { api: { bodyParser: false } };
const raw = req => new Promise(r => { let d = ''; req.on('data', c => d += c); req.on('end', () => r(d)); });

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(200).json({ ok: true, info: 'POST Whop webhooks here' });
  const body = await raw(req);
  const v = verifySignature(process.env.WHOP_WEBHOOK_SECRET, req.headers, body);
  if (!v.ok) return res.status(v.reason === 'secret_not_configured' ? 503 : 401).json({ error: v.reason });
  let evt; try { evt = JSON.parse(body); } catch { return res.status(400).json({ error: 'bad_json' }); }
  const plan = planActions(evt, process.env);
  let stored = 'skipped';
  if (plan.tasks.length && process.env.BLOB_READ_WRITE_TOKEN) {
    try {
      const { put } = await import('@vercel/blob');
      await put(`whop-queue/${Date.now()}-${req.headers['webhook-id']}.json`,
        JSON.stringify({ ...plan, webhook_id: req.headers['webhook-id'], received_at: new Date().toISOString() }),
        { access: 'private', contentType: 'application/json', addRandomSuffix: true });
      stored = 'blob';
    } catch (e) { stored = 'error'; }
  }
  // Customer.io + ClickUp: only on payment.succeeded; both default OFF (CIO_LIVE / CLICKUP_LIVE).
  let cio = 'n/a', clickup = 'n/a';
  if (plan.type === 'payment.succeeded') {
    try { cio = await sendCio(process.env, buildCio(evt)); } catch { cio = 'error'; }
    try { clickup = await sendClickup(process.env, buildClickup(evt)); } catch { clickup = 'error'; }
  }
  console.log(JSON.stringify({ evt: plan.type, sku: plan.sku, tasks: plan.tasks, terac: plan.terac, stored, cio, clickup }));
  return res.status(200).json({ ok: true, ...plan, stored, cio, clickup });
}
