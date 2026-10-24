// Whop webhook receiver (sandbox). Verifies Standard-Webhooks signature with WHOP_WEBHOOK_SECRET,
// then (when WIX_PUSH_SECRET set) flips the Wix listing to "sold". Never moves money itself.
import crypto from 'node:crypto';
export const config = { api: { bodyParser: false } };
const raw = req => new Promise(r => { let d = ''; req.on('data', c => d += c); req.on('end', () => r(d)); });
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(200).json({ ok: true, info: 'POST Whop webhooks here' });
  const body = await raw(req); const sec = process.env.WHOP_WEBHOOK_SECRET;
  if (sec) {
    const id = req.headers['webhook-id'], ts = req.headers['webhook-timestamp'], sig = req.headers['webhook-signature'] || '';
    const key = Buffer.from(sec.replace(/^whsec_/, ''), 'base64');
    const expect = crypto.createHmac('sha256', key).update(`${id}.${ts}.${body}`).digest('base64');
    if (!sig.split(' ').some(s => s.split(',')[1] === expect)) return res.status(401).json({ error: 'bad signature' });
  }
  const evt = JSON.parse(body || '{}'); const type = evt.type || evt.action;
  const md = evt?.data?.metadata || evt?.data?.checkout_configuration?.metadata || {};
  const targetId = md.target_id; let wix = 'skipped';
  if ((type === 'payment.succeeded' || type === 'membership.activated') && targetId && process.env.WIX_PUSH_SECRET) {
    const r = await fetch((process.env.WIX_SITE || 'https://impactquadrant.info') + '/_functions/targets', { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-rollupops-secret': process.env.WIX_PUSH_SECRET }, body: JSON.stringify({ targetId, status: 'sold' }) });
    wix = r.status;
  }
  const amt = Number(evt?.data?.final_amount ?? evt?.data?.total ?? evt?.data?.amount ?? 0);
  // Terac human check #2 only: retainer or >= $15k fee path (or anomaly) -> buyer_screening; everything else stays automated.
  const human_check = (md.kind === 'retainer' || md.kind === 'fee' || amt >= 15000 || Number(md.anomaly || 0) >= 0.7)
    ? (process.env.TERAC_ENABLED === '1' ? 'buyer_screening: pending (Terac)' : 'buyer_screening: pending_human') : 'none';
  console.log(JSON.stringify({ human_check, type, targetId, match_id: md.match_id, duckdb: 'pulled by rollupops.orchestrator whop_sync', fulfillment: 'draft queued for owner approval (rollupops.fulfillment)', segment: md.segment, wix, verifier_transfer: 'queued (sandbox)' }));
  return res.status(200).json({ ok: true, type, targetId, wix, human_check });
}
