# PILOT00 Linux preparation

Status: Planning document (P1). Not a pilot qualification.
Package: `PILOT00-LINUX-PLAN`
Profile proposal: `linux-rootless-synthetic` in `docs/AP-029_PILOT_PROFILE_ADR.md`
Current checkpoint: PILOT00, unchanged, `TODO / NOT RUN`
Planning base: `8fa8d0a7f6957ef7f532560ed35826b9f9a7be29`
Unchanged Windows package SHA256: `48EBFE9F4170EC93B60E807F953133463EFD8747CDD118EB4D8866DB99F0CE8D`
Historical blocker evidence, preserved and not rewritten: `build/ap-029-pilot00/linux-plan/20260926T211200Z/`

This document is the versioned preparation owner. It does not deploy, qualify,
or start PILOT01. P0 wins where this plan proposes a change. The Linux profile
stays `PROPOSED / HUMAN_DECISION_REQUIRED`.

<!-- PILOT00_LINUX_CONTROL_START -->
active_preparation: PILOT00-LINUX-PLAN
preparation_status: PLAN_DOCS_LOCAL
deployment_status: NOT RUN
formal_pilot_status: NOT RUN
current_checkpoint: PILOT00
current_checkpoint_count: 1
windows_scm_status: NOT RUN
linux_profile_status: PROPOSED
linux_profile_decision: HUMAN_DECISION_REQUIRED
slot2_lab_bypass: forbidden
automatic_pilot01: forbidden
settings_pg_blocks_pilot: true
signature_recovery_blocks_pilot: true
target_recovery_blocks_pilot: true
package_order: C before D; A-D before E
dual_write: forbidden
runtime_ddl: forbidden
sqlite_product_fallback: forbidden
external_module_calls: modules/<name>/api.py
ux_d37: accepted-limited
accessibility_smoke: included
accessibility_evidence: NOT RUN
greenfield: required
synthetic_data: required
first_password_change: required
signature_identity: own-authentication
recommendations_are_approvals: false
rootless_setup_is_deployment: false
closeout_verdicts: TECHNICAL_PASS, SECURITY_REVIEW_PASS, ARCHITECTURE_REVIEW_PASS, HUMAN_ACCEPTANCE_PASS
closeout_evidence: NOT RUN
human_recovery_required: true
git_approval: separate
remote_approval: separate
phase_approval: separate
plan_challenge_status: UNAVAILABLE
roadmap_architect_status: UNAVAILABLE
native_role_pass: not-claimed
control_plane_pinned: false
runtime_attested: false
codex_plan_review: HUMAN_AUTHORIZED_INDEPENDENT_CODEX_PLAN_REVIEW
<!-- PILOT00_LINUX_CONTROL_END -->

## Disposition of this planning run

`[ROLE:roadmap-architect]` on the configured Sol model and `[ROLE:plan-challenger]`
on the configured Terra model are `UNAVAILABLE` because of quota. This run does
not retry them. It does not claim a native role PASS, `CONTROL_PLANE_PINNED`,
or `RUNTIME_ATTESTED`. Configuration in `.cursor/agent-system.json` is not
runtime attestation.

Two separate read-only Codex audits are recorded as
`HUMAN_AUTHORIZED_INDEPENDENT_CODEX_PLAN_REVIEW`. They are not native Cursor
role verdicts. Their incorporated result is: the package is executable as a
plan; Linux stays `PROPOSED / HUMAN_DECISION_REQUIRED`; Q02 has no evidenced
person and stays `OPEN`; no password manager is assumed; Q01–Q32 are mapped
including subpoints; UX-D37 and the accessibility smoke are already decided;
packages A–E stay in the order C before D and A–D before E; new external module
calls use only `modules/<name>/api.py`; runtime DDL, dual-write, and SQLite
product fallback stay forbidden. No further reviewer or challenger substitute
is executed in this run.

Final-audit rework 1 records the verified settings callgraph, keeps decided
mandatory scope on `DECIDED` with evidence `NOT RUN`, adds the three decision
blocks, and adds the still unauthorized A–E follow-up order. Native Sol and
Terra stay `UNAVAILABLE`. This rework does not attest them.

The one available-context closing review is a read-only diff review by the
writer session after the docs gates. It is not a Terra or Sol PASS. Its
fingerprint is stored under this run's evidence directory when the gates are
green.

Risk class of the preparation package: HIGH. Requirement traceability is the
Q01–Q32 matrix below plus the P0 documents it cites. Risk-to-evidence is the
matrix in the package section. The package integration scenario is specified
and `NOT RUN`. Plan challenge status is `UNAVAILABLE`, not PASS. Product
checkpoints stay unstarted until the three decision blocks at the end of
this document are answered. After those answers, the copyable follow-up order
is the serial authorization and does not ask the answered questions again.
That order is still `NICHT AUTORISIERT` in this file. Linux stays
`PROPOSED / HUMAN_DECISION_REQUIRED` until block 1 is answered.

## What remains decided

- PDF-first, greenfield, synthetic data, webclient, PostgreSQL-only.
- No live data and no legacy takeover before PILOT00 PASS and a separate PILOT01 decision.
- No new PyQt product work. CONV00 does not block the pilot.
- Functional account names. Admin is not automatically QMB. Document creation needs QMB or delegated document rights.
- Own authentication and reauthentication for every signature. No shared real-person accounts and no password handoff.
- Initial credentials stay outside Git and evidence. `must_change_password=true`, first change, and session revocation on reset stay mandatory.
- UX-D37 "Unbekannter Autor" is accepted for this limited pilot, with follow-up. Technical ids are not author names. This is not a global UX acceptance.
- A representative accessibility and screenreader smoke is in scope. Tool, browser, and tester are still open. Automated checks do not replace a human screenreader pass or a conformance certificate.
- The Windows VM and repository-plus-venv release form are historical decisions for the old profile. They are not silently reused as the Linux contract.
- Q25 is the complete fachliche Human-Smoke. Every step is in scope. Its evidence stays `NOT RUN`.
- Open HIGH or CRITICAL security findings block the pilot. That gate is decided. The review itself is `NOT RUN`.
- Q30 evidence fields are mandatory. Captured values stay `NOT RUN`.
- A sealed backup includes the PostgreSQL dump, blob inventory, release identity, schema identity, and checksum manifest. That content is decided. The proof is `NOT RUN`.
- Public recovery is one public operator command, with target guards and the mandatory negative checks. Q02 names no person, and Q14-17 names no recovery operator.

## What is only recommended

These values are not user approvals: a short campaign of about two weeks, a
small tester group, 10–20 synthetic PDFs, seven daily and two weekly backup
generations, 24h RPO and 4h RTO, Node 24 as the preferred build LTS, the name
`qmtool-pilot.lunatix.me`, and bundling technical operator duties. Node 20 is
EOL and Node 22 is also LTS on the nodejs.org previous-releases page read on
2026-09-26. Node 24 is the preferred proposal, not a pin.

## Infrastructure precondition, not deployment

Already verified and not to be provisioned again: Ubuntu 24.04.4 LTS on
`servinglunatix` at `192.168.0.4`; user `qmtool-deploy` UID/GID 1004 without
`/var/run/docker.sock`; rootless Docker 27.3.1 and Compose 2.29.7 on
`unix:///run/user/1004/docker.sock`, linger enabled, no reboot proof; data root
`/mnt/md0/agents/qmtool-pilot` on ext4 RAID0 `/dev/md0` with filesystem UUID
`b1b8155d-fccd-48e0-982f-159ba5aafbcb`. At the end of that access setup there
were 0 images and 0 containers. cgroup cpu, memory, and pids controllers exist.
Qualified IO throttling does not. A second directory on the same RAID0 is not
an off-disk backup. This evidence is not PILOT00 acceptance.

`192.168.0.4` is also the protected runtime/lab host. The new rootless cluster
is not a Slot-2 target. The destructive guard does not gain a host-wide
exception.

## Verified code gaps at the planning base

Settings. Both current SQLite opens belong to the backend host and share one
owner. Verified at this planning base, not assumed.
`src/backend/bootstrap.py` `build_backend_container` calls
`wire_backend_usermanagement` and then `wire_backend_documents` on the same
lifecycle.

Path 1. `qm_platform/runtime/backend_bootstrap.py`
`wire_backend_usermanagement` calls `_force_hardened_usermanagement_settings`.
That function migrates only `PLATFORM_SETTINGS_DATABASE_CONTRIBUTION` through
`DatabaseEvolutionService.migrate` with reason `backend_platform_settings`,
using `resolve_platform_settings_db_path`. It then calls
`attach_settings_persistence` in
`qm_platform/settings/persistence_bootstrap.py`, which constructs
`SqliteSettingsRepository` and attaches it to the one `settings_service`.
The hardened Usermanagement seed is written through that service.

Path 2. `wire_backend_documents` always puts the same
`PLATFORM_SETTINGS_DATABASE_CONTRIBUTION` in its contribution tuple. `_spec_for`
resolves that database id with `resolve_platform_settings_db_path` again.
`evolution.migrate` then runs with reason `backend_documents`. This second
call does not call `attach_settings_persistence`. PostgreSQL DSNs remove the
registry, documents, and signature SQLite contributions from that migrate.
They do not remove `platform_settings`.

Shared owners: `qm_platform/persistence/platform_settings_contribution.py`;
`resolve_platform_settings_db_path` (`storage/platform/platform_settings.db`,
or `QMTOOL_DB_PLATFORM_SETTINGS_PATH`); `SqliteSettingsRepository`; and the
single `settings_service` from `build_platform_ports`.
`qm_platform/settings/settings_cutover.py` `ensure_settings_residual_ready`
runs from `attach_settings_persistence` and reads SQLite integrity keys.
`qm_platform/persistence/database_evolution.py` also opens
`SqliteSettingsRepository` for residual backup checks. PostgreSQL tables
`platform.platform_settings` and `platform.platform_settings_integrity` already
exist as SQL under `qm_platform/persistence/postgres/migrations/`. No
PostgreSQL settings repository class exists. Historical PG00 PASS stays.

Lifecycle and shutdown at this base. Each wire function calls
`LifecycleManager.start(strict=True)`. `LifecycleManager.stop` stops started
modules in reverse order and does not close settings.
`SqliteSettingsRepository` opens one connection per call and closes it with
`contextlib.closing`. It has no shutdown method. `ServiceHost.stop` drains
requests, stops the server, and removes the host-running marker. It does not
call `LifecycleManager.stop`.

Profile separation. The backend host profile is `build_backend_container`
with `QMTOOL_RUNTIME_PROFILE` `prod` or `production`, read by
`is_production_profile` in `src/backend/service_host.py`. The desktop core
profile is `qm_platform/runtime/bootstrap.py` `activate_core_modules`. That
function also migrates `PLATFORM_SETTINGS_DATABASE_CONTRIBUTION` and calls
`attach_settings_persistence`, and `prepare_core_modules` selects contracts
with `client_runtime_profile` (`backend` or `legacy`). Package A changes only
the backend host path. It does not attach SQLite and PostgreSQL together, and
it does not edit the desktop bootstrap. The open runtime cutover is package A.

Signature backup. `modules/signature/wiring.py` builds
`EncryptedSignatureBlobStore` for the signature assets root and master key from
`modules/signature/module.py`. `EncryptedSignatureBlobStore._load_or_create_key`
creates a new key when the file is missing. `qm_platform/blob/backup_orchestrator.py`
`create_backup` seals the database and `storage/platform/blobs`. It does not
inventory signature assets or the master key. Restore of those assets is not
proven. `modules/signature/api.py` has no recovery method. Package C must add
the smallest public recovery contract there, or a port registered by signature
wiring. Platform code and new operator adapters must not import signature
internals.

Service release. `requirements.txt` unconditionally requires `pywin32`. The
Python contract stays `>=3.14,<3.15`. `webclient/package.json` and
`webclient/.nvmrc` pin Node 20, which is EOL. There is no current product
backend Dockerfile. `tests/postgres/compose.yaml` is not a pilot installer.
`ServiceHost.run_forever` handles `KeyboardInterrupt` and then `stop`; Docker
SIGTERM, drain, host marker, operation lock, and controlled stop still need a
real-process proof on that same host. `qm_platform/licensing/machine_id.py`
falls back to the MAC node id off Windows. Container recreate can change that
id. License checks are not bypassed and licenses are not silently generated.
`docs/LICENSE_SPEC.md` says the base license is not an application start
blocker. `build_platform_ports(fail_closed_license=True)` requires
`QMTOOL_LICENSE_MODE` and aborts when a non-dev mode fails validation, and it
rejects `dev`/`auto` when the runtime profile is production. That conflict
stays open. This plan does not change license policy.

Usermanagement `ensure_postgres_schema_ready` verifies schema and does not
apply migrations. Package E keeps migration as an explicit operator step.
Package A adds no runtime DDL.

Target recovery. `PILOT00-TARGET-RECOVERY-ADAPTER` stays mandatory before
target mutation. It is not optional and not replaced by inline calls to
`restore_backup_set`. Slot-2 live evidence is not a pilot proof.

## Section I — plan, profile, and one approval package

The active preparation package inside PILOT00 is `PILOT00-LINUX-PLAN`.
Its status is local planning. It is not deployment and not formal pilot
approval. PILOT00 stays the only current checkpoint. A Linux proposal and the
Windows history do not count as each other's PASS.

The earliest browser test is a synthetic functional proof of the real DMS. It
does not replace restore, security, or human gates.

## Section II — preparation packages

Order: C before D. A, B, C, and D before a durable pilot instance. B may be
qualified build-only earlier. No backend start on the home server is a shortcut
around this order.

Budgets for a later execution come from `.cursor/agent-system.json` at that
time. This plan does not create new budgets. Current defaults used for the
contract text: two checkpoint reworks, one escalation review, one reviewer
verification pass, one scope-correction round. Destructive target actions need
a later approved procedure with target binding and a run budget. Nondestructive
local tests of an approved package do not need a fresh micro-approval.
Resource note: do not claim IO isolation. CPU, memory, and pids controllers
exist; no qualified IO controller was evidenced.

### A. PILOT00-SETTINGS-PG

Owner: the one platform settings persistence used by the backend host.
Callgraph verified by reading the files at
`8fa8d0a7f6957ef7f532560ed35826b9f9a7be29`.

Both bootstrap paths, shared owners. `src/backend/bootstrap.py`
`build_backend_container` calls `wire_backend_usermanagement` and then
`wire_backend_documents` on one lifecycle. Path 1 is
`_force_hardened_usermanagement_settings`: `migrate` reason
`backend_platform_settings`, then `attach_settings_persistence`. Path 2 is
`wire_backend_documents`: `PLATFORM_SETTINGS_DATABASE_CONTRIBUTION` inside
`evolution.migrate` reason `backend_documents`, and no second attach.
Shared contribution:
`qm_platform/persistence/platform_settings_contribution.py`. Shared path:
`resolve_platform_settings_db_path`. Shared repository today:
`SqliteSettingsRepository`, constructed in `attach_settings_persistence`.
Shared service: the one `settings_service`. `settings_cutover.py` and
`database_evolution.py` also read that SQLite file. PostgreSQL schema files
already present, and not applied as runtime DDL:
`qm_platform/persistence/postgres/migrations/0001_platform_settings.sql` and
`0002_platform_settings_integrity.sql`.

Lifecycle. `LifecycleManager.start(strict=True)` runs on the shared lifecycle.
`LifecycleManager.stop` does not close settings. `ServiceHost.stop` does not
call it. The SQLite repository holds no connection across calls. The
PostgreSQL replacement must not add a long-lived second writer. Editing
`src/backend/service_host.py` or `qm_platform/runtime/bootstrap.py` is
`SCOPE_EXPANSION` for this package: the first file is the service-release
owner, and the second is the desktop profile.

Profile separation. Backend host versus desktop `activate_core_modules` and
`client_runtime_profile`. Package A does not mix those profiles and does not
dual-write.

Exact allowlist. Frozen for the first executable checkpoint. This list is not
provisional.

- `src/backend/bootstrap.py`
- `qm_platform/runtime/backend_bootstrap.py`
- `qm_platform/settings/persistence_bootstrap.py`
- `qm_platform/settings/settings_service.py`
- `qm_platform/settings/settings_cutover.py`
- `qm_platform/settings/sqlite_settings_repository.py`
- `qm_platform/settings/postgres_settings_repository.py` (absent at this base; the only new file; it replaces the SQLite repository on the backend profile behind the existing `SettingsService`)
- `qm_platform/persistence/platform_settings_contribution.py`
- `qm_platform/persistence/path_resolver.py`
- `qm_platform/persistence/database_evolution.py`
- `tests/platform/test_core_database_migrations.py`
- `tests/platform/test_settings_cutover.py`
- `tests/platform/test_settings_governance_enforcement.py`
- `tests/platform/test_postgres_schema_static.py`
- `tests/platform/test_postgres_schema_live.py`
- `tests/backend/test_documents_http_api.py`
- `tests/backend/test_postgres_backend_bootstrap_live.py`

Read-only in package A, not writable: the four existing settings SQL files,
`qm_platform/runtime/lifecycle.py`, `qm_platform/runtime/bootstrap.py`,
`qm_platform/runtime/client_runtime_profile.py`, `src/backend/service_host.py`,
and `modules/usermanagement/api.py`.

No parallel settings path. No dual-write. No runtime DDL. No new module API.
External calls stay on `modules/<name>/api.py`.

Acceptance, all currently `NOT RUN`: a fresh empty home on the backend profile
does not open SQLite and does not create `platform_settings.db` from either
bootstrap path; both paths use one repository; restart still reads the same
PostgreSQL settings; stop leaves no second writer; the desktop
`activate_core_modules` profile is unchanged; defaults, governance, revisions,
actor and audit, locks, and organization boundaries survive; PostgreSQL outage
fails closed; legacy import only as a separate read-only path. Local
nondestructive tests are not the later isolated PostgreSQL proof.

Existing test owners and commands. Run them serially, with a project-local
temp and a fresh basetemp. Static command first:

`.\.venv\Scripts\python.exe -m pytest tests/platform/test_core_database_migrations.py tests/platform/test_settings_cutover.py tests/platform/test_settings_governance_enforcement.py tests/platform/test_postgres_schema_static.py tests/backend/test_documents_http_api.py::test_wire_backend_documents_registers_documents_sqlite_owner -q -p no:cacheprovider --basetemp build/pt/pilot00-settings-pg-<stamp>`

PostgreSQL live only through the guarded runner, and only after the static
command is green:

`.\.venv\Scripts\python.exe scripts/run_postgres_live_tests.py tests/platform/test_postgres_schema_live.py tests/backend/test_postgres_backend_bootstrap_live.py`

Evidence directory for that later run:
`build/ap-029-pilot00/settings-pg/<utc-stamp>/`.
Review gate: one fresh independent reviewer. The implementer cannot grant
`PASS`. Rework budget is the configured two checkpoint reworks, then one
escalation review. One scope-correction round, and only for an existing owner
omitted from this allowlist. Anything else is `SCOPE_EXPANSION` and stops
before the edit. Local commit boundary: one commit of this exact allowlist
after reviewer `PASS`, on the package branch, never on `main`. The first red
static or live gate stops the checkpoint. `SCOPE_CORRECTION_REQUIRED` is the
stop before any edit outside the allowlist.

HIGH risk: silent SQLite fallback. Evidence: the fresh-home negative test on
both bootstrap paths.

### B. PILOT00-SERVICE-RELEASE

Owner: existing backend host and the existing webclient build. No second
server. Trace seeds, not an allowlist. The follow-up order freezes an exact
allowlist only after a read-only owner, import, and lifecycle trace: Linux-relevant dependency
metadata, webclient Node pin and lockfile, a new non-privileged image
definition owned next to the backend start contract, `src/backend/service_host.py`,
`qm_platform/licensing/machine_id.py` only for an explicit stable binding that
does not skip checks, and build tests. Those seeds are not the frozen allowlist.

Acceptance, `NOT RUN`: reproducible Python 3.14 and web build; Node pin moved
only with lockfile, build, types, Vitest, and browser regression, and without
`npm audit fix --all`; image has no Git worktree, no secrets, no PyQt, no
Word COM, and no license issuer; the only start owner is `python -m src.backend`;
candidate, image, and dist identity are immutable; data volume is separate.
First build-only tests do not start the product backend and do not mutate the
pilot data target. SIGTERM, drain, marker, and restart are a later real-process
gate on the same host. License policy conflict stays unresolved here.

HIGH risk: MAC-based machine id changes when the container is recreated.
Evidence: restart and recreate comparison without generating a license.

### C. PILOT00-SIGNATURE-RECOVERY

Owner: signature module public API plus the existing backup orchestrator.
No platform import of signature internals. Trace seeds, not an allowlist.
The follow-up order freezes an exact allowlist only after a read-only owner,
import, and lifecycle trace: `modules/signature/api.py`, `modules/signature/secure_store.py`,
`modules/signature/wiring.py`, `modules/signature/module.py` for the existing
paths, `qm_platform/blob/backup_orchestrator.py`, and behavior tests. A public
recovery method does not exist today. Adding one is inside this package's
later freeze, not inside this planning diff.

Acceptance, `NOT RUN`: a sealed backup is not called complete until signature
assets and the master key are covered by the existing backup set; missing or
wrong key with existing ciphertext fails closed and does not look like success;
readback decrypts with the original key; secrets stay out of export, logs, and
evidence. No second backup stack.

HIGH risk: silent key rotation. Evidence: the wrong-key and missing-key tests.

This package blocks D.

### D. PILOT00-TARGET-RECOVERY-ADAPTER

Owner: the existing recovery package boundary. Public operator commands.
`qm_platform/blob/backup_orchestrator.py` and
`qm_platform/runtime/maintenance.py` are the current backup and update-abort
owners. Those paths are trace seeds, not an allowlist. The follow-up order
freezes an exact allowlist only after a read-only owner, import, and
lifecycle trace.
Negative tests must reject the lab cluster, the wrong socket, host, or project,
the wrong identity, an existing target, symlinks, and an incomplete set.
Cleanup stays exact. The Slot-2 contract stays unchanged. No host-wide
exception for `192.168.0.4`.

HIGH risk: restore onto the lab database. Evidence: negative guard tests, not a
live mutation of the lab host.

This package blocks a durable pilot instance. It stays mandatory before target
mutation on the future execution branch.

### E. PILOT00-LINUX-INTEGRATION

Binds the same release to A–D. Not an allowlist yet. The follow-up order
freezes E only after A–D have their own frozen contracts, and only after a
read-only owner, import, and lifecycle trace of E itself:
exact Compose project name, private PostgreSQL without a LAN port, separate
runtime, migration, and restore roles, resource limits without a claim of IO
isolation, health and readiness, start/stop/diagnose, migration as an operator
step. No privileged container, no Docker socket mount, no host network.
Real rootless gates need a later target approval. Fakes are not a Linux or
PostgreSQL PASS.

HIGH risk: treating build-only green as target qualification. Evidence: the
integration scenario below, executed only after A–D.

## Package integration scenario

Status: specified, `NOT RUN`.

One release identity from B is used only after A, C, and D are integrated.
On a fresh home, backend start does not create a settings SQLite file and
reads settings from PostgreSQL. A sealed backup includes signature assets.
Restore through the public operator command refuses the lab database and a
foreign socket, then restores into a separate database and asset target.
Readback decrypts existing signature material with the original key and shows
the same PDF and history. This scenario is not a PILOT00 PASS and does not
start PILOT01.

## Section III — isolated instance and formal qualification

These steps stay `NOT RUN` and start only after the preparation packages, a
bound release identity, and a bundled target decision:

1. Idempotent abortable preflight. No foreign resources change.
2. Own database and volumes. One first-admin bootstrap through the existing owner, then bootstrap credentials are removed.
3. Same-origin HTTPS. NPM only through one separately authorized change. Rootless and system Docker do not share a network automatically. Do not assume `127.0.0.1` inside the NPM container is the upstream.
4. Prefer the existing NPM and keep the backend TLS contract. A direct LAN HTTPS endpoint is the alternative if it needs fewer rights. An HTTP upstream needs its own approved trust contract. No mount of the whole NPM certificate store. `verify=false` is not a standing setting.
5. LAN-only needs rules plus a negative test, including IPv6, proxy headers, and a direct backend port. Local DNS alone does not protect a public NPM.
6. Early real browser run: login and password change, PDF import, comment, roles, ETag conflict, signature reauthentication, release, authorized download, history. Not a TestClient substitute.
7. A fast human functional test with synthetic data. It is not PILOT00 or PILOT01 acceptance.
8. Full backup, restore, and update abort with signature readback, PDF and history readback, database integrity, and release plus schema identity.
9. Separate portability, audit, and diagnostic exports. No secrets. Do not claim an automatic runtime export where the CLI requires an input file.
10. Monitoring must show alarm delivery and recovery clear. Container restart is not a host reboot. License binding survives recreate. Host reboot needs its own window.
11. Formal human smoke, then a separate PILOT00 closeout. PILOT01 stays blocked.

Closeout requires separate `TECHNICAL_PASS`, `SECURITY_REVIEW_PASS`,
`ARCHITECTURE_REVIEW_PASS`, and `HUMAN_ACCEPTANCE_PASS`, plus recovery, update
abort, reboot, monitoring, TLS, license, and accessibility evidence. All of
those are `NOT RUN`. Open HIGH or CRITICAL findings block the pilot. Reviewers
do not downgrade them to advice. RPO, RTO, and maximum backup, restore, update,
and alarm times are human decisions and measurements. End of pilot plans
retention, account deactivation, secret withdrawal, and an abort path. This
plan does not delete volumes.

Git, phase, and remote publication stay separate approvals. This planning
package does not authorize commit, push, pull request, or merge.

## Q01–Q32 subpoint disposition

Source questionnaire section is the original heading. Decision status is
`DECIDED`, `RECOMMENDED`, `OPEN`, `SUPERSEDED`, `N/A`, or `DEFERRED`.
Evidence status is `IMPLEMENTED_VERIFIED`, `PARTIAL`, or `NOT RUN`.
An infrastructure `IMPLEMENTED_VERIFIED` row is not a product PASS.
Recommendations are not approvals. Neighbor PASS does not fill an open row.

### Q01 1. Zweck und Pilotgrenze (14)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q01-01 | PILOT00 qualifiziert die Betriebsbereitschaft. | DECIDED | NOT RUN | PLAN | — | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-02 | PILOT00 verwendet ausschließlich synthetische Daten. | DECIDED | NOT RUN | PLAN | — | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-03 | Echtdaten sind bis zu `PILOT00 PASS` und einer separaten PILOT01-Freigabe verboten. | DECIDED | NOT RUN | PLAN | — | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-04 | Pilotkern ist PDF-first. | DECIDED | NOT RUN | PLAN | — | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-05 | DOCX/DOTX-Konvertierung gehört zu `CONV00` und blockiert PILOT00 nicht. | DECIDED | NOT RUN | PLAN | — | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-06 | Keine neue PyQt-/Desktop-Produktentwicklung. | DECIDED | NOT RUN | PLAN | — | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-07 | Produktclient ist der WEB01-Webclient. | DECIDED | NOT RUN | PLAN | — | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-08 | Welche Organisationseinheit führt den Pilot durch? | OPEN | NOT RUN | PLAN | konkreter Wert fehlt | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-09 | Wie viele Pilotbenutzer und gleichzeitige Sitzungen werden erwartet? | OPEN | NOT RUN | PLAN | konkreter Wert fehlt | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-10 | Welche Laufzeit ist für den technischen Pilot vorgesehen? | OPEN | NOT RUN | PLAN | konkreter Wert fehlt | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-11 | Welche Betriebszeiten gelten? | OPEN | NOT RUN | PLAN | konkreter Wert fehlt | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-12 | Welche Ausfallzeiten sind während PILOT00 zulässig? | OPEN | NOT RUN | PLAN | konkreter Wert fehlt | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-13 | Wer darf den Pilot stoppen? | OPEN | NOT RUN | PLAN | konkreter Wert fehlt | Zielumfang vor H-TARGET; Personen vor H-HUMAN |
| Q01-14 | Wer entscheidet über Abbruch oder Fortsetzung? | OPEN | NOT RUN | PLAN | konkreter Wert fehlt | Zielumfang vor H-TARGET; Personen vor H-HUMAN |

### Q02 2. Verantwortlichkeiten (15)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q02-01 | technischer Pilotverantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-02 | Infrastruktur-/VM-Verantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-03 | Windows-/Active-Directory-Verantwortlicher | N/A | NOT RUN | H-HUMAN | Windows-/AD-Rolle entfaellt fuer linux-rootless-synthetic; keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-04 | Netzwerk-/Firewall-Verantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-05 | DNS-Verantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-06 | PKI-/Zertifikatsverantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-07 | PostgreSQL-Verantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-08 | Backup-/Restore-Verantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-09 | Monitoring-/Alarmierungsverantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-10 | AV-/EDR-Verantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-11 | Lizenzverantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-12 | QMTool-Applikationsverantwortlicher | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-13 | Security-Abnehmer | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-14 | fachlicher Abnehmer | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |
| Q02-15 | finale PILOT00-Freigabeperson | OPEN | NOT RUN | H-HUMAN | keine belegte Person | vor der jeweiligen Handlung; nicht vor lokaler Docs- oder Buildarbeit |

### Q03 3. Virtualisierung und Zielserver (29)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q03-01 | Es wird eine dedizierte neue Pilot-VM verwendet. | SUPERSEDED | PARTIAL | PLAN | Windows-VM historisch; Hostzugang servinglunatix verifiziert; P0-Profil HUMAN_DECISION_REQUIRED; kein Produkt-PASS | H-PROFIL |
| Q03-02 | Virtualisierungsplattform: | N/A | NOT RUN | PLAN | keine neue VM; Option entfaellt fuer linux-rootless-synthetic | H-PROFIL |
| Q03-03 | Hyper-V | N/A | NOT RUN | PLAN | keine neue VM; Option entfaellt fuer linux-rootless-synthetic | H-PROFIL |
| Q03-04 | VMware | N/A | NOT RUN | PLAN | keine neue VM; Option entfaellt fuer linux-rootless-synthetic | H-PROFIL |
| Q03-05 | Proxmox | N/A | NOT RUN | PLAN | keine neue VM; Option entfaellt fuer linux-rootless-synthetic | H-PROFIL |
| Q03-06 | Azure | N/A | NOT RUN | PLAN | keine neue VM; Option entfaellt fuer linux-rootless-synthetic | H-PROFIL |
| Q03-07 | andere | N/A | NOT RUN | PLAN | keine neue VM; Option entfaellt fuer linux-rootless-synthetic | H-PROFIL |
| Q03-08 | physischer beziehungsweise logischer VM-Host | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-09 | zuständiger Infrastruktur-Owner | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-10 | Windows-Edition | N/A | NOT RUN | PLAN | Windows-VM-Feld entfaellt fuer dieses Profil | H-PROFIL |
| Q03-11 | Windows-Version und Build | N/A | NOT RUN | PLAN | Windows-VM-Feld entfaellt fuer dieses Profil | H-PROFIL |
| Q03-12 | Lizenzierungsstatus des Betriebssystems | N/A | NOT RUN | PLAN | Windows-VM-Feld entfaellt fuer dieses Profil | H-PROFIL |
| Q03-13 | VM-Name | N/A | NOT RUN | PLAN | Windows-VM-Feld entfaellt fuer dieses Profil | H-PROFIL |
| Q03-14 | CPU-Anzahl | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-15 | RAM | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-16 | Systemdisk-Größe | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-17 | getrennte Daten-/Backup-Volumes | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-18 | Firmware/UEFI/Secure-Boot-Konfiguration | N/A | NOT RUN | PLAN | Windows-VM-Feld entfaellt fuer dieses Profil | H-PROFIL |
| Q03-19 | TPM-Anforderung | N/A | NOT RUN | PLAN | Windows-VM-Feld entfaellt fuer dieses Profil | H-PROFIL |
| Q03-20 | Zeitzone: vorgesehen `Europe/Berlin` | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-21 | NTP-/Zeitsynchronisationsquelle | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-22 | Windows-Update-/Patchstand | N/A | NOT RUN | B/E | Windows-Update entfaellt; Linux-Patchfenster bleibt offen | H-TARGET |
| Q03-23 | Patchfenster | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-24 | Rebootfenster | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-25 | Snapshot-Policy | N/A | NOT RUN | C/D | VM-Snapshot oder VM-Backup ist kein Pilot-Backup | H-TARGET |
| Q03-26 | VM-Backup-Policy | N/A | NOT RUN | C/D | VM-Snapshot oder VM-Backup ist kein Pilot-Backup | H-TARGET |
| Q03-27 | Zugriffsmethode für Administratoren | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |
| Q03-28 | zulässige Remote-Administration, beispielsweise RDP oder Managementsystem | N/A | NOT RUN | E | RDP entfaellt; vorhandener SSH-Zugang ist kein Deployment | H-TARGET |
| Q03-29 | Notfallzugriff bei Netzwerkproblemen | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Profil vor H-PROFIL; Hostreboot nur im eigenen Fenster |

### Q04 4. Netzwerk (19)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q04-01 | isoliertes Pilot-/Staging-Netzwerksegment | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-02 | VLAN beziehungsweise Subnetz | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-03 | statische oder dynamische IP-Adresse | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-04 | reservierte IP-Adresse | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-05 | Default Gateway | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-06 | DNS-Server | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-07 | ausgehende Internetverbindung erlaubt oder verboten | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-08 | notwendige Proxy-Konfiguration | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-09 | Zugriff auf Paketquellen während Installation | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-10 | Zugriff auf Git-Remote während Installation | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-11 | Zugriff auf PostgreSQL | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-12 | Zugriff auf Backupziel | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-13 | Zugriff auf Monitoring | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-14 | Zugriff auf interne PKI/CRL/OCSP | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-15 | Zugriff der Pilotclients auf den QMTool-HTTPS-Endpunkt | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-16 | erlaubte Client-Netze | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-17 | Firewall-Owner | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-18 | Verfahren für Firewall-Freigaben | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q04-19 | Negativtest für nicht freigegebene Netze | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |

### Q05 5. DNS, FQDN und HTTPS-Port (14)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q05-01 | gewünschter FQDN, beispielsweise `qmtool-pilot.intern.example` | OPEN | NOT RUN | E | Empfehlung qmtool-pilot.lunatix.me, Name nicht angelegt und nicht freigegeben | H-TARGET |
| Q05-02 | DNS-Zone | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-03 | DNS-A-/AAAA-Eintrag | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-04 | DNS-Owner | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-05 | TTL | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-06 | gewünschter HTTPS-Port | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-07 | wird Port `443` oder ein dedizierter Port verwendet? | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-08 | ist der Port bereits belegt? | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-09 | nur FQDN-Zugriff oder zusätzlich Hostname/IP? | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-10 | Redirects ausdrücklich erforderlich oder nicht? | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-11 | HTTP vollständig geschlossen? | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-12 | externer Reverse Proxy vorhanden oder direkter ServiceHost? | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-13 | falls Reverse Proxy: wer terminiert TLS? | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Exposition |
| Q05-14 | Same-Origin-Vertrag `/api/v1` bleibt erhalten | DECIDED | NOT RUN | E | Same-Origin /api/v1 bleibt | H-TARGET |

### Q06 6. Installations- und Releaseform (28)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q06-01 | Zunächst kontrollierter `Repository + venv + webclient/dist`-Releasebaum. | SUPERSEDED | NOT RUN | B | Windows-Releaseform historisch; Linux-Image nur vorgeschlagen, nicht freigegeben | H-PROFIL |
| Q06-02 | Kein ad hoc kopierter Entwickler-Workspace. | DECIDED | NOT RUN | B | Ausschluss bleibt verbindlich | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-03 | Kein Betrieb aus einem beliebigen Git-Checkout. | DECIDED | NOT RUN | B | Ausschluss bleibt verbindlich | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-04 | Installationsroot, getrennt von `QMTOOL_HOME` | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-05 | Verfahren, wie der exakte Git-Commit auf die VM gelangt | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-06 | Git-Checkout auf Zielsystem oder vorbereiteter Releasebaum? | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-07 | wer darf den Releasebaum verändern? | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-08 | soll der Releasebaum nach Installation read-only sein? | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-09 | Python-Version, kanonisch Python 3.14.x | DECIDED | NOT RUN | B | Python >=3.14,<3.15 bleibt; Zielinstallation NOT RUN | H-PROFIL |
| Q06-10 | Quelle des Python-Installers | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-11 | exakte Python-Version | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-12 | Erstellung der virtuellen Umgebung | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-13 | Dependency-Installation | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-14 | erlaubte Python-Paketquelle | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-15 | Offline-/Cache-Verfahren | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-16 | Hash-/Lockfile-Prüfung der Dependencies | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-17 | Node.js nur auf Buildsystem oder auch auf Ziel-VM? | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-18 | Empfohlen: `webclient/dist` vor Deployment bauen; kein Node.js im Runtimebetrieb. | RECOMMENDED | NOT RUN | B | Empfehlung, keine Nutzerfreigabe | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-19 | exakte Node-/npm-Version für den Build | OPEN | NOT RUN | B | Empfehlung Node 24 LTS, keine Freigabe; Node 20 EOL und Node 22 ebenfalls LTS laut nodejs.org am 2026-09-26 | H-PROFIL |
| Q06-20 | Buildsystem für `webclient/dist` | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-21 | Integritätsprüfung des gebauten Webclients | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-22 | Release-Manifest | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-23 | Candidate-SHA | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-24 | Dependency-Fingerprints | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-25 | `webclient/dist`-Fingerprint | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-26 | `release/identity`-Datei | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-27 | Aufbewahrung vorheriger Releaseversionen | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |
| Q06-28 | Rollbackverfahren zum vorherigen Releasebaum | OPEN | NOT RUN | B | konkreter Wert fehlt | H-PROFIL vor Umsetzung; Freeze vor H-TARGET |

### Q07 7. Laufzeitverzeichnisse (19)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q07-01 | `QMTOOL_HOME=C:\ProgramData\QMTool` | SUPERSEDED | PARTIAL | E | Windows-Default ersetzt; Wurzel /mnt/md0/agents/qmtool-pilot existiert; interne Mountmatrix offen | H-TARGET |
| Q07-02 | Logverzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-03 | Blobverzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-04 | Backupverzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-05 | Zertifikatsverzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-06 | Lizenzverzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-07 | Release-Identitätsverzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-08 | Maintenance-Marker-Verzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-09 | Operation-Lock-Verzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-10 | Diagnose-Bundle-Verzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-11 | Temp-Verzeichnis | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-12 | freier Speicherplatz | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-13 | Speicherplatzwarnschwellen | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-14 | maximale Loggröße | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-15 | Logrotation | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-16 | Logaufbewahrung | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-17 | Cleanup-Policy | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |
| Q07-18 | NTFS-ACLs je Verzeichnis | N/A | NOT RUN | E | NTFS entfaellt; Unix-Rechte bleiben offen | H-TARGET |
| Q07-19 | Schutz vor normalen interaktiven Benutzern | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET vor Workloads |

### Q08 8. Windows-Dienst und SCM (23)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q08-01 | existiert ein organisationsweit vorgegebener Service-Wrapper? | SUPERSEDED | NOT RUN | B/E | Windows-SCM-Punkt wird fuer das vorgeschlagene Profil nicht als bestanden gewertet | H-PROFIL |
| Q08-02 | Name und Version des Wrappers | SUPERSEDED | NOT RUN | B/E | Windows-SCM-Punkt wird fuer das vorgeschlagene Profil nicht als bestanden gewertet | H-PROFIL |
| Q08-03 | falls keiner existiert: separates `PILOT00-SCM-ADAPTER` erforderlich | SUPERSEDED | NOT RUN | B/E | Windows-SCM-Punkt wird fuer das vorgeschlagene Profil nicht als bestanden gewertet | H-PROFIL |
| Q08-04 | Dienstname, vorgeschlagen `QMToolV7-Pilot` | SUPERSEDED | NOT RUN | B/E | Windows-SCM-Punkt wird fuer das vorgeschlagene Profil nicht als bestanden gewertet | H-PROFIL |
| Q08-05 | Dienstbeschreibung | SUPERSEDED | NOT RUN | B/E | Windows-SCM-Punkt wird fuer das vorgeschlagene Profil nicht als bestanden gewertet | H-PROFIL |
| Q08-06 | Startart, empfohlen Automatic Delayed Start | SUPERSEDED | NOT RUN | B/E | Windows-SCM-Punkt wird fuer das vorgeschlagene Profil nicht als bestanden gewertet | H-PROFIL |
| Q08-07 | Working Directory | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-08 | Startkommando muss letztlich `python -m src.backend` aufrufen | DECIDED | NOT RUN | B | einziger Startowner python -m src.backend | vor Start |
| Q08-09 | Starttimeout | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-10 | Stopptimeout | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-11 | Reaktion auf unerwarteten Prozessabbruch | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-12 | automatische Restart-Policy | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-13 | maximale Restartanzahl | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-14 | Recovery-Delay | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-15 | Verhalten bei wiederholtem Startfehler | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-16 | kontrollierter Stop vor Windows-Reboot | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-17 | Verhalten bei hängenden Requests | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-18 | Maintenance-Modus während Updates | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-19 | SCM-Eventlog-/Diagnosenachweis | SUPERSEDED | NOT RUN | B/E | Windows-SCM-Punkt wird fuer das vorgeschlagene Profil nicht als bestanden gewertet | H-PROFIL |
| Q08-20 | Reboot-Smoke | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-21 | automatischer Start nach Reboot | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-22 | Host-Marker korrekt angelegt und entfernt | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |
| Q08-23 | keine Beendigung fremder Prozesse | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Stoppvertrag vor Start; Hostreboot nur mit Wartungsfenster |

### Q09 9. Dienstidentität und Berechtigungen (16)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q09-01 | `LOCAL SERVICE` oder dediziertes Dienstkonto? | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-02 | falls dediziert: lokales Konto oder Domänenkonto? | N/A | NOT RUN | B/E | Windows-Kontomechanik entfaellt fuer dieses Profil | vor Deployment |
| Q09-03 | Konto-Owner | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-04 | Passwortrotation beziehungsweise Managed Service Account | N/A | NOT RUN | B/E | Windows-Kontomechanik entfaellt fuer dieses Profil | vor Deployment |
| Q09-05 | interaktive Anmeldung verboten | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-06 | lokale Administratorrechte verboten | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-07 | „Log on as a service“ | N/A | NOT RUN | B/E | Windows-Kontomechanik entfaellt fuer dieses Profil | vor Deployment |
| Q09-08 | Zugriff auf Releasebaum | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-09 | Schreibzugriff ausschließlich auf notwendige Runtimepfade | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-10 | Leserechte auf Zertifikat und Private Key | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-11 | Zugriff auf PostgreSQL-Secrets | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-12 | Zugriff auf Lizenzdatei | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-13 | Zugriff auf Backupziel | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-14 | Zugriff auf Remote-Netzfreigaben | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-15 | keine unnötigen Rechte auf andere Anwendungen | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |
| Q09-16 | ACL-Negativtests mit unberechtigtem Benutzer | OPEN | NOT RUN | B/E | konkreter Wert fehlt | vor Deployment |

### Q10 10. TLS und Zertifikate (22)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q10-01 | interne CA, öffentliche CA oder anderer Zertifikatsowner | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-02 | Zertifikats-Subject | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-03 | SAN enthält den festgelegten FQDN | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-04 | Aussteller | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-05 | Gültigkeitsdauer | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-06 | Ablaufdatum | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-07 | Zertifikatsfingerprint | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-08 | Schlüssellänge und Algorithmus | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-09 | Serverzertifikat im PEM-Format | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-10 | Private-Key-Ablage | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-11 | ACL auf Private Key | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-12 | Trust-Verteilung an Pilotclients | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-13 | Root-/Intermediate-Zertifikate | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-14 | CRL-/OCSP-Erreichbarkeit | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-15 | Zertifikatserneuerung | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-16 | Erneuerungsowner | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-17 | Alarm vor Ablauf | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-18 | dokumentierter Zertifikatswechsel | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-19 | Negativtest falscher Hostname | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-20 | Negativtest nicht vertrauenswürdige CA | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-21 | Negativtest abgelaufenes Zertifikat | OPEN | NOT RUN | E | konkreter Wert fehlt | H-TARGET |
| Q10-22 | Keine Private-Key-Inhalte in Git oder Evidence | DECIDED | NOT RUN | E | Ausschluss bleibt verbindlich | H-TARGET |

### Q11 11. PostgreSQL (31)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q11-01 | neue Instanz auf Pilot-VM oder separatem Server? | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-02 | PostgreSQL-Version | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-03 | PostgreSQL-Host | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-04 | PostgreSQL-Port | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-05 | Pilot-Datenbankname, beispielsweise `qmtool_pilot` | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-06 | Datenbank-Owner | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-07 | Backup-Owner | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-08 | TLS für PostgreSQL | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-09 | Runtime-Login | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-10 | Migrator-Login | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-11 | administrative Provisionierungsidentität | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-12 | Runtime und Migrator strikt getrennt | DECIDED | NOT RUN | E | Runtime und Migrator bleiben getrennt | H-TARGET |
| Q11-13 | Runtime ohne DDL-/Schemaänderungsrechte | DECIDED | NOT RUN | A/E | kein Runtime-DDL | vor Umsetzung |
| Q11-14 | Migrator ohne unnötige Superuserrechte | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-15 | Connection-Limits | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-16 | Timeoutwerte | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-17 | Verschlüsselung at rest | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-18 | PostgreSQL-Logaufbewahrung | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-19 | Wartungsfenster | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-20 | Vacuum-/Analyse-Policy | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-21 | Zeitzone | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-22 | Monitoring | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-23 | Schema-Provisionierung | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-24 | Migrationsverfahren | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-25 | Schema-Fingerprint | DECIDED | NOT RUN | A/E | Schemaidentität ist Pflicht; gemessener Fingerprint NOT RUN | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-26 | Seed-Verfahren ausschließlich über öffentliche Modul-APIs | DECIDED | NOT RUN | E | Seed nur ueber modules/<name>/api.py | H-TARGET |
| Q11-27 | Fresh-Install-Test | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-28 | Restart-/Readback-Test | OPEN | NOT RUN | A/E | konkreter Wert fehlt | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-29 | Slot 1 `qmtool_test` nicht als Pilotziel verwenden | DECIDED | NOT RUN | A/E | Ausschluss bleibt verbindlich | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-30 | Slot 2 `qmtool_j04_destructive_test` nicht als Pilotziel verwenden | DECIDED | NOT RUN | A/E | Ausschluss bleibt verbindlich | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |
| Q11-31 | Keine Zugangsdaten im Klärungsbogen | DECIDED | NOT RUN | A/E | Ausschluss bleibt verbindlich | Schemavertrag vor Umsetzung; exaktes Ziel vor H-TARGET |

### Q12 12. Blobstorage (12)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q12-01 | absoluter Blobpfad | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-02 | Volume | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-03 | Kapazität | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-04 | erwartetes Wachstum | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-05 | NTFS-ACLs | N/A | NOT RUN | E | NTFS entfaellt; Unix-Rechte bleiben offen | H-TARGET |
| Q12-06 | Backupintegration | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-07 | Dateisperren durch AV/EDR | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-08 | Verhalten bei vollem Datenträger | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-09 | Verhalten bei unbeschreibbarem Verzeichnis | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-10 | Checksummen-/Inventarnachweis | DECIDED | NOT RUN | C/E | Checksumme und Inventar sind Pflicht; Nachweis NOT RUN | vor Target-Freeze; Nachweis vor Closeout |
| Q12-11 | Restore in getrennten Blobpfad | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |
| Q12-12 | keine manuelle Veränderung durch Pilotbenutzer | OPEN | NOT RUN | C/E | konkreter Wert fehlt | vor Target-Freeze; Nachweis vor Closeout |

### Q13 13. Backup (19)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q13-01 | Backupziel | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-02 | separates Volume oder Netzfreigabe | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-03 | Backupziel physisch/logisch vom aktiven System getrennt | DECIDED | NOT RUN | C/D/E | Trennung vom aktiven System ist Pflicht; konkretes Ziel bleibt in Q13-01 offen; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-04 | Backupdienstkonto beziehungsweise Zugriff | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-05 | Backupintervall | OPEN | NOT RUN | C/D/E | Empfehlung 7 Tages- und 2 Wochenstaende, keine Nutzerfreigabe | H-TARGET |
| Q13-06 | Aufbewahrungsdauer | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-07 | Rotation | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-08 | Verschlüsselung | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-09 | Kapazitätsplanung | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-10 | Integritätsprüfung | DECIDED | NOT RUN | C/D/E | Integritätsprüfung ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-11 | versiegelte Backupsets | DECIDED | NOT RUN | C/D/E | versiegeltes Backup ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-12 | PostgreSQL-Dump enthalten | DECIDED | NOT RUN | C/D/E | Dump im versiegelten Set ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-13 | Blobinventar enthalten | DECIDED | NOT RUN | C/D/E | Blobinventar im versiegelten Set ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-14 | Releaseidentität enthalten | DECIDED | NOT RUN | C/D/E | Releaseidentität im versiegelten Set ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-15 | Schemafingerprint enthalten | DECIDED | NOT RUN | C/D/E | Schemaidentität im versiegelten Set ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-16 | Checksummenmanifest | DECIDED | NOT RUN | C/D/E | Checksummenmanifest ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-17 | Monitoring bei Backupfehler | DECIDED | NOT RUN | C/D/E | Monitoring bei Backupfehler ist Pflichtumfang; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-18 | verantwortlicher Operator | OPEN | NOT RUN | C/D/E | konkreter Wert fehlt | Strategie vor H-TARGET; Beweis vor Closeout |
| Q13-19 | manueller Backup-Drill | DECIDED | NOT RUN | C/D/E | manueller Backup-Drill ist Pflicht; Nachweis NOT RUN | Strategie vor H-TARGET; Beweis vor Closeout |

### Q14 14. Restore und Disaster Recovery (28)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q14-01 | isolierte Restore-Datenbank | DECIDED | NOT RUN | D/E | isolierte Restore-Datenbank ist Pflicht; konkreter Name bleibt in Q14-02 offen; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-02 | separater Restore-Datenbankname | OPEN | NOT RUN | D/E | konkreter Wert fehlt | Adapter integriert und H-TARGET vor Zieltests |
| Q14-03 | separater Restore-Blobpfad | OPEN | NOT RUN | D/E | konkreter Wert fehlt | Adapter integriert und H-TARGET vor Zieltests |
| Q14-04 | Restore darf niemals aktive Source überschreiben | DECIDED | NOT RUN | D | Source wird nicht ueberschrieben | vor Zieltests |
| Q14-05 | Cleanup nach Restore-Drill | DECIDED | NOT RUN | D/E | Cleanup nach Restore-Drill ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-06 | Restore-ServiceHost gegen Restoreziel | DECIDED | NOT RUN | D/E | Restore-ServiceHost gegen das Restoreziel ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-07 | funktionaler Readback | DECIDED | NOT RUN | D/E | funktionaler Readback ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-08 | PDF-Readback | DECIDED | NOT RUN | D/E | PDF-Readback ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-09 | Workflowstatus-Readback | DECIDED | NOT RUN | D/E | Workflowstatus-Readback ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-10 | Signaturstatus-Readback | DECIDED | NOT RUN | D/E | Signaturstatus-Readback ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-11 | Benutzer-/Sessionverhalten nach Restore | DECIDED | NOT RUN | D/E | Benutzer- und Sessionverhalten nach Restore ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-12 | gemessene Restorezeit | DECIDED | NOT RUN | D/E | Messen der Restorezeit ist Pflicht; Messwert NOT RUN; Schwelle bleibt in Q29-04 offen | Adapter integriert und H-TARGET vor Zieltests |
| Q14-13 | akzeptiertes RPO | OPEN | NOT RUN | D/E | konkreter Wert fehlt | Adapter integriert und H-TARGET vor Zieltests |
| Q14-14 | akzeptiertes RTO | OPEN | NOT RUN | D/E | konkreter Wert fehlt | Adapter integriert und H-TARGET vor Zieltests |
| Q14-15 | Eskalation bei RPO-/RTO-Verletzung | OPEN | NOT RUN | D/E | konkreter Wert fehlt | Adapter integriert und H-TARGET vor Zieltests |
| Q14-16 | Notfallhandbuch | DECIDED | NOT RUN | D/E | Notfallhandbuch ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-17 | verantwortlicher Recovery-Operator | OPEN | NOT RUN | D/E | konkreter Wert fehlt | Adapter integriert und H-TARGET vor Zieltests |
| Q14-18 | separates `PILOT00-TARGET-RECOVERY-ADAPTER`-Paket | DECIDED | NOT RUN | D | PILOT00-TARGET-RECOVERY-ADAPTER bleibt zwingend und NOT RUN | vor Zielmutation |
| Q14-19 | öffentliches Operator-Kommando | DECIDED | NOT RUN | D/E | öffentlicher Recovery-Owner ist das Operator-Kommando; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-20 | Pilot-Target-Guard | DECIDED | NOT RUN | D/E | Guard ist Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-21 | Source-/Lab-Negativtests | DECIDED | NOT RUN | D/E | Negativtests sind Pflicht; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-22 | getrennte Restore-DB-/Blobziele | DECIDED | NOT RUN | D/E | Trennung ist Pflicht; konkrete Namen bleiben in Q14-02 und Q14-03 offen; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-23 | Update-Abort | DECIDED | NOT RUN | D/E | Update-Abort ist Pflichtprüfung; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-24 | Cleanup | DECIDED | NOT RUN | D/E | Cleanup bleibt exakt; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-25 | statische Tests | DECIDED | NOT RUN | D/E | statische Pflichtprüfung; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-26 | isolierte Zieltests | DECIDED | NOT RUN | D/E | isolierte Pflichtprüfung; Nachweis NOT RUN | Adapter integriert und H-TARGET vor Zieltests |
| Q14-27 | Bestehender Slot‑2-`restore-drill` ist kein PILOT00-Nachweis | DECIDED | NOT RUN | D/E | Ausschluss bleibt verbindlich | Adapter integriert und H-TARGET vor Zieltests |
| Q14-28 | Kein direkter Import interner Restore-Funktionen | DECIDED | NOT RUN | D/E | Ausschluss bleibt verbindlich | Adapter integriert und H-TARGET vor Zieltests |

### Q15 15. Update und Rollback (19)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q15-01 | Updateverfahren | DECIDED | NOT RUN | B/D/E | Updatefolge ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-02 | Maintenance aktivieren | DECIDED | NOT RUN | B/D/E | Maintenance ist Pflichtschritt; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-03 | Request Drain | DECIDED | NOT RUN | B/D/E | Request Drain ist Pflichtschritt; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-04 | Dienst stoppen | DECIDED | NOT RUN | B/D/E | Dienststopp ist Pflichtschritt; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-05 | Backup vor Update | DECIDED | NOT RUN | B/D/E | Backup vor Update ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-06 | Kandidat B bereitstellen | DECIDED | NOT RUN | B/D/E | Kandidat B ist Pflichtschritt; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-07 | Releaseidentität prüfen | DECIDED | NOT RUN | B/D/E | Releaseidentität prüfen ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-08 | Migrationen ausführen | DECIDED | NOT RUN | B/D/E | Migration bleibt expliziter Operator-Schritt; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-09 | Dienst starten | DECIDED | NOT RUN | B/D/E | Dienststart ist Pflichtschritt; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-10 | Readiness prüfen | DECIDED | NOT RUN | B/D/E | Readiness prüfen ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-11 | funktionaler Smoke | DECIDED | NOT RUN | B/D/E | funktionaler Smoke ist Pflichtschritt; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-12 | Abortkriterien | DECIDED | NOT RUN | B/D/E | Abortprüfung ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-13 | Rollback auf Release A | DECIDED | NOT RUN | B/D/E | Rollback auf Release A ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-14 | Restore von PostgreSQL und Blobbestand | DECIDED | NOT RUN | B/D/E | Restore von PostgreSQL und Blobbestand ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-15 | exakter Rückkehrnachweis | DECIDED | NOT RUN | B/D/E | exakter Rückkehrnachweis ist Pflicht; Nachweis NOT RUN | H-TARGET vor zielgerichtetem Update |
| Q15-16 | Updatezeit | DECIDED | NOT RUN | B/D/E | Messen der Updatezeit ist Pflicht; Messwert NOT RUN; Schwelle bleibt in Q29-05 offen | H-TARGET vor zielgerichtetem Update |
| Q15-17 | Rollbackzeit | DECIDED | NOT RUN | B/D/E | Messen der Rollbackzeit ist Pflicht; Messwert NOT RUN; Schwelle bleibt in Q29-06 offen | H-TARGET vor zielgerichtetem Update |
| Q15-18 | Update-Owner | OPEN | NOT RUN | B/D/E | konkreter Wert fehlt | H-TARGET vor zielgerichtetem Update |
| Q15-19 | Rollback-Owner | OPEN | NOT RUN | B/D/E | konkreter Wert fehlt | H-TARGET vor zielgerichtetem Update |

### Q16 16. Secrets und Konfiguration (16)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q16-01 | Secret-Owner | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-02 | Bereitstellung der PostgreSQL-DSNs | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-03 | Bereitstellung des initialen Admin-Secrets | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-04 | Bereitstellung von TLS-Key-Pfaden | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-05 | Bereitstellung der Lizenz | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-06 | verschlüsselte Ablage oder OS-Secret-Store | OPEN | NOT RUN | B/C/E | kein Passwortmanager unterstellt | vor Provisionierung |
| Q16-07 | ACL-geschützte `.env`, falls verwendet | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-08 | keine Secrets im Releasebaum | DECIDED | NOT RUN | B/C/E | Verbot bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q16-09 | keine Secrets in Git | DECIDED | NOT RUN | B/C/E | Verbot bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q16-10 | keine Secrets in Logs | DECIDED | NOT RUN | B/C/E | Verbot bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q16-11 | keine Secrets in Diagnose-ZIPs | DECIDED | NOT RUN | B/C/E | Verbot bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q16-12 | keine Secrets in Screenshots | DECIDED | NOT RUN | B/C/E | Verbot bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q16-13 | keine Secrets oder Secret-Hashes in Evidence | DECIDED | NOT RUN | B/C/E | Verbot bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q16-14 | Rotation | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-15 | Notfallrotation | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |
| Q16-16 | Entzug bei Pilotende | OPEN | NOT RUN | B/C/E | konkreter Wert fehlt | vor der jeweiligen Provisionierung |

### Q17 17. Lizenz (12)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q17-01 | produktionsnahe Pilotlizenz | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-02 | Lizenzowner | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-03 | Bereitstellungsverfahren | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-04 | erlaubte Module | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-05 | Gültigkeitszeitraum | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-06 | Fingerprint ohne Lizenzinhalt | DECIDED | NOT RUN | B/E | Fingerprint ohne Lizenzinhalt ist Pflicht; Nachweis NOT RUN | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-07 | Ablaufüberwachung | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-08 | Verhalten bei ungültiger Lizenz | OPEN | NOT RUN | B/E | LICENSE_SPEC: Basislizenz blockiert den Start nicht; Backend fail_closed_license bricht Nicht-dev-Modi ab. Policy unveraendert. | H-PROFIL |
| Q17-09 | Verhalten bei abgelaufener Lizenz | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-10 | `doctor --strict` erfolgreich | DECIDED | NOT RUN | B/E | `doctor --strict` Produktions-/Lizenznachweis ist Pflicht; Nachweis NOT RUN | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-11 | kein `dev`-Lizenzmodus im Produktionsprofil | DECIDED | NOT RUN | B/E | Ausschluss bleibt verbindlich | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |
| Q17-12 | Lizenzdatei nicht in Git oder Evidence kopieren | DECIDED | NOT RUN | B/E | Ausschluss bleibt verbindlich | Policy vor H-PROFIL; konkrete Lizenz vor Backendstart |

### Q18 18. Monitoring und Alarmierung (21)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q18-01 | Monitoring-System | OPEN | NOT RUN | E | konkreter Wert fehlt | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-02 | Monitoring-Owner | OPEN | NOT RUN | E | konkreter Wert fehlt | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-03 | Pollingintervall | OPEN | NOT RUN | E | konkreter Wert fehlt | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-04 | `/health` als Liveness | DECIDED | NOT RUN | E | /health bleibt Liveness; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-05 | `/ready` als Readiness | DECIDED | NOT RUN | E | /ready bleibt Readiness; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-06 | Lizenzdiagnose separat von `/ready` | DECIDED | NOT RUN | E | Lizenzdiagnose bleibt getrennt von /ready; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-07 | Alarm bei Datenbankausfall | DECIDED | NOT RUN | E | Alarm bei Datenbankausfall ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-08 | Alarm bei Blobfehler | DECIDED | NOT RUN | E | Alarm bei Blobfehler ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-09 | Alarm bei Maintenance | DECIDED | NOT RUN | E | Alarm bei Maintenance ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-10 | Alarm bei Updatezustand | DECIDED | NOT RUN | E | Alarm bei Updatezustand ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-11 | Alarm bei Operation-Lock | DECIDED | NOT RUN | E | Alarm bei Operation-Lock ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-12 | Alarm bei Zertifikatsablauf | DECIDED | NOT RUN | E | Alarm bei Zertifikatsablauf ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-13 | Alarm bei niedrigem Speicherplatz | DECIDED | NOT RUN | E | Alarm bei niedrigem Speicherplatz ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-14 | Alarm bei Backupfehler | DECIDED | NOT RUN | E | Alarm bei Backupfehler ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-15 | Alarm bei wiederholtem Dienststartfehler | DECIDED | NOT RUN | E | Alarm bei wiederholtem Dienststartfehler ist Pflichtumfang; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-16 | nachgewiesene Alarmzustellung | DECIDED | NOT RUN | E | nachgewiesene Alarmzustellung ist Pflicht; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-17 | Eskalationsziel | OPEN | NOT RUN | E | konkreter Wert fehlt | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-18 | Bereitschafts-/Betriebszeiten | OPEN | NOT RUN | E | konkreter Wert fehlt | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-19 | Recovery-Clear nach Fehlerbehebung | DECIDED | NOT RUN | E | Recovery-Clear nach Fehlerbehebung ist Pflicht; Nachweis NOT RUN | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-20 | Alarmquittierung | OPEN | NOT RUN | E | konkreter Wert fehlt | Empfaenger vor Alarmtest; vollstaendig vor Closeout |
| Q18-21 | Aufbewahrung der Monitoringdaten | OPEN | NOT RUN | E | konkreter Wert fehlt | Empfaenger vor Alarmtest; vollstaendig vor Closeout |

### Q19 19. Logging, Audit und Diagnose (14)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q19-01 | Speicherort der Logs | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-02 | Logrotation | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-03 | Aufbewahrungsdauer | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-04 | Zeitstempel und Zeitsynchronisation | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-05 | Zugriffsschutz | DECIDED | NOT RUN | B/E | Zugriffsschutz ist Pflicht; Nachweis NOT RUN | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-06 | Diagnose-Bundle | DECIDED | NOT RUN | B/E | Diagnose-Bundle ist Pflicht; Nachweis NOT RUN | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-07 | Secret-Redaction | DECIDED | NOT RUN | B/E | Secret-Redaction ist Pflicht; Nachweis NOT RUN | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-08 | Bearer-/Basic-/DSN-/Passwort-Redaction | DECIDED | NOT RUN | B/E | Bearer-/Basic-/DSN-/Passwort-Redaction ist Pflicht; Nachweis NOT RUN | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-09 | Auditnachweis für fachliche Aktionen | DECIDED | NOT RUN | B/E | Auditnachweis für fachliche Aktionen ist Pflicht; Nachweis NOT RUN | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-10 | Correlation IDs | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-11 | Fehleranalyseverfahren | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-12 | Übergabe von Diagnose-Bundles | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-13 | Datenschutzprüfung | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Konfiguration vor Betrieb; Nachweis vor Closeout |
| Q19-14 | kein stilles Nachbearbeiten von Evidence | DECIDED | NOT RUN | B/E | Evidence bleibt unverändert; kein stilles Nachbearbeiten; Nachweis NOT RUN | Konfiguration vor Betrieb; Nachweis vor Closeout |

### Q20 20. AV/EDR (16)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q20-01 | eingesetztes AV-/EDR-Produkt | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-02 | AV-/EDR-Owner | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-03 | Scanpolicy | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-04 | Quarantänepolicy | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-05 | File-Lock-Verhalten | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-06 | Verhalten bei Python-/venv-Dateien | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-07 | Verhalten bei `webclient/dist` | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-08 | Verhalten bei Logs | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-09 | Verhalten bei Blobdateien | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-10 | Verhalten bei Backupsets | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-11 | Verhalten bei PEM-/Key-Dateien | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-12 | minimal notwendige Ausnahmen | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-13 | Genehmigung der Ausnahmen | OPEN | NOT RUN | B/E | konkreter Wert fehlt | Disposition vor Target-Freeze |
| Q20-14 | Alarmierung bei Quarantäne | DECIDED | NOT RUN | B/E | Alarmierung bei Quarantäne ist Pflichtumfang; Nachweis NOT RUN | Disposition vor Target-Freeze |
| Q20-15 | Test einer gesperrten Datei | DECIDED | NOT RUN | B/E | Test einer gesperrten Datei ist Pflichtnachweis; Nachweis NOT RUN | Disposition vor Target-Freeze |
| Q20-16 | keine pauschale Verzeichnisausnahme ohne Freigabe | DECIDED | NOT RUN | B/E | keine pauschale Verzeichnisausnahme ohne Freigabe ist Pflicht; Nachweis NOT RUN | Disposition vor Target-Freeze |

### Q21 21. Pilotbenutzer und Rollen (24)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q21-01 | Benutzer nach Funktion benennen. | DECIDED | NOT RUN | E/H-HUMAN | — | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-02 | / Benutzer / Zweck / | N/A | NOT RUN | E/H-HUMAN | Tabellenkopf, keine Entscheidung | H-HUMAN |
| Q21-03 | / `admin` / Administration / | RECOMMENDED | NOT RUN | E/H-HUMAN | funktionaler Kontoname, keine Personenfreigabe | vor Provisionierung |
| Q21-04 | / `editor` / Dokumentbearbeitung / | RECOMMENDED | NOT RUN | E/H-HUMAN | funktionaler Kontoname, keine Personenfreigabe | vor Provisionierung |
| Q21-05 | / `reviewer` / Review / | RECOMMENDED | NOT RUN | E/H-HUMAN | funktionaler Kontoname, keine Personenfreigabe | vor Provisionierung |
| Q21-06 | / `approver` / Freigabe/Signatur / | RECOMMENDED | NOT RUN | E/H-HUMAN | funktionaler Kontoname, keine Personenfreigabe | vor Provisionierung |
| Q21-07 | endgültige Benutzernamen | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-08 | globale Rolle je Konto | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-09 | `is_qmb` je Konto | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-10 | Dokument-Workflowrolle je Konto | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-11 | Signaturberechtigung | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-12 | Adminberechtigung | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-13 | Testperson je Konto | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-14 | Vertretung | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-15 | Ablaufdatum der Pilotkonten | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-16 | Deaktivierung nach Pilotende | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-17 | initiale Passwörter sicher erzeugen | DECIDED | NOT RUN | E/H-HUMAN | Pflicht bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q21-18 | initiale Passwörter außerhalb Git/Evidence übergeben | DECIDED | NOT RUN | E/H-HUMAN | Pflicht bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q21-19 | `must_change_password=true` | DECIDED | NOT RUN | E/H-HUMAN | Pflicht bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q21-20 | Passwortwechsel beim ersten Login | DECIDED | NOT RUN | E/H-HUMAN | Pflicht bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q21-21 | Session-Widerruf bei Passwortreset | DECIDED | NOT RUN | E/H-HUMAN | Pflicht bleibt; kein Passwortmanager unterstellt | vor Provisionierung |
| Q21-22 | `editor:editor` ist nicht zulässig. | DECIDED | NOT RUN | E/H-HUMAN | Ausschluss bleibt verbindlich | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-23 | Passwörter werden nicht dokumentiert. | DECIDED | NOT RUN | E/H-HUMAN | Ausschluss bleibt verbindlich | Personen vor Provisionierung; Ergebnis vor Closeout |
| Q21-24 | Mindestlänge der Standard-Policy: 10 Zeichen. | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Personen vor Provisionierung; Ergebnis vor Closeout |

### Q22 22. Signatur-Onboarding (17)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q22-01 | Signatur bleibt Bestandteil des Pilotkerns. | DECIDED | NOT RUN | C/E/H-HUMAN | — | vor Fachsmoke |
| Q22-02 | Jeder Benutzer verwendet seine eigene Authentifizierung. | DECIDED | NOT RUN | C/E/H-HUMAN | — | vor Fachsmoke |
| Q22-03 | keine Passwortweitergabe. | DECIDED | NOT RUN | C/E/H-HUMAN | Ausschluss bleibt verbindlich | vor Fachsmoke |
| Q22-04 | wie erhält jeder Signer sein Signaturasset? | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-05 | kontrollierte Selbstbereitstellung über bestehenden authentifizierten Vertrag? | RECOMMENDED | NOT RUN | E/H-HUMAN | begleitet ueber bestehende authentifizierte APIs; keine Nutzerfreigabe der UI | vor Fachsmoke |
| Q22-06 | separater Operator-Provisioning-Owner erforderlich? | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-07 | separates Self-Service-SPA-Paket erforderlich? | N/A | NOT RUN | E | kein Self-Service-UI als Pilotblocker | vor Fachsmoke |
| Q22-08 | Signaturasset-Format | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-09 | Aktivierung | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-10 | Austausch | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-11 | Deaktivierung | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-12 | Berechtigungen | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-13 | Reauthentication beim Signieren | DECIDED | NOT RUN | E | Reauthentifizierung bleibt Pflicht | vor Fachsmoke |
| Q22-14 | Auditnachweis | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-15 | Negative Tests für falsches Passwort | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-16 | Negative Tests für fehlendes Asset | OPEN | NOT RUN | C/E/H-HUMAN | konkreter Wert fehlt | vor Fachsmoke |
| Q22-17 | keine QES-Behauptung | DECIDED | NOT RUN | E | keine QES-Behauptung | vor Fachsmoke |

### Q23 23. Synthetische Testdaten (16)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q23-01 | ausschließlich synthetische Daten | DECIDED | NOT RUN | E/H-HUMAN | — | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-02 | Greenfield-Installation | DECIDED | NOT RUN | E/H-HUMAN | — | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-03 | keine Echtdaten | DECIDED | NOT RUN | E/H-HUMAN | Ausschluss bleibt verbindlich | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-04 | kein produktiver Legacy-Cutover | DECIDED | NOT RUN | E/H-HUMAN | Ausschluss bleibt verbindlich | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-05 | Anzahl synthetischer Dokumente | OPEN | NOT RUN | E/H-HUMAN | Empfehlung 10-20 PDFs, keine Nutzerfreigabe | vor Testdaten |
| Q23-06 | synthetische PDF-Fixtures | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-07 | Versionsstände | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-08 | Kommentare | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-09 | Review-/Approval-Zustände | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-10 | Konfliktfall | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-11 | kontrollierter Download | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-12 | Signaturfall | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-13 | Restore-Readback-Dokument | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-14 | Datenkennzeichnung als synthetisch | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-15 | Cleanup nach PILOT00 | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |
| Q23-16 | Archivierung der Testevidence | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Datensatz vor Test; Cleanup nur H-CLEANUP |

### Q24 24. Browser und Clients (17)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q24-01 | unterstützte Browser | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-02 | exakte Browserversionen | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-03 | mindestens ein verwalteter realer Pilotclient | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-04 | Windows-Version des Clients | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-05 | Zertifikatstrust auf Client | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-06 | Zugriff über FQDN | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-07 | Proxyverhalten | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-08 | Cookie-/Sessionverhalten | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-09 | Downloadverzeichnis | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-10 | PDF-Anzeige | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-11 | Bildschirmauflösung | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-12 | Skalierungsfaktor | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-13 | Tastaturlayout | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-14 | Sprache/Locale | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-15 | Zeitzone | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-16 | Browser-Härtung | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |
| Q24-17 | Private-/Inkognito-Modus erforderlich oder ausgeschlossen? | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | vor der jeweiligen Browser- oder Humanrunde |

### Q25 25. Fachlicher Human-Smoke (23)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q25-01 | Login | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-02 | erzwungener Passwortwechsel | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-03 | Logout | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-04 | Verbindungsverlust und Recovery | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-05 | Wartungsbanner | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-06 | Dashboard | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-07 | Dokumentenliste | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-08 | Dokument anlegen/importieren | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-09 | PDF anzeigen | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-10 | Version bearbeiten | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-11 | ETag-/Konfliktfall | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-12 | Kommentar erstellen | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-13 | Review starten | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-14 | Review akzeptieren | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-15 | Review ablehnen | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-16 | Freigabe | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-17 | Signatur mit Reauthentication | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-18 | Verlauf/History | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-19 | kontrollierter Download | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-20 | Admin-Benutzerliste | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-21 | Benutzer deaktivieren | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-22 | Passwort administrativ zurücksetzen | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |
| Q25-23 | Dienstrestart mit erhaltener fachlicher Persistenz | DECIDED | NOT RUN | E/H-HUMAN | Pflichtumfang des fachlichen Human-Smoke; Nachweis NOT RUN | H-HUMAN |

### Q26 26. UX-Entscheidungen (13)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q26-01 | PDF-first. | DECIDED | NOT RUN | E/H-HUMAN | — | vor Fachsmoke; keine generelle UX-Abnahme |
| Q26-02 | DOCX/DOTX blockiert PILOT00 nicht. | DECIDED | NOT RUN | E/H-HUMAN | — | vor Fachsmoke; keine generelle UX-Abnahme |
| Q26-03 | UX-D37 „Unbekannter Autor“ wird für den begrenzten Pilot akzeptiert. | DECIDED | NOT RUN | E/H-HUMAN | — | vor Fachsmoke; keine generelle UX-Abnahme |
| Q26-04 | UX-D37 bleibt als Follow-up dokumentiert. | DECIDED | NOT RUN | E/H-HUMAN | Follow-up bleibt; keine erneute Freigabe | vor Fachsmoke |
| Q26-05 | keine UUID/technischen IDs als sichtbarer Autorenname | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-06 | Ladezustände verständlich | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-07 | Fehlerzustände verständlich | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-08 | Maintenance deutlich sichtbar | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-09 | Konfliktdialog verständlich | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-10 | read-only Zustand eindeutig | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-11 | erlaubte Aktionen entsprechen `allowed_actions` | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-12 | keine clientseitig erfundene Berechtigung | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |
| Q26-13 | keine deferred Funktion als implementiert darstellen | DECIDED | NOT RUN | E/H-HUMAN | Darstellungspflicht bleibt; Human-Nachweis NOT RUN | vor Fachsmoke |

### Q27 27. Accessibility (19)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q27-01 | repräsentativer Accessibility-/Screenreader-Smoke soll eingeschlossen werden. | DECIDED | NOT RUN | E/H-HUMAN | Umfang eingeschlossen; Nachweis NOT RUN | vor Human-Smoke |
| Q27-02 | verwendeter Screenreader | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Werkzeug vor Human-Smoke; Finding-Disposition vor PILOT01 |
| Q27-03 | verantwortlicher Tester | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Werkzeug vor Human-Smoke; Finding-Disposition vor PILOT01 |
| Q27-04 | Tastaturnavigation | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-05 | sichtbarer Fokus | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-06 | Fokusführung in Dialogen | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-07 | Formularlabels | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-08 | Fehlermeldungen | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-09 | Status nicht ausschließlich über Farbe | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-10 | Kontrast | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-11 | Zoom/Skalierung | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-12 | Login | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-13 | Dokumentenliste | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-14 | Detailansicht | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-15 | Konfliktdialog | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-16 | Signaturdialog | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-17 | Adminansicht | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-18 | Abweichungen dokumentieren | DECIDED | NOT RUN | E/H-HUMAN | Pruefpunkt bleibt im Umfang; Nachweis NOT RUN | vor Human-Smoke |
| Q27-19 | Entscheidung, welche Findings PILOT01 blockieren | OPEN | NOT RUN | E/H-HUMAN | konkreter Wert fehlt | Werkzeug vor Human-Smoke; Finding-Disposition vor PILOT01 |

### Q28 28. Security Review (23)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q28-01 | Authentifizierung | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-02 | Sessioncookies | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-03 | CSRF | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-04 | Reauthentication | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-05 | Passwortwechsel | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-06 | Rollen und Berechtigungen | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-07 | `allowed_actions` | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-08 | ETag/If-Match | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-09 | Upload | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-10 | Download | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-11 | Signaturassets | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-12 | Audit | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-13 | Secret-Ablage | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-14 | TLS | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-15 | Dienstkonto | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-16 | Firewall | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-17 | Backupmissbrauch | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-18 | Restoremissbrauch | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-19 | Diagnose-Redaction | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-20 | Export-Redaction | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-21 | Logzugriff | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-22 | Datenlöschung nach Pilotende | DECIDED | NOT RUN | E | Pflichtumfang des Security Review; Nachweis NOT RUN | vor formaler Pilotbereitschaft |
| Q28-23 | offene HIGH-/CRITICAL-Findings blockieren den Pilot | DECIDED | NOT RUN | E | HIGH/CRITICAL blockiert; Review selbst NOT RUN | vor formaler Pilotbereitschaft |

### Q29 29. RPO und RTO (10)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q29-01 | RPO: maximal zulässiger Datenverlust | OPEN | NOT RUN | D/E/H-HUMAN | Empfehlung 24h RPO, keine Nutzerfreigabe | vor Betriebsnachweis |
| Q29-02 | RTO: maximal zulässige Wiederherstellungszeit | OPEN | NOT RUN | D/E/H-HUMAN | Empfehlung 4h RTO, keine Nutzerfreigabe | vor Betriebsnachweis |
| Q29-03 | maximal zulässige Backupdauer | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |
| Q29-04 | maximal zulässige Restorezeit | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |
| Q29-05 | maximal zulässige Updatezeit | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |
| Q29-06 | maximal zulässige Rollbackzeit | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |
| Q29-07 | maximale Alarmierungszeit | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |
| Q29-08 | maximale Reaktionszeit | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |
| Q29-09 | Konsequenz bei Überschreitung | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |
| Q29-10 | Freigabeperson | OPEN | NOT RUN | D/E/H-HUMAN | konkreter Wert fehlt | vor qualifizierendem Betriebsnachweis; nicht vor lokalem Build |

### Q30 30. Evidence und Nachvollziehbarkeit (18)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q30-01 | Candidate-SHA | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-02 | Zielsystem-ID | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-03 | Releasefingerprint | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-04 | Schemafingerprint | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-05 | TLS-Fingerprint | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-06 | Lizenzfingerprint | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-07 | Start- und Endzeit | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-08 | ausführende Rolle | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-09 | exakter Befehl | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-10 | Exitcode | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-11 | Ergebnis | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-12 | Artefakt-SHA256 | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-13 | Screenshots nur mit synthetischen Daten | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-14 | Secret-Scan | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-15 | Prozessleckprüfung | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-16 | ehrliche `NOT RUN`-Einträge | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-17 | technische und menschliche Acceptance getrennt | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |
| Q30-18 | keine nachträgliche Veränderung grüner Evidence | DECIDED | NOT RUN | jedes Paket | Pflichtfeld; erfasster Wert NOT RUN | ab dem ersten Gate dieses Pakets |

### Q31 31. Abnahmekriterien (14)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q31-01 | `TECHNICAL_PASS` | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-02 | `SECURITY_REVIEW_PASS` | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-03 | `ARCHITECTURE_REVIEW_PASS` | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-04 | `HUMAN_ACCEPTANCE_PASS` | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-05 | Backup und Restore bestanden | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-06 | Update-Abort bestanden | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-07 | Reboot bestanden | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-08 | Monitoring und Alarmzustellung bestanden | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-09 | TLS/LAN bestanden | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-10 | Lizenzprüfung bestanden | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-11 | Human-Smoke bestanden | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-12 | Accessibility-Disposition abgeschlossen | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-13 | keine offenen blockierenden Findings | DECIDED | NOT RUN | PILOT00-Closeout | Pflichtnachweis; Evidence NOT RUN | vor Closeout |
| Q31-14 | finale menschliche Unterschrift/Freigabe | OPEN | NOT RUN | H-HUMAN | keine belegte Freigabeperson | vor Closeout |

### Q32 32. Pilotende und Cleanup (11)

| SP | Unterpunkt | Entscheidung | Evidence | Owner | Offener Wert | Spaetestes Gate |
| --- | --- | --- | --- | --- | --- | --- |
| Q32-01 | Aufbewahrung der Evidence | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-02 | Aufbewahrung synthetischer Daten | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-03 | Deaktivierung der Pilotkonten | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-04 | Entzug temporärer Secrets | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-05 | Entfernen temporärer Firewallregeln | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-06 | Entfernen temporärer AV-Ausnahmen | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-07 | Snapshot-/Backup-Aufbewahrung | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-08 | Entscheidung über Weiterbetrieb der VM | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-09 | Übergabe an PILOT01 | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |
| Q32-10 | PILOT01 bleibt bis zu separater Echtdatenfreigabe `NOT RUN` | DECIDED | NOT RUN | H-CLEANUP | PILOT01 bleibt bis zur separaten Echtdatenfreigabe gesperrt | H-PILOT01 |
| Q32-11 | Abbruch-/Rollbackverfahren, falls PILOT00 nicht bestanden wird | OPEN | NOT RUN | H-CLEANUP | konkreter Wert fehlt | H-CLEANUP oder gesonderte PILOT01-Freigabe |

## Entscheidungsblock 1 — Profil/Ausführung

Profilfreigabe und Ausführungsfreigabe sind zwei verschiedene Ja-Worte.
Linux bleibt `PROPOSED / HUMAN_DECISION_REQUIRED`. Windows Server first bleibt
P0. PILOT00 bleibt `TODO / NOT RUN`.

Bereits entschieden:

- PDF-first, Greenfield, synthetische Daten, Webclient, nur PostgreSQL.
- Keine Echtdaten und keine PILOT01-Freigabe durch diese Planung.
- Keine neue PyQt-Produktarbeit. CONV00 blockiert PILOT00 nicht.
- Das historische Windows-VM-Profil wird nicht still zum Linux-Vertrag.
- Eine Profilfreigabe startet keine Paketänderung und keinen Pilot.

Nur echte offene Wahlen:

- Ob `linux-rootless-synthetic` als zusätzliches, begrenztes PILOT00-Profil akzeptiert wird.
- Ob der P0-Satz Windows Server first in einem separaten Entscheidungsdokument geändert werden soll. Diese Datei ändert ihn nicht.

Empfehlung: `linux-rootless-synthetic` als zusätzliches Profil annehmen und den P0-Satz Windows Server first unverändert lassen. Die Ausführungsfreigabe in diesem Block auf `NEIN` lassen.

Antwort:

```text
Profilfreigabe linux-rootless-synthetic: <leer>
P0 Windows Server first unveraendert lassen: <leer>
Ausführungsfreigabe A-E: NEIN
```

Spätestes Gate: H-PROFIL, vor der ersten Änderung eines Ausführungspakets.
Die Profilfreigabe ist nicht die Ausführungsfreigabe.

## Entscheidungsblock 2 — Zielbetrieb

Profilfreigabe wählt das Profil. Ausführungsfreigabe erlaubt später die
Zieländerung. Beides ist hier noch offen beziehungsweise `NEIN`.

Bereits entschieden:

- Slot 1 `qmtool_test` und Slot 2 `qmtool_j04_destructive_test` sind keine Pilotziele.
- `192.168.0.4` erhält keine host-weite Guard-Ausnahme.
- Runtime und Migrator bleiben getrennt. Kein Runtime-DDL.
- Kein Dual-Write und kein SQLite-Produktfallback.
- Versiegeltes Backup enthält PostgreSQL-Dump, Blobinventar, Releaseidentität, Schemaidentität und Checksummenmanifest. Der Nachweis ist `NOT RUN`.
- Öffentlicher Recovery-Owner ist das Operator-Kommando. Guards und die Pflichtnegativtests sind entschieden. Die Personen in Q02 und Q14-17 fehlen.
- Reihenfolge: C vor D, A–D vor E. B darf build-only früher laufen und ist dann kein Deployment-PASS.
- Der Lizenz-Policy-Konflikt gehört in diesen Block und bleibt ungelöst.

Lizenz-Policy-Konflikt, Q17-08. `docs/LICENSE_SPEC.md` sagt, die Basislizenz ist kein Startblocker der Anwendung. `build_platform_ports(fail_closed_license=True)` in `src/backend/bootstrap.py` verlangt `QMTOOL_LICENSE_MODE`, bricht bei fehlgeschlagener Validierung eines anderen Modus ab und lehnt `dev` und `auto` ab, wenn `QMTOOL_RUNTIME_PROFILE` `prod` oder `production` ist. Diese Planung ändert die Lizenzpolicy nicht.

Nur echte offene Werte und Wahlen:

- Konkrete Zielwerte, die in der Matrix `OPEN` sind, weil der Wert fehlt: PostgreSQL-Version, Host, Port, Datenbankname, Rollen, TLS, Volumes, FQDN, Ressourcen, Patch- und Rebootfenster.
- Die Wahl zu Q17-08. Sie ist keine schon getroffene Policyänderung.

Empfehlung: den bereits beschriebenen rootless Host nur als Kandidat behandeln, nicht als Deployment. Q17-08 so beantworten, dass `LICENSE_SPEC` und der bestehende Production-Fail-Closed-Check beide unverändert bleiben und der Production-Check für `prod`/`production` der Pilotstart bleibt. Keine neue Lizenzpolicy in A–E.

Antwort:

```text
Zielhost-Kandidat servinglunatix rootless bestaetigt: <leer>
Q17-08 Lizenzpolicy: <leer>
Fehlende Zielwerte: <leer>
Ausführungsfreigabe Zielmutation: NEIN
```

Spätestes Gate: H-TARGET, vor jeder Zielmutation. Die Profilfreigabe ersetzt diese Ausführungsfreigabe nicht.

## Entscheidungsblock 3 — Mensch/Test/Betriebsziele

Profilfreigabe besetzt keine Personen und startet keinen Human-Smoke.
Die Ausführungsfreigabe für den Smoke ist ein späteres Ja.

Bereits entschieden, Nachweis jeweils `NOT RUN`:

- Q25 ist der vollständige fachliche Human-Smoke und bleibt im Umfang.
- Offene HIGH- oder CRITICAL-Findings blockieren den Pilot.
- Die Evidencefelder in Q30 sind Pflicht.
- Accessibility- und Screenreader-Smoke bleiben eingeschlossen. Werkzeug und Tester bleiben offen. Der Umfang wird nicht neu aufgemacht.
- UX-D37 „Unbekannter Autor“ bleibt für diesen begrenzten Pilot akzeptiert, mit Follow-up. Das ist keine generelle UX-Abnahme und wird nicht neu aufgemacht.
- Kein Passwortmanager wird vorausgesetzt.
- Q02 erfindet keine fachlich abnehmende Person. Q02-14 bleibt `OPEN`.
- `must_change_password=true`, Wechsel beim ersten Login und Session-Widerruf bleiben Pflicht.
- Empfehlungen zu Dauer, Gruppengröße, RPO, RTO und Node 24 sind keine Freigaben.

Nur echte offene Werte:

- Die Personen in Q02, der Accessibility-Tester, der Screenreader, die PILOT01-Finding-Disposition und die finale Freigabeperson Q31-14.
- Organisation, Benutzerzahl, Laufzeit, Betriebs- und Ausfallzeiten, Stopp- und Abbruchrecht in Q01.
- Die Zahlen in Q29. Die genannten 24h und 4h sind Empfehlungen.

Empfehlung: Personenfelder leer lassen, bis ein Mensch einen belegten Namen einträgt. RPO 24h und RTO 4h nur als Empfehlung stehen lassen. Die Ausführungsfreigabe für den Human-Smoke auf `NEIN` lassen.

Antwort:

```text
Fachlicher Abnehmer: <leer>
Screenreader: <leer>
Accessibility-Tester: <leer>
RPO: <leer>
RTO: <leer>
Ausführungsfreigabe Human-Smoke: NEIN
```

Spätestes Gate: H-HUMAN, vor dem fachlichen Human-Smoke und vor `HUMAN_ACCEPTANCE_PASS`. Die Profilfreigabe ist nicht diese Ausführungsfreigabe.

## Folgeauftrag A–E

Status dieses Auftrags: `NICHT AUTORISIERT`.
Den folgenden Block nicht ausführen, solange dieses Wort hier steht oder ein Antwortfeld `<leer>` ist.
Profilfreigabe allein ist keine Ausführungsfreigabe.

```text
/execute-work-package PILOT00-AE-MACRO

Dieser Auftrag ist nur gültig, wenn ein Mensch ihn ausdrücklich sendet, in
docs/AP-029_PILOT00_LINUX_PREPARATION.md das Wort NICHT AUTORISIERT für diesen
Folgeauftrag entfernt hat und die drei Antwortfelder in den Entscheidungsblöcken
Profil/Ausführung, Zielbetrieb und Mensch/Test/Betriebsziele ausgefüllt sind.
Leere Antwortfelder oder ein noch gesetztes NICHT AUTORISIERT sind ein
HUMAN_GATE. `<leer>` gilt als leeres Antwortfeld. Bereits beantwortete Punkte nicht erneut fragen. Empfehlungen nicht
als Antwort lesen. Q02 nicht mit einer erfundenen Person füllen. Keinen
Passwortmanager voraussetzen. UX-D37 und den Accessibility-/Screenreader-Umfang
nicht wieder öffnen.

Linux bleibt PROPOSED / HUMAN_DECISION_REQUIRED, bis Block 1 JA zur
Profilfreigabe sagt. Windows Server first bleibt P0, außer Block 1 sagt
ausdrücklich etwas anderes. PILOT00 bleibt TODO / NOT RUN, bis das formale
Closeout eigene TECHNICAL_PASS, SECURITY_REVIEW_PASS, ARCHITECTURE_REVIEW_PASS
und HUMAN_ACCEPTANCE_PASS hat. Dieser Auftrag ist keine dieser Passes.

Ziel. Serielles Makropaket, ein Checkpoint nach dem anderen:
A PILOT00-SETTINGS-PG, dann B PILOT00-SERVICE-RELEASE, dann
C PILOT00-SIGNATURE-RECOVERY, dann D PILOT00-TARGET-RECOVERY-ADAPTER, dann
E PILOT00-LINUX-INTEGRATION. C ist fertig, bevor D beginnt. A, B, C und D sind
reviewer-PASS, bevor E beginnt. B darf build-only früher als C, D und E laufen
und nur dann vor A, wenn die eingefrorene B-Allowlist disjunkt zur A-Allowlist
ist, das Produktbackend nicht startet und das Pilotziel nicht angefasst wird.
Ein grünes B ist kein Deployment-PASS.

Vor dem ersten Edit, fail-closed:
1. Cursor erzeugt selbst den TargetRoot und den Branch. Nicht den Planungs-Worktree
   umhängen, nicht checkout, rebase, reset, stash oder clean. Neuer Worktree
   build/worktrees/ap-029-pilot00-ae und Branch feature/ap-029-pilot00-ae von dem
   Commit, der diese beantwortete Planung enthält. Liegt die Planung nur dirty
   vor, stoppen und keine Paketdatei ändern.
2. Identitätsgate: registrierter TargetRoot, Branch ist nicht main, HEAD ist der
   erwartete Planungscommit, origin/main-Divergenz gelesen, Index leer, genau ein
   Worktree hält den Ausführungsbranch. Abweichung: stoppen.
3. .cursor/tools/assert-execution-host.ps1 gegen genau diesen TargetRoot mit
   -RequireGitWrite und -RequirePythonTemp. EXECUTION_HOST_REQUIRED: stoppen.
4. Exklusiver Writer: kein index.lock, kein zweiter Worktree auf demselben Branch.
5. Human-Gate der drei Entscheidungsblöcke erneut lesen. Widerspruch zwischen
   Antwort und P0: stoppen, P0 nicht still ändern.
6. Native Sol/Terra bei Quota UNAVAILABLE nicht erneut starten und nicht als PASS
   werten. Ein unabhängiger Reviewer bleibt Pflicht. Fällt er aus, HUMAN_GATE,
   kein Self-PASS.

Pakete nicht produktiv vermischen. Ein Checkpoint, eine Allowlist, ein Commit.
Unklarer Owner oder nötige Scope-Erweiterung: nicht still weiterarbeiten.
SCOPE_CORRECTION_REQUIRED nur, wenn jede genannte Datei ein bestehender Owner
ist, der in der Allowlist fehlt, von einem Abnahmekriterium direkt verlangt wird
und keine neue Verhaltenfläche, API, Architektur oder Technik einführt. Budget:
ein Scope-Correction-Round aus .cursor/agent-system.json. Danach SCOPE_EXPANSION
und HUMAN_GATE. Erstes rotes Pflichtgate stoppt. Spätere Pflichtgates nicht
starten. Kein Retry, der einen Fehlschlag verdeckt.

Review und Rework je Checkpoint: ein frischer unabhängiger Reviewer, höchstens
ein Verification-Pass, höchstens zwei normale Reworks, danach höchstens ein
Escalation-Review. FAIL nach dem Escalation-Review ist BLOCKED_HUMAN. Der
Implementierer vergibt kein PASS. Commitgrenze: git-steward, ein lokaler Commit
der exakten Allowlist nach reviewer-PASS, nie auf main. Push, PR und Merge nur,
wenn dieser Auftrag sie nach dem letzten grünen Checkpoint ausdrücklich noch
trägt; bis dahin kein Push. Kein Secret, kein DDL am lebenden Ziel, kein
Lab- oder Slot-2-Ziel als Pilot.

EvidenceRoot: build/ap-029-pilot00-ae/<checkpoint>/<utc-stamp>/ mit Vertrag,
SHA256, Diff, JUnit und Verdict. Workflow-State nur im Ausführungs-Worktree.

A PILOT00-SETTINGS-PG ist der erste ausführbare Checkpoint und bereits
eingefroren. Nach dem read-only Ownertrace gilt die exakte Allowlist aus dem
Abschnitt A von docs/AP-029_PILOT00_LINUX_PREPARATION.md, nicht eine
vorläufige Liste. Beide Bootstrap-Pfade
wire_backend_usermanagement/_force_hardened_usermanagement_settings und
wire_backend_documents mit PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
attach_settings_persistence und migrate. Gemeinsame Owner, Lifecycle/Shutdown
und Profiltrennung wie dort beschrieben. Kein Parallelpfad, kein Dual-Write,
kein Runtime-DDL. Externe Modulzugriffe nur über modules/<name>/api.py.
Die neue Datei qm_platform/settings/postgres_settings_repository.py ist die
einzige neue Datei und ersetzt SqliteSettingsRepository auf dem Backend-Profil
hinter dem bestehenden SettingsService.
Bestehende Testowner und Befehle, strikt seriell, projektlokales TEMP/TMP,
frischer Basistemp:
.\.venv\Scripts\python.exe -m pytest tests/platform/test_core_database_migrations.py tests/platform/test_settings_cutover.py tests/platform/test_settings_governance_enforcement.py tests/platform/test_postgres_schema_static.py tests/backend/test_documents_http_api.py::test_wire_backend_documents_registers_documents_sqlite_owner -q -p no:cacheprovider --basetemp build/pt/pilot00-settings-pg-<stamp>
Erst danach, und nur über den Runner:
.\.venv\Scripts\python.exe scripts/run_postgres_live_tests.py tests/platform/test_postgres_schema_live.py tests/backend/test_postgres_backend_bootstrap_live.py
Evidence: build/ap-029-pilot00/settings-pg/<utc-stamp>/ im Ausführungsbaum.
Reviewgate, lokale Commitgrenze und Fail-fast/SCOPE_CORRECTION_REQUIRED wie
im Abschnitt A. ServiceHost und Desktop-Bootstrap nicht anfassen; das wäre
SCOPE_EXPANSION.

B, C, D und E werden erst unmittelbar vor ihrer eigenen ersten Änderung
eingefroren. Vorher Pflicht: read-only Owner-, Import- und Lifecycle-Trace,
eine ausdrückliche erlaubte Scope-Korrekturentscheidung, dann eine eigene
feste Allowlist. Trace-Seeds im Plan sind keine Allowlist. Keine produktive
Vermischung mit dem gerade grünen Paket. B-Build ohne Backend-Start am
Pilotziel. C liefert den kleinsten öffentlichen Recovery-Vertrag unter
modules/signature/api.py, bevor D ein Operator-Kommando darauf setzt. D bleibt
vor jeder Zielmutation Pflicht und ruft restore_backup_set nicht inline als
Ersatz auf. E bindet dieselbe Release-Identität erst nach A–D.

Konkrete Gates je späterem Paket erst nach dem eigenen Freeze aus den
bestehenden Owner-Tests ableiten, nicht erfinden. Docs-Planung dieses
Vorgängerpakets bleibt tests/docs/test_pilot00_linux_plan.py,
tests/docs/test_docs_consistency.py und tests/docs. Produkt-, PostgreSQL-,
Build- und Servertests nur, wenn das eingefrorene Paket sie als bestehende
Owner nennt. Slot 2 nie mit bloßem pytest -m postgres.
```
