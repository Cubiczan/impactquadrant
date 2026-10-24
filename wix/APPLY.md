# Apply ImpactQuadrant to impactquadrant.info (Wix + Velo). Do NOT publish until Shyam reviews.
Box check (2026-10-24): no Wix API key, no WIX_* env, no Wix CLI login, no saved Wix session. Editing must be done in the browser (Wix editor), signed in by Shyam.

## Browser task, step by step
1. Sign in at https://manage.wix.com (Shyam signs in; agent never handles the password). Open the impactquadrant.info site → **Edit Site**.
2. Turn on **Dev Mode** (Editor top bar → Dev Mode → Turn on Dev Mode / Velo).
3. **CMS → Create collection `Targets`** (permissions: read = Anyone, write = Admin). Fields (field key = name, type):
   targetId (Text, primary-ish), title (Text), trade (Text), region (Text), country (Text), revenueBand (Text), earningsBand (Text), yearsInBusiness (Text), strengths (Text), dealType (Text), valuationBand (Text), score (Number), verified (Boolean), status (Text), trustBadge (Text), checkoutUrl (URL), checkoutUrlIndividual (URL), individualUnlockPrice (Number), equityHint (Text), staleAfter (Text).
4. Create collections **`NdaAcceptances`** (targetId, buyerType, segment, acceptedAt; read Admin, create Anyone), **`DealBoxes`** (segment, trades[Tags], regions[Tags], country, stateProvince, currency, maxPrice, funding, email, createdAt; create Anyone, read Admin), **`Leads`** (email, source, createdAt; create Anyone, read Admin).
5. **Import data**: Targets → ⋯ → Import CSV → `wix/targets_import.csv` (rename column `stale_after` → `staleAfter`). (Alternative after step 6: run `python -m rollupops.wix_push --send`.)
6. **Secrets Manager** (Developer Tools → Secrets Manager): add `ROLLUPOPS_PUSH_SECRET` = a new random value; put the same value in local `.env` / Vercel env `WIX_PUSH_SECRET`. Never paste it in chat.
7. **Backend**: Code panel → Backend → create `http-functions.js` → paste `wix/backend/http-functions.js`.
8. **Page `/marketplace`** (Add page, URL slug `marketplace`): add text `#headline`, text `#subhead`, buttons `#subBtn` ("PE platforms: Get Deal Flow $499/mo"), `#dropBtn` ("Individual buyers: Off-Market Deal Drop $49/mo"), `#teardownBtn` ("Deal Teardown $149"), `#calcBtn` ("Free valuation calculator"), `#dealBoxBtn` ("Set your deal box"), `#freeTdBtn` ("Free weekly teardown"). Add a **Repeater** `#repeater` with items: `#title`, `#meta`, `#strengths`, `#valuation`, `#equity`, `#badge`, buttons `#unlockBtn`, `#indivBtn`. Paste page code `wix/pages/marketplace.js`.
9. **Lightbox `NDA`** (Add → Lightbox, name exactly `NDA`): text `#ndaText` (paste `wix/nda_text.md`), checkbox `#agree`, dropdown `#buyerType` (PE platform / Independent sponsor / Individual buyer / Strategic), checkbox `#fundsProof`, buttons `#continueBtn`, `#cancelBtn`. Paste `wix/lightboxes/nda.js`.
10. **Page `/deal-box`**: radio `#segment`, checkbox groups `#trades`, `#regions`, dropdowns `#country`, `#currency`, `#maxPrice`, `#funding`, inputs `#stateProvince`, `#email`, button `#saveBtn`, text `#msg`. Paste `wix/pages/deal-box.js`.
11. **Page `/free-teardown`**: input `#email`, button `#joinBtn`, box `#gate`, box `#teardown` containing `#tdTitle`, `#tdFlags`, `#tdVerdict`, button `#teardownCta`. Paste `wix/build/free-teardown.js` (generated; has this week's teardown inlined).
12. **Page `/valuation-calculator`**: Add → Embed Code → Embed a site → `https://dashboard-six-fawn-83.vercel.app/calculator.html` (or paste the HTML from `dashboard/public/calculator.html` in an HTML embed).
13. **Page `/thanks`**: "Thanks. Your unlock is confirmed; the blind deal memo is in your Whop account. Owner identity is released after verification."
14. **Homepage edits**: hero headline "Business brokerage, reimagined and automated."; sub "Agents run the brokerage; humans guarantee trust."; two CTAs → `/marketplace` ("Browse vetted deals") and `/deal-box` ("Set your deal box"); add **Marketplace** to the site menu. Global copy (no US-only wording). No-pressure tone.
15. **Preview** and test: open /marketplace, click an unlock → NDA → Whop sandbox checkout (card 4242 4242 4242 4242). Test `GET https://<site>/_functions/targets` (works only after publish; in preview use the `-dev` functions URL Wix shows).
16. **Stop and report to Shyam before Publish.**

Sandbox checkout links are hard-coded at the top of `marketplace.js`/`free-teardown.js`; swap to live plan URLs only after the Needs-Shyam go-live.
