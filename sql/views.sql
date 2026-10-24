CREATE OR REPLACE VIEW v_green_jurisdictions AS SELECT code, kind FROM jurisdictions WHERE status='GREEN';
CREATE OR REPLACE VIEW v_platform_activity AS
SELECT p.platform_id, p.name platform, s.name sponsor, p.priority, count(b.signal_id) n_signals,
       count(b.signal_id) FILTER (WHERE b.type IN ('addon_press','registry','addon_log')) n_addons, max(b.date) last_signal
FROM platforms p JOIN sponsors s USING(sponsor_id) LEFT JOIN buyer_signals b USING(platform_id) GROUP BY ALL;
CREATE OR REPLACE VIEW v_listing_states AS SELECT l.*, unnest(CAST(json(l.states_json) AS TEXT[])) state FROM listings l;
-- buyer<->seller candidates: vertical + geography + size + GREEN seller state
CREATE OR REPLACE VIEW v_match_candidates AS
SELECT m.mandate_id, m.authoritative, p.name platform, s.name sponsor, s.agreement_status, sp.seller_id, sp.kind seller_kind, sp.name seller, sp.vertical,
  sp.state seller_state, (m.geo_json LIKE '%"US"%' OR m.geo_json LIKE '%"'||sp.state||'"%') geo_fit,
  coalesce(l.valuation_lo BETWEEN coalesce(m.ev_min,0) AND coalesce(m.ev_max,1e12), TRUE) size_fit, m.activity_score
FROM buyer_mandates m JOIN platforms p USING(platform_id) JOIN sponsors s USING(sponsor_id)
JOIN seller_pipeline sp ON sp.vertical = m.vertical AND sp.vertical <> 'other' AND sp.jurisdiction_status='GREEN'
LEFT JOIN listings l ON l.listing_id = sp.seller_id
WHERE m.active;
CREATE OR REPLACE VIEW v_agent_summary AS
SELECT agent, side, count(*) runs, max(finished_at) last_run FROM agent_runs GROUP BY ALL;
