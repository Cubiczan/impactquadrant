# ImpactQuadrant nurture + delivery (all DRAFT / OFF)

## Customer.io (workspace 216782) — 9 draft automations, every email action `sending_state: draft`, none started
UI: https://fly.customer.io/workspaces/216782/journeys/automations/<id>

| ID | Name | Trigger event | Steps |
|---|---|---|---|
| 1 | IQ Onboarding - Valuation Snapshot | iq_snapshot_purchased | email, wait 3d, email |
| 2 | IQ Onboarding - Deal Access | iq_deal_access_started | email, wait 5d, email |
| 3 | IQ Onboarding - Deal Room | iq_deal_room_started | email, wait 7d, email |
| 4 | IQ Upsell - Snapshot to Deal Access | iq_snapshot_purchased | wait 10d, email |
| 5 | IQ Upsell - Deal Access to Deal Room | iq_deal_access_started | wait 21d, email |
| 6 | IQ PROPOSED - 30-day Snapshot upgrade credit | iq_snapshot_purchased | wait 20d, email, wait 7d, email |
| 7 | IQ Scorecard - High band follow-up | iq_scorecard_high | email, wait 4d, email |
| 8 | IQ Scorecard - Mid band follow-up | iq_scorecard_mid | email, wait 7d, email |
| 9 | IQ Scorecard - Low band follow-up | iq_scorecard_low | email, wait 14d, email |

Copy: `copy.json` and `html/`. #6 is a PROPOSED offer: needs owner approval and a Whop promo/credit mechanism before it can run.

Before starting any automation: set sender identity, add exit conditions (e.g. exit upsell #4/#6 when `iq_deal_access_started` or `iq_deal_room_started`; exit #5 on `iq_deal_room_started`), and set re-entry to "once".

## Events sent by the webhook (dashboard/lib/integrations.js), only when CIO_LIVE=1
- identify: id = lowercased email; attrs email, first_name, whop_user_id, iq_<sku>=true
- `iq_payment_succeeded` on every payment.succeeded
- `iq_snapshot_purchased` / `iq_deal_access_started` / `iq_deal_room_started` on first payment (not renewals)
- Scorecard (to wire into the scorecard form): `iq_scorecard_high|mid|low` via `scorecardEvent(score)` (proposed thresholds 70/40)

Env (not set): CIO_LIVE, CIO_SITE_ID, CIO_API_KEY (Track API), optional CIO_REGION=eu.

## ClickUp — folder "ImpactQuadrant Client Delivery" (901712061269)
- `_Template - Phase task sets` list 901718006377: template tasks with phase subtasks
- `Active Clients` list 901718006378: where the webhook creates a parent task + phase subtasks per first payment

Env (not set): CLICKUP_LIVE, CLICKUP_API_TOKEN, CLICKUP_LIST_ID=901718006378.
