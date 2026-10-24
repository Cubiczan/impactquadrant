// POST /api/track {event, distinct_id, props}. Allow-listed funnel events only, forwarded to Mixpanel with the env token.
import { buildEvent, send, originOk } from '../lib/mixpanel.js';
export default async function handler(req, res) {
  const o = req.headers.origin; if (o && originOk(o)) { res.setHeader('Access-Control-Allow-Origin', o); res.setHeader('Vary', 'Origin'); }
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type'); res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  if (!originOk(o)) return res.status(403).json({ error: 'origin' });
  const token = process.env.MIXPANEL_TOKEN;
  if (!token) return res.status(202).json({ ok: false, status: 'mixpanel_not_configured' });   // site keeps working
  let body = req.body; if (typeof body === 'string') { try { body = JSON.parse(body); } catch { body = {}; } }
  const b = buildEvent(body, token, req.headers['x-forwarded-for']); if (b.error) return res.status(400).json({ error: b.error });
  const ok = await send(b.event).catch(() => false);
  return res.status(ok ? 200 : 502).json({ ok });
}
