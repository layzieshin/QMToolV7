# AP-029 Agent Workflow Cost Profile — AGENT-COST-01

Status: **PLANNED / NOT ACTIVE** (P1 package contract; not a product checkpoint)
Package ID: `AGENT-COST-01`
Profile target (future): `cursor-first` v1
Effective profile today: `balanced` v2 in `.cursor/agent-system.json`
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` (P0 wins on architecture boundaries)
Operation guide: `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md`
Source plan: `QMTool_Agent_Workflow_Cursor_First_20260927.md` (2026-09-27; external handover artifact)

## Authority and P0 precedence

- This document is **P1**. When it conflicts with P0 architecture, persistence, operations, or
  `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` on binding product boundaries, **P0 wins**.
- This document is the **authoritative package contract** for AGENT-COST-01 checkpoints W0–W3.
  Ignored evidence under `build/agent-cost-01/` is an index and control record only; it is **not**
  a second source of truth.
- **No activation by W0, W1, or W2.** The `cursor-first` profile becomes effective only after W3
  PASS, an independent critical Codex final audit, merge, and a documented safe transition at the
  next package or checkpoint boundary. Until then `.cursor/agent-system.json` remains `balanced` v2.
- **No retrofit** on the paused PILOT00 B1 attempt (`feature/ap-029-pilot00-service-release` at
  `60f4649ed89e195c770558b928ba464de9d1c0e0`). Resume keeps contract revision and
  `rework_count=2`; the first post-resume pilot step remains OCI double-build after resume preflight.

## Goal

Reduce routine GPT usage inside Cursor by routing regular execution and read-only exploration to
Composer 2.5 Standard, routine independent reviews to Grok 4.7 Extra High Standard, and reserving
GPT/Codex for critical final audit and exhausted technical escalation only — without weakening
existing authorization, Git, secret, stop, or evidence guards.

## Non-goals

- No new agent runner, queue, workflow engine, or global cache service.
- No product code, webclient, database migration, packaging, server, certificate, SSH/Docker, or
  pilot data changes through this package.
- No API-key bridge, Auto/inherit/fast fallback, or quota bypass for configured custom roles.
- No cost-percentage, token, cache-hit, or billing claims without host-provided measurements.
- No claim that the external Codex/ChatGPT orchestrator is a Cursor model ID, `RUNTIME_ATTESTED`,
  or `CONTROL_PLANE_PINNED`.
- No silent reuse of `INDEPENDENT_ORCHESTRATOR_REVIEW` from PILOT00 packages for AGENT-COST-01;
  W1 must define its own fail-closed, agent-/target-/contract-/diff-bound review authority.

## Current basis, worktree, and pilot isolation

Verified execution basis for W0 (2026-09-27):

| Item | Value |
| --- | --- |
| Remote `main` / package base | `4bedcc84cd81a46b6e8802a3a6b2296f9f5f9d5c` |
| AGENT-COST-01 worktree | `I:\Projekte\QMToolV7-agent-system-v3` |
| Branch | `feature/cursor-agent-system-v3` |
| Divergence vs `origin/main` | 0 ahead / 0 behind at W0 start |
| Writer policy | One writer per worktree; Cursor coordinator/implementer only in this tree |
| PILOT00 protected branch | `feature/ap-029-pilot00-service-release` @ `60f4649ed89e195c770558b928ba464de9d1c0e0` |
| PILOT00 worktree | `I:\Projekte\QMToolV7\build\worktrees\ap-029-pilot00-service-release` — **out of scope** |

Preparatory Git/worktree setup before Cursor W0 is an orchestrator responsibility via normal
allowed Git/worktree tools. Cursor must not fake `FINAL_GIT` or disable hooks to perform it.

## Owner trace and configuration hardcodes

Normative configuration owner: `.cursor/agent-system.json` (`profile: balanced`, `version: 2`).

Additional hardcoded or mirrored owners that W1 must reconcile to the configuration owner (not
changed in W0):

| Area | Owner path(s) | Notes |
| --- | --- | --- |
| Role frontmatter | `.cursor/agents/<role>.md` | Six GPT-bound roles today; two Composer roles |
| Subagent hook | `.cursor/hooks/subagent-start.ps1` | Validates `subagent_model`; catalog/frontmatter = control check only |
| Main launcher | `.cursor/tools/invoke-cursor-agent.ps1` | No explicit model parameter today |
| Profile apply | `.cursor/skills/apply-agent-profile/SKILL.md` | Must mirror JSON changes |
| Macro protocol | `.cursor/skills/execute-gated-macro/SKILL.md`, `references/checkpoint-protocol.md` | D15/Terra hardcodes in tests and protocol |
| D15 decision | `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` § D15 | Reviewer evidence profiles; successor references this package after activation |
| Autonomous rules | `.cursor/rules/02-autonomous-work-package.mdc` | PILOT00 `INDEPENDENT_ORCHESTRATOR_REVIEW` marker — not reused silently |
| Docs tests | `tests/docs/test_cursor_agent_system.py`, `test_cursor_macro_workflow.py`, `test_cursor_execution_hygiene.py`, `test_docs_consistency.py` | Synthetic + owner-path verification |
| Independent Codex path | `.cursor/skills/qmtool-module-development/references/independent-codex-review.md` | Must be explicitly bounded in W2; not stacked with new final path |

W0 records these owners only. W1 edits them per allowlist below.

## Target role matrix and host boundaries

Planned **active** mapping after safe activation (not effective until post-W3 transition):

| Responsibility | Host | Planned Cursor model / path | Boundary |
| --- | --- | --- | --- |
| Package coordinator, repo-explorer, implementer, git-steward | Cursor native | `composer-2.5[]` (Standard; `fast=false` equivalent) | One writer per worktree |
| checkpoint-reviewer, plan-challenger, external-review-triager | Cursor native subagent | `grok-4.7[effort=xhigh,fast=false]` (catalog slug `grok-4.7-xhigh` if natively equivalent) | Independent read-only context; no self-approval |
| roadmap-architect (in-package planning/final audit) | Cursor native | Grok 4.7 xhigh Standard | Fresh final audit context for normal packages |
| Critical final audit / exhausted escalation | External Codex/ChatGPT-authenticated orchestrator | **Not a Cursor model ID** | Agent-ID, separate context, contract, full diff, primary evidence; no Cursor-GPT fallback |
| User/orchestrator product decisions | Human + external orchestrator | N/A | No second live detail controller of the same Cursor checkpoint |

External orchestrator responsibilities: goal clarification, architecture decisions, package release,
and critical GPT audit. It must not approve a diff it implemented. It is **not** `gpt-5.6-sol`,
`gpt-5.6-terra`, `RUNTIME_ATTESTED`, or `CONTROL_PLANE_PINNED`.

Catalog presence of `composer-2.5`, `composer-2.5-fast`, `grok-4.7-xhigh`, and
`grok-4.7-xhigh-fast` is **availability metadata only**. Token, cost, cache, and actual serving
model remain `UNKNOWN` unless the host exposes them in primary evidence.

## Planning quality

| Field | Value |
| --- | --- |
| `planning_risk_level` | **HIGH** |
| Requirement traceability | Required — see `build/agent-cost-01/.../requirement-traceability.md` |
| Risk-to-evidence | Required — see `build/agent-cost-01/.../risk-to-evidence.md` |
| Plan challenge | Required (HIGH) — external read-only Codex plan review PASS for W0 |
| Package integration scenario | Required — W0→W1→W2→W3 serial profile switch without breaking guards |

## Requirement traceability (summary)

| Req ID | Requirement | W0 evidence | Later checkpoint |
| --- | --- | --- | --- |
| R-COST-01 | Freeze package contract PLANNED / NOT ACTIVE | This doc + W0 evidence | W3 activation note |
| R-COST-02 | Exact per-checkpoint tracked allowlists | § Allowlists | W1–W3 commits |
| R-COST-03 | Composer for routine Cursor execution | Role matrix § | W1 JSON + launcher |
| R-COST-04 | Grok xhigh Standard for routine reviews | Role matrix § | W1 agents + hook tests |
| R-COST-05 | Critical GPT audit via external Codex host | Host boundaries § | W1 handoff contract |
| R-COST-06 | No false runtime/cost/cache claims | § Evidence semantics | W2 metrics, W3 canary |
| R-COST-07 | D15 successor without silent Terra/Sol claims | D15 reference § | W1 tests + docs |
| R-COST-08 | PILOT00 isolation / no retrofit | Basis table § | All checkpoints |
| R-COST-09 | 12 verification cases in real owner tests | § Verification contract | W1–W3 tests |
| R-COST-10 | Safe activation only after W3 + Codex audit + merge | § Activation boundary | W3 only |

## Risk-to-evidence matrix (summary)

| Risk | Mitigation | Evidence owner |
| --- | --- | --- |
| Wrong model / effort / fast fallback | Hook + launcher + config parity tests | W1 `tests/docs/*`, native smoke |
| False `RUNTIME_ATTESTED` | D15 three-profile discipline; UNKNOWN honest | W1 macro tests, W3 canary |
| Self-approval / reviewer mutation | Existing role forbiddens + new guards | W1 tests cases 5–6 |
| Stale contract/diff/PR head | Contract SHA256 + context manifest invalidation | W2 manifest, W1 tests case 6–8 |
| Missing critical GPT audit | Explicit external handoff; no Grok boolean substitute | W1 config + W3 canary case 7 |
| Pilot/profile retrofit | Frozen PILOT00 SHA; activation at next boundary only | W0 basis record, W3 report |
| Secret/credential leakage in telemetry | Redacted evidence; no prompt/DSN storage | W2 policy + scans |
| External review policy drift | Explicit W2 policy change with guard tests or N/A report | W2 allowlist |
| GitHub API overreach | Narrow git-guard extension or capability gap report | W2 |
| Cost/cache fiction | `UNKNOWN` semantics mandatory | W2 metrics, test case 10 |

## Package integration scenario

**Scenario:** After W3 PASS, a new MEDIUM-risk docs-only package starts on `main` post-merge.

1. Coordinator launches with explicit Composer 2.5 Standard via updated launcher (W1).
2. Implementer edits only allowlisted docs; checkpoint-reviewer runs as Grok 4.7 xhigh in a
   separate context with contract-bound diff review (W1).
3. Context manifest from W2 is created at checkpoint start; stale manifest blocks reuse (W2).
4. Package completes with one checkpoint review instance per attempt; no stacked Codex+Grok+Sol
   final audit for the same inner release (W2).
5. Critical HIGH package still routes final audit to external Codex orchestrator with bound
   agent/target/contract/diff (W1/W3).
6. PILOT00 resume on its frozen profile does not pick up the new mapping until its own documented
   transition (W0 isolation).

## Checkpoint allowlists (tracked paths only)

### W0 — Basis, boundaries, routing contract

**Tracked allowlist (exact):**

- `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md` (create)
- `docs/DOCS_CANONICAL_INDEX.md` (one P1 entry)

**Ignored evidence only:** `build/agent-cost-01/w0/<attempt>/`

**Gate:** External read-only Codex plan review PASS; docs consistency tests green; `git diff --name-only` exact.

**Commit message:** `docs(agent-cost): freeze cursor-first workflow profile`

**W1 start condition:** W0 committed; tracked tree clean; this contract SHA256 recorded in W1
`checkpoint-contract.md`. **W1 NOT RUN until then.**

### W1 — Cursor-first routing (full, test-protected)

**Tracked allowlist:**

- `.cursor/agent-system.json`
- `.cursor/agents/roadmap-architect.md`
- `.cursor/agents/checkpoint-reviewer.md`
- `.cursor/agents/plan-challenger.md`
- `.cursor/agents/external-review-triager.md`
- `.cursor/agents/escalation-reviewer.md`
- `.cursor/agents/git-steward.md`
- `.cursor/hooks/subagent-start.ps1`
- `.cursor/tools/invoke-cursor-agent.ps1`
- `.cursor/skills/apply-agent-profile/SKILL.md`
- `.cursor/skills/execute-gated-macro/SKILL.md`
- `.cursor/skills/execute-gated-macro/references/checkpoint-protocol.md`
- `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md` (bounded workflow references only)
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` (D15 successor references only)
- `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md` (status still PLANNED until W3)
- `tests/docs/test_cursor_agent_system.py`
- `tests/docs/test_cursor_macro_workflow.py`
- `tests/docs/test_cursor_execution_hygiene.py`

**Must define:** Fail-closed external Codex orchestrator review authority for this package (agent,
target, contract, diff binding) — not a reuse of PILOT00 `INDEPENDENT_ORCHESTRATOR_REVIEW` without
new contract fields.

**Gate:** Targeted docs tests + native Grok/Composer smoke + synthetic hook tests.

### W2 — Context handoffs, reuse, measurability

**Tracked allowlist (extends W1 only where needed):**

- `.cursor/skills/execute-work-package/SKILL.md`
- `.cursor/skills/execute-gated-macro/SKILL.md` (context manifest extensions)
- `.cursor/hooks/git-guard.ps1` (only if narrow review-thread API extension is implemented)
- `.cursor/hooks/workflow-watchdog.ps1` (only if wait/progress distinction requires it)
- `.cursor/skills/qmtool-module-development/references/independent-codex-review.md` (explicit boundary)
- `.cursor/reviews/README.md`
- `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md`
- `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md`
- `tests/docs/test_cursor_agent_system.py`
- `tests/docs/test_cursor_execution_hygiene.py`
- `tests/docs/test_docs_consistency.py` (if index or doc links change)

If GitHub review-thread mutation guard cannot be implemented safely: report capability gap; do not
disable gates or set `DISABLED` without replacement tests.

### W3 — Qualification, publication, safe activation

**Tracked allowlist:**

- All W1/W2 workflow owners required by failing tests or activation docs
- `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md` (activation section + status change only here)
- `docs/DOCS_CANONICAL_INDEX.md` (status wording if needed)
- `tests/docs/*` (as required by canary and regression)
- `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md` (activation pointer)

**Gates:** Full `tests/docs` serial green; representative native canary; independent critical Codex
final audit PASS; CI on PR; policy-compliant merge only under explicit package authorization.

**Activation:** Update `.cursor/agent-system.json` profile to `cursor-first` v1 only in W3 after
all gates, documenting the next safe package/checkpoint boundary. Running attempts stay on prior
profile version.

### Global exclusions (all checkpoints)

- Product modules, `src/backend/*` (except if a test-only import path is already in docs tests),
  `webclient/*`, PostgreSQL migrations, packaging, service host, pilot Linux artifacts
- `.cursor/runtime/workflow-state.json` and live pilot state
- PILOT00 worktree `ap-029-pilot00-service-release` and its commits
- New parallel roadmap, runner, cache, or API credential bridge
- Blanket `git add .`; only explicit allowlist paths per checkpoint

## Verification contract — 12 mandatory cases

Cases 1–12 must be enforced in **real owner tests** (primarily `tests/docs/*` and hooks), not only
in copied validator logic. W0 documents them; W1–W3 implement and prove them.

1. Configuration, agent frontmatter, invocation, and required model parameters agree.
2. Grok Standard/xhigh allowed; Fast, wrong effort, unknown variants, and expensive fallback rejected.
3. Parent and child model metadata not conflated; missing fields do not produce runtime attestation.
4. Cursor main start uses explicit allowed Composer path; preserves prompt as one argument and host security settings.
5. Implementer cannot grant own PASS or Git/merge approval; reviewer mutation blocked.
6. Foreign package/target/contract/diff hash, stale PR head, or new material invalidates affected approvals.
7. Missing critical GPT review cannot be replaced by routine Grok PASS or a free boolean.
8. Context manifest invalidates on relevant file/base/plan changes; manipulated ignored JUnit/log/contract files invalidate evidence.
9. Resume does not repeat completed steps, re-ask, or re-reserve reviews; abort/repair limits remain.
10. Missing cost/cache values stay `UNKNOWN`; untagged helpers do not imply full cost coverage.
11. If external review selection changes: real open P1, required check/review/conversation, or stale evidence remains merge-blocking.
12. Review comment resolution: wrong repo, foreign PR/thread, unverified/stale fix, open material finding, or arbitrary API mutation rejected.

**W0 verification scope:** `tests/docs/test_docs_consistency.py` and full `tests/docs` via
`.cursor/tools/run-pytest-gate.ps1`. No PostgreSQL live tests. No product builds.

## Evidence, hash, and context-manifest semantics

- Layout: `build/agent-cost-01/<checkpoint>/<unique-attempt>/` — never overwrite prior attempts.
- `checkpoint-contract.md`: frozen goal, scope, allowlist, criteria; SHA256 in journal.
- `context-manifest.json`: package, checkpoint, base HEAD, contract hash, profile version, owner
  file hashes/paths, verification commands, evidence paths — **index only**, not alternate truth.
- Ignored `build/` artifacts are not in the repository fingerprint; hash contract files, JUnit, and
  relevant logs individually in `SHA256SUMS.json`.
- Reuse requires matching verification command, source/test stand, and environment; equal HEAD alone
  is insufficient when diffs are dirty.
- Fields: `configured`, `requested`, hook-observed, and `observed_runtime_*` are distinct. Catalog,
  frontmatter, and hook metadata prove control-plane selection, not serving model, unless D15
  `RUNTIME_ATTESTED` criteria are fully met.
- Token, cache-read/write, reasoning cost, and billing: **`UNKNOWN`** unless host-provided in primary
  evidence. Never use `0` or “cache active” as placeholder.

## Rework budgets, fail-fast, and commit boundaries

Numeric limits remain those in `.cursor/agent-system.json` until W3 activation:

- `max_checkpoint_reworks`: 2
- `max_escalation_reviews`: 1
- `max_final_audit_reworks`: 2
- `max_reviewer_verification_passes`: 1
- `max_plan_challenge_rounds`: 1

Fail-fast: first red gate stops the current sequence; preserve evidence; use bounded rework within
the approved contract without resetting counters via relabeling.

Commit boundaries: one scoped commit per checkpoint after green gates; exact-path staging only;
`git-steward` performs checkpoint/final Git only in `CHECKPOINT_GIT` / `FINAL_GIT` under hook gates.
W0 authorizes only the two tracked doc paths.

## Safe activation boundary

| Phase | Profile effective | Document status |
| --- | --- | --- |
| W0–W2 | `balanced` v2 | PLANNED / NOT ACTIVE |
| W3 pre-merge | `balanced` v2 | PLANNED until explicit W3 activation section |
| Post-W3 merge + documented transition | `cursor-first` v1 | ACTIVE for **new** packages/checkpoints only |

In-flight PILOT00 B1 and any running checkpoint remain on their started profile version and evidence
interpretation. Old PASS evidence stays historically correct.

## Model availability vs runtime attestation

| Evidence type | What it proves | What it does **not** prove |
| --- | --- | --- |
| Account/catalog listing | Slug availability | Serving model, cost, cache |
| Agent frontmatter `model:` | Intended binding | Runtime model |
| `subagent-start` hook match | Control-plane selection metadata | Internal tool-agent billing |
| D15 `CONTROL_PLANE_PINNED` | Full pin checklist for Terra-era reviewer | Runtime model (explicitly forbidden) |
| D15 `RUNTIME_ATTESTED` | Observed model+reasoning match config | N/A when metadata absent |
| External Codex orchestrator review | Independent host decision on bound artifact | Cursor native Terra/Sol execution |

AGENT-COST-01 W1 must add Grok-equivalent D15 successor rules referencing configured roles, not
historical `gpt-5.6-terra` strings, without claiming runtime attestation where metadata is absent.

## W0 completion criteria

- [x] Package contract written (this document)
- [x] P1 index entry added
- [x] W0 evidence bundle under `build/agent-cost-01/w0/<attempt>/`
- [x] `git diff --name-only` shows exactly two tracked paths
- [x] Docs tests green
- [x] Local commit `docs(agent-cost): freeze cursor-first workflow profile`
- [ ] W1 implementation — **NOT RUN**

**End state after W0:** `W0_COMMITTED_READY_FOR_INTERMEDIATE_PACKAGE`. W1 NOT RUN.
