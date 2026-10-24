// Page /free-teardown. Lead magnet: this week's free AI teardown of one anonymized listing, behind email signup.
// Elements: #email, #joinBtn, #gate (box shown before signup), #teardown (box hidden until signup), #tdTitle, #tdFlags, #tdVerdict, #teardownCta
import wixData from 'wix-data';
import wixLocation from 'wix-location';
const TEARDOWN_URL = 'https://sandbox.whop.com/checkout/plan_K5LRRtkdPMull';
const TD = {
  "listing": "Precision Machining business, Carolinas",
  "value_range": "$7.2M-$27.8M (estimate, EBITDA basis)",
  "down_payment": "Estimate: deal size likely above SBA 7(a) loan limits; PE / conventional financing",
  "red_flags": [
    "Ask for 3 years of tax returns vs. P&L: add-backs over 20% of earnings trigger a QoE review.",
    "Customer concentration: request top-10 customer share before LOI.",
    "Owner dependence: who quotes jobs and holds key accounts today?"
  ],
  "verdict": "Worth a call if concentration < 30% and add-backs are documented.",
  "cta": "Want this on a deal you found? Deal Teardown, $149.",
  "tone": "No pressure. No $10k course. Just the deals."
}; // replaced by scripts/build_wix.py from out/07_free_teardown.json
$w.onReady(() => {
  $w('#teardown').hide();
  $w('#joinBtn').onClick(async () => {
    const email = $w('#email').value; if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return;
    await wixData.insert('Leads', { email, source: 'free-teardown', createdAt: new Date() }); // stored only; sending needs Shyam
    $w('#tdTitle').text = `${TD.listing} · ${TD.value_range}`;
    $w('#tdFlags').text = TD.red_flags.map(f => '• ' + f).join('\n');
    $w('#tdVerdict').text = `${TD.verdict}\n${TD.down_payment}`;
    $w('#gate').hide(); $w('#teardown').show();
  });
  $w('#teardownCta').onClick(() => wixLocation.to(TEARDOWN_URL)); // soft CTA, no pressure
});
