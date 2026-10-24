// Velo backend: https://impactquadrant.info/_functions/targets
// POST (agent push, header x-rollupops-secret) upserts blind teasers into CMS "Targets".
// GET returns public teaser fields only. PATCH-style status update via POST {targetId,status}.
import { ok, badRequest, forbidden, serverError } from 'wix-http-functions';
import wixData from 'wix-data';
import { getSecret } from 'wix-secrets-backend';

const PUBLIC = ['targetId','title','trade','region','revenueBand','earningsBand','yearsInBusiness','strengths',
  'dealType','valuationBand','score','verified','status','checkoutUrl','checkoutUrlIndividual','individualUnlockPrice','equityHint','trustBadge','country','staleAfter'];
const OPTS = { suppressAuth: true };
const json = (body) => ({ headers: { 'Content-Type': 'application/json' }, body });

async function authorized(request) {
  const secret = await getSecret('ROLLUPOPS_PUSH_SECRET');
  return request.headers['x-rollupops-secret'] === secret;
}

export async function get_targets() {
  const r = await wixData.query('Targets').ne('status', 'withdrawn').descending('score').limit(100).find(OPTS);
  return ok(json(r.items.map(i => Object.fromEntries(PUBLIC.map(k => [k, i[k]])))));
}

export async function post_targets(request) {
  try {
    if (!(await authorized(request))) return forbidden(json({ error: 'bad secret' }));
    const payload = await request.body.json();
    const items = Array.isArray(payload) ? payload : [payload];
    const results = [];
    for (const it of items) {
      if (!it.targetId) return badRequest(json({ error: 'targetId required' }));
      const clean = Object.fromEntries(PUBLIC.filter(k => k in it).map(k => [k, k === 'strengths' ? (it[k] || []).join(' · ') : it[k]]));
      const found = await wixData.query('Targets').eq('targetId', it.targetId).find(OPTS);
      results.push(found.items.length
        ? await wixData.update('Targets', { ...found.items[0], ...clean }, OPTS)
        : await wixData.insert('Targets', clean, OPTS));
    }
    return ok(json({ upserted: results.length }));
  } catch (e) { return serverError(json({ error: String(e) })); }
}
