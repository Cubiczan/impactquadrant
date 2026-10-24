// Lightbox "NDA". Elements: #ndaText (text), #agree (checkbox), #buyerType (dropdown: PE platform / Independent sponsor / Strategic),
// #fundsProof (checkbox; label set from segment), #continueBtn, #cancelBtn.
import wixWindow from 'wix-window';
import wixData from 'wix-data';
$w.onReady(() => {
  const ctx = wixWindow.lightbox.getContext() || {};
  $w('#continueBtn').disable();
  $w('#fundsProof').label = ctx.segment === 'individual'
    ? 'I can show liquid funds or a lender pre-qualification letter sized to this deal before identity is released'
    : 'We are a fund/PE platform with recent closed add-ons, or can show proof of funds';
  const check = () => ($w('#agree').checked && $w('#fundsProof').checked) ? $w('#continueBtn').enable() : $w('#continueBtn').disable();
  $w('#agree').onChange(check); $w('#fundsProof').onChange(check);
  $w('#continueBtn').onClick(async () => {
    await wixData.insert('NdaAcceptances', { targetId: ctx.targetId, buyerType: $w('#buyerType').value, segment: ctx.segment, acceptedAt: new Date() });
    wixWindow.lightbox.close({ accepted: true });
  });
  $w('#cancelBtn').onClick(() => wixWindow.lightbox.close({ accepted: false }));
});
