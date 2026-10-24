CREATE TABLE jurisdictions(code TEXT PRIMARY KEY, kind TEXT, status TEXT, basis TEXT, source_url TEXT, src_file TEXT);
CREATE TABLE sponsors(sponsor_id TEXT PRIMARY KEY, name TEXT, src_file TEXT);
CREATE TABLE platforms(platform_id TEXT PRIMARY KEY, name TEXT, sponsor_id TEXT, segment TEXT, priority INT, regions_json TEXT, thesis TEXT, src_file TEXT);
CREATE TABLE platform_verticals(platform_id TEXT, vertical TEXT, raw_segment TEXT, src_file TEXT, PRIMARY KEY(platform_id, vertical));
CREATE TABLE portfolio_companies(portco_id TEXT PRIMARY KEY, name TEXT, platform_id TEXT, city TEXT, state TEXT, trade TEXT, acquired_date TEXT, source_url TEXT, src_file TEXT);
CREATE TABLE buyer_signals(signal_id TEXT PRIMARY KEY, platform_id TEXT, type TEXT, date TEXT, note TEXT, url TEXT, src_file TEXT);
CREATE TABLE contacts(contact_id TEXT PRIMARY KEY, name TEXT, sponsor TEXT, email_domain TEXT, email TEXT, src_file TEXT); -- email NULL in public DB
CREATE TABLE operators(operator_id TEXT PRIMARY KEY, name TEXT, trade TEXT, vertical TEXT, town TEXT, state TEXT, country TEXT, website TEXT, notes TEXT, src_file TEXT);
CREATE TABLE listings(listing_id TEXT PRIMARY KEY, title TEXT, trade TEXT, vertical TEXT, region TEXT, states_json TEXT, revenue_band TEXT, earnings_band TEXT, valuation_lo DOUBLE, valuation_band TEXT, score INT, verified BOOLEAN, status TEXT, src_file TEXT);
CREATE TABLE raw_records(src_file TEXT, sheet TEXT, row_no INT, data_json TEXT);
-- agent-maintained (both sides + matching)
CREATE TABLE agent_runs(run_id TEXT PRIMARY KEY, agent TEXT, side TEXT CHECK(side IN ('buy','sell','match')), started_at TIMESTAMP, finished_at TIMESTAMP, input_json TEXT, output_json TEXT);
CREATE TABLE agent_actions(action_id TEXT PRIMARY KEY, run_id TEXT, agent TEXT, side TEXT, action TEXT, entity_id TEXT, input_json TEXT, output_json TEXT, ts TIMESTAMP);
CREATE TABLE buyer_mandates(mandate_id TEXT PRIMARY KEY, platform_id TEXT, vertical TEXT, geo_json TEXT, ebitda_min DOUBLE, ev_min DOUBLE, ev_max DOUBLE, activity_score INT, active BOOLEAN, refreshed_at TIMESTAMP, evidence_json TEXT);
CREATE TABLE seller_pipeline(listing_id TEXT PRIMARY KEY, operator_id TEXT, verification_status TEXT, terac_check_required BOOLEAN, terac_status TEXT, jurisdiction_status TEXT, updated_at TIMESTAMP);
CREATE TABLE matches(match_id TEXT PRIMARY KEY, mandate_id TEXT, listing_id TEXT, score DOUBLE, rationale TEXT, status TEXT CHECK(status IN ('proposed','intro_requested','nda','closed','rejected')), created_at TIMESTAMP, updated_at TIMESTAMP);
