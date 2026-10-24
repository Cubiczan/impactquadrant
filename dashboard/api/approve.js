// Human approval gate: requires FULFILL_APPROVE_SECRET. Records approval; delivery happens via Whop after rollupops.fulfillment.approve(). No auto-send.
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const { order, secret } = req.body || {};
  if (!process.env.FULFILL_APPROVE_SECRET || secret !== process.env.FULFILL_APPROVE_SECRET) return res.status(401).json({ error: 'approval secret required' });
  console.log(JSON.stringify({ approved: order, at: new Date().toISOString() }));
  return res.status(200).json({ ok: true, order, status: 'approved -> delivered via Whop by orchestrator' });
}
