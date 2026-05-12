# PBI 1736268 DB-Only Rerun Evidence

Date: 2026-04-24

## Scope
- Source path validated: `CDS_STG_OWNER.STCCCALQ_GG_VW` -> `CCAL_OWNER.CDSM_RULE_MAP` -> `CCAL_OWNER.TXN/APA/FIP/TXN_RLTNP`
- Business day: `2026-03-30`
- Streams: `SRC_STM_ID IN (29,30,71,72)`
- Required target IDs checked: `TXN.TXN_SBTP_ID`, `TXN.EXEC_SBTP_ID`, `TXN.SRC_PCS_TP_ID`

## Saved TFS Artifacts
- Full work item context: `work_item_full_context.json`
- Hyperlinks extracted from TFS item: 5
- Attachments extracted from TFS item: 1 (`RE_ Forcing classification changes in CCAL.msg`)

## Hyperlink Retrieval Status
The following hyperlinks were discovered and attempted for extraction, but require authenticated SharePoint sign-in from this environment:
1. `NonStopTechnicalSpecification_CDSMANUC.docx`
2. `CDSMANUL.xlsx`
3. `Q_file to CCAL mapping S10DEL and S10REC.xlsx`
4. `Q_file to CCAL mapping S10TFRS.xlsx`
5. `CDSMANUL for CCAL.xlsx`

## New DB-Only Test Suite
- Folder: `PBI1736268-TrailerParsing-v3-DB-20260424_114435`
- Folder ID: `18`
- Test IDs: `394-405`
- Batch ID: `813abc42-b80`
- Result: `9 passed, 3 failed, 0 error`

## Diagnostic Append (Requested "do it")
- Added diagnostic test IDs: `406-408`
- Diagnostic batch ID: `0ce774da-a66`
- Diagnostic result: `3 passed, 0 failed, 0 error`
- Folder test count after append: `15`

### Diagnostic expected counts (captured from current slice)
- Missing source rows in `MATCH NOT FOUND` subset: `2`
- Missing regex winner rows: `20`
- Regex winner count: `0`

### Diagnostic row-level evidence files
- `diag_append_report_20260424_121025.json`
- `diag_missing_src_rows_20260424_121025.json`
- `diag_missing_winner_rows_20260424_121025.json`
- `diag_rule_fit_20260424_121025.json`

## Diagnostic Pack 2 (Grouping Root Cause)
- Report: `diag2_report_20260424_122739.json`
- Summary: `TOTAL_SRC_ROWS=18`, `NO_RULE_PREFILTER=0`, `REGEX_BLOCKED=18`, `REGEX_MATCHED=0`
- Top TERM_NAME contributors:
	- `ZTQ1.#Q056` -> `15`
	- `STKMULTIH` -> `2`
	- `ZTQQ.#QQ45` -> `1`
- Top TRAILER prefixes:
	- `DIRECT ROLLOVER - STOCK` -> `15`
	- `SECURITY RECEIVED IN BRANCH` -> `2`
	- `ACAT TEST` -> `1`

### Diagnostic Pack 2 files
- `diag2_no_winner_detail_20260424_122739.json`
- `diag2_group_term_20260424_122739.json`
- `diag2_group_record_type_20260424_122739.json`
- `diag2_group_trailer_prefix_20260424_122739.json`
- `diag2_blocking_summary_20260424_122739.json`

## Diagnostic Pack 3 (Closest Regex Candidates)
- Report: `diag3_report_20260424_123533.json`
- Prefixes analyzed:
	- `DIRECT ROLLOVER - STOCK`
	- `SECURITY RECEIVED IN BRANCH`
	- `ACAT TEST`
- Coverage summary:
	- `ACAT TEST`: `txn_cnt=1`, `candidate_rule_cnt=397`, `any_regex_match=0`
	- `DIRECT ROLLOVER - STOCK`: `txn_cnt=15`, `candidate_rule_cnt=403`, `any_regex_match=0`
	- `SECURITY RECEIVED IN BRANCH`: `txn_cnt=2`, `candidate_rule_cnt=403`, `any_regex_match=0`
- Conclusion: many prefilter-compatible rules exist, but regex still blocks all candidates for these prefixes.

### Diagnostic Pack 3 files
- `diag3_report_20260424_123533.json`
- `diag3_closest_candidates_20260424_123533.json`
- `diag3_prefix_coverage_20260424_123533.json`
- `diag3_prefix_term_split_20260424_123533.json`

## Diagnostic Pack 4 (Draft Regex Patch Candidates)
- Report: `diag4_regex_patch_drafts_20260424_124133.json`
- SQL draft (not executed): `diag4_regex_patch_drafts_20260424_124133.sql`
- Markdown review: `diag4_regex_patch_drafts_20260424_124133.md`
- Draft regex validation results:
	- `DIRECT ROLLOVER - STOCK`: `15/15` rows matched by draft regex
	- `SECURITY RECEIVED IN BRANCH`: `2/2` rows matched by draft regex
	- `ACAT TEST`: `1/1` rows matched by draft regex
- Drafts include inheritance options from top closest `CDSM_RULE_MAP_ID` candidates (no DB update performed).

## Why 3 Tests Failed
The three failed tests are expected data-quality gaps in this date slice, not SQL/runtime errors:
- `Regex parsing produced at least one winning rule` -> actual = `1` (no winning regex rows found)
- `Every scoped TXN has source MATCH NOT FOUND row` -> actual = `2` (2 scoped TXNs not in this source subset)
- `Every scoped TXN has regex winner row` -> actual = `20` (20 scoped TXNs without regex winner)

## Folder Link Verification (Non-Empty Proof)
- API snapshot after append: `test_count = 15`
- SQLite verification file: `%LOCALAPPDATA%/DBTestingTool/app.db`
- Linked rows in `test_case_folders`: `15`
- Linked test IDs: `394-405,406-408`

## Key Evidence Files
- `dbtool_v3b_result_20260424_114435.json`
- `dbtool_v3b_runs_813abc42-b80.json`
- `dbtool_v3b_probe_20260424_114435.json`
- `stcccalq_gg_vw_columns.json`
- `cdsm_rule_map_columns.json`
- `work_item_full_context.json`
