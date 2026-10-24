// Server-side Mixpanel proxy helpers. Token lives ONLY in env (MIXPANEL_TOKEN); never sent to the browser.
export const FUNNEL = ['scorecard_viewed', 'scorecard_started', 'scorecard_completed', 'pricing_viewed', 'checkout_clicked', 'checkout_completed'];
const ALLOWED_PROPS = ['score_band', 'score', 'plan', 'sku', 'price', 'page', 'utm_source', 'utm_medium', 'utm_campaign', 'referrer_host', 'device'];
const ORIGINS = /^https:\/\/(www\.)?(impactquadrant\.com|[a-z0-9-]+\.wixsite\.com|dashboard-six-fawn-83\.vercel\.app)$/;
export function originOk(o) { return !o || ORIGINS.test(o); }
export function buildEvent(body, token, ip) {
  const { event, distinct_id, props } = body || {};
  if (!FUNNEL.includes(event)) return { error: 'event_not_allowed' };
  if (!distinct_id || !/^[A-Za-z0-9_-]{8,64}$/.test(String(distinct_id))) return { error: 'bad_distinct_id' };
  const p = {}; for (const k of ALLOWED_PROPS) if (props && props[k] != null) p[k] = String(props[k]).slice(0, 120);   // no PII (emails/names dropped)
  return { event: { event, properties: { ...p, token, distinct_id: String(distinct_id), time: Math.floor(Date.now() / 1000), $insert_id: crypto.randomUUID().replace(/-/g, '').slice(0, 32), ip: ip ? 1 : 0, brand: 'ImpactQuadrant' } } };
}
export async function send(ev, fetchImpl = fetch) {
  const r = await fetchImpl('https://api.mixpanel.com/track?strict=1', { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify([ev]) });
  return r.ok;
}
