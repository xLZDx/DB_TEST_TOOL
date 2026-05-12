# Implementation Plan: db-testing-tool Repair and Hardening

Artifact note: no prior `IMPLEMENTATION_PLAN_2026-05-12.md` was present under `db-testing-tool`; this document is the current approval-candidate baseline.

## Approval Workflow Status

| Stage | Status | Basis | Owner | Next Gate |
| --- | --- | --- | --- | --- |
| Review | Approved | Validated findings plus `pytest -q` on 2026-05-12 failing during collection with 5 errors in 8.45s (`No module named 'app'`, `app.models.agent_profile`, `app.services.copilot_auth_service`, `app.connectors.base`) | Completed review | None |
| Plan | Pending approval | This revised plan | User | Explicit plan approval in chat |
| Implementation | Not approved | No implementation changes approved yet | User | Blocked until plan approval |
| Close-out | Not started | Requires implementation review, tests, and last-50-line log checks | User | Explicit implementation approval |

## Overview

The executable baseline is broken before functional behavior can be trusted. `pytest -q` currently collects `app/services/test_executor.py` and `app/services/test_generator.py` as tests, fails to import the `app` package, and then fails again on missing modules imported from `app/models/__init__.py`, `app/routers/ai.py`, `app/services/ai_service.py`, and the connector implementations. The repository tree confirms the import graph is stale: `app/models/__init__.py:3-12` imports eight model modules that are not present under `app/models/`, `app/services` does not contain `copilot_auth_service.py`, and `app/connectors` does not contain `base.py`.

Security hardening must follow immediately after startup repair. `app/main.py:49-71` wires sensitive routers directly onto the FastAPI app and starts background work with no in-app auth boundary. `app/routers/credentials.py:105-118` decrypts and returns stored credentials, `app/routers/datasources.py:426-457` returns and exports datasource passwords, `app/routers/external_tools.py:268-317,436-475` allows HTTP-driven `.env` updates, remote URL probing, and local process launch, `app/routers/odi.py:40-42,357-360` trusts caller-controlled root paths and shells commands, and `app/services/tfs_service.py:113,154,253,288,306,360,421,454,479,706,791,911` disables TLS verification while `app/services/tfs_service.py:901-906` can forward tokens into hyperlink fetches. After those P0 items are fixed, architecture cleanup should target the stale composition root in `app/main.py`, the router-to-service inversion in `app/services/session_watchdog.py:10-28`, and process-local mutable state in `app/routers/tests.py:52-53`, `app/routers/ai.py:37,269-287`, `app/routers/odi.py:24-26`, and `app/routers/external_tools.py:26`.

A non-follow `git log -- ...` scan for `app/models/agent_profile.py`, `app/connectors/base.py`, `app/services/copilot_auth_service.py`, and the other missing core model files returned no history, so phase 1 must assume canonical modules need to be recreated or the dependent features must be gated off; simple file restoration from git history is not currently available.

## Requirements

- Restore a stable import and startup graph so `pytest -q` can collect tests and `from app.main import app` can succeed.
- Repair stale model/service/connector imports without guessing; recreate missing canonical modules or temporarily gate features until their dependencies exist.
- Introduce an in-app auth boundary for sensitive API routes before any further feature restoration.
- Remove plaintext secret retrieval and transport from credentials and datasources, including browser-facing injection and export flows.
- Remove HTTP-controlled host/path selection, shell execution, `.env` mutation, and local process launch from the app surface.
- Re-enable TLS verification and add SSRF-safe, allowlisted hyperlink fetching with correctly scoped credentials.
- After the P0 security work, repair composition-root boundaries, remove router-owned mutable state, split oversized modules, and add executable regression gates.

## Architecture/Change Table

| Change | Priority | File/Area | Rationale | Risks | Benefits | Reviewer/Approver | Pros/Cons Summary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pytest collection and package bootstrap repair | P0 | `pytest.ini` (new), `app/__init__.py` (new), `tests/`, top-level `test_download_pbi1736268.py` | Stop accidental collection of implementation modules and make the `app` package importable during tests | May surface additional hidden failures immediately | Unblocks every later executable check | Reviewer: python-reviewer; Approver: User | Pro: fastest path to a truthful baseline. Con: reveals more missing surfaces right away. |
| Import graph and missing module repair | P0 | `app/models/__init__.py`, missing `app/models/*`, `app/services/copilot_auth_service.py`, `app/connectors/base.py`, dependent routers/services, `app/main.py` | `app/models/__init__.py:3-12` and multiple routers/services import modules that do not exist in the tree | High churn if unsupported features are still wired in | Restores app importability and startup determinism | Reviewer: python-reviewer; Approver: User | Pro: fixes root cause rather than patching tests. Con: may require gating features before reintroducing them. |
| Auth boundary at the composition root | P0 | `app/main.py`, new auth dependency module under `app/`, sensitive routers | `app/main.py:49-61` registers all API routers without security dependencies | Can break existing UI/API flows if allowlist is incomplete | Converts the app from implicit trust to explicit authorization | Reviewer: security-reviewer; Approver: User | Pro: single choke point for enforcement. Con: needs careful anonymous-route allowlisting. |
| Plaintext secret removal and datasource secret migration | P0 | `app/routers/credentials.py`, `app/routers/datasources.py`, datasource model/storage, `app/services/credential_service.py`, UI callers | Credentials and datasource endpoints currently disclose passwords to the browser | Migration risk for existing saved datasource secrets | Eliminates the highest-confidence secret exposure paths | Reviewer: security-reviewer; Approver: User | Pro: closes direct data leak paths. Con: requires data migration and UI/API contract updates. |
| Host-control and shell execution removal | P0 | `app/routers/external_tools.py`, `app/routers/odi.py`, `app/static/js/app.js`, affected templates | Current APIs can mutate `.env`, select paths/URLs, launch processes, and shell ODI commands | Users may lose convenient but unsafe local-host workflows | Removes remote control of the server host | Reviewer: security-reviewer; Approver: User | Pro: largest reduction in host compromise surface. Con: some workflows must be redesigned or temporarily disabled. |
| TLS verification and SSRF/token-scoping repair | P0 | `app/services/tfs_service.py`, `app/config.py`, possibly a new fetch policy/helper module | `ssl=False` is pervasive and hyperlink scraping can forward credentials to fetched URLs | Enterprise CA requirements can cause rollout friction | Restores transport integrity and prevents credential leakage to untrusted hosts | Reviewer: security-reviewer; Approver: User | Pro: hardens all remote fetches consistently. Con: requires explicit CA and allowlist handling. |
| Composition-root and service-boundary cleanup | P1 | `app/main.py`, `app/services/session_watchdog.py`, extracted ODI/session services | `session_watchdog.py:10` imports router code and `main.py` couples imports, registration, and startup side effects | Refactor can widen scope if done too early | Makes the app boot sequence testable and resilient | Reviewer: code-reviewer; Approver: User | Pro: lowers future regression rate. Con: should wait until P0 behavior is stable. |
| Router-state isolation and test-gate enforcement | P1 | `app/routers/tests.py`, `app/routers/ai.py`, `app/routers/odi.py`, `app/routers/external_tools.py`, `tests/` | Router globals are process-local and oversized modules are hard to reason about or test | Medium effort with several follow-on migrations | Adds durable state handling and regression protection | Reviewer: pr-test-analyzer; Approver: User | Pro: prevents recurrence. Con: not the first blocker once startup/security are broken. |

## Implementation Steps Table

| Phase | Phase Priority | Step | Task Priority | Change/Action | Files/Area | Action/What | Why (Rationale) | Dependencies | Risk | Reviewer | Approver | Pros/Cons Summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Startup Graph Repair | P0 | 1 | P0 | Define pytest collection boundary | `pytest.ini` (new), `tests/`, top-level `test_download_pbi1736268.py` | Add explicit `testpaths`, make a deliberate decision on whether `test_download_pbi1736268.py` is a real test or a diagnostic script, and prevent `app/services/test_executor.py` and `app/services/test_generator.py` from being collected as tests by filename alone | Current failures start before behavior is tested because pytest is collecting implementation modules as tests | None | Low | python-reviewer | User | Pro: immediately improves signal. Con: can temporarily hide diagnostic scripts until relocated. |
| 1. Startup Graph Repair | P0 | 2 | P0 | Make the `app` package importable | `app/__init__.py` (new), optional `tests/conftest.py` | Add the missing package root and minimal test bootstrap so `from app...` imports resolve consistently under pytest and startup smoke checks | The collection errors explicitly show `No module named 'app'` | Step 1 | Low | python-reviewer | User | Pro: minimal foundational change. Con: still exposes stale imports next. |
| 1. Startup Graph Repair | P0 | 3 | P0 | Repair or gate stale module imports | `app/models/__init__.py`, missing model files, `app/services/copilot_auth_service.py`, `app/connectors/base.py`, dependent routers/services, `app/main.py` | Recreate the missing canonical abstractions that are still in active use, and temporarily remove or feature-flag router registrations whose dependency graph cannot be restored in the same slice | `app/models/__init__.py:3-12` imports missing modules and `git log -- ...` showed no direct history for the missing files, so import repair must be intentional | Steps 1-2 | High | python-reviewer | User | Pro: fixes the actual startup graph. Con: may require temporary feature gating before full restoration. |
| 1. Startup Graph Repair | P0 | 4 | P0 | Validate startup baseline | `tests/`, `app/main.py` | Run `pytest -q` and a focused app import smoke such as `python -c "from app.main import app"` until collection and app import both pass | This is the first hard gate before security work | Step 3 | Medium | python-reviewer | User | Pro: keeps later work grounded. Con: can expose more missing runtime dependencies. |
| 2. Auth Boundary and Secret Containment | P0 | 5 | P0 | Add a default-deny auth boundary | `app/main.py`, new auth dependency module under `app/`, sensitive routers | Introduce `require_app_auth` or equivalent and apply it at router registration time for `/api/*` routes, with a short explicit anonymous allowlist for page routes, static content, and health/bootstrap endpoints | `app/main.py:49-61` currently registers sensitive routers with no in-app authorization layer | Phase 1 | Medium | security-reviewer | User | Pro: one central enforcement point. Con: needs coordinated frontend/API behavior changes. |
| 2. Auth Boundary and Secret Containment | P0 | 6 | P0 | Remove plaintext credential delivery | `app/routers/credentials.py`, `app/services/credential_service.py`, UI callers | Eliminate browser-facing plaintext password injection; replace `/inject` with a server-side credential binding flow or one-time server-only use path; keep only metadata such as `has_password` in API responses | `app/routers/credentials.py:105-118` decrypts and returns the stored password | Step 5 | Medium | security-reviewer | User | Pro: removes a direct secret leak. Con: requires UI flow redesign. |
| 2. Auth Boundary and Secret Containment | P0 | 7 | P0 | Migrate datasource secrets off raw password fields | Datasource model/storage, `app/routers/datasources.py`, `app/services/credential_service.py`, `app/static/js/app.js` | Replace raw datasource password storage with encrypted storage or a credential-profile reference, remove passwords from GET/export responses, and add a migration path for existing saved secrets | `app/routers/datasources.py:434-457` returns and exports plaintext datasource passwords | Steps 3, 5 | High | security-reviewer | User | Pro: closes the second direct secret exposure path. Con: data migration must preserve connectivity. |
| 3. Host-Control and Shell Removal | P0 | 8 | P0 | Remove external-tools host control | `app/routers/external_tools.py`, `app/static/js/app.js`, templates | Remove or hard-disable HTTP endpoints that write `.env`, accept caller-provided stream URLs, probe remote URLs, launch processes, stop processes, or stream desktop capture; replace with server-owned, read-only diagnostics only if still required | `app/routers/external_tools.py:122-155`, `268-317`, and `436-475` currently mutate host state and launch local executables | Steps 5-7 | Medium | security-reviewer | User | Pro: biggest host-surface reduction in one slice. Con: removes convenience features that need replacement later. |
| 3. Host-Control and Shell Removal | P0 | 9 | P0 | Remove ODI caller-controlled paths and shell execution | `app/routers/odi.py`, UI callers, extracted ODI/session service if needed | Replace request-supplied `root_path` with a configured allowlisted root, disable command execution until a fixed-argv service exists, and keep only read-only metadata parsing inside the trusted root | `app/routers/odi.py:40-42` trusts arbitrary paths and `app/routers/odi.py:357-360` shells a command string | Step 8 | High | security-reviewer | User | Pro: prevents remote path traversal and shell execution. Con: may temporarily narrow ODI functionality. |
| 4. TLS and SSRF Hardening | P0 | 10 | P0 | Re-enable TLS verification and constrain remote fetches | `app/services/tfs_service.py`, `app/config.py`, optional new fetch policy module | Remove `ssl=False`, add CA-bundle/SSL-context support where enterprise certs are required, allowlist hyperlink hosts, and ensure PAT/bearer headers are only sent to approved hosts and never to arbitrary hyperlinks | `app/services/tfs_service.py:113,154,253,288,306,360,421,454,479,706,791,911` disable TLS checks and `app/services/tfs_service.py:901-906` scope credentials too loosely | Steps 5-9 | High | security-reviewer | User | Pro: closes transport and SSRF/token leakage gaps together. Con: needs explicit cert and host policy decisions. |
| 5. Architecture and Test Gate | P1 | 11 | P1 | Rebuild composition root and invert router/service dependencies | `app/main.py`, `app/services/session_watchdog.py`, extracted service modules | Introduce an app factory or equivalent registration layer, move router registration behind dependency health checks, and extract `sweep_odi_sessions` out of the ODI router so the watchdog depends on services rather than routers | `app/main.py` is a stale composition root and `app/services/session_watchdog.py:10-28` imports router code directly | Steps 1-10 | Medium | code-reviewer | User | Pro: makes startup deterministic and testable. Con: should happen only after P0 surfaces are stable. |
| 5. Architecture and Test Gate | P1 | 12 | P1 | Replace router-owned mutable state and add regression gates | `app/routers/tests.py`, `app/routers/ai.py`, `app/routers/odi.py`, `app/routers/external_tools.py`, `app/services/operation_control.py`, `tests/` | Move in-memory globals into service-owned or durable stores, split oversized router/service modules where needed, and add regression tests for import smoke, auth enforcement, secret redaction, disabled host control, and allowlisted remote fetch behavior | Router globals at `tests.py:52-53`, `ai.py:37,269-287`, `odi.py:24-26`, and `external_tools.py:26` are process-local and brittle | Step 11 | Medium | pr-test-analyzer | User | Pro: prevents recurrence and adds safe delivery gates. Con: more structural work after urgent security fixes. |

## Agent Pros/Cons Summaries

- `planner`: Pro: keeps the sequence anchored to executable blockers and the requested priority order. Con: planning alone cannot prove feasibility once missing modules are reconstructed.
- `python-reviewer`: Pro: best fit for pytest discovery, package bootstrap, and stale import graph repair. Con: less focused on host-control and SSRF abuse paths.
- `security-reviewer`: Pro: required for auth boundary, secret transport, host-control removal, and TLS/SSRF fixes. Con: can widen scope unless bounded by the phase gates above.
- `code-reviewer`: Pro: useful once P0 issues are fixed and composition-root boundaries can be judged on stable code. Con: too early a refactor pass would mix structural cleanup with urgent security work.
- `silent-failure-hunter`: Pro: strong fit for background startup failures and watchdog behavior after import repair. Con: low signal before the startup graph is repaired.
- `pr-test-analyzer` and `tdd-guide`: Pro: convert each phase into executable regression gates. Con: most valuable after the affected interfaces stop changing daily.

## Testing Strategy

- Unit tests: add focused tests for pytest collection boundaries, auth enforcement, credentials redaction, datasource secret handling, ODI path policy, external-tools endpoint removal/disablement, TFS fetch allowlisting, and watchdog service boundaries.
- Integration tests: keep `pytest -q` as the first gate after phase 1; add a startup smoke test that imports `app.main:app`; add `TestClient` coverage for unauthorized versus authorized access on sensitive routes.
- Security regression tests: verify credentials and datasource APIs never return plaintext passwords, verify disabled host-control endpoints reject requests, verify ODI ignores caller-supplied arbitrary roots, and verify TFS hyperlink fetches reject unapproved hosts and do not forward PAT/bearer headers to them.
- Operational validation: after implementation slices that affect startup or background jobs, inspect the last 50 lines of `stdout_capture.txt` and `stderr_capture.txt` or the active runtime logs before claiming success.
- Documentation review: update `docs/architecture.md`, `docs/agents.md`, and any operator guidance touched by auth, secret storage, or external-tool behavior changes.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Additional missing modules appear after the first import fixes | Keep phase 1 iterative: repair the startup graph, rerun `pytest -q`, and gate unsupported routers until their dependencies are restored. |
| Datasource secret migration breaks existing saved connections | Add a one-time migration with dry-run reporting, keep an encrypted fallback path during rollout, and validate connection tests against migrated records before deleting legacy fields. |
| Auth boundary blocks existing UI flows unexpectedly | Implement a short explicit anonymous allowlist and cover key pages and APIs with integration tests before widening enforcement. |
| Removing external-tools and ODI execution endpoints disrupts user workflows | Replace unsafe control surfaces with read-only diagnostics first and document the temporary restrictions plus the server-managed replacement path. |
| TLS verification fails in enterprise environments with private CAs | Support CA bundle or SSL-context configuration and test against representative enterprise endpoints before making the gate mandatory. |
| Moving router globals into durable state changes in-flight behavior | Migrate state behind service interfaces with TTL/cleanup semantics and add compatibility handling for operations already in progress during rollout. |

## Success Criteria

- [ ] `pytest -q` no longer fails during collection and no implementation modules under `app/services/` are collected as tests by accident.
- [ ] `from app.main import app` succeeds without missing-module or stale-composition-root failures.
- [ ] Sensitive API routers enforce an in-app auth boundary, with anonymous access limited to explicitly approved routes.
- [ ] Credentials and datasource APIs no longer return or export plaintext passwords to the browser.
- [ ] No HTTP endpoint can write `.env`, launch local processes, select arbitrary host paths, or shell ODI commands.
- [ ] TFS and hyperlink fetches validate TLS and only send credentials to approved hosts.
- [ ] `session_watchdog` no longer imports router logic, and router-owned mutable state is isolated behind service-owned or durable stores.
- [ ] Regression tests and log reviews pass, and implementation approval is obtained after the post-change review.

## Reviewer/Approver Table

| Workstream | Reviewer | Approver | Current Status |
| --- | --- | --- | --- |
| Review baseline and phase ordering | planner | User | Review approved; plan pending |
| Import/startup graph repair | python-reviewer | User | Pending implementation |
| Auth, secrets, host-control, TLS, SSRF | security-reviewer | User | Pending implementation |
| Composition root and service boundaries | code-reviewer | User | Pending implementation |
| Silent failure and background task behavior | silent-failure-hunter | User | Pending implementation |
| Regression tests and delivery gate | pr-test-analyzer / tdd-guide | User | Pending implementation |