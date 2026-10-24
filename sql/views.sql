CREATE OR REPLACE VIEW v_green_jurisdictions AS SELECT code, kind FROM jurisdictions WHERE status='GREEN';
CREATE OR REPLACE VIEW v_platform_activity AS
SELECT p.platform_id, p.name platform, s.name sponsor, p.priority, count(b.signal_id) n_signals,
       count(*) FILTER (WHERE b.type IN ('addon_press','registry') ) n_addons, max(b.date) last_signal
FROM platforms p JOIN sponsors s USING(sponsor_id) LEFT JOIN buyer_signals b USING(platform_id) GROUP BY ALL;
CREATE OR REPLACE VIEW v_listing_states AS
SELECT l.*, unnest(CAST(json(l.states_json) AS TEXT[])) state FROM listings l;
-- candidate buyer<->seller pairs: vertical + geography + size + GREEN seller jurisdiction
CREATE OR REPLACE VIEW v_match_candidates AS
SELECT DISTINCT m.mandate_id, p.name platform, s.name sponsor, l.listing_id, l.title, l.vertical, ls.state seller_state,
  j.status seller_jurisdiction, l.valuation_lo,
  (m.geo_json LIKE '%"US"%' OR m.geo_json LIKE '%"'||ls.state||'"%') geo_fit,
  (l.valuation_lo IS NULL OR l.valuation_lo BETWEEN coalesce(m.ev_min,0) AND coalesce(m.ev_max,1e12)) size_fit
FROM buyer_mandates m JOIN platforms p USING(platform_id) JOIN sponsors s USING(sponsor_id)
JOIN listings l ON l.vertical = m.vertical
JOIN v_listing_states ls ON ls.listing_id = l.listing_id
JOIN jurisdictions j ON j.code = ls.state AND j.status='GREEN'
WHERE m.active;
