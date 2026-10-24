// ImpactQuadrant nurture + delivery integrations for Whop payment.succeeded.
// Customer.io (CIO_LIVE=1) and ClickUp (CLICKUP_LIVE=1) are both OFF by default:
// when off, payloads are built and returned for logging only; nothing is sent.

export const PLAN_SKU = {
  plan_DxqY6XEluwGE6: 'valuation_snapshot',
  plan_dz3xCCAiGVTns: 'deal_access',
  plan_wFIIKYKAZbP1n: 'deal_room',
};

// Customer.io event names. Each starts a DRAFT automation in workspace 216782.
export const CIO_START_EVENT = {
  valuation_snapshot: 'iq_snapshot_purchased', // onboarding (1), upsell (4), proposed 30-day credit (6)
  deal_access: 'iq_deal_access_started',       // onboarding (2), upsell to Deal Room (5)
  deal_room: 'iq_deal_room_started',           // onboarding (3)
};

export const CLICKUP_PHASES = {
  valuation_snapshot: ['1. Intake: review checkout answers (company, revenue, EBITDA)',
    '2. Data review: normalize financials and add-backs', '3. Valuation draft: comps and value range',
    '4. QA: Shyam review', '5. Deliver Snapshot and note 30-day upgrade window'],
  deal_access: ['1. Welcome and buy-box intake (industry, size, region)',
    '2. Add to first-look deal alerts (GREEN jurisdictions only)',
    '3. Send first matched deal shortlist (within 7 days)', '4. 30-day check-in and Deal Room fit'],
  deal_room: ['1. Confirm access to the 3 forums', '2. Welcome post and buy-box intake',
    '3. Publish monthly valuation report or teardown', '4. 30-day check-in and topic requests'],
};
const LABEL = { valuation_snapshot: 'Valuation Snapshot', deal_access: 'Deal Access', deal_room: 'Deal Room' };

export function skuOf(data = {}) {
  const md = { ...(data?.plan?.metadata || {}), ...(data?.product?.metadata || {}), ...(data?.metadata || {}) };
  return md.sku || PLAN_SKU[data?.plan?.id || data?.plan_id] || 'unknown';
}

export function customerOf(data = {}) {
  const u = data.user || data.member?.user || {};
  const email = u.email || data.email || data.user_email;
  const name = u.name || u.username || '';
  return { id: email ? String(email).toLowerCase() : undefined, email, first_name: String(name).split(' ')[0] || undefined, whop_user_id: u.id || data.user_id };
}

// Renewals also fire payment.succeeded; only the first payment should start onboarding.
export const isRenewal = data => ['subscription_cycle', 'renewal'].includes(data?.billing_reason);

export function buildCio(evt) {
  const data = evt?.data || {}; const sku = skuOf(data); const c = customerOf(data);
  if (!c.id) return { skip: 'no_email' };
  const attrs = { email: c.email, first_name: c.first_name, whop_user_id: c.whop_user_id, [`iq_${sku}`]: true, last_payment_at: Math.floor(Date.now() / 1000) };
  const events = [{ name: 'iq_payment_succeeded', data: { sku, plan_id: data?.plan?.id, payment_id: data?.id, amount: data?.final_amount ?? data?.total ?? data?.subtotal } }];
  if (CIO_START_EVENT[sku] && !isRenewal(data)) events.push({ name: CIO_START_EVENT[sku], data: { sku, plan_id: data?.plan?.id } });
  return { id: c.id, attrs, events };
}

export function buildClickup(evt) {
  const data = evt?.data || {}; const sku = skuOf(data);
  if (!CLICKUP_PHASES[sku] || isRenewal(data)) return { skip: 'no_task_set' };
  const c = customerOf(data);
  return { parent: { name: `${LABEL[sku]} - ${c.email || data?.id || 'new client'}`, markdown_description: `Whop payment ${data?.id || ''} (${data?.plan?.id || sku}). Created by webhook.`, tags: ['iq-client', sku] },
    subtasks: CLICKUP_PHASES[sku] };
}

const b64 = s => Buffer.from(s).toString('base64');

export async function sendCio(env, p, f = fetch) {
  if (env.CIO_LIVE !== '1') return 'dry_run';
  if (p.skip) return `skipped:${p.skip}`;
  if (!env.CIO_SITE_ID || !env.CIO_API_KEY) return 'missing_keys';
  const base = `https://${env.CIO_REGION === 'eu' ? 'track-eu' : 'track'}.customer.io/api/v1/customers/${encodeURIComponent(p.id)}`;
  const headers = { Authorization: `Basic ${b64(`${env.CIO_SITE_ID}:${env.CIO_API_KEY}`)}`, 'Content-Type': 'application/json' };
  const r = await f(base, { method: 'PUT', headers, body: JSON.stringify(p.attrs) });
  if (!r.ok) return `identify_error:${r.status}`;
  for (const e of p.events) { const t = await f(`${base}/events`, { method: 'POST', headers, body: JSON.stringify(e) }); if (!t.ok) return `track_error:${t.status}`; }
  return 'sent';
}

export async function sendClickup(env, p, f = fetch) {
  if (env.CLICKUP_LIVE !== '1') return 'dry_run';
  if (p.skip) return `skipped:${p.skip}`;
  if (!env.CLICKUP_API_TOKEN || !env.CLICKUP_LIST_ID) return 'missing_keys';
  const url = `https://api.clickup.com/api/v2/list/${env.CLICKUP_LIST_ID}/task`;
  const headers = { Authorization: env.CLICKUP_API_TOKEN, 'Content-Type': 'application/json' };
  const r = await f(url, { method: 'POST', headers, body: JSON.stringify(p.parent) });
  if (!r.ok) return `parent_error:${r.status}`;
  const { id } = await r.json();
  for (const name of p.subtasks) { const s = await f(url, { method: 'POST', headers, body: JSON.stringify({ name, parent: id }) }); if (!s.ok) return `subtask_error:${s.status}`; }
  return `created:${id}`;
}

// Scorecard -> Customer.io band event (iq_scorecard_high|mid|low). Thresholds are a proposal.
export const scoreBand = s => (s >= 70 ? 'high' : s >= 40 ? 'mid' : 'low');
export const scorecardEvent = score => ({ name: `iq_scorecard_${scoreBand(Number(score))}`, data: { score: Number(score), band: scoreBand(Number(score)) } });
