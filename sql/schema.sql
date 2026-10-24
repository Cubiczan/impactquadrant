CREATE TABLE jurisdictions(code TEXT PRIMARY KEY, kind TEXT, status TEXT, basis TEXT, source_url TEXT, src_file TEXT);
CREATE TABLE sponsors(sponsor_id TEXT PRIMARY KEY, name TEXT, website TEXT, hq_city TEXT, hq_state TEXT, country TEXT, rollup_model TEXT, active_sectors TEXT, evidence_url TEXT, firm_status TEXT, firm_status_notes TEXT, agreement_status TEXT, src_file TEXT); -- agreement_status only populated in the PRIVATE build
CREATE TABLE platforms(platform_id TEXT PRIMARY KEY, name TEXT, sponsor_id TEXT, segment TEXT, priority INT, regions_json TEXT, thesis TEXT, hq TEXT, appetite TEXT, deal_size TEXT, addons_logged INT, status TEXT, confidence TEXT, source_urls TEXT, src_file TEXT);
CREATE TABLE platform_verticals(platform_id TEXT, vertical TEXT, raw_segment TEXT, src_file TEXT, PRIMARY KEY(platform_id, vertical));
CREATE TABLE portfolio_companies(portco_id TEXT PRIMARY KEY, name TEXT, platform_id TEXT, city TEXT, state TEXT, trade TEXT, acquired_date TEXT, source_url TEXT, src_file TEXT);
CREATE TABLE buyer_signals(signal_id TEXT PRIMARY KEY, platform_id TEXT, type TEXT, date TEXT, note TEXT, url TEXT, src_file TEXT);
CREATE TABLE contacts(contact_id TEXT PRIMARY KEY, name TEXT, title TEXT, org TEXT, email_domain TEXT, email TEXT, phone TEXT, src_file TEXT); -- name/email/phone NULL in public DB
CREATE TABLE operators(operator_id TEXT PRIMARY KEY, name TEXT, trade TEXT, vertical TEXT, service_group TEXT, town TEXT, state TEXT, country TEXT, website TEXT, size_estimate TEXT, ownership TEXT, sponsor_if_known TEXT, independent BOOLEAN, sale_intent TEXT, lane TEXT, notes TEXT, evidence_url TEXT, src_file TEXT);
CREATE TABLE listings(listing_id TEXT PRIMARY KEY, title TEXT, trade TEXT, vertical TEXT, region TEXT, states_json TEXT, revenue_band TEXT, earnings_band TEXT, valuation_lo DOUBLE, valuation_band TEXT, score INT, verified BOOLEAN, status TEXT, src_file TEXT);
CREATE TABLE candidate_buyer_map(company TEXT, lane TEXT, best_partner_buyer TEXT, other_buyers TEXT, rationale TEXT, confidence TEXT, src_file TEXT);
CREATE TABLE exclusions(entity TEXT, category TEXT, reason TEXT, src_file TEXT);
CREATE TABLE documents(doc_id TEXT PRIMARY KEY, title TEXT, kind TEXT, body TEXT, src_file TEXT);
CREATE TABLE raw_records(src_file TEXT, sheet TEXT, row_no INT, data_json TEXT);
-- agent-maintained (both sides + matching)
CREATE TABLE agent_runs(run_id TEXT PRIMARY KEY, agent TEXT, side TEXT CHECK(side IN ('buy','sell','match','orchestrate','whop')), started_at TIMESTAMP, finished_at TIMESTAMP, input_json TEXT, output_json TEXT);
CREATE TABLE agent_actions(action_id TEXT PRIMARY KEY, run_id TEXT, agent TEXT, side TEXT, action TEXT, entity_id TEXT, input_json TEXT, output_json TEXT, ts TIMESTAMP);
CREATE TABLE buyer_mandates(mandate_id TEXT PRIMARY KEY, platform_id TEXT, vertical TEXT, geo_json TEXT, ebitda_min DOUBLE, ev_min DOUBLE, ev_max DOUBLE, criteria TEXT, authoritative BOOLEAN, activity_score INT, active BOOLEAN, refreshed_at TIMESTAMP, evidence_json TEXT);
CREATE TABLE seller_pipeline(seller_id TEXT PRIMARY KEY, kind TEXT, name TEXT, vertical TEXT, state TEXT, verification_status TEXT, terac_check_required BOOLEAN, terac_status TEXT, jurisdiction_status TEXT, source TEXT, updated_at TIMESTAMP);
CREATE TABLE matches(match_id TEXT PRIMARY KEY, mandate_id TEXT, seller_id TEXT, score DOUBLE, rationale TEXT, status TEXT CHECK(status IN ('proposed','intro_requested','nda','closed','rejected')), created_at TIMESTAMP, updated_at TIMESTAMP);
CREATE TABLE whop_outbox(payload_id TEXT PRIMARY KEY, match_id TEXT, kind TEXT, payload_json TEXT, published BOOLEAN, whop_response TEXT, created_at TIMESTAMP);
CREATE TABLE whop_events(event_id TEXT PRIMARY KEY, type TEXT, plan_id TEXT, membership_id TEXT, amount DOUBLE, metadata_json TEXT, received_at TIMESTAMP);
