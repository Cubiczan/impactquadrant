// Page /deal-box (onboarding: buyer criteria filter). Elements: #segment (radio: PE platform / Individual buyer),
// #trades (checkbox group: precision machining, industrial distribution, fabrication), #regions (checkbox group),
// #country (dropdown, ISO country), #stateProvince (input), #currency (dropdown, display only), #maxPrice (dropdown: <$1M, $1-3M, $3-10M, $10M+), #funding (dropdown: SBA / cash / fund), #email (input), #saveBtn, #msg.
import wixData from 'wix-data';
import wixLocation from 'wix-location';
import { session } from 'wix-storage';
$w.onReady(() => {
  $w('#saveBtn').onClick(async () => {
    const box = { segment: $w('#segment').value, trades: $w('#trades').value, regions: $w('#regions').value, country: $w('#country').value, stateProvince: $w('#stateProvince').value, currency: $w('#currency').value,
      maxPrice: $w('#maxPrice').value, funding: $w('#funding').value, email: $w('#email').value, createdAt: new Date() };
    await wixData.insert('DealBoxes', box);           // agent reads this to match deals; no emails are sent automatically
    session.setItem('dealBox', JSON.stringify(box));
    $w('#msg').text = 'Saved. Your marketplace view is now filtered to your deal box.';
    wixLocation.to('/marketplace');
  });
});
