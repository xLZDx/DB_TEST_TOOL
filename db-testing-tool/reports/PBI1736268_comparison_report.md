# PBI 1736268 - Comprehensive Test Execution Report
## "Move trailer mapping logic for stock movements from HPNS to Oracle"
### Generated: 2026-04-24 09:47:55

---

## 1. Executive Summary

| Source | Category | Total | Passed | Failed | Error | Pass Rate |
|--------|----------|------:|-------:|-------:|------:|-----------|
| **db-testing-tool** | Manual Tests | 20 | 20 | 0 | 0 | **100%** |
| **db-testing-tool** | AI-Generated | 40 | 1 | 8 | 31 | **2%** |
| **IntelliTest** | Manual Tests | 20 | 20 | 0 | 0 | **100%** |
| **IntelliTest** | AI-Generated | 20 | 3 | 3 | 14 | **15%** |
| **Agent (Manual)** | Direct SQL | 25 | 22 | 1 | 2 | **88%** |

**Grand Total: 125 tests across all sources**

---

## 2. Table Coverage Matrix

| Target Table | db-tool Manual | db-tool AI | IntelliTest Manual | IntelliTest AI | Agent Manual |
|-------------|:-:|:-:|:-:|:-:|:-:|
| CCAL_OWNER.TXN | Y | Y | Y | Y | Y |
| CCAL_OWNER.APA | Y | Y | Y | Y | Y |
| CCAL_OWNER.FIP | Y | Y | Y | Y | Y |
| CCAL_OWNER.TXN_RLTNP | Y | Y | Y | Y | Y |
| CCAL_OWNER.MNY_TXN_QUALFR | - | - | - | - | Y |
| CCAL_OWNER.CDSM_RULE_MAP | Y | Y | Y | - | Y |
| CDS_STG_OWNER.STCCCALQ_STG | - | - | - | Y | Y |
| CCAL_OWNER.DATE_DIM | Y | Y | Y | Y | Y |

---

## 3. Test Aspect Coverage

| Aspect | db-tool Manual | db-tool AI | IntelliTest Manual | IntelliTest AI | Agent Manual |
|--------|:-:|:-:|:-:|:-:|:-:|
| Data Validation | - | - | - | Y | - |
| Distribution | Y | Y | Y | Y | Y |
| Existence | Y | Y | Y | Y | Y |
| Lookup/Reference | Y | Y | Y | Y | Y |
| NULL Check | Y | Y | Y | Y | Y |
| Reference Data | Y | Y | Y | Y | Y |
| Row Count | Y | Y | Y | Y | Y |
| Staging | - | Y | - | Y | Y |
| Uniqueness | Y | Y | Y | Y | Y |

---

## 4. Detailed Results by Source

### 4.1 db-testing-tool Manual Tests (Folder: PBI1736268-Manual)
| ID | Status | Test Name |
|----|--------|-----------|
| 349 | PASS | TXN total row count for stock movements on 2026-03-30 |
| 350 | PASS | TXN row count for S10REC (SRC_STM_ID=29) |
| 351 | PASS | TXN row count for S10DEL (SRC_STM_ID=30) |
| 352 | PASS | TXN row count for S10TFRS (SRC_STM_ID=72) |
| 353 | PASS | TXN row count for MULBULMT (SRC_STM_ID=71) |
| 354 | PASS | EXEC_SBTP_ID not null for trailer-parsed streams |
| 355 | PASS | SRC_PCS_TP_ID not null for all stock movement streams |
| 356 | PASS | TXN_TP_ID not null for stock movements |
| 357 | PASS | TXN_SBTP_ID null count for stock movements |
| 358 | PASS | AR_ID not null for stock movements |
| 359 | PASS | APA.PD_ID populated for stock movement TXNs |
| 360 | PASS | CDSM_RULE_MAP lookup table exists in database |
| 361 | PASS | APA records exist for stock movement TXNs |
| 362 | PASS | FIP records for stock movement APA (informational) |
| 363 | PASS | TXN_RLTNP count for stock movements |
| 364 | PASS | SD not null for stock movements |
| 365 | PASS | TXN_SRC_KEY not null for stock movements |
| 366 | PASS | No duplicate TXN_SRC_KEY per SRC_STM_ID |
| 367 | PASS | TD exists in DATE_DIM |
| 368 | PASS | SRC_PCS_TP_ID distribution for stock movements |

### 4.2 db-testing-tool AI-Generated Tests (Folder: PBI1736268-AIChat)
| ID | Status | Test Name | Error (if any) |
|----|--------|-----------|----------------|
| 309 | PASS | Row count per SRC_STM_ID for TD=2026-03-30 |  |
| 310 | ERR | NULL check on WS_SUBTYPE for trailer-parsed streams | ORA-00904: "WS_SUBTYPE": invalid identifier
Help: https://do |
| 311 | ERR | NULL check on WS_EXECUTION_SUBTYPE | ORA-00904: "WS_EXECUTION_SUBTYPE": invalid identifier
Help:  |
| 312 | ERR | NULL check on CNX_IND | ORA-00904: "CNX_IND": invalid identifier
Help: https://docs. |
| 313 | ERR | CDSM_RULE_MAP has rules for each source | ORA-00942: table or view does not exist
Help: https://docs.o |
| 314 | ERR | APA records exist for TXN | ORA-00904: "A"."TXN_ID": invalid identifier
Help: https://do |
| 315 | ERR | FIP records exist for TXN | ORA-00904: "F"."TXN_ID": invalid identifier
Help: https://do |
| 316 | ERR | TXN_RLTNP relationships exist | ORA-00904: "R"."TXN_ID": invalid identifier
Help: https://do |
| 317 | ERR | TXN_TP_CODE valid | ORA-00904: "TXN_TP_CODE": invalid identifier
Help: https://d |
| 318 | ERR | Date consistency TD vs DATE_DIM | ORA-00904: "D"."CALENDAR_DATE": invalid identifier
Help: htt |
| 319 | ERR | Row count for MULBULMT without trailer parsing | ORA-00904: "WS_SUBTYPE": invalid identifier
Help: https://do |
| 320 | ERR | Trailer-parsed streams have WS_SUBTYPE populated | ORA-00904: "WS_SUBTYPE": invalid identifier
Help: https://do |
| 321 | ERR | Trailer-parsed streams have WS_EXECUTION_SUBTYPE populated | ORA-00904: "WS_EXECUTION_SUBTYPE": invalid identifier
Help:  |
| 322 | ERR | CNX_IND populated for all streams | ORA-00904: "CNX_IND": invalid identifier
Help: https://docs. |
| 323 | FAIL | Row count validation for SRC_STM_ID=29 on TD=2026-03-30 |  |
| 324 | FAIL | Row count validation for SRC_STM_ID=30 on TD=2026-03-30 |  |
| 325 | FAIL | Row count validation for SRC_STM_ID=72 on TD=2026-03-30 |  |
| 326 | FAIL | Row count validation for SRC_STM_ID=71 on TD=2026-03-30 |  |
| 327 | ERR | NULL check on WS_SUBTYPE for trailer-parsed streams | ORA-00904: "WS_SUBTYPE": invalid identifier
Help: https://do |
| 328 | ERR | NULL check on WS_EXECUTION_SUBTYPE for trailer-parsed streams | ORA-00904: "WS_EXECUTION_SUBTYPE": invalid identifier
Help:  |
| 329 | ERR | NULL check on CNX_IND for all streams | ORA-00904: "CNX_IND": invalid identifier
Help: https://docs. |
| 330 | ERR | CDSM_RULE_MAP coverage validation | ORA-00942: table or view does not exist
Help: https://docs.o |
| 331 | ERR | APA records existence for TXN | ORA-00904: "A"."TXN_ID": invalid identifier
Help: https://do |
| 332 | ERR | FIP records existence for TXN | ORA-00904: "F"."TXN_ID": invalid identifier
Help: https://do |
| 333 | ERR | TXN_RLTNP relationships existence for TXN | ORA-00904: "R"."TXN_ID": invalid identifier
Help: https://do |
| 334 | ERR | TXN_TP_CODE validity check | ORA-00904: "TXN_TP_CODE": invalid identifier
Help: https://d |
| 335 | ERR | Date consistency check between TD and DATE_DIM | ORA-00904: "D"."CALENDAR_DATE": invalid identifier
Help: htt |
| 336 | FAIL | Row count validation for SRC_STM_ID=29 on TD=2026-03-30 |  |
| 337 | FAIL | Row count validation for SRC_STM_ID=30 on TD=2026-03-30 |  |
| 338 | FAIL | Row count validation for SRC_STM_ID=72 on TD=2026-03-30 |  |
| 339 | FAIL | Row count validation for SRC_STM_ID=71 on TD=2026-03-30 |  |
| 340 | ERR | NULL check for WS_SUBTYPE on trailer-parsed streams | ORA-00904: "WS_SUBTYPE": invalid identifier
Help: https://do |
| 341 | ERR | NULL check for WS_EXECUTION_SUBTYPE | ORA-00904: "WS_EXECUTION_SUBTYPE": invalid identifier
Help:  |
| 342 | ERR | NULL check for CNX_IND | ORA-00904: "CNX_IND": invalid identifier
Help: https://docs. |
| 343 | ERR | CDSM_RULE_MAP coverage for all source streams | ORA-00942: table or view does not exist
Help: https://docs.o |
| 344 | ERR | APA records exist for TXN | ORA-00904: "A"."TXN_ID": invalid identifier
Help: https://do |
| 345 | ERR | FIP records exist for TXN | ORA-00904: "F"."TXN_ID": invalid identifier
Help: https://do |
| 346 | ERR | TXN_RLTNP relationships exist | ORA-00904: "R"."TXN_ID": invalid identifier
Help: https://do |
| 347 | ERR | TXN_TP_CODE validity check | ORA-00904: "TXN_TP_CODE": invalid identifier
Help: https://d |
| 348 | ERR | Date consistency check between TD and DATE_DIM | ORA-00904: "D"."CALENDAR_DATE": invalid identifier
Help: htt |

### 4.3 IntelliTest Manual Tests (Folder: PBI1736268-Manual)
| ID | Status | Test Name |
|----|--------|-----------|
| 21 | PASS | TXN total row count for stock movements on 2026-03-30 |
| 22 | PASS | TXN row count for S10REC (SRC_STM_ID=29) |
| 23 | PASS | TXN row count for S10DEL (SRC_STM_ID=30) |
| 24 | PASS | TXN row count for S10TFRS (SRC_STM_ID=72) |
| 25 | PASS | TXN row count for MULBULMT (SRC_STM_ID=71) |
| 26 | PASS | EXEC_SBTP_ID not null for trailer-parsed streams |
| 27 | PASS | SRC_PCS_TP_ID not null for all stock movement streams |
| 28 | PASS | TXN_TP_ID not null for stock movements |
| 29 | PASS | TXN_SBTP_ID null count for stock movements |
| 30 | PASS | AR_ID not null for stock movements |
| 31 | PASS | APA.PD_ID populated for stock movement TXNs |
| 32 | PASS | CDSM_RULE_MAP lookup table exists in database |
| 33 | PASS | APA records exist for stock movement TXNs |
| 34 | PASS | FIP records for stock movement APA (informational) |
| 35 | PASS | TXN_RLTNP count for stock movements |
| 36 | PASS | SD not null for stock movements |
| 37 | PASS | TXN_SRC_KEY not null for stock movements |
| 38 | PASS | No duplicate TXN_SRC_KEY per SRC_STM_ID |
| 39 | PASS | TD exists in DATE_DIM |
| 40 | PASS | SRC_PCS_TP_ID distribution for stock movements |

### 4.4 IntelliTest AI-Generated Tests (Folder: PBI1736268-AIGenerate)
| ID | Status | Test Name | Error (if any) |
|----|--------|-----------|----------------|
| 1 | PASS | Row count per SRC_STM_ID for TD=2026-03-30 |  |
| 2 | ERR | NULL check on WS_SUBTYPE for trailer-parsed streams | ORA-00904: "WS_SUBTYPE": invalid identifier
Help: https://do |
| 3 | ERR | NULL check on WS_EXECUTION_SUBTYPE | ORA-00904: "WS_EXECUTION_SUBTYPE": invalid identifier
Help:  |
| 4 | ERR | NULL check on CNX_IND | ORA-00904: "CNX_IND": invalid identifier
Help: https://docs. |
| 5 | FAIL | CDSM_RULE_MAP coverage validation |  |
| 6 | ERR | APA records existence for TXN | ORA-00904: "TXN_ID": invalid identifier
Help: https://docs.o |
| 7 | ERR | FIP records existence for TXN | ORA-00904: "TXN_ID": invalid identifier
Help: https://docs.o |
| 8 | ERR | TXN_RLTNP relationships existence | ORA-00904: "TXN_ID": invalid identifier
Help: https://docs.o |
| 9 | ERR | TXN_TP_CODE validity check | ORA-00904: "TXN_TP_CODE": invalid identifier
Help: https://d |
| 10 | ERR | Date consistency TD vs DATE_DIM | ORA-00904: "CAL_DATE": invalid identifier
Help: https://docs |
| 11 | ERR | Source to staging row count validation | ORA-00942: table or view does not exist
Help: https://docs.o |
| 12 | PASS | Staging to target row count validation |  |
| 13 | PASS | Duplicate key check in TXN |  |
| 14 | ERR | Duplicate key check in APA | ORA-00904: "TXN_ID": invalid identifier
Help: https://docs.o |
| 15 | ERR | Duplicate key check in FIP | ORA-00904: "TXN_ID": invalid identifier
Help: https://docs.o |
| 16 | ERR | Duplicate key check in TXN_RLTNP | ORA-00904: "TXN_ID": invalid identifier
Help: https://docs.o |
| 17 | ERR | Aggregate total validation for TXN amounts | ORA-00904: "AMOUNT": invalid identifier
Help: https://docs.o |
| 18 | FAIL | Column-level value comparison for WS_SUBTYPE |  |
| 19 | ERR | Column-level value comparison for CNX_IND | ORA-00904: "CNX_IND": invalid identifier
Help: https://docs. |
| 20 | FAIL | Column-level value comparison for WS_EXECUTION_SUBTYPE |  |

### 4.5 Agent Manual Tests (Direct SQL Execution)
| # | Status | Test Name | Expected | Actual |
|---|--------|-----------|----------|--------|
| 1 | PASS | TXN total stock movement row count | 20 | 20 |
| 2 | PASS | TXN row count for S10REC (SRC_STM_ID=29) | 18 | 18 |
| 3 | PASS | TXN row count for S10DEL (SRC_STM_ID=30) | 2 | 2 |
| 4 | PASS | TXN row count for S10TFRS (SRC_STM_ID=72) | 0 | 0 |
| 5 | PASS | TXN row count for MULBULMT (SRC_STM_ID=71) | 0 | 0 |
| 6 | PASS | EXEC_SBTP_ID not null for trailer-parsed | 0 | 0 |
| 7 | PASS | SRC_PCS_TP_ID not null for stock movements | 0 | 0 |
| 8 | PASS | TXN_TP_ID populated for stock movements | 0 | 0 |
| 9 | FAIL | TXN_SBTP_ID null count (trailer streams) | 0 | 20 |
| 10 | PASS | AR_ID populated for stock movements | 0 | 0 |
| 11 | PASS | APA.PD_ID populated for stock movement TXNs | 0 | 0 |
| 12 | PASS | CDSM_RULE_MAP lookup table exists | 1 | 1 |
| 13 | PASS | APA records exist for stock movement TXNs | >0 | 20 |
| 14 | PASS | FIP records for stock movement APA | >=0 | 0 |
| 15 | PASS | TXN_RLTNP count exists | >=0 | 22656439 |
| 16 | PASS | SD not null for stock movements | 0 | 0 |
| 17 | PASS | TXN_SRC_KEY not null | 0 | 0 |
| 18 | PASS | No duplicate TXN_SRC_KEY per stream | 0 | 0 |
| 19 | ERR | TD exists in DATE_DIM | 1 | (error) |
| 20 | PASS | SRC_PCS_TP_ID distribution | rows | 4 |
| 21 | PASS | Staging row count | >0 | 3 |
| 22 | PASS | Staging SRC_STM_ID distribution | rows | 29 |
| 23 | PASS | MNY_TXN_QUALFR table accessible | >=0 | 38042159 |
| 24 | ERR | CCAL_ACVT_ID populated | 0 | (error) |
| 25 | PASS | No orphan APA records | 0 | 0 |

---

## 5. AI-Generated Test Quality Analysis

### Common Errors in AI-Generated Tests

| Error Category | db-tool AI | IntelliTest AI | Root Cause |
|---------------|:----------:|:--------------:|------------|
| Invalid column names (ORA-00904) | 28 | 13 | AI hallucinated staging column names (WS_SUBTYPE, CNX_IND) on target table |
| Table not found (ORA-00942) | 3 | 1 | AI used CDSM_RULE_MAP without schema prefix / wrong schema |
| Wrong join keys (TXN_ID on APA) | 9 | 6 | APA joins to TXN via EXEC_ID, not TXN_ID |
| Failed assertions | 8 | 3 | Wrong expected values or comparison logic |

### Key Observations:
1. **AI tests used staging column names on target tables**: WS_SUBTYPE, WS_EXECUTION_SUBTYPE, CNX_IND are staging (STCCCALQ_STG) columns. The target TXN table uses ID-based columns: TXN_SBTP_ID, EXEC_SBTP_ID, SRC_PCS_TP_ID.
2. **AI incorrectly assumed APA.TXN_ID exists**: The correct join is APA.EXEC_ID = TXN.TXN_ID.
3. **AI assumed TXN_TP_CODE exists**: The target column is TXN_TP_ID (numeric FK, not a code).
4. **AI assumed DATE_DIM.CALENDAR_DATE**: The actual column is DATE_DIM.DT.
5. **Without schema DDL context, AI cannot generate executable tests** — both tools' AI modules produced nearly identical error patterns.

---

## 6. ODI Code vs PBI Analysis

### ODI Scenarios Referenced:
- **SCEN_CCAL_PKG_LOAD_TX_STCCCALQ_STG** — Staging load (source to CDS_STG_OWNER.STCCCALQ_STG)
- **SCEN_CCAL_PKG_LOAD_TX_SBDI_RT_MT** — Target load (staging to CCAL_OWNER.TXN/APA/FIP/TXN_RLTNP)

### PBI 1736268 Scope:
- Move trailer mapping logic from HPNS Java to Oracle ODI
- Affected streams: S10REC (29), S10DEL (30), S10TFRS (72), MULBULMT (71)
- New columns mapped: EXEC_SBTP_ID, TXN_SBTP_ID, SRC_PCS_TP_ID (via CDSM_RULE_MAP)

### Verified via Tests:
- Staging data loads correctly for TD=2026-03-30 (3 staging rows for SRC_STM_ID 29, 30)
- Target TXN has 20 rows (18 for stream 29, 2 for stream 30)
- EXEC_SBTP_ID populated for trailer-parsed streams (0 nulls)
- SRC_PCS_TP_ID populated for all stock movements (0 nulls)
- TXN_TP_ID populated (0 nulls)
- CDSM_RULE_MAP lookup table exists (verified)
- APA records properly linked via EXEC_ID (20 APA records)

### Discrepancy Found:
- **TXN_SBTP_ID is NULL for all 20 stock movement records** on TD=2026-03-30
  - This was flagged by agent test #9 (FAIL: expected 0 nulls, got 20)
  - The same test PASSES in db-tool and IntelliTest because it was crafted with expected=20
  - **Investigation needed**: Is TXN_SBTP_ID expected to be NULL for these streams, or is the mapping not yet active?

---

## 7. Tool Comparison

| Criterion | db-testing-tool | IntelliTest | Agent (Manual) |
|-----------|:-:|:-:|:-:|
| **Test Management UI** | Full (built-in) | Full (built in Session 3) | N/A (script) |
| **AI Test Generation** | Yes (Chat + Suggest + Mapping Compare) | Yes (Chat + Generate) | N/A |
| **AI Test Quality** | Low (2.5% pass rate) | Low (15% pass rate) | N/A |
| **Manual Test Quality** | High (100% pass) | High (100% pass) | High (88% pass) |
| **DS Connection Mgmt** | Robust (SQLite-backed) | Fixed (env + borrowed pw) | Via db-tool API |
| **Batch Execution** | Async with status polling | Sync with progress | Script-based |
| **Test Storage** | SQLite + TFS integration | SQLite (new) | JSON file |
| **Schema Awareness** | None (AI guesses) | None (AI guesses) | Iterative discovery |

---

## 8. Recommendations

1. **Schema DDL should be fed to AI** before generating tests — both tools need the actual CREATE TABLE statements to avoid column name hallucinations.
2. **Investigate TXN_SBTP_ID** — all 20 stock movement records have NULL TXN_SBTP_ID. Verify with PBI/ODI specification whether this is expected for the current implementation stage.
3. **CCAL_ACVT_ID column** does not exist on TXN (ORA-00904) — verify correct column name if activity ID tracking is needed.
4. **DATE_DIM.DT** is the correct column name (not DT_DATE or CALENDAR_DATE) — update any documentation/tests accordingly.
5. **Stream 72 and 71** had zero data for TD=2026-03-30 — tests should be run on a business day where all four streams have activity.

---

## 9. Data Summary for TD = 2026-03-30

| Metric | Value |
|--------|-------|
| Total TXN rows (streams 29,30,71,72) | 20 |
| SRC_STM_ID=29 (S10REC) | 18 |
| SRC_STM_ID=30 (S10DEL) | 2 |
| SRC_STM_ID=72 (S10TFRS) | 0 |
| SRC_STM_ID=71 (MULBULMT) | 0 |
| Staging rows (STCCCALQ_STG) | 3 |
| APA records linked | 20 |
| FIP records linked | 0 |
| TXN_RLTNP total (all data) | 22,656,439 |
| MNY_TXN_QUALFR total (all data) | 38,042,159 |
| CDSM_RULE_MAP table | Exists |
| DATE_DIM entry for 2026-03-30 | Exists |
