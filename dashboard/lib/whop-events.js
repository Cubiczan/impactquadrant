// ImpactQuadrant Whop event handling (pure, testable). No money moves here; no messages are sent.
import crypto from 'node:crypto';
import { PLAN_SKU } from './integrations.js';

const TOLERANCE_S = 300;

// Standard Webhooks signature check (Whop uses webhook-id / webhook-timestamp / webhook-signature).
export function verifySignature(secret, headers, body, nowS = Math.floor(Date.now() / 1000)) {
  if (!secret) return { ok: false, reason: 'secret_not_configured' };
  const id = headers['webhook-id'], ts = headers['webhook-timestamp'], sig = headers['webhook-signature'] || '';
  if (!id || !ts || !sig) return { ok: false, reason: 'missing_headers' };
  if (Math.abs(nowS - Number(ts)) > TOLERANCE_S) return { ok: false, reason: 'stale_timestamp' };
  const key = Buffer.from(secret.replace(/^whsec_/, ''), 'base64');
  const expect = Buffer.from(crypto.createHmac('sha256', key).update(`${id}.${ts}.${body}`).digest('base64'));
  const match = sig.split(' ').some(s => {
    const v = Buffer.from(s.split(',')[1] || '');
    return v.length === expect.length && crypto.timingSafeEqual(v, expect);
  });
  return match ? { ok: true } : { ok: false, reason: 'bad_signature' };
}

const SKU_ACTIONS = {
  valuation_snapshot: ['onboarding:valuation_snapshot'],
  deal_access: ['onboarding:deal_access', 'grant:deal_alerts'],
  deal_room: ['onboarding:deal_room', 'grant:deal_room'],
  deal_deposit: ['onboarding:deal_deposit', 'hold:refundable_deposit'],
  owner_listing: ['onboarding:owner_listing', 'queue:owner_verification'],
};

// Map a Whop event to queued agent tasks. Every task is a draft for owner approval.
export function planActions(evt, env = {}) {
  const type = evt?.type || evt?.action || 'unknown';
  const data = evt?.data || {};
  const md = { ...(data?.plan?.metadata || {}), ...(data?.product?.metadata || {}), ...(data?.metadata || {}) };
  const sku = md.sku || PLAN_SKU[data?.plan?.id || data?.plan_id] || 'unknown';
  const tasks = [];
  if (['payment.succeeded', 'membership.went_valid', 'membership.activated'].includes(type)) {
    for (const a of SKU_ACTIONS[sku] || ['onboarding:generic']) tasks.push(a);
  } else if (['membership.went_invalid', 'membership.deactivated'].includes(type)) {
    tasks.push('revoke:access_review');
  } else if (type === 'refund.created' || type === 'payment.refunded') {
    tasks.push('log:refund');
  } else if (type === 'payment.failed') {
    tasks.push('shyam:review_failed_payment');
  } else if (type === 'dispute.created') {
    tasks.push('shyam:review_dispute');
  }
  // Terac owner verification: only sellers (business owners), never buyers. Launching a study
  // additionally requires TERAC_LIVE plus an owner approval record, so here it is only queued.
  const terac = tasks.includes('queue:owner_verification')
    ? (env.TERAC_LIVE === '1' ? 'queued_pending_owner_approval' : 'queued_dry_run')
    : 'none';
  return { type, sku, tasks, terac, status: tasks.length ? 'queued_for_owner_approval' : 'ignored',
    membership_id: data?.membership_id || data?.membership?.id || (String(data?.id || '').startsWith('mem_') ? data.id : undefined),
    payment_id: String(data?.id || '').startsWith('pay_') ? data.id : undefined };
}
