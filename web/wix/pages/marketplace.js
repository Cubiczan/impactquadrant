// Page code for /marketplace. Elements: #repeater (dataset not required), inside: #title, #meta, #strengths,
// #valuation, #badge, #unlockBtn. Top: #headline, #subBtn (Deal Flow subscription).
import wixData from 'wix-data';
import wixWindow from 'wix-window';
import wixLocation from 'wix-location';
import { session } from 'wix-storage';
// Sandbox URLs; swap to live plan URLs only after Needs-Shyam go-live
const SUB_URL = 'https://sandbox.whop.com/checkout/plan_G3u2jR3bL0Mva';      // PE Deal Flow $499/mo
const DROP_URL = 'https://sandbox.whop.com/checkout/plan_PobV6T3Hak8FP';     // Off-Market Deal Drop $49/mo (individual buyers)
const TEARDOWN_URL = 'https://sandbox.whop.com/checkout/plan_K5LRRtkdPMull'; // Deal Teardown $149

$w.onReady(async () => {
  $w('#headline').text = 'Business brokerage, reimagined and automated.';
  $w('#subhead').text = 'Agents run the brokerage; humans guarantee trust. Every seller and buyer is verified by a real person before identities are shared.';
  $w('#subBtn').onClick(() => wixLocation.to(SUB_URL));          // "PE platforms: Get Deal Flow"
  $w('#dropBtn').onClick(() => wixLocation.to(DROP_URL));        // "Individual buyers: Off-Market Deal Drop"
  $w('#teardownBtn').onClick(() => wixLocation.to(TEARDOWN_URL)); // "Deal Teardown: AI red-flag review"
  $w('#calcBtn').onClick(() => wixLocation.to('/valuation-calculator')); // free lead magnet
  let q = wixData.query('Targets').ne('status', 'withdrawn');
  const box = JSON.parse(session.getItem('dealBox') || 'null'); // deal-box onboarding filter
  if (box && box.trades && box.trades.length) q = q.hasSome('trade', box.trades);
  if (box && box.regions && box.regions.length) q = q.hasSome('region', box.regions);
  if (box && box.country && box.country !== 'ANY') q = q.eq('country', box.country);
  $w('#dealBoxBtn').onClick(() => wixLocation.to('/deal-box'));
  $w('#freeTdBtn').onClick(() => wixLocation.to('/free-teardown'));
  const { items } = await q.descending('score').find();
  $w('#repeater').data = items.map(i => ({ ...i, _id: i._id }));
  $w('#repeater').onItemReady(($item, d) => {
    $item('#title').text = d.title;
    $item('#meta').text = `${d.country || 'US'} · ${d.region} · ${d.revenueBand} revenue · ${d.earningsBand} · ${d.yearsInBusiness} · ${d.dealType}`;
    $item('#strengths').text = d.strengths || '';
    $item('#valuation').text = `Value range: ${d.valuationBand}`; // estimate band, never an asking price
    $item('#badge').text = d.status === 'sold' ? 'Unlocked' : (d.trustBadge || 'Agent-vetted'); // 'Verified by human (Terac)' / 'Flagged' / pending
    $item('#equity').text = d.equityHint || '';
    $item('#unlockBtn').label = d.status === 'sold' ? 'Unlocked' : 'PE platform: NDA & unlock';
    $item('#indivBtn').label = `Individual buyer: NDA & unlock ($${d.individualUnlockPrice || 49})`;
    const gate = async (segment, url) => {
      // NDA click-through + buyer qualification gate BEFORE the paid Whop unlock
      const res = await wixWindow.openLightbox('NDA', { targetId: d.targetId, title: d.title, segment });
      if (res && res.accepted && url) wixLocation.to(url);
    };
    $item('#unlockBtn').onClick(() => gate('pe', d.checkoutUrl));
    $item('#indivBtn').onClick(() => gate('individual', d.checkoutUrlIndividual));
  });
});
