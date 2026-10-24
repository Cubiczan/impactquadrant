// Intake receiver: verifies per-order HMAC token (FULFILL_APPROVE_SECRET), logs answers for the orchestrator to ingest
// (rollupops.fulfillment.receive_intake writes DuckDB + drafts). No sends.
import crypto from 'node:crypto';
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const { order, t, answers } = req.body || {}; const sec = process.env.FULFILL_APPROVE_SECRET;
  if (!sec) return res.status(503).json({ error: 'intake not configured' });
  const ok = crypto.createHmac('sha256', sec).update(String(order)).digest('hex').slice(0, 16);
  if (!t || t !== ok) return res.status(401).json({ error: 'bad intake link' });
  console.log(JSON.stringify({ intake_received: order, keys: Object.keys(answers || {}) }));
  return res.status(200).json({ ok: true, order, status: 'intake_received' });
}
