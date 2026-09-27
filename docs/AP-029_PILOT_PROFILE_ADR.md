# ADR: limited pilot profile `linux-rootless-synthetic`

Status: Accepted for PILOT00 only (not P0, not a qualification PASS)
Decision status: `ACCEPTED_LIMITED`
Historical decision status at 2026-09-26: `PROPOSED / HUMAN_DECISION_REQUIRED`
Accepted on: 2026-09-27
Acceptance source: `Orchestrator_Autonomer_Pilotauftrag_20260927.md`
Acceptance package: `PILOT00-AUTONOMY-AMENDMENT`
Valid as proposal from: 2026-09-26
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
Preparation owner: `docs/AP-029_PILOT00_LINUX_PREPARATION.md`
Supersedes nothing in the production operations decision.

P0 operations still say Windows Server first. This file does not amend that
decision. It records one additional, bounded PILOT00 profile. The historical
proposal text below is kept. Acceptance is not a Windows, pilot, or deployment PASS.

## Context

PILOT00 is the current checkpoint and remains `TODO / NOT RUN`. The existing
unversioned package `build/ap-029-pilot00/PILOT00_WORK_PACKAGE.md` is a Windows
SCM/ACL/reboot contract in status `READY_FOR_HUMAN_ENVIRONMENT_FREEZE`. Its
SHA256 at planning start `8fa8d0a7f6957ef7f532560ed35826b9f9a7be29` is
`48EBFE9F4170EC93B60E807F953133463EFD8747CDD118EB4D8866DB99F0CE8D`. That file
stays unchanged.

Later user direction is a synthetic PDF-first browser pilot on an already
prepared Ubuntu 24.04 rootless Docker host (`servinglunatix`, LAN
`192.168.0.4`), not a new Windows VM. That direction is a profile change. The
completed SSH and rootless setup is infrastructure evidence. It is not
architecture acceptance, not deployment, and not a PILOT00 PASS.

Verified code gaps that any accepted profile still has to close are recorded in
the preparation owner: platform settings still open SQLite at backend start,
sealed backups do not cover signature assets or the signature master key, and
there is no qualified Linux release or pilot target guard.

## Decision

Add a bounded profile id `linux-rootless-synthetic` for PILOT00 only.
The 2026-09-27 macro accepts that addition for the named PILOT00 sequence.
Historical status remains `PROPOSED / HUMAN_DECISION_REQUIRED` and is not relabeled as a PASS.

On acceptance:

- The pilot client stays the existing webclient. PostgreSQL stays the only
  productive datastore. Data stays synthetic and greenfield. PDF-first stays.
  CONV00, PyQt, Kubernetes, a new VM, and a new agent platform stay out of the
  pilot.
- Windows Server remains the decided production option in
  `docs/OPERATIONS_CANONICAL.md`. Its SCM, ACL, certificate-store, and reboot
  gates stay `NOT RUN`. They are not relabeled as passed.
- A Linux result qualifies only `linux-rootless-synthetic`. It is not a Windows readiness PASS, and a Windows PASS would not be a Linux PASS.
- The Windows SCM adapter is replaced, for this profile only, by an explicit
  container/service contract around the existing `python -m src.backend`
  owner. No second server is introduced.
- Package order stays: signature recovery before the target recovery adapter;
  settings cutover, B-BUILD, signature recovery, and the target recovery
  adapter before E. B-RUNTIME (real process, SIGTERM, drain, marker, locks,
  restart, recreate, TLS, and license) is mandatory inside E and is not a
  waiver. Build-only release checks are not target qualification.
- External module calls from new operator or test adapters stay on
  `modules/<name>/api.py`. No runtime DDL, no dual-write, and no SQLite
  product fallback.

Historical rejection path, not the current decision: a rejection would have
left PILOT00 on the unchanged Windows package. The rootless host would have
stayed an unused precondition, not a failed Windows gate.

## Consequences

Acceptance is recorded by `PILOT00-AUTONOMY-AMENDMENT` and is limited to
PILOT00. It does not change Windows Server first, does not pass Windows SCM,
ACL, certificate-store, or reboot gates, and does not pass PILOT00.

The unchanged Windows package remains the production-option contract.
Rejecting this profile later would block further Linux implementation and
would not fail a Windows gate. That rejection is not the current decision.

Either outcome leaves PILOT01 blocked until PILOT00 has passed and a separate
human live-data decision exists.

## Non-decisions

This proposal does not choose the LAN name, TLS termination, license file,
backup location, tester names, RPO/RTO, or screenreader tool. Those stay in
the preparation owner with their own latest safe gates.
