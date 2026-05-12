# PBI 1736268 Trailer Parsing Validation Rerun (v2)

Date: 2026-04-24

## Scope
Validation focus was narrowed to trailer parsing transformation path:
- Source: `CDS_STG_OWNER.STCCCALQ_GG_VW`
- Lookup rules: `CCAL_OWNER.CDSM_RULE_MAP`
- Targets: `CCAL_OWNER.TXN`, `CCAL_OWNER.APA`, `CCAL_OWNER.FIP`, `CCAL_OWNER.TXN_RLTNP`
- Required mapped target fields:
  - `TXN.TXN_SBTP_ID`
  - `TXN.SRC_PCS_TP_ID`
  - `TXN.EXEC_SBTP_ID`

Business day tested: `2026-03-30`
Streams tested: `SRC_STM_ID IN (29,30,71,72)`

## New Transformation-Based Suite
Created 12 join-based SQL tests (source+mapping+target), not target-only checks.

### db-testing-tool
- Folder: `PBI1736268-TrailerParsing-v2-DB-20260424_105520`
- Test IDs: `369-380`
- Batch: `143215c8-18b`
- Result: `12 passed, 0 failed, 0 error`

### IntelliTest
- Folder: `PBI1736268-TrailerParsing-v2-IT-20260424_105520`
- Test IDs: `41-52`
- Batch: `5b6de397-58b`
- Result: `12 passed, 0 failed, 0 error`

## What Was Validated
1. Row-level source-target linkage exists via `TXN_SRC_KEY` (base population check).
2. Parsed source fields used by trailer logic are populated:
   - `WS_EXECUTION_SUBTYPE`
   - `WS_CNX_IND`
3. Target ID mapping correctness from parsed source fields:
   - `EXEC_SBTP_ID` from `WS_EXECUTION_SUBTYPE` via `CCAL_OWNER.CL_VAL`
   - `SRC_PCS_TP_ID` from `WS_CNX_IND` via `CCAL_OWNER.SRC_PCS_TP`
   - `TXN_SBTP_ID` from `WS_SUBTYPE` via `CCAL_OWNER.CL_VAL` when present
   - `TXN_SBTP_ID` stays null when `WS_SUBTYPE` is null
4. Rule-map linkage check when source provides rule text:
   - `WS_TRAILER_RULE_TEXT_MATCH` maps to active `CDSM_RULE_MAP.TRLR_RULE_TXT`
   - `WS_EXECUTION_SUBTYPE` agrees with `CDSM_RULE_MAP.EXEC_SBTP_CD` when populated
5. Downstream integrity checks for parsed transactions:
   - APA exists for each parsed TXN (`APA.EXEC_ID = TXN.TXN_ID`)
   - FIP rows tied to parsed TXNs have valid APA
   - TXN_RLTNP rows tied to parsed TXNs have valid source/target TXN references

## db-testing-tool AI Chat Improvements Implemented
1. Test-generation prompt was tightened to SQL-first behavior:
   - Requires Oracle SQL in `sql` code blocks
   - Explicitly disallows JSON output for test generation mode
   - Instructs join-based transformation tests for trailer parsing using `STCCCALQ_GG_VW`, `CDSM_RULE_MAP`, and target tables

2. New API endpoint added to save chat SQL into test suite:
   - `POST /api/chat/conversations/{conv_id}/save-sql-tests`
   - Extracts SQL code blocks from assistant response
   - Splits statements and saves as `custom_sql` test cases
   - Creates/uses target folder and links tests automatically

3. Chat Assistant UI enhancement:
   - Added `Save SQL to Tests` button
   - Prompts for datasource id and folder name
   - Saves latest assistant SQL directly to test management

### Endpoint Verification
- Conversation created and SQL generated in chat
- Save endpoint executed successfully
- Verification folder: `_verify_chat_save_sql`
- Saved test count: `1`
- Saved test ID: `381`

## Key Notes
- This rerun addresses the original issue: tests are now transformation-aware and join-based.
- Validation used ODI-consistent source→lookup→target semantics rather than target-only null/count checks.
- Both tool executions succeeded with the same 12-test trailer-parsing suite.
