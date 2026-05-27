# Codebase Master Mega Improvement Plan

Date: 2026-05-22
Author: GitHub Copilot (assistant)

## Overview

This consolidated mega plan merges the repository-wide improvement recommendations with the focused DRD-first generator redesign and the consolidated specialist reviews for `AVY_FACT_SIDE` generation.

Scope: refactor high-risk services, make SQL generation DRD-first and plan-based, add sanitization/provenance, and introduce robust unit/integration/regression tests and CI gating.

This approach is designed to generalize to any DRD and any target table. `AVY_FACT_SIDE` is used here as the training and validation example because it is a large, complex table with many transformation rules; if we can build the correct INSERT statement for this table, the same approach and tooling should apply to other complex DRDs and target tables.

## Requirements

- DRD-first per-column selection for generated expressions; baseline/ODI as per-column fallback only.
- Preserve and emit per-run provenance (counts of DRD / baseline / fallback) and save run metadata under `data/local_kb/generator_runs/`.
- Sanitization: strict allowlist for SQL tokens/functions and forbidding DDL/DCL, semicolons, `EXECUTE IMMEDIATE`, and `eval`/`exec`-like patterns.
- Replace fragile regex-driven SQL repairs with a plan + renderer architecture.
- Add deterministic fixtures (DRD, PDM JSON, baseline KB) and tests to prevent regressions.
- Plain-text parity reports for human review (no JSON final reports unless explicitly requested).
- Operator approval (`GO` or `ГО`) required before implementation commits that change generator behavior.

## Architecture / Change Table

| Change | Priority | File / Area | Rationale | Risks | Benefits | Reviewer / Approver |
|---|---:|---|---|---|---|---|
| DRD-first per-column selection | P0 | `app/services/control_table_service.py` | Current whole-query baseline short-circuits DRD | Regressions if untested | Aligns generator with DRD; fixes many mismatches | code-reviewer, python-reviewer |
| Provenance + run metadata | P1 | `data/local_kb/generator_runs/` + SQL header | Traceability for runs and triage | Small storage overhead | Easier triage and audit | planner, architect |
| Sanitizer & allowlist | P0 | `app/services/drd_import_service.py` + `app/services/sql_validator.py` | Prevent unsafe expressions & SQL injection | False positives may block valid exprs | Security and stability | security-reviewer |
| Planner / renderer architecture | P1 | `app/services/sql/planner.py`, renderers | Replace regex rewrites with plan-based rendering | Implementation effort | Deterministic SQL + testability | architect, code-architect |
| Decompose large services | P1 | `drd_import_service.py`, `control_table_service.py` | Improve testability and single responsibility | Merge conflicts, refactor cost | Easier maintenance & focused tests | code-reviewer |
| Tests & CI gating | P0 | `tests/` + CI workflow | Prevent regressions; gate dangerous merges | CI maintenance | Early detection and safe rollouts | tdd-guide, python-reviewer |

## Implementation Steps Table

Phase 1 — Stabilize & Baseline (3–6h)
- Step 1.1 (High): Re-run DRD parse and produce a column-level provenance matrix using existing DRD fixtures. Files: `app/services/drd_import_service.py`. Reviewer: planner.
- Step 1.2 (High): Reproduce current 100-TXN_ID sample parity run and save a plain-text baseline report. Files: `_tmp_find_common.py`, `_tmp_compare_avyfact.py`.

Phase 2 — Design & API (3–5h)
- Step 2.1 (High): Design `select_expr_for_column(drd_expr, baseline_expr, manual_expr) -> {chosen_source, expression, reason}` and `build_insert_with_per_column_fallback(...)`. Files: `app/services/control_table_service.py`.
- Step 2.2 (Medium): Define run metadata schema and SQL header format (provenance counts). Files: `data/local_kb/generator_runs/` spec.

Phase 3 — Implement & Unit Tests (6–12h)
- Step 3.1 (High): Remove early baseline short-circuit and implement per-column selection + provenance emission. Add unit tests for `select_expr_for_column()` and sanitizers. Files: `app/services/control_table_service.py`, `app/services/drd_import_service.py`.
- Step 3.2 (Medium): Add `sql_validator` module and a strict `sanitize_generated_expression()` with allowlist tests. Files: `app/services/sql_validator.py`.

Phase 4 — Integration & Iterate (6–12h)
- Step 4.1 (High): Restart service via `Restart-DB-Testing-Tool.ps1`, generate SQL for `AVY_FACT_SIDE`, and execute sample load CTAS limited to 100 TXN_IDs.
- Step 4.2 (High): Run per-column plain-text comparisons against `TRANSACTIONS_OWNER.AVY_FACT`. Triage mismatches and iterate until acceptance.

Phase 5 — CI & Docs (2–4h)
- Step 5.1 (Medium): Add CI gates: static sanitizer checks, unit tests, integration smoke, and approval checks requiring `security-reviewer` and `code-reviewer` sign-off plus operator `GO`/`ГО` for generator changes.

## Agent Pros/Cons Summaries
- **Code-Reviewer**: Focused on must-fix items (remove baseline short-circuit, sanitize DRD, add tests). Pro: clear high-priority fixes; Con: large refactor risk if not incremental.
- **Python-Reviewer**: Suggested concrete pytest additions and fixtures for DRD-first behavior and provenance. Pro: concise test targets; Con: requires mocking connectors.
- **Database-Reviewer**: Emphasized NVL/date normalization, safe CTAS, explicit INSERT column alignment, and validated joins. Pro: concrete SQL snippets to reduce false positives.
- **Security-Reviewer**: Strong guardrails (ban `eval`/`exec`/DDL, identifier validation, least-privilege execution, CI gating). Pro: reduces RCE/SQL risks.
- **TDD-Guide**: Clear test-suite roadmap (unit → integration → AVY E2E) and acceptance criteria; Pro: good CI coverage plan.
- **Architect / Code‑Architect**: Advocated planner+renderer architecture, helper names, and minimal API changes for testability.

## Testing Strategy
- Unit tests: `select_expr_for_column`, sanitizer, provenance writer, sql_validator functions.
- Integration tests: generate SQL, run limited load (10–100 TXN_IDs), run parity queries and assert acceptance criteria.
- Regression tests: fixture-driven tests using `tests/fixtures/` (sample DRD, PDM JSON, baseline SQL) to catch whole-query fallback regressions.
- CI gating: static sanitizer pass → unit tests → integration smoke → manual approvals for generator changes.

## Risks & Mitigations
- Risk: Sanitizer over-blocks valid DRD expressions. Mitigation: staged allowlist with opt-in exceptions and review workflow.
- Risk: Regressions from refactor. Mitigation: add tests first, feature-flag the change, incremental commits with smoke integration runs.
- Risk: Missing PDM columns for join fragments. Mitigation: require pre-flight PDM validation for any JOIN fragment added by generator.

## Success Criteria
- 100-row parity: all non-audit business columns match between generated control table and `TRANSACTIONS_OWNER.AVY_FACT` for the sample set.
- Provenance emitted and run metadata saved under `data/local_kb/generator_runs/`.
- Unit & integration tests pass locally and in CI.
- Operator explicitly approves the implementation with `GO` or `ГО` in the PR/commit.

## Reviewer / Approver Table
- **Architect**: approves design and planner changes.
- **Code-Reviewer & Python-Reviewer**: approve code-level and test changes.
- **Security-Reviewer**: approve sanitizer and guardrails.
- **Database-Reviewer**: approve SQL changes and parity validation queries.
- **Operator**: provides `GO`/`ГО` to start implementation.

## Next Immediate Actions (short)
1. Implement `select_expr_for_column()` and remove baseline short-circuit behind a feature flag (`USE_BASELINE_WHOLE=false`) — small change and unit tests.
2. Add `sanitize_generated_expression()` and unit tests using the fixtures suggested by the test plan.
3. Add provenance writer and write one sample run to `data/local_kb/generator_runs/` for `AVY_FACT_SIDE`.
4. Run sample CTAS/100-TXN_ID loop and produce a plain-text parity report.

---

Saved artifacts: this consolidated plan is written to `docs/codebase_master_mega_plan.md` and references the original plans at `docs/codebase_master_improvement_plan.md`, `docs/AVY_FACT_SIDE_generator_plan.md`, and `docs/AVY_FACT_SIDE_review_plan.md`.
