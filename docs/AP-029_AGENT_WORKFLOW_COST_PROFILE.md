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
- **No production activation by W0, W1, or W2.** W1 may install the full `cursor-first` v1
  **candidate** on the isolated AGENT-COST branch for qualification only; `main` and other worktrees
  remain on `balanced` v2 until squash-merge and documented safe transition. W3 qualifies the frozen
  final candidate commit/tree — not a last-minute JSON change after canary or audit.
- **No retrofit** on the paused PILOT00 B1 attempt (`feature/ap-029-pilot00-service-release` at
  `60f4649ed89e195c770558b928ba464de9d1c0e0`). Resume keeps contract revision and
  `rework_count=2`; the first post-resume pilot step remains OCI double-build after resume preflight.

## Goal

Reduce routine GPT usage inside Cursor by routing regular execution and read-only exploration to
Composer 2.5 Standard, routine independent reviews to `grok-4.7-high` with
`runtime_reasoning=high`, and reserving GPT/Codex for critical final audit and exhausted technical
escalation only — without weakening existing authorization, Git, secret, stop, or evidence guards.

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

## Package-local candidate lifecycle and controlstate

### Candidate lifecycle (qualification vs activation)

| Phase | Branch / tree | Profile behavior |
| --- | --- | --- |
| `main` and foreign worktrees | unchanged until merge | `balanced` v2 effective |
| W1 | isolated `feature/cursor-agent-system-v3` | installs **complete** `cursor-first` v1 candidate in tracked allowlisted owners for qualification; does **not** activate for other running packages |
| W2 | same branch | may extend candidate (context manifest, guards, docs); after W2 a **final candidate commit/tree** must be frozen before W3 qualification |
| W3 canary / tests / Codex audit / PR / CI | **same final frozen commit/tree/diff** | no further tracked candidate changes between freeze and audit |
| Post-merge | `main` after squash-merge + documented transition | `cursor-first` v1 effective for **new** packages/checkpoints only |

Rules:

- Any tracked change after the W3 qualification freeze **invalidates** affected canary, audit, CI,
  and merge evidence; gates and audit must rerun on the new frozen stand. **No** unreviewed final
  JSON or owner edit after canary or audit.
- Activation for new packages is **squash-merge into `main` plus documented safe transition**, not
  branch-local qualification alone.
- PILOT00 B1 (`60f4649…`) keeps its started profile and evidence interpretation; no retrofit.

### Controlstate separation (AGENT-COST vs PILOT00)

| State / evidence | AGENT-COST-01 | PILOT00 |
| --- | --- | --- |
| Tracked `.cursor/runtime/workflow-state.json` | **forbidden** (all checkpoints) | out of scope; **do not read/write/copy/invalidate** |
| Local workflow resume | gitignored state **only in this worktree**, bound to TargetRoot / branch / base / contract / profile of AGENT-COST | **not** a resume source |
| Package evidence | `build/agent-cost-01/` only | `build/ap-029-pilot00/` and pilot worktrees — **untouched** |
| Writer | single writer in `QMToolV7-agent-system-v3` | separate worktree; protected |

AGENT-COST must not treat PILOT00 workflow-state, evidence, or worktree as resume input or
invalidation target.

## Owner trace and configuration hardcodes

Normative configuration owner: `.cursor/agent-system.json` (`profile: balanced`, `version: 2`).

Additional hardcoded or mirrored owners that W1 must reconcile to the configuration owner (not
changed in W0):

| Area | Owner path(s) | Notes |
| --- | --- | --- |
| Role frontmatter | `.cursor/agents/<role>.md` | Six GPT-bound roles today; two Composer roles |
| Subagent / Task hook | `.cursor/hooks.json`, `.cursor/hooks/subagent-start.ps1` | `preToolUse` matcher `^Task$` = supported pre-execution cost-control gate; `subagentStart` = lifecycle audit only; model routing is cost control, not a general security boundary (Git/file/secret/permission guards stay separate) |
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
| checkpoint-reviewer, plan-challenger, external-review-triager | Cursor native subagent | Ladder attempt 1 `grok-4.7-high` → `cursor-grok-4.6-xhigh` → `cursor-grok-4.6-high` → `gpt-5.6-terra-high` after explicit prior `UNAVAILABLE` only | Independent read-only context; no self-approval; evidenced ladder only |
| roadmap-architect (in-package planning/final audit) | Cursor native | Same ladder shape ending with `gpt-5.6-sol-high` after explicit prior `UNAVAILABLE` only | Fresh final audit context for normal packages |
| Critical final audit / exhausted escalation | External Codex/ChatGPT-authenticated orchestrator | **Not a Cursor model ID** | Agent-ID, separate context, contract, full diff, primary evidence; Cursor GPT only after ladder exhaustion, then external Codex if Cursor GPT unavailable |
| User/orchestrator product decisions | Human + external orchestrator | N/A | No second live detail controller of the same Cursor checkpoint |

External orchestrator responsibilities: goal clarification, architecture decisions, package release,
and critical GPT audit. It must not approve a diff it implemented. It is **not** `gpt-5.6-sol`,
`gpt-5.6-terra`, `RUNTIME_ATTESTED`, or `CONTROL_PLANE_PINNED`.

Catalog presence of configured ladder models and Fast/Auto variants is **availability metadata only**. Token, cost, cache, and actual serving
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
| R-COST-04 | `grok-4.7-high` with `runtime_reasoning=high` for routine reviews | Role matrix § | W1 agents + hook tests |
| R-COST-05 | Critical GPT audit via external Codex host | Host boundaries § | W1 handoff contract |
| R-COST-06 | No false runtime/cost/cache claims | § Evidence semantics | W2 metrics, W3 canary |
| R-COST-07 | D15 successor without silent Terra/Sol claims | D15 reference § | W1 tests + docs |
| R-COST-08 | PILOT00 isolation / no retrofit | Basis table § | All checkpoints |
| R-COST-09 | 12 verification cases in real owner tests | § Verification contract | W1–W3 tests |
| R-COST-10 | Safe activation only after W3 + Codex audit + merge | § Candidate lifecycle | W3 only |
| R-COST-17 | W3 qualifies frozen candidate; no post-canary JSON edit | § Candidate lifecycle | W1–W3 |
| R-COST-18 | Exact finite W2/W3 allowlists | § Allowlists | W0 contract |
| R-COST-19 | AGENT-COST controlstate isolated from PILOT00 | § Controlstate | All checkpoints |

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
| Post-canary candidate drift | W3 freeze + invalidation rule | W3 report, contract § lifecycle |
| PILOT00 state bleed | Controlstate separation | § Controlstate, W0 evidence |

## Package integration scenario

**Scenario:** After W3 PASS, a new MEDIUM-risk docs-only package starts on `main` post-merge.

1. Coordinator launches with explicit Composer 2.5 Standard via updated launcher (W1).
2. Implementer edits only allowlisted docs; checkpoint-reviewer runs as `grok-4.7-high` with
   `runtime_reasoning=high` in a separate context with contract-bound diff review (W1).
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

**W0 rework:** `rework_count=2` after this round (round 1: attempt 002; round 2: attempt 003). Counters
are not reset by relabeling.

**W1 start condition:** W0 complete with independent read-only reviewer **PASS** on contract commit
`2f577327…` (contract SHA `A3C07ED5…B213DE`). **Met.** One bounded scope correction consumed before
implementation (see § Plan challenge).

### Plan challenge and scope correction (W1)

| Field | Value |
| --- | --- |
| Challenger ID | `/root/agent_cost_w1_challenge` |
| Mode | read-only |
| Verdict | `PLAN_REVISION_REQUIRED` |
| Scope corrections | **1 of 1 consumed** |
| Correction | Add `.cursor/skills/execute-work-package/SKILL.md` as 19th W1 path (lifecycle owner for package resume/execute) |
| W0 R2 review | PASS on `2f577327…` / contract `A3C07ED5…B213DE` |

No further scope expansion permitted in W1.

### W1 capability/process-hygiene correction (separate authorization)

| Field | Value |
| --- | --- |
| Checkpoint | `W1-CAPABILITY-PROCESS-HYGIENE` |
| Authorization | Bounded hygiene correction only; **not** W1 activation or readiness |
| Scope correction | Add `.cursor/tools/run-pytest-gate.ps1` as 20th W1 path (JUnit gate owner) |
| Preserved counters | `rework_count=2/2` and `exceptional_recovery=1/1` — **not reset** |
| Evidence root | `build/agent-cost-01/w1/w1-capability-process-hygiene-001/` |
| Status | Hygiene edits allowed; **W1 remains blocked** pending fresh evidence and independent review |

Historical exceptional-recovery evidence and its finalizer under
`build/agent-cost-01/w1/w1-exceptional-recovery-001/` remain read-only history. A future fresh
finalizer must consume the gate-runner exit code as owner truth; do not overwrite or rerun that
attempt.

### W1 corrective writer authorization (hooks matcher)

| Field | Value |
| --- | --- |
| Checkpoint | `W1-CORRECTIVE-WRITER` |
| Authorization | Bounded corrective writer only; **not** activation or readiness |
| Scope correction | Add `.cursor/hooks.json` as 21st W1 path (case-sensitive `beforeShellExecution` matcher owner) |
| Preserved counters | `rework_count=2/2` and `exceptional_recovery=1/1` — **not reset** |
| Status | Corrective edits allowed; **W1 remains blocked** pending fresh evidence and independent review |

### W1 — Cursor-first routing (full, test-protected)

**Tracked allowlist (exact 21 paths):**

- `.cursor/agent-system.json`
- `.cursor/agents/roadmap-architect.md`
- `.cursor/agents/checkpoint-reviewer.md`
- `.cursor/agents/plan-challenger.md`
- `.cursor/agents/external-review-triager.md`
- `.cursor/agents/escalation-reviewer.md`
- `.cursor/agents/git-steward.md`
- `.cursor/hooks.json`
- `.cursor/hooks/subagent-start.ps1`
- `.cursor/tools/invoke-cursor-agent.ps1`
- `.cursor/tools/run-pytest-gate.ps1`
- `.cursor/skills/apply-agent-profile/SKILL.md`
- `.cursor/skills/execute-gated-macro/SKILL.md`
- `.cursor/skills/execute-gated-macro/references/checkpoint-protocol.md`
- `.cursor/skills/execute-work-package/SKILL.md`
- `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md`
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
- `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md`
- `tests/docs/test_cursor_agent_system.py`
- `tests/docs/test_cursor_macro_workflow.py`
- `tests/docs/test_cursor_execution_hygiene.py`

**Must define:** Fail-closed external Codex orchestrator review authority for this package (agent,
target, contract, diff binding) — not a reuse of PILOT00 `INDEPENDENT_ORCHESTRATOR_REVIEW` without
new contract fields.

**Gate:** Targeted docs tests + native Grok/Composer smoke + synthetic hook tests.

**Candidate install:** W1 produces the complete `cursor-first` v1 candidate on this branch (including
`.cursor/agent-system.json` and bound owners). This is qualification material, not activation on
`main` or for foreign packages.

**W1 implementation status:** scope committed (`0213f23…`); implementation prepared uncommitted for
external Codex review (`READY_FOR_EXTERNAL_CODEX_W1_REVIEW`). Native smokes and gate evidence under
`build/agent-cost-01/w1/w1-implementation-001/`. After bounded hygiene correction
(`W1-CAPABILITY-PROCESS-HYGIENE`), W1 remains **blocked** pending fresh evidence/review;
`rework_count=2/2` and `exceptional_recovery=1/1` are preserved and not reset by hygiene work.

**W1 successor recovery (2026-09-29):** User authorized one bounded successor-recovery package with
`successor_recovery_authorized=true` and `successor_recovery_attempt=1/1`. Historical counters remain
unchanged (`rework_count=2/2`, `exceptional_recovery=1/1`). Tracked repair scope is exactly eight
owners: `.cursor/agent-system.json`, `.cursor/hooks/subagent-start.ps1`,
`.cursor/skills/execute-work-package/SKILL.md`, `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md`,
`docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`, `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md`,
`tests/docs/test_cursor_agent_system.py`, `tests/docs/test_cursor_macro_workflow.py`. Evidence under
`build/agent-cost-01/w1/w1-successor-recovery-001/`. **Native hook observation (historical failed
probe; preserved):** on Cursor IDE 3.22.7, native Task `tool_7410bc54-7779-4757-a0e5-bfc17a606db`
received valid `subagentStart` deny (exit 2, `blocked action`) twice yet still created child
`8c77cf5c-8a57-4557-8f53-21d719d5a1c3`; `subagentStart` must not be claimed as a proven hard spawn
blocker. The supported pre-execution cost-control gate is `preToolUse` with matcher `^Task$` (same
`subagent-start.ps1` owner; `subagentStart` retained as second lifecycle audit). Model routing is
cost control only; Git, file, secret, and permission guards remain separate and unchanged. This
repair does not claim activation, total W1 completion, cost savings, cache behavior, or runtime model
observation; W2 and W3 remain.

### W2 — Context handoffs, reuse, measurability

**Tracked allowlist (exact finite maximal list; no inheritance, no globs):**

- `.cursor/skills/execute-work-package/SKILL.md`
- `.cursor/skills/execute-gated-macro/SKILL.md`
- `.cursor/skills/execute-gated-macro/references/checkpoint-protocol.md`
- `.cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py`
- `.cursor/skills/verify-reports-and-plan/SKILL.md`
- `.cursor/skills/verify-reports-and-plan/references/evidence-and-prompt-patterns.md`
- `.cursor/skills/qmtool-module-development/SKILL.md`
- `.cursor/skills/qmtool-module-development/references/independent-codex-review.md`
- `.cursor/hooks/git-guard.ps1`
- `.cursor/hooks/session-start.ps1`
- `.cursor/hooks/workflow-watchdog.ps1`
- `.cursor/runtime/README.md`
- `.cursor/runtime/workflow-state.template.json`
- `.cursor/reviews/README.md`
- `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md`
- `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md`
- `tests/docs/test_cursor_agent_system.py`
- `tests/docs/test_cursor_execution_hygiene.py`
- `tests/docs/test_cursor_macro_workflow.py`
- `tests/docs/test_docs_consistency.py`

Paths in this maximal list that W2 does not need remain **unmodified**; the W2 report names unused
optional paths explicitly. If GitHub review-thread mutation guard cannot be implemented safely:
report capability gap; do not disable gates or set `DISABLED` without replacement tests.

After W2, freeze the **final candidate commit/tree** before any W3 qualification step.

### W3 — Qualification, publication, safe activation

**Tracked allowlist (exact finite union of W1 + W2 paths plus publication docs; no wildcards):**

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
- `.cursor/skills/execute-work-package/SKILL.md`
- `.cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py`
- `.cursor/skills/verify-reports-and-plan/SKILL.md`
- `.cursor/skills/verify-reports-and-plan/references/evidence-and-prompt-patterns.md`
- `.cursor/skills/qmtool-module-development/SKILL.md`
- `.cursor/skills/qmtool-module-development/references/independent-codex-review.md`
- `.cursor/hooks/git-guard.ps1`
- `.cursor/hooks/session-start.ps1`
- `.cursor/hooks/workflow-watchdog.ps1`
- `.cursor/runtime/README.md`
- `.cursor/runtime/workflow-state.template.json`
- `.cursor/reviews/README.md`
- `docs/AP-029_AGENT_WORKFLOW_COST_PROFILE.md`
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
- `docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md`
- `docs/DOCS_CANONICAL_INDEX.md`
- `docs/MASTER_ORCHESTRATION_ROADMAP.md`
- `tests/docs/test_cursor_agent_system.py`
- `tests/docs/test_cursor_macro_workflow.py`
- `tests/docs/test_cursor_execution_hygiene.py`
- `tests/docs/test_docs_consistency.py`

No further tracked paths. Unused maximal-list paths stay untouched; W3 report names them.

**Gates:** Full `tests/docs` serial green on the **frozen final candidate** commit/tree; representative
native canary; independent critical Codex final audit PASS on the **same** commit/tree/diff; CI on
PR; policy-compliant merge only under explicit package authorization.

**Qualification vs activation:** W3 proves the frozen candidate already installed through W1/W2.
Canary, deterministic tests, Codex final audit, push, PR, and CI all target that same frozen stand.
**Activation** for new packages is squash-merge into `main` plus documented safe transition — not an
extra unreviewed `.cursor/agent-system.json` edit after audit. Running attempts and PILOT00 B1 stay
on their prior profile version.

### Global exclusions (all checkpoints)

- Product modules, `src/backend/*` (except if a test-only import path is already in docs tests),
  `webclient/*`, PostgreSQL migrations, packaging, service host, pilot Linux artifacts
- Tracked edits to `.cursor/runtime/workflow-state.json` (gitignored live state)
- PILOT00 workflow-state, evidence, worktree `ap-029-pilot00-service-release`, and its commits —
  no read-as-resume, write, copy, or invalidation from AGENT-COST
- New parallel roadmap, runner, cache, or API credential bridge
- Blanket `git add .`; only explicit allowlist paths per checkpoint

## Verification contract — 12 mandatory cases

Cases 1–12 must be enforced in **real owner tests** (primarily `tests/docs/*` and hooks), not only
in copied validator logic. W0 documents them; W1–W3 implement and prove them.

1. Configuration, agent frontmatter, invocation, and required model parameters agree.
2. `grok-4.7-high` with `runtime_reasoning=high` allowed; Fast, wrong effort, unknown variants,
   and expensive fallback rejected.
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

W0 checkpoint rework: **`rework_count=2`** after this round (attempts 002 and 003). Not reset.

Numeric limits remain those in `.cursor/agent-system.json` until merge activation:

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

| Phase | `main` / foreign worktrees | AGENT-COST branch candidate | Document status |
| --- | --- | --- | --- |
| W0–W2 | `balanced` v2 | W1+ installs/extends `cursor-first` v1 candidate (qualification only) | PLANNED / NOT ACTIVE |
| W3 pre-merge | `balanced` v2 | frozen final candidate under test/audit | PLANNED until merge |
| Post-squash-merge + documented transition | `cursor-first` v1 | merged into `main` | ACTIVE for **new** packages only |

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
- [x] P1 index entry added (commit `61f0f44…`)
- [x] W0 evidence attempts under `build/agent-cost-01/w0/<attempt>/`
- [x] Candidate lifecycle, exact W2/W3 allowlists, controlstate separation documented
- [x] `rework_count=2` recorded honestly
- [ ] Independent W0 review R2 PASS on post-rework contract
- [ ] W1 implementation — **NOT RUN**

**End state after this rework commit:** `READY_FOR_INDEPENDENT_W0_REVIEW_R2`. W1 NOT RUN until
independent reviewer PASS on the new contract commit.
