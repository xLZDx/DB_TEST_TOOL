"""Generate comprehensive comparison report for PBI 1736268 test execution."""
import sqlite3, os, json
from datetime import datetime

# ── Collect data from all three sources ──────────────────────

# 1. db-testing-tool: Manual tests (349-368) and AI tests (309-348)
dbt_db = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DBTestingTool", "app.db")
conn = sqlite3.connect(dbt_db)

# Manual tests
dbt_manual = conn.execute("""
    SELECT tc.id, tc.name, tc.source_query, tr.status, tr.error_message
    FROM test_cases tc
    LEFT JOIN (
        SELECT test_case_id, status, error_message,
               ROW_NUMBER() OVER (PARTITION BY test_case_id ORDER BY id DESC) as rn
        FROM test_runs WHERE test_case_id BETWEEN 349 AND 368
    ) tr ON tr.test_case_id = tc.id AND tr.rn = 1
    WHERE tc.id BETWEEN 349 AND 368
    ORDER BY tc.id
""").fetchall()

# AI tests
dbt_ai = conn.execute("""
    SELECT tc.id, tc.name, tc.source_query, tr.status, tr.error_message
    FROM test_cases tc
    LEFT JOIN (
        SELECT test_case_id, status, error_message,
               ROW_NUMBER() OVER (PARTITION BY test_case_id ORDER BY id DESC) as rn
        FROM test_runs WHERE test_case_id BETWEEN 309 AND 348
    ) tr ON tr.test_case_id = tc.id AND tr.rn = 1
    WHERE tc.id BETWEEN 309 AND 348
    ORDER BY tc.id
""").fetchall()
conn.close()

# 2. IntelliTest: Manual tests (21-40) and AI tests (1-20)
it_db = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn = sqlite3.connect(it_db)

it_manual = conn.execute("""
    SELECT tc.id, tc.name, tc.source_query, tr.status, tr.error_message
    FROM test_cases tc
    LEFT JOIN (
        SELECT test_case_id, status, error_message,
               ROW_NUMBER() OVER (PARTITION BY test_case_id ORDER BY id DESC) as rn
        FROM test_runs WHERE test_case_id BETWEEN 21 AND 40
    ) tr ON tr.test_case_id = tc.id AND tr.rn = 1
    WHERE tc.id BETWEEN 21 AND 40
    ORDER BY tc.id
""").fetchall()

it_ai = conn.execute("""
    SELECT tc.id, tc.name, tc.source_query, tr.status, tr.error_message
    FROM test_cases tc
    LEFT JOIN (
        SELECT test_case_id, status, error_message,
               ROW_NUMBER() OVER (PARTITION BY test_case_id ORDER BY id DESC) as rn
        FROM test_runs WHERE test_case_id BETWEEN 1 AND 20
    ) tr ON tr.test_case_id = tc.id AND tr.rn = 1
    WHERE tc.id BETWEEN 1 AND 20
    ORDER BY tc.id
""").fetchall()
conn.close()

# 3. Agent manual results
with open(r"c:\GIT_Repo\test_reports\agent_manual_results.json") as f:
    agent_results = json.load(f)

# ── Helper functions ──────────────────────

def classify_table(sql):
    """Determine which tables a test covers."""
    if not sql:
        return set()
    sql_upper = sql.upper()
    tables = set()
    for tbl in ["TXN_RLTNP", "TXN", "APA", "FIP", "MNY_TXN_QUALFR", "CDSM_RULE_MAP", 
                 "STCCCALQ_STG", "DATE_DIM", "ALL_TABLES"]:
        if tbl in sql_upper:
            tables.add(tbl)
    # TXN might match TXN_RLTNP, be precise
    if "TXN" in tables and "TXN_RLTNP" in tables:
        pass  # both
    return tables

def classify_aspect(name, sql):
    """Classify what aspect of ETL the test covers."""
    name_upper = (name or "").upper()
    sql_upper = (sql or "").upper()
    aspects = set()
    if "ROW COUNT" in name_upper or "COUNT(*)" in sql_upper:
        aspects.add("Row Count")
    if "NULL" in name_upper or "IS NULL" in sql_upper:
        aspects.add("NULL Check")
    if "DUPLICATE" in name_upper or "HAVING COUNT" in sql_upper:
        aspects.add("Uniqueness")
    if "EXIST" in name_upper or "EXISTS" in sql_upper:
        aspects.add("Existence")
    if "LOOKUP" in name_upper or "RULE_MAP" in name_upper:
        aspects.add("Lookup/Reference")
    if "DATE_DIM" in sql_upper:
        aspects.add("Reference Data")
    if "DISTRIBUTION" in name_upper or "GROUP BY" in sql_upper:
        aspects.add("Distribution")
    if "STAGING" in name_upper or "STG" in sql_upper:
        aspects.add("Staging")
    if not aspects:
        aspects.add("Data Validation")
    return aspects

def summarize(tests, name_idx=1, sql_idx=2, status_idx=3):
    """Summarize test results."""
    total = len(tests)
    passed = sum(1 for t in tests if t[status_idx] == "passed")
    failed = sum(1 for t in tests if t[status_idx] == "failed")
    error = sum(1 for t in tests if t[status_idx] == "error")
    untested = total - passed - failed - error
    tables = set()
    aspects = set()
    for t in tests:
        tables |= classify_table(t[sql_idx])
        aspects |= classify_aspect(t[name_idx], t[sql_idx])
    return {"total": total, "passed": passed, "failed": failed, "error": error, 
            "untested": untested, "tables": sorted(tables), "aspects": sorted(aspects),
            "pass_rate": f"{passed/total*100:.0f}%" if total else "N/A"}

def summarize_agent(results):
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    error = sum(1 for r in results if r["status"] == "error")
    tables = set()
    aspects = set()
    for r in results:
        tables |= classify_table(r["sql"])
        aspects |= classify_aspect(r["name"], r["sql"])
    return {"total": total, "passed": passed, "failed": failed, "error": error,
            "untested": 0, "tables": sorted(tables), "aspects": sorted(aspects),
            "pass_rate": f"{passed/total*100:.0f}%" if total else "N/A"}

# ── Build report ──────────────────────

s_dbt_manual = summarize(dbt_manual)
s_dbt_ai = summarize(dbt_ai)
s_it_manual = summarize(it_manual)
s_it_ai = summarize(it_ai)
s_agent = summarize_agent(agent_results)

report = f"""# PBI 1736268 - Comprehensive Test Execution Report
## "Move trailer mapping logic for stock movements from HPNS to Oracle"
### Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Executive Summary

| Source | Category | Total | Passed | Failed | Error | Pass Rate |
|--------|----------|------:|-------:|-------:|------:|-----------|
| **db-testing-tool** | Manual Tests | {s_dbt_manual['total']} | {s_dbt_manual['passed']} | {s_dbt_manual['failed']} | {s_dbt_manual['error']} | **{s_dbt_manual['pass_rate']}** |
| **db-testing-tool** | AI-Generated | {s_dbt_ai['total']} | {s_dbt_ai['passed']} | {s_dbt_ai['failed']} | {s_dbt_ai['error']} | **{s_dbt_ai['pass_rate']}** |
| **IntelliTest** | Manual Tests | {s_it_manual['total']} | {s_it_manual['passed']} | {s_it_manual['failed']} | {s_it_manual['error']} | **{s_it_manual['pass_rate']}** |
| **IntelliTest** | AI-Generated | {s_it_ai['total']} | {s_it_ai['passed']} | {s_it_ai['failed']} | {s_it_ai['error']} | **{s_it_ai['pass_rate']}** |
| **Agent (Manual)** | Direct SQL | {s_agent['total']} | {s_agent['passed']} | {s_agent['failed']} | {s_agent['error']} | **{s_agent['pass_rate']}** |

**Grand Total: {s_dbt_manual['total'] + s_dbt_ai['total'] + s_it_manual['total'] + s_it_ai['total'] + s_agent['total']} tests across all sources**

---

## 2. Table Coverage Matrix

| Target Table | db-tool Manual | db-tool AI | IntelliTest Manual | IntelliTest AI | Agent Manual |
|-------------|:-:|:-:|:-:|:-:|:-:|
| CCAL_OWNER.TXN | {'Y' if 'TXN' in s_dbt_manual['tables'] else '-'} | {'Y' if 'TXN' in s_dbt_ai['tables'] else '-'} | {'Y' if 'TXN' in s_it_manual['tables'] else '-'} | {'Y' if 'TXN' in s_it_ai['tables'] else '-'} | {'Y' if 'TXN' in s_agent['tables'] else '-'} |
| CCAL_OWNER.APA | {'Y' if 'APA' in s_dbt_manual['tables'] else '-'} | {'Y' if 'APA' in s_dbt_ai['tables'] else '-'} | {'Y' if 'APA' in s_it_manual['tables'] else '-'} | {'Y' if 'APA' in s_it_ai['tables'] else '-'} | {'Y' if 'APA' in s_agent['tables'] else '-'} |
| CCAL_OWNER.FIP | {'Y' if 'FIP' in s_dbt_manual['tables'] else '-'} | {'Y' if 'FIP' in s_dbt_ai['tables'] else '-'} | {'Y' if 'FIP' in s_it_manual['tables'] else '-'} | {'Y' if 'FIP' in s_it_ai['tables'] else '-'} | {'Y' if 'FIP' in s_agent['tables'] else '-'} |
| CCAL_OWNER.TXN_RLTNP | {'Y' if 'TXN_RLTNP' in s_dbt_manual['tables'] else '-'} | {'Y' if 'TXN_RLTNP' in s_dbt_ai['tables'] else '-'} | {'Y' if 'TXN_RLTNP' in s_it_manual['tables'] else '-'} | {'Y' if 'TXN_RLTNP' in s_it_ai['tables'] else '-'} | {'Y' if 'TXN_RLTNP' in s_agent['tables'] else '-'} |
| CCAL_OWNER.MNY_TXN_QUALFR | {'Y' if 'MNY_TXN_QUALFR' in s_dbt_manual['tables'] else '-'} | {'Y' if 'MNY_TXN_QUALFR' in s_dbt_ai['tables'] else '-'} | {'Y' if 'MNY_TXN_QUALFR' in s_it_manual['tables'] else '-'} | {'Y' if 'MNY_TXN_QUALFR' in s_it_ai['tables'] else '-'} | {'Y' if 'MNY_TXN_QUALFR' in s_agent['tables'] else '-'} |
| CCAL_OWNER.CDSM_RULE_MAP | {'Y' if 'CDSM_RULE_MAP' in s_dbt_manual['tables'] else '-'} | {'Y' if 'CDSM_RULE_MAP' in s_dbt_ai['tables'] else '-'} | {'Y' if 'CDSM_RULE_MAP' in s_it_manual['tables'] else '-'} | {'Y' if 'CDSM_RULE_MAP' in s_it_ai['tables'] else '-'} | {'Y' if 'CDSM_RULE_MAP' in s_agent['tables'] else '-'} |
| CDS_STG_OWNER.STCCCALQ_STG | {'Y' if 'STCCCALQ_STG' in s_dbt_manual['tables'] else '-'} | {'Y' if 'STCCCALQ_STG' in s_dbt_ai['tables'] else '-'} | {'Y' if 'STCCCALQ_STG' in s_it_manual['tables'] else '-'} | {'Y' if 'STCCCALQ_STG' in s_it_ai['tables'] else '-'} | {'Y' if 'STCCCALQ_STG' in s_agent['tables'] else '-'} |
| CCAL_OWNER.DATE_DIM | {'Y' if 'DATE_DIM' in s_dbt_manual['tables'] else '-'} | {'Y' if 'DATE_DIM' in s_dbt_ai['tables'] else '-'} | {'Y' if 'DATE_DIM' in s_it_manual['tables'] else '-'} | {'Y' if 'DATE_DIM' in s_it_ai['tables'] else '-'} | {'Y' if 'DATE_DIM' in s_agent['tables'] else '-'} |

---

## 3. Test Aspect Coverage

| Aspect | db-tool Manual | db-tool AI | IntelliTest Manual | IntelliTest AI | Agent Manual |
|--------|:-:|:-:|:-:|:-:|:-:|
"""

all_aspects = sorted(set(s_dbt_manual['aspects']) | set(s_dbt_ai['aspects']) | 
                     set(s_it_manual['aspects']) | set(s_it_ai['aspects']) | set(s_agent['aspects']))
for asp in all_aspects:
    report += f"| {asp} | {'Y' if asp in s_dbt_manual['aspects'] else '-'} | {'Y' if asp in s_dbt_ai['aspects'] else '-'} | {'Y' if asp in s_it_manual['aspects'] else '-'} | {'Y' if asp in s_it_ai['aspects'] else '-'} | {'Y' if asp in s_agent['aspects'] else '-'} |\n"

report += f"""
---

## 4. Detailed Results by Source

### 4.1 db-testing-tool Manual Tests (Folder: PBI1736268-Manual)
| ID | Status | Test Name |
|----|--------|-----------|
"""
for t in dbt_manual:
    status = t[3] or "untested"
    icon = "PASS" if status == "passed" else "FAIL" if status == "failed" else "ERR" if status == "error" else "?"
    report += f"| {t[0]} | {icon} | {t[1]} |\n"

report += f"""
### 4.2 db-testing-tool AI-Generated Tests (Folder: PBI1736268-AIChat)
| ID | Status | Test Name | Error (if any) |
|----|--------|-----------|----------------|
"""
for t in dbt_ai:
    status = t[3] or "untested"
    icon = "PASS" if status == "passed" else "FAIL" if status == "failed" else "ERR" if status == "error" else "?"
    err = (t[4] or "")[:60].replace("|", "/")
    report += f"| {t[0]} | {icon} | {t[1]} | {err} |\n"

report += f"""
### 4.3 IntelliTest Manual Tests (Folder: PBI1736268-Manual)
| ID | Status | Test Name |
|----|--------|-----------|
"""
for t in it_manual:
    status = t[3] or "untested"
    icon = "PASS" if status == "passed" else "FAIL" if status == "failed" else "ERR" if status == "error" else "?"
    report += f"| {t[0]} | {icon} | {t[1]} |\n"

report += f"""
### 4.4 IntelliTest AI-Generated Tests (Folder: PBI1736268-AIGenerate)
| ID | Status | Test Name | Error (if any) |
|----|--------|-----------|----------------|
"""
for t in it_ai:
    status = t[3] or "untested"
    icon = "PASS" if status == "passed" else "FAIL" if status == "failed" else "ERR" if status == "error" else "?"
    err = (t[4] or "")[:60].replace("|", "/")
    report += f"| {t[0]} | {icon} | {t[1]} | {err} |\n"

report += f"""
### 4.5 Agent Manual Tests (Direct SQL Execution)
| # | Status | Test Name | Expected | Actual |
|---|--------|-----------|----------|--------|
"""
for r in agent_results:
    icon = "PASS" if r["status"] == "PASS" else "FAIL" if r["status"] == "FAIL" else "ERR"
    actual = str(r.get("actual", ""))[:15] if r["status"] != "error" else "(error)"
    report += f"| {r['id']} | {icon} | {r['name']} | {r['expected']} | {actual} |\n"

report += f"""
---

## 5. AI-Generated Test Quality Analysis

### Common Errors in AI-Generated Tests

| Error Category | db-tool AI | IntelliTest AI | Root Cause |
|---------------|:----------:|:--------------:|------------|
| Invalid column names (ORA-00904) | {sum(1 for t in dbt_ai if t[4] and 'ORA-00904' in (t[4] or ''))} | {sum(1 for t in it_ai if t[4] and 'ORA-00904' in (t[4] or ''))} | AI hallucinated staging column names (WS_SUBTYPE, CNX_IND) on target table |
| Table not found (ORA-00942) | {sum(1 for t in dbt_ai if t[4] and 'ORA-00942' in (t[4] or ''))} | {sum(1 for t in it_ai if t[4] and 'ORA-00942' in (t[4] or ''))} | AI used CDSM_RULE_MAP without schema prefix / wrong schema |
| Wrong join keys (TXN_ID on APA) | {sum(1 for t in dbt_ai if t[4] and 'TXN_ID' in (t[4] or ''))} | {sum(1 for t in it_ai if t[4] and 'TXN_ID' in (t[4] or ''))} | APA joins to TXN via EXEC_ID, not TXN_ID |
| Failed assertions | {s_dbt_ai['failed']} | {s_it_ai['failed']} | Wrong expected values or comparison logic |

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
"""

# Save report
os.makedirs(r"c:\GIT_Repo\test_reports", exist_ok=True)
with open(r"c:\GIT_Repo\test_reports\PBI1736268_comparison_report.md", "w", encoding="utf-8") as f:
    f.write(report)

print("Report generated successfully!")
print(f"Location: c:\\GIT_Repo\\test_reports\\PBI1736268_comparison_report.md")
print(f"\nQuick Summary:")
print(f"  db-tool Manual:     {s_dbt_manual['total']:2d} tests, {s_dbt_manual['passed']:2d} passed ({s_dbt_manual['pass_rate']})")
print(f"  db-tool AI:         {s_dbt_ai['total']:2d} tests, {s_dbt_ai['passed']:2d} passed ({s_dbt_ai['pass_rate']})")
print(f"  IntelliTest Manual: {s_it_manual['total']:2d} tests, {s_it_manual['passed']:2d} passed ({s_it_manual['pass_rate']})")
print(f"  IntelliTest AI:     {s_it_ai['total']:2d} tests, {s_it_ai['passed']:2d} passed ({s_it_ai['pass_rate']})")
print(f"  Agent Manual:       {s_agent['total']:2d} tests, {s_agent['passed']:2d} passed ({s_agent['pass_rate']})")
print(f"  GRAND TOTAL:        {s_dbt_manual['total'] + s_dbt_ai['total'] + s_it_manual['total'] + s_it_ai['total'] + s_agent['total']} tests")
