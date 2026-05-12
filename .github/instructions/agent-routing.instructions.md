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
- After meaningful implementation, run `code-reviewer` and add `security-reviewer` for APIs, auth, data access, secrets, or external input.
- For Python/FastAPI/SQL changes, always include the corresponding domain reviewer.
- For performance-sensitive paths, include `performance-optimizer` before finalizing.
- For flaky tests, swallowed exceptions, or brittle fallbacks, include `silent-failure-hunter`.
- For test strategy, include `tdd-guide`; for regression coverage, include `pr-test-analyzer`; for browser/user-flow validation, include `e2e-runner`.
- For CI/build breakages, route to the relevant `*-build-resolver` immediately.

## Delegation Scope

- Keep delegation narrow. Use the smallest specialist set needed for the current task.
- Avoid circular handoffs.
- Prefer one lead specialist plus one verifier over broad parallel delegation.
