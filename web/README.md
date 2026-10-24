# ImpactQuadrant web UI

Everything visitors see: the Wix site at https://www.impactquadrant.info and the Vercel dashboard at https://dashboard-six-fawn-83.vercel.app.

| Page | Source | Live URL |
|---|---|---|
| Services (pricing cards + Whop checkouts) | `wix/services-embed.html` (Wix HTML embed) | https://www.impactquadrant.info/services |
| Home | Wix editor page (no custom code) | https://www.impactquadrant.info |
| Marketplace (blind deal teasers) | `wix/pages/marketplace.js` (Velo) | https://www.impactquadrant.info/marketplace |
| Free teardown request | `wix/pages/free-teardown.js` (Velo) | https://www.impactquadrant.info/free-teardown |
| Deal box | `wix/pages/deal-box.js` (Velo) | https://www.impactquadrant.info/deal-box |
| NDA lightbox | `wix/lightboxes/nda.js` (Velo) | shown on Marketplace |
| Teaser push endpoint | `wix/backend/http-functions.js` (Velo HTTP functions) | `/_functions/targets` |
| Dashboard | `dashboard/public/index.html` | https://dashboard-six-fawn-83.vercel.app |
| Valuation calculator | `dashboard/public/calculator.html` | https://dashboard-six-fawn-83.vercel.app/calculator.html |
| Seller intake | `dashboard/public/intake.html` | https://dashboard-six-fawn-83.vercel.app/intake.html |
| Reviewer evidence page | `dashboard/public/review.html` | https://dashboard-six-fawn-83.vercel.app/review.html |

Screenshots: `screenshots/`.

## Run locally

Static preview (no APIs):

```bash
cd web/dashboard/public && python3 -m http.server 8080   # http://localhost:8080
open web/wix/services-embed.html                          # or open the file in any browser
```

Full dashboard with API routes (`/api/*`, Whop webhook) lives in `/dashboard`:

```bash
cd dashboard && npm install && npm test
npx vercel dev            # http://localhost:3000
```

Secrets (Whop webhook secret, approval secret, Wix push secret) come only from environment variables or Wix Secrets Manager; none are in this repo. Velo files are pasted into the Wix editor per `wix/APPLY.md`. The `/web` copy uses the secret name `IMPACTQUADRANT_PUSH_SECRET` and header `x-impactquadrant-secret`.
