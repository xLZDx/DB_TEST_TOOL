# AVY_FACT_SIDE Full E2E — Execution Plan
**Date**: 2026-05-20  
**Status**: AWAITING APPROVAL  
**Reviewed by**: architect agent, fastapi-reviewer agent

---

## Requirements

| # | Requirement |
|---|---|
| R1 | Use the existing /mappings GUI + control table service — NOT ad-hoc Python scripts |
| R2 | Target table: IKOROSTELEV.AVY_FACT_SIDE on datasource LH (id=3) |
| R3 | DRD source: DRD_Activity_Fact.xlsx sheet "Table-View (2)" |
| R4 | INSERT must produce real data rows (not NULL/0), no ORA errors |
| R5 | TFS test plan named "Test123", static suite "test statick", PBI suite for PBI2674782 |
| R6 | All pytest tests pass, health check 200, error log clean |

---

## Agent Review Corrections Applied

| # | Agent | Finding | Correction |
|---|---|---|---|
| C1 | Architect | verify-xml returns parity score NOT INSERT SQL | Removed verify-xml from SQL generation path; analyze is sole INSERT generator |
| C2 | Architect | ROWNUM appended after INSERT → ORA-00933 | Fixed: ROWNUM injected inside the SELECT subquery |
| C3 | Architect | No validation that generated_sql is non-empty | Added Phase 2.4: validate generated_sql contains "INSERT" |
| C4 | Architect | Source table might be empty → R4 violated silently | Added Phase 3.3: pre-flight COUNT on TRANSACTIONS_OWNER.AVY_FACT_SIDE |
| C5 | Security | Use /api/tests/control-table/check-insert for INSERT (has NOT NULL validation + diagnostics) | Phase 4.2 now uses check-insert with execute=true |
| C6 | Security | get_connector() may be called with 7 args (known bug) | Added Phase 0.1: verify/fix before any query execution |

---

## Architecture / Change Table

| Change | Priority | File/Area | Rationale | Risk |
|---|---|---|---|---|
| Pre-flight connector check | P0 | app/routers/datasources.py | Known get_connector() 7-arg bug — must confirm fixed before queries | Low |
| Restart service | P0 | OS / uvicorn | Clear stuck connection pool | Low |
| Parse DRD via /api/tests/control-table/analyze | P1 | Tests router | GUI control table flow, generates INSERT SQL | Medium |
| CREATE TABLE DDL via /api/datasources/3/query | P1 | LH datasource | CTAS from real table structure | Low |
| Execute INSERT via /api/tests/control-table/check-insert | P1 | Tests router | NOT NULL validation + diagnostics built in | Medium |
| Validation queries | P2 | SQL terminal | COUNT, NULLs, key uniqueness | Low |
| Save combined SQL artifact | P2 | reports/ | Persist DDL + INSERT + validation | Low |
| TFS test plan POST | P2 | /api/tfs/test-plans | Creates "Test123" plan | Low |
| TFS suites POST | P2 | /api/tfs/test-suites | Static + PBI2674782 suites | Low |
| pytest suite | P3 | tests/ | Regression gate | Medium |

---

## Implementation Steps

### Phase 0 — Pre-flight (P0)

| Step | Action | Endpoint / File | Why | Risk |
|---|---|---|---|---|
| 0.1 | Check get_connector() call signature in app/routers/datasources.py — fix if uses 7 positional args instead of get_connector(ds) | datasources.py | Known bug that crashes all /query calls | Low |

### Phase 1 — Setup (P0) ✅ ALREADY DONE

| Step | Action | Endpoint / File | Why | Risk |
|---|---|---|---|---|
| 1.1 | Restart service | Restart-DB-Testing-Tool.ps1 | Clear stuck pool | Low |
| 1.2 | Health check GET / = 200 | http://127.0.0.1:8550/ | Confirm live | Low |

### Phase 2 — DRD Parse via Control Table Service (P1)

| Step | Action | Endpoint / File | Why | Risk |
|---|---|---|---|---|
| 2.1 | POST DRD_Activity_Fact.xlsx to /api/tests/control-table/analyze with sheet_name="Table-View (2)", target_schema=IKOROSTELEV, target_table=AVY_FACT_SIDE, source_datasource_id=3, target_datasource_id=3 | /api/tests/control-table/analyze | Extract DRD-mapped INSERT SQL via control table service (R1, R3) | Medium |
| 2.2 | Capture generated_insert_sql (or generated_sql) from response | Response field | Feed Phase 4 | Low |
| 2.3 | POST DRD + XML to /api/tests/control-table/pdm-enrich with drd_file, xml_file=1_SCEN_LH_AVY_PKG_LOAD_AVY_FACT_SIDE_V1_RT_ST_Version_001.xml, target_schema=IKOROSTELEV, target_table=AVY_FACT_SIDE, source_datasource_id=3, target_datasource_id=3 | /api/tests/control-table/pdm-enrich | Enrich mappings with ODI ETL logic from XML | Medium |
| 2.4 | Validate: generated_sql is non-empty and contains "INSERT" | Local check | Fail fast before DDL execution | Low |

### Phase 3 — CREATE TABLE on LH (P1)

| Step | Action | Endpoint / File | Why | Risk |
|---|---|---|---|---|
| 3.1 | Drop if exists: BEGIN EXECUTE IMMEDIATE 'DROP TABLE IKOROSTELEV.AVY_FACT_SIDE'; EXCEPTION WHEN OTHERS THEN NULL; END; | POST /api/datasources/3/query | Clean slate | Low |
| 3.2 | CREATE TABLE IKOROSTELEV.AVY_FACT_SIDE AS SELECT * FROM TRANSACTIONS_OWNER.AVY_FACT_SIDE WHERE 1!=1 | POST /api/datasources/3/query | Fastest correct DDL with real column structure (R2) | Low |
| 3.3 | Pre-flight: SELECT COUNT(*) FROM TRANSACTIONS_OWNER.AVY_FACT_SIDE WHERE ROWNUM <= 1 — fail if 0 | POST /api/datasources/3/query | Ensure source has rows (R4 guard) | Low |
| 3.4 | Verify: SELECT COUNT(*) FROM IKOROSTELEV.AVY_FACT_SIDE = 0 | POST /api/datasources/3/query | Table exists and is empty | Low |

### Phase 4 — INSERT with Real Data (P1)

| Step | Action | Endpoint / File | Why | Risk |
|---|---|---|---|---|
| 4.1 | Inject ROWNUM <= 10 INSIDE the SELECT subquery of generated_sql (not appended after INSERT) | Local SQL string modification | Valid Oracle syntax — avoids ORA-00933 (R4) | Medium |
| 4.2 | Submit INSERT to /api/tests/control-table/check-insert with execute=true, target_datasource_id=3, sql=<modified_sql> | /api/tests/control-table/check-insert | NOT NULL validation + diagnostics; catches column mismatches (R4) | Medium |
| 4.3 | Verify: SELECT COUNT(*) FROM IKOROSTELEV.AVY_FACT_SIDE > 0 | POST /api/datasources/3/query | Confirm real rows loaded (R4) | Low |

### Phase 5 — Validation + Artifact (P2)

| Step | Action | Endpoint / File | Why | Risk |
|---|---|---|---|---|
| 5.1 | Run reports/avyfactside_validation.sql via POST /api/datasources/3/query | POST /api/datasources/3/query | NULL checks, key uniqueness | Low |
| 5.2 | Write reports/AVY_FACT_SIDE_complete_e2e.sql combining: DDL (Phase 3.2) + INSERT (Phase 4.1) + validation (avyfactside_validation.sql) | reports/AVY_FACT_SIDE_complete_e2e.sql | Combined artifact | Low |

### Phase 6 — TFS Test Plan & Suites (P2)

| Step | Action | Body | Endpoint | Risk |
|---|---|---|---|---|
| 6.1 | Create test plan | {"project": "Lighthouse", "name": "Test123"} | POST /api/tfs/test-plans | Low |
| 6.2 | Create static suite | {"project": "Lighthouse", "plan_id": <id_from_6.1>, "name": "test statick", "suite_type": "staticTestSuite"} | POST /api/tfs/test-suites | Low |
| 6.3 | Create PBI suite | {"project": "Lighthouse", "plan_id": <id_from_6.1>, "name": "PBI2674782", "suite_type": "requirementTestSuite", "requirement_id": 2674782} | POST /api/tfs/test-suites | Low |

### Phase 7 — E2E Gate, Error Log, Commit (P3)

| Step | Action | How | Risk |
|---|---|---|---|
| 7.1 | Run full pytest suite | python -m pytest tests/ -v | Medium |
| 7.2 | Check last 50 lines of error log | C:\GIT_Repo\logs\db-testing-tool-main.err.log | Low |
| 7.3 | Commit all changes | git add -A && git commit -m "feat: AVY_FACT_SIDE E2E complete — DRD parse, CREATE TABLE, INSERT, TFS plan" | Low |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| get_connector() 7-arg bug crashes all query calls | Phase 0.1 checks and fixes before anything runs |
| analyze endpoint slow (>30s for 720KB DRD) | Use 120s timeout; known issue with preview endpoint |
| ROWNUM in wrong position → ORA-00933 | Phase 4.1 injects ROWNUM inside SELECT, not after INSERT |
| Source table empty → R4 fails silently | Phase 3.3 pre-flight COUNT guard |
| generated_sql is NULL or empty | Phase 2.4 validation before DDL |
| TFS endpoint not configured | Check response; document failure as non-blocking if TFS unreachable |
| pytest pre-existing failures | Document individually; don't block on pre-existing failures |
| Column name mismatches between DRD and source | Fix iteratively from ORA-00904 errors reported by check-insert |

---

## Success Criteria

- [ ] Phase 0.1: get_connector() confirmed correct (1 arg)
- [ ] Phase 1: Service health = 200
- [ ] Phase 2: analyze returns generated_sql containing "INSERT"
- [ ] Phase 3: CREATE TABLE IKOROSTELEV.AVY_FACT_SIDE executes with no errors
- [ ] Phase 3.3: TRANSACTIONS_OWNER.AVY_FACT_SIDE has >= 1 row
- [ ] Phase 4: check-insert returns no NOT NULL violations, rows_affected >= 1
- [ ] Phase 4.3: SELECT COUNT(*) FROM IKOROSTELEV.AVY_FACT_SIDE > 0
- [ ] Phase 5: Validation queries show non-null key columns
- [ ] Phase 5.2: reports/AVY_FACT_SIDE_complete_e2e.sql saved
- [ ] Phase 6: TFS "Test123" plan created with static + PBI suites
- [ ] Phase 7.1: pytest passes (or pre-existing failures documented)
- [ ] Phase 7.2: Error log last 50 lines clean
- [ ] Phase 7.3: All changes committed

---

## Attached Source Files

| File | Role |
|---|---|
| DRD_Activity_Fact.xlsx | DRD source — sheet "Table-View (2)" — used in Phase 2.1 |
| 1_SCEN_LH_AVY_PKG_LOAD_AVY_FACT_SIDE_V1_RT_ST_Version_001.xml | ODI scenario — used in Phase 2.3 (pdm-enrich) |
| reports/avyfactside_validation.sql | Validation queries — used in Phase 5.1 |
