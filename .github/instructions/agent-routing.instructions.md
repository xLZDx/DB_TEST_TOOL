---
name: "Global Agent Routing"
description: "Use when planning features, architecture, implementation, reviews, testing, docs, open-source packaging, networking, and build/test failure resolution across this repository."
applyTo: "**"
---

# Global Agent Routing

Prefer delegating focused work to specialized custom agents instead of solving everything in one pass.

## Core Routing By Phase

- Planning and discovery: `planner`, `architect`, `code-architect`, `code-explorer`
- Implementation and refactoring: `code-simplifier`, `refactor-cleaner`, `performance-optimizer`, `a11y-architect`
- Review and risk analysis: `code-reviewer`, `security-reviewer`, `comment-analyzer`, `type-design-analyzer`, `silent-failure-hunter`, `conversation-analyzer`
- Testing and validation: `tdd-guide`, `pr-test-analyzer`, `e2e-runner`, `harness-optimizer`, `training-inspector`

## Language and Framework Routing

- Python changes: `python-reviewer`
- FastAPI changes: `fastapi-reviewer`
- C++ changes: `cpp-reviewer`
- Flutter changes: `flutter-reviewer`
- SQL/schema/query work: `database-reviewer`

## Build and Failure Routing

- Generic build/test failures: `build-error-resolver`
- C++ build failures: `cpp-build-resolver`
- Dart/Flutter build failures: `dart-build-resolver`
- PyTorch and CUDA/training build failures: `pytorch-build-resolver`

## Infrastructure and Network Routing

- Network design and policy: `network-config-reviewer`
- Runtime connectivity and diagnostics: `network-troubleshooter`

## Open Source and Delivery Routing

- Prepare reusable code extraction: `opensource-forker`
- Package and release readiness: `opensource-packager`
- Security/legal hygiene for publishing: `opensource-sanitizer`

## Documentation and Content Routing

- Documentation and changelog updates: `doc-updater`
- SEO-focused content refinements: `seo-specialist`


## Operational Rules

- For multi-step feature work, invoke `planner` or `architect` first.
- Before editing unfamiliar areas, use `code-explorer` to gather context.
- After meaningful implementation, run `code-reviewer` and add `security-reviewer` for APIs, auth, data access, secrets, external input, or **any build script or executable change** (including automation/macro tools like pynput, pyautogui, etc.).
- For any build script or executable change, also run an environment-check agent to detect likely antivirus/endpoint security interference. Proactively warn users and reference the AV-exe checklist in repo memory.
- For Python/FastAPI/SQL changes, always include the corresponding domain reviewer.
- For performance-sensitive paths, include `performance-optimizer` before finalizing.
- For flaky tests, swallowed exceptions, or brittle fallbacks, include `silent-failure-hunter`.
- For test strategy, include `tdd-guide`; for regression coverage, include `pr-test-analyzer`; for browser/user-flow validation, include `e2e-runner`.
- For CI/build breakages, route to the relevant `*-build-resolver` immediately.

## Delegation Scope

- Keep delegation narrow. Use the smallest specialist set needed for the current task.
- Avoid circular handoffs.
- Prefer one lead specialist plus one verifier over broad parallel delegation.


## Additional Global Rules



- **Grid-based plan/report template required:** All planning, analysis, and reporting must use the following combined, grid-based template, presented in chat and in the repository:
	- Overview: summary of the plan/report and its scope.
	- Requirements: explicit goals and constraints.
	- Architecture/Change Table: grid with columns for Change, Priority, File/Area, Rationale, Risks, Benefits, Reviewer/Approver, Pros/Cons Summary.
	- Implementation Steps Table: grid grouped by phase and step, with columns for Phase, Phase Priority, Step, Task Priority, Change/Action, Files/Area, Action/What, Why (Rationale), Dependencies, Risk, Reviewer, Approver, Pros/Cons Summary.
	- Agent Pros/Cons Summaries: bullet points for each agent.
	- Testing Strategy: unit, integration, regression, and doc review.
	- Risks & Mitigations: explicit risk/mitigation pairs.
	- Success Criteria: checklist of outcomes.
	- Reviewer/Approver Table: grid of workstreams and responsible agents.
	- The template must be shown in chat for review and approval before any code is written or merged, and must be referenced in the PR/commit.
- **Approval workflow required:** The work must move through explicit stage gates in chat:
	- Review approval needed before the plan is finalized.
	- Plan approval needed before implementation starts.
	- Implementation approval needed before merge, release, or close-out.
	- Do not advance to the next stage without explicit user approval.
- **Approval gate:** Every implementation requires a written plan and a double-ask confirmation before code is written.
- **No guessing:** All answers and code must cite their source inline (file:line, command output).
- **Agent review mandatory:** A specialist reviewer must review the plan before writing code and again after completion. Reviewer/approver agent name must be recorded in the plan.
- **Validate logs before claiming success:** Always check and reference the last 50 lines of every relevant log before reporting success.
- **Functional tests prove behavior:** Tests must verify actual behavior, not just string matches.
- **Regression test maintenance:** Every change must include or update a regression test.
- **Git lifecycle:** Commit before each major phase; commit and push after completion. Include the todo list in the commit body.
