// Token-gated reviewer API for Terac evidence reviews. Shows REDACTED bundles only; stores verdicts in a private Vercel Blob store.
// GET  /api/review?c=<check>&t=<token>          -> redacted bundle + whether a verdict exists
// POST /api/review {c,t,verdict,reasons,reviewer,submissionId} -> stores verdict (pending our approval; Terac pays only after we approve)
// GET  /api/review?summary=1                    -> public verdict summary for the dashboard (no reasons, no evidence)
// GET  /api/review?all=1  (header x-review-admin) -> full verdicts incl. reasons, for the owner
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { put, list, get } from '@vercel/blob';
const VERDICTS = ['verified', 'concerns', 'fail'];
const sec = () => process.env.REVIEW_TOKEN_SECRET || '';
const tok = (c) => crypto.createHmac('sha256', sec()).update(c).digest('hex').slice(0, 32);
const eq = (a, b) => { const x = Buffer.from(String(a || '')), y = Buffer.from(String(b || '')); return x.length === y.length && crypto.timingSafeEqual(x, y); };
const okId = (c) => /^[a-z0-9-]{3,64}$/.test(c || '');
const bundle = (c) => { try { return JSON.parse(fs.readFileSync(path.join(process.cwd(), 'review_evidence', `${c}.json`), 'utf8')); } catch { return null; } };
async function verdicts(prefix = 'verdicts/') {
  const out = []; let cursor;
  do { const r = await list({ prefix, cursor }); cursor = r.cursor;
    for (const b of r.blobs) { const g = await get(b.pathname, { access: 'private' }); if (g && g.stream) out.push(JSON.parse(await new Response(g.stream).text())); }
  } while (cursor);
  return out;
}
export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store'); res.setHeader('X-Robots-Tag', 'noindex');
  if (!sec()) return res.status(503).json({ error: 'review not configured' });
  const q = req.query || {};
  try {
    if (req.method === 'GET' && q.summary) {
      const v = await verdicts();
      return res.status(200).json({ verdicts: v.map(x => ({ check_id: x.check_id, kind: x.kind, verdict: x.verdict, at: x.at, approved: !!x.approved })) });
    }
    if (req.method === 'GET' && q.all) {
      if (!eq(req.headers['x-review-admin'], tok('admin'))) return res.status(401).json({ error: 'admin token required' });
      return res.status(200).json({ verdicts: await verdicts() });
    }
    const body = req.method === 'POST' ? (typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {})) : {};
    const c = req.method === 'POST' ? body.c : q.c, t = req.method === 'POST' ? body.t : q.t;
    if (!okId(c) || !eq(t, tok(c))) return res.status(401).json({ error: 'invalid or expired link' });
    const b = bundle(c); if (!b) return res.status(404).json({ error: 'no evidence published for this check' });
    if (req.method === 'GET') { const v = await verdicts(`verdicts/${c}/`); return res.status(200).json({ bundle: b, submitted: v.length }); }
    if (req.method !== 'POST') return res.status(405).json({ error: 'GET or POST' });
    const verdict = String(body.verdict || ''); const reasons = String(body.reasons || '').trim().slice(0, 4000);
    if (!VERDICTS.includes(verdict)) return res.status(400).json({ error: 'verdict must be verified, concerns or fail' });
    if (reasons.length < 20) return res.status(400).json({ error: 'please give reasons (at least 20 characters)' });
    const rec = { check_id: c, kind: b.kind, verdict, reasons, reviewer: String(body.reviewer || '').slice(0, 120),
      submissionId: String(body.submissionId || '').slice(0, 64), at: new Date().toISOString(), approved: false,
      note: 'Pending ImpactQuadrant approval; Terac pays only after we approve (manual_review).' };
    await put(`verdicts/${c}/${Date.now()}.json`, JSON.stringify(rec), { access: 'private', contentType: 'application/json', addRandomSuffix: true });
    return res.status(200).json({ ok: true, stored: true, verdict, submissionId: rec.submissionId });
  } catch (e) { return res.status(500).json({ error: 'server error' }); }
}
