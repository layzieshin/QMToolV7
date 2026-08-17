# J04-M0 Acceptance Report

## Status

Current status: `Rejected / follow-up required` — **WR03 Safe-Mode PASS; DispatchEx PASS; add-ins not causal; freeze not set**

Allowed values: `Draft` | `Ready for acceptance` | `Accepted` | `Rejected / follow-up required`

`Accepted` bleibt ausschließlich dem menschlichen Abnahmeprozess vorbehalten.
`Ready for acceptance` darf erst nach den Final-/Live-/Packaging-Gates (Meilensteine 3–8)
gesetzt werden.

> **Historische Evidence:** Abschnitte „Verification (Meilenstein 0)“ bis „Verification (M2R)“
> unten dokumentieren frühere Teilläufe (2026-08-06/07) mit teils widersprüchlichen oder
> unvollständigen Rohlogs unter `.j04_*_evidence/`. Diese Zahlen sind **nicht** der aktuelle
> Closure-Lauf. Aktuelle Evidence entsteht erst unter `build/j04-m0-closure/` ab CP00.

## Technical acceptance candidate

`$CandidateSha` — **not set after CP08-R1/R2**. Last frozen SHA was `8c273de` (CP04-R). Product
`fbea360` (R1) and test `30b73e9` (R2) are remediations; docs HEAD `e8a015c` is documentation
only. A new freeze covering R1+R2 **including documentation** is deferred until Word COM
readiness **PASS** in an interactive desktop PowerShell.

### CP04-R — PostgreSQL test infrastructure (adopted PASS)

Completed by separate agent; **do not re-implement**. Verified by closure run 2026-08-17.

| Item | Value |
| --- | --- |
| Commit | `8c273de` — `test(j04-m0): pin destructive PG major via env for local PG18 smoke` |
| Slot 1 (Lab, untouched) | `192.168.0.4:5432` / `qmtool_test` |
| Slot 2 (destructive) | `127.0.0.1:5432` / PostgreSQL 18.4 |
| Test DB / admin | `qmtool_j04_destructive_test` / `qmtool_j04_test_admin` |
| Marker | `j04_m0_destructive_pg16` |
| Major contract | `QMTOOL_PG_TEST_EXPECTED_MAJOR`: local 18, CI 16, default 16; floor >= 16 |
| RESET | not stored; `scripts/run_postgres_live_tests.py` read-only preflight + child-only opt-in |

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP04R-GUARD | `pytest tests/test_postgres_destructive_guard.py tests/test_run_postgres_live_tests.py -q` | **28 passed** (closure verify) |
| CP04R-LIVE | Live smoke `test_provision_is_idempotent` via runner | **PASS** (reported by infra agent; not re-run here) |
| CP04R-PREFLIGHT | Preflight major=18, marker valid | **PASS** (reported by infra agent) |

No PG16 installation planned. No Slot-1 changes.

## Verification (CP08 — final acceptance gate, aborted)

Ausgeführt am 2026-08-17 auf `feature/ap-j04-m0`, Produkt-Baseline `8c273de`, Doc-HEAD `94fb480`.
Gate-Regel: keine Reparatur während des laufenden Gates.

| # | Gate | Ergebnis |
| --- | --- | --- |
| CP08-PG-LIVE | `scripts/run_postgres_live_tests.py` (PG18, `QMTOOL_PG_TEST_EXPECTED_MAJOR=18`) | **51 passed**; preflight major=18 |
| CP08-REGRESSION | `pytest -m "not postgres and not j04_final_acceptance" -q` | **1 failed** — siehe unten |
| CP08-WORD | Word COM availability probe | **BLOCKED** (`CO_E_SERVER_EXEC_FAILURE`) |
| CP08-E2E / ONEDIR / GOLIVE | — | **NOT RUN** (gate abort) |

Regression failure:

```
tests/modules/test_module_contract_wiring.py::test_module_wiring_hard_get_ports_are_declared_as_required_ports
AssertionError: modules\documents\wiring.py uses non-literal get_port
```

Evidence logs: `build/j04-m0-closure/cp08-pg-live-runner-clean.log`, `build/j04-m0-closure/cp08-regression.log`

**Candidate status: NOT_READY** — CP08-R1 remediates the wiring architecture failure; freeze
is deferred until CP08-R2 (real-process scenario) is complete.

## Verification (CP08-R1 — literal optional documents port)

Ausgeführt am 2026-08-17. Product change only in `modules/documents/wiring.py`.
`DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` remains exported. Architecture test unchanged.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R1-FOCUS | wiring contract, documents ports, HTTP gates, bootstrap provenance | **16 passed** (`build/j04-m0-closure/cp08-r1`) |
| CP08R1-DIFF | `git diff -- modules/documents/wiring.py` | two string-literal replacements; constant export unchanged |
| CP08R1-DIFFCHECK | `git diff --check` | **Exit 0** (CRLF warnings only on known stat-only files) |

No freeze after R1. Next: CP08-R2 (replace real-process `pytest.skip` stub), then Word COM
readiness, then a new technical freeze before a second CP08 attempt.

CP08-R1 commit: `fbea360` — `fix(j04-m0): use literal optional documents port in wiring`

## Verification (CP08-R2 — real-process scenario implementation)

Test-only remediation. Replaces the `pytest.skip` stub with `run_acceptance_scenario()`.
**No freeze.** Live PG, full gate execution, Word COM live, and Onedir **NOT RUN**.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R2-FOCUS | harness unit + scenario unit + realprocess excluded marker | **15 passed** (`build/j04-m0-closure/cp08-r2`) |
| CP08R2-GATE-SKIP | `test_j04_m0_realprocess.py -m j04_final_acceptance` ohne Opt-in | **1 skipped** |
| CP08R2-DIFFCHECK | `git diff --check` | **Exit 0** (expected) |

Scenario step catalog (17 steps): preconditions → PG bootstrap → backend start → health/openapi →
bootstrap login → seed users/profile → two client sessions → document baseline → ETag race →
artifacts → signature → training read → comments/CR/lifecycle → backend restart → persistence/sessions →
Word COM boundary (SKIP until CP08 interactive opt-in).

Next: Word COM readiness in interactive session → new technical freeze → second CP08 attempt.

CP08-R2 commit: `30b73e9` — `test(j04-m0): implement realprocess acceptance scenario`

## Verification (Word COM readiness — BLOCKED)

Minimal `DispatchEx` probe on 2026-08-17. **No DOCX/PDF E2E.** Pre-existing Word sessions not terminated.

| # | Check | Ergebnis |
| --- | --- | --- |
| WR-BEFORE | Existing WINWORD PIDs | **15936**, **23944** |
| WR-PROBE | `DispatchEx("Word.Application")` + controlled `Quit` | **BLOCKED** — HRESULT **0x80080005** (`CO_E_SERVER_EXEC_FAILURE`) |
| WR-AFTER | Pre-existing PIDs preserved | **15936**, **23944** still running |
| WR-FREEZE | Post-R1/R2 candidate freeze | **not set** (blocked on Word readiness) |
| WR-CP08 | Second full CP08 attempt | **not started** |

Evidence: `build/j04-m0-closure/word-com-readiness/probe-result.json`

Classification: interactive Windows/COM environment failure, **not** a new product deviation.
Pre-existing Word PIDs were left unchanged; the failed `DispatchEx` instance was not
terminated; no DOCX/PDF E2E; no freeze; no second CP08 run. Docs commit `e8a015c` is
documentation only.

On interactive **PASS** only, in this order:

1. Document Word readiness in checklist and report
2. Freeze R1+R2 including documentation HEAD
3. Record the new `$CandidateSha`
4. Start exactly one second CP08 run against that SHA

Until then overall status remains **`NOT_READY`**.

## Verification (WR03 — Safe mode + add-in isolation)

2026-08-17. **No DOCX/PDF E2E.** WR02 leftover PID already gone; WINWORD list empty at start.

| # | Check | Ergebnis |
| --- | --- | --- |
| WR03-SAFE | `WINWORD.EXE /safe` PID 21364 | **PASS** — window title **`Microsoft Word (Abgesicherter Modus)`** |
| WR03-HKLM | Disable Acrobat/Citavi `LoadBehavior=3` | **BLOCKED** — HKLM access denied |
| WR03-HKCU | Acrobat then Citavi `LoadBehavior=0` | applied; originals snapshotted |
| WR03-A | Acrobat=0, Citavi=2, `DispatchEx` | **PASS** Word 16.0 |
| WR03-B | Acrobat=2, Citavi=0, `DispatchEx` | **PASS** Word 16.0 |
| WR03-C | both HKCU restored to 2, `DispatchEx` | **PASS** Word 16.0 |
| WR03-EFFECT | Add-in causality | **not causal** — COM works after clean session even with add-ins restored |
| WR03-FREEZE | R1+R2 freeze / second CP08 | **not started** |

## Technical acceptance candidate (CP07 freeze — historical)

`$CandidateSha` was `d19e8b999c126dbc3ecbfeecd1d807a109d60edd` (`d19e8b9`) until remediation `8c273de`.

### Checkpoint / commit table (this closure run)

| CP | Status | Technical commit | Follow-up docs commit |
| --- | --- | --- | --- |
| CP00 | PASS | `0a844c2` preserve baseline | `8469add` |
| CP01 | PASS | `3f3f7b1` backend transport contracts | `54181ba` |
| CP02 | PASS | `c2d6f3d` client use-case gates | `cc4e9f2` |
| CP03 | PASS | `1993292` isolate Word COM | `ce5a8a7` |
| CP04 | PASS | `c71c1f1` harden PG16 gates (static/CI) | `54d4d37` |
| CP04-R | PASS | `8c273de` PG test infra remediation | _(adopted; no duplicate commit)_ |
| CP05 | PASS | `29ddaa6` real-process harness | `136d9e4` |
| CP06 | PASS | `ba67126` prepare onedir | `a6959ea` |
| CP07 | PASS | `d19e8b9` freeze (superseded candidate) | SHA record |
| CP08 | FAILED | — (gate abort; no product commit) | `c47a514` |
| CP08-R1 | PASS | `fbea360` literal optional documents port | SHA record |
| CP08-R2 | PASS | `30b73e9` real-process scenario | this documentation |

### Remaining gates (explicitly NOT RUN)

| Gate | Status |
| --- | --- |
| Isolated PostgreSQL live (Slot-2 PG18 local / CI PG16) | **CP04-R PASS** (guard+runner); full live suites **NOT RUN** (CP08) |
| M8 `pg_dump`/`pg_restore` live drill | **NOT RUN** |
| Full `j04_final_acceptance` real-process E2E | **NOT RUN** (scenario implemented in CP08-R2) |
| Real Word COM document conversion E2E | **NOT RUN** |
| Word COM `DispatchEx` readiness probe | **BLOCKED** — `CO_E_SERVER_EXEC_FAILURE` (0x80080005) in agent session |
| `packaging/build_onedir.py` | **Packaging NOT RUN** |
| Built EXE against separate backend | **NOT RUN** |
| Full non-destructive regression | **FAILED** (CP08): `test_module_contract_wiring` / `documents/wiring.py` |
| `scripts/golive_gate.py` | **NOT RUN** |
| Human visible onedir acceptance | **NOT RUN** (`ACCEPTED` not set) |

### Worktree at freeze

- No F/G files. No untracked product/test paths.
- Remaining dirty paths are the two known stat-only files (no content diff): `label_geometry.py`, `modules/training/wiring.py`.
- Historical `.j04*_evidence/` remains local/ignored (category E).

### Verification (CP07 — freeze)

Ausgeführt am 2026-08-17, Python 3.14 aus `.\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres and not j04_final_acceptance"`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP07-FOCUS | docs artifact package, OpenAPI snapshot, PG guard, architecture gates | **60 passed** (`build/j04-m0-closure/cp07`) |
| CP07-PACKAGING | `tests/packaging/test_j04_m0_onedir_contract.py` | **5 passed** (`build/j04-m0-closure/cp07-packaging`) |
| CP07-DIFFCHECK | `git diff --check`; `git diff --cached --check` | **Exit 0** |

CP07 freeze commit / `$CandidateSha`: `d19e8b9` — `checkpoint(j04-m0): freeze technical acceptance candidate`

CP07 documentation-only correction: SHA-256 entries in
`docs/QMToolV7_Dokumentenlenkung_Artefaktpaket_v2/QMToolV7_Dokumentenlenkung_MANIFEST_v2.txt`
for `JSON_TO_DATABASE_MIGRATION_PLAN.md` (J04-M0 content from CP00) and
`JSON_STORAGE_INVENTORY.md` (pre-existing stale hash vs current worktree). No product or test code changed.

## Verification (CP00 — baseline preservation)

Ausgeführt am 2026-08-17 im Worktree `QMToolV7-j04-m0`, Branch `feature/ap-j04-m0`,
`HEAD`/`origin/main` = `125709f`, Python 3.14 aus `.\.venv\Scripts\python.exe`,
`PYTHONPATH=.`, Marker `-m "not postgres"`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP00-FOCUS | Fokussierter Architektur-/Contract-Smoke (siehe Checkliste) | **24 passed** |
| CP00-DIFFCHECK | `git diff --check`; `git diff --cached --check` | **Exit 0** (CRLF warnings only on stat-only unstaged paths) |

CP00 commit: `0a844c2` — `checkpoint(j04-m0): preserve current implementation baseline`

## Verification (CP01 — backend transport contracts)

Ausgeführt am 2026-08-17, Python 3.14 aus `.\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres"`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP01-BACKEND | Fokussierter Backend-/Client-/OpenAPI-Smoke (siehe Plan CP01) | **77 passed** |
| CP01-EXPORT | `python scripts/export_openapi.py` | **Exit 0** (kein Snapshot-Drift) |
| CP01-SNAPSHOT | `pytest …::test_openapi_snapshot_is_reproducible` | **1 passed** |

Keine reproduzierbaren Vertragsabweichungen — keine Produktkorrekturen in CP01.

Execution path (verified by tests, unchanged):

- Auth: HTTP → `src/backend/*` routes → `modules/usermanagement/api.py` → service → session `UserContext`
- Documents mutation: HTTP client → backend routes → `modules/documents/api.py` → service (policy-on-lock, ETag)
- Actor: exclusively from authenticated session; request actor fields ignored
- `allowed_actions`: computed server-side; clients fail-closed
- Artifacts: backend transports IDs/bytes; clients never open backend file paths
- Documents SQLite: backend-only (`DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` opt-in for tests)

## Verification (CP02 — client-facing M0 use-case gates)

Ausgeführt am 2026-08-17, Python 3.14 aus `.\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres"`, `--basetemp build/j04-m0-closure/cp02`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP02-GATES | Fokussierter Client-/GUI-/HTTP-Smoke (12 Testmodule, siehe Plan CP02) | **62 passed** |
| CP02-DIFFCHECK | `git diff --check`; `git diff --cached --check` | **Exit 0** (CRLF warnings only on stat-only unstaged paths) |

CP02 commit: `c2d6f3d` — `checkpoint(j04-m0): verify client use-case gates`

Keine reproduzierbaren Abweichungen — keine Produktkorrekturen in CP02.

Verified M0 vertical slices (same-process HTTP; not live multi-process):

- **Artifacts:** read/download via HTTP artifact IDs/bytes (`test_documents_artifacts_http`, `test_documents_http_reads`)
- **Signature:** shared session transport; authorization matrix (`test_signature_http_api`, `test_signature_authorization_http`)
- **Training read:** documents read-only consumer (`test_documents_training_read_http`)
- **Comments / header / lifecycle / change requests:** P4–P9 HTTP + M2R CAS consumers (`test_documents_p4_p9_http`, `test_m2r_*`)
- **Profile manager:** backend HTTP mutation only; no local SQLite path (`test_documents_workflow_profile_manager_gate`, `test_pyqt_backend_profile_scope`)
- **PyQt actions:** server-driven `available_actions`; fail-closed visibility (`test_action_bar_visibility`, `test_m2r_control_action_gates`)
- **Authorization matrix:** 16-action coverage index + execution (`test_documents_authorization_matrix`)

Out-of-scope paths remain `not_in_m0` / fail-closed (no J04-M1 or parallel paths introduced).

CP02 commit: `c2d6f3d` — `checkpoint(j04-m0): verify client use-case gates`

## Verification (CP03 — Word COM isolation)

Ausgeführt am 2026-08-17, Python 3.14 aus `.\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres"`, `--basetemp build/j04-m0-closure/cp03`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP03-FOCUS | `test_docx_to_pdf`, `test_docx_conversion_worker`, `test_documents_p4_p9_http` | **24 passed** |
| CP03-DIFFCHECK | `git diff --check`; `git diff --cached --check` | **Exit 0** (CRLF warnings only on stat-only unstaged paths) |

CP03 commit: `1993292` — `fix(j04-m0): isolate Word COM conversion`

## Verification (CP04 — PostgreSQL-16 destructive gate)

Ausgeführt am 2026-08-17, Python 3.14 aus `.\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres"`, `--basetemp build/j04-m0-closure/cp04`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP04-GUARD-STATIC | Guard + static + M8 prep (non-`postgres` marker) | **57 passed** |
| CP04-RG-AUDIT | `rg` über Guard-/DROP-/DSN-Pfade in tests, CI, `.env.example`, `pytest.ini` | **grün** (alle DROP-Pfade über `require_approved_admin_dsn`) |
| CP04-DIFFCHECK | `git diff --check`; `git diff --cached --check` | **Exit 0** |

CP04 commit: `c71c1f1` — `test(j04-m0): harden isolated PostgreSQL 16 gates`

## Verification (CP05 — real-process acceptance harness)

Ausgeführt am 2026-08-17, Python 3.14 aus `.\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres and not j04_final_acceptance"`, `--basetemp build/j04-m0-closure/cp05`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP05-HARNESS | Harness-Unit-Tests + Same-Process-Referenz (`two_clients…`, `version_read…`) | **10 passed** |
| CP05-FINAL-GATE | `test_j04_m0_realprocess.py` mit `-m "not j04_final_acceptance"` | **0 collected** (absichtlich ausgeschlossen) |
| CP05-DIFFCHECK | `git diff --check`; `git diff --cached --check` | **Exit 0** |

CP05 commit: `29ddaa6` — `test(j04-m0): add deterministic real-process acceptance harness`

## Verification (CP06 — onedir packaging preparation)

Ausgeführt am 2026-08-17, Python 3.14 aus `.\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres and not j04_final_acceptance"`, `--basetemp build/j04-m0-closure/cp06`.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP06-PACKAGING | Bundle guards + onedir contract + backend client scope | **16 passed** |
| CP06-DIFFCHECK | `git diff --check`; `git diff --cached --check` | **Exit 0** |

CP06 commit: `ba67126` — `test(j04-m0): prepare reproducible onedir acceptance`

**Packaging NOT RUN** — kein `packaging/build_onedir.py`-Lauf, kein EXE-Fachworkflow in CP06.

Änderungen:

- `packaging/build_onedir.py` — explizite J04-Client-/COM-`hidden-import`s ergänzt
- `packaging/verify_customer_bundle.py` — fail-closed gegen `.env`, `.db`, `.sqlite`, J04-Evidence
- `tests/packaging/test_j04_m0_onedir_contract.py` — statischer Onedir-Vertrag (Entrypoint, Imports, kein baked `QMTOOL_BACKEND_URL`)
- `QMTOOL_BACKEND_URL` bleibt Laufzeitkonfiguration (`resolve_backend_base_url_from_env`)

**Final acceptance NOT RUN** — kein `j04_final_acceptance`-Lauf, kein `QMTOOL_J04_FINAL_ACCEPTANCE`-Opt-in.

Test-only Harness unter `tests/acceptance/`:

- `j04_m0_realprocess_harness.py` — `python -m src.backend` auf Port 8000, eigene PIDs, redigierte Logs
- `j04_m0_client_worker.py` — Client-Subprozess mit getrenntem `QMTOOL_HOME` und In-Memory-Session
- `test_j04_m0_harness_unit.py` — Lifecycle/Redaction/Port/Session-Unit-Tests
- `test_j04_m0_realprocess.py` — CP08-Vollgate (Marker + Opt-in; in CP05 nicht ausgeführt)

Kein neuer Produkt-Entrypoint, Port oder fachliche API.

**PG16 LIVE NOT RUN** — keine Verbindung zur lokalen Runtime-/Lab-DB, PG18 oder `.env`.
Destruktive Live-Fixtures bleiben bis zur dedizierten externen PG16-Instanz blockiert.

Konfigurationsänderungen (kein Produktcode):

- `.env.example`: Runtime/Lab- vs. `QMTOOL_PG_TEST_*`-Variablen getrennt
- `pytest.ini`: `postgres`-Marker dokumentiert isolierten destructive cluster
- `.github/workflows/ci-gates.yml`: Guard-Test in `quality-gates`; CI-Service auf
  `qmtool_j04_destructive_test` + Marker-Init; Live-Lauf mit `QMTOOL_PG_TEST_*` (M8 zuletzt)
- `tests/postgres/README.md`: CI-Ephemeral-Cluster-Hinweis

**Kein echter Word-E2E-Lauf** — ausschließlich mockbasierte Unit-/Component-Tests.

Änderungen in `modules/documents/docx_to_pdf.py`:

- `DispatchEx("Word.Application")` statt `Dispatch` für isolierte Word-Instanz
- `Quit()` ausschließlich auf selbst erzeugter Instanz; `doc.Close`/`word.Quit` in `finally`
- partielle Initialisierung: kein `Quit()` wenn `DispatchEx` fehlschlägt
- Fehlerredaktion via `_redact_error_message` (keine vollen Pfade, kein rohes COM-Repr)

Baseline-Klassifizierung: `docs/J04_M0_EXECUTABLE_CHECKLIST.md` (A–D staged; E ignoriert;
2 stat-only Pfade nicht gestaged).

## Deploymentumfang (verbindlich)

Abnahmeziel für J04-M0:

- **gepackter PyQt-Onedir-Client** gegen einen **separat installierten Backenddienst**
- **kein** gepacktes Backend-Artefakt
- Documents-/Signature-Persistenz und Artefakte nur im Backend-Prozess
- **genau ein Backendprozess** besitzt die Documents-Persistenz (kein Multi-Worker /
  Multi-Prozess-Schreiben auf dieselbe Documents-DB im Abnahmeziel)
- Comment-Status-CAS (`set_workflow_comment_status_if_current`) ist unter diesem
  Vertrag **prozesslokal** (`threading.RLock` + Vergleich auf `expected_updated_at`).
  Es gibt **kein** datenbankweites konditionales UPDATE auf `expected_updated_at`.
  Multi-Worker/Multi-Prozess auf derselben DB liegt **außerhalb** des Abnahmeziels und
  würde ohne DB-CAS last-writer-wins bedeuten.
- PostgreSQL-Live-Fixtures nur gegen einen isolierten PostgreSQL-16-Testcluster (nicht Runtime-DSN)

## P0–P10 Teilpaket-Stand (Summary)

| Paket | Inhalt | Stand | Evidence (Auszug) |
| --- | --- | --- | --- |
| **D0** | Pfadmatrix + Report + Allowed-Actions-Analyse | **Done (M0-Doku)** | `docs/J04_M0_PATH_MATRIX.md`, `docs/J04_M0_ALLOWED_ACTIONS_ANALYSIS.md`, dieses Dokument |
| **P0** | Backend-Session + HTTP-Transport | **Done** | Session-/HTTP-Client-Tests (Same-Process) |
| **P1** | Client/Backend-Komposition, DB-Ownership | **Remediated Execute / unaccepted** | G3: `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` + Interfaces **174 passed**; Live-/Zwei-Prozess weiter offen |
| **P2** | Reads + Capabilities | **Remediated Execute / unaccepted** | Backend-Reads grün; PyQt fail-closed auf Backend-`available_actions` (**M2**); Live/Zwei-Prozess offen |
| **P3** | Core Workflow + Concurrency | **Remediated Execute / unaccepted** | Policy-on-Lock-`current` + Tokenfortschreibung (M1/G1); OpenAPI If-Match/428 + `current_state` (**M2**); kein Zwei-Prozess-Live |
| **P3A** | Artefakttransport | **Remediated Execute / unaccepted** | Reads/Downloads Same-Process; Open/Edit/Default-Open an Backend-`open_source` gebunden (**M2**); Live offen |
| **P3B** | Backend-Signatur | **Remediated Execute / unaccepted** | Assets/Standalone Same-Process; Signed Transitions Policy-on-`current` (M1/G1); Live offen |
| **P3C** | Training Documents-Read | **Done (HTTP Same-Process)** | Training-Read-HTTP im Backend-Lauf |
| **P4** | Workflow-Kommentare | **Remediated Execute / unaccepted** | Mutationen tokengebunden (M1R3); UI/Sync nur mit Backend-Action `comments` (**M2**); Status-CAS prozesslokal (F4) |
| **P5** | Header / Metadaten | **Remediated Execute / unaccepted** | Metadata/Header Execute (M1R1/M1R3); UI an Backend-Actions `update_metadata`/`update_header`/`assign_roles` (**M2**); Live offen |
| **P6** | DOCX / Template | **Partial** | Route/Port vorhanden; create-from-template If-Match konditional dokumentiert (**M2**); **Word-COM Live NOT RUN** |
| **P7** | Lifecycle | **Remediated Execute / unaccepted** | Archive/Extend/`new_version` Execute (M1R); UI an `extend_validity`/`new_version` (**M2**); Live offen |
| **P8** | Change Requests | **Remediated Execute / unaccepted** | Create Execute + ETag (M1R1); UI an Backend-Action `change_requests` (**M2**); Live offen |
| **P9** | Workflowprofil-Admin | **Remediated Execute / unaccepted** | Backend-HTTP Create positiv; CLI `profile-list` ok; mutierende Profile-CLI-Befehle `legacy_not_in_m0`; PyQt-Manager/Live offen |
| **P10** | Legacy-Entfernung + Gates | **Partial / unaccepted** | Interfaces **174** + Backend Same-Process grün (G3/M2); Live/Packaging/Final offen |

## Architektur-Invarianten (weiterhin verbindlich)

- Ein Use Case nie halb lokal / halb HTTP.
- Backend-DB/Artefakte nur im Backend-Prozess.
- Actor aus Backend-Session; PyQt Bearer via Session-Port (nicht Env).
- Backend-Routen importieren nur öffentliche Modul-APIs.
- Domainmodule importieren keine `interfaces`.
- Same-Process-`TestClient`-Nachweise sind **kein** Zwei-Client-/Live-Evidence.

## Bekannte Abnahmeblocker (Allowed Actions)

Vollständige Analyse: `docs/J04_M0_ALLOWED_ACTIONS_ANALYSIS.md`.

1. ~~Lokaler PyQt-Fallback bei fehlenden `available_actions`~~ — **remediated (M2)**; fail-closed ohne lokale Policy.
2. ~~Fehlende serverseitige Actor-/QMB-Prüfung für `create_new_version_after_archive`~~ — **remediated (M1/G1)**.
3. ~~Gemeinsame Policy vor dem Compare-and-Mutate-Lock~~ — **remediated (M1/G1)**; Policy auf Lock-`current` inkl. Tokenfortschreibung.
4. ~~Actor×Status×Assignment×Action-Ausführungsmatrix unvollständig~~ — **Coverage-Index +
   Public-API-/HTTP-Ausführungsnachweise remediated (M1R3 + Evidence-Nachschärfung)**;
   Live-/Zwei-Prozess-Nachweise fehlen weiterhin.
   `test_sixteen_action_execution_coverage_table` ist ein **Index** (Zuordnung ACTION_ID → Testmethode),
   kein alleiniger Ausführungsnachweis.
5. ~~OpenAPI: `If-Match` optional, kein 428, Konfliktfeld `state`~~ — **remediated (M2)**;
   required If-Match-Menge + 428; `ErrorDetail.current_state`; required `available_actions`.
5b. ~~Header-/Kommentarstatus-CAS im PyQt-Consumer ohne ETag~~ — **remediated (M2R)**;
   Header speichert geladenes `updated_at` als If-Match; Kommentarlisten liefern `updated_at`;
   Resolve/Reactivate senden Kommentar-Token; stale → 409 ohne Mutation.
6. TestClient/Same-Process ≠ Zwei-Prozess-Live.
7. ~~Interfaces-Collection: fehlende Wiring-Konstante~~ — **remediated (G3)**; Suite **174 passed** (M2), **189 passed** (M2R inkl. neuer CAS-/Control-Tests).
8. Comment-Status-CAS bewusst **prozesslokal** unter dem Ein-Prozess-Abnahmeziel (F4); keine DB-CAS in M0/M1.

## Verification (Meilenstein 0)

Ausgeführt am 2026-08-06 im Worktree `QMToolV7-j04-m0` mit
`I:\Projekte\QMToolV7\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres"`, jeweils **eigenes** `--basetemp` unter
`.j04_m0_evidence/`.

Nur tatsächlich gelaufene Befehle und Ergebnisse:

| # | Befehl | Ergebnis |
| --- | --- | --- |
| 1 | `pytest tests/backend -m "not postgres" -q --basetemp .j04_m0_evidence/backend` | **71 passed, 1 failed** — Failure: `tests/backend/test_documents_concurrency_http.py::test_two_writers_with_same_if_match_have_one_winner` (`sqlite3.ProgrammingError` Thread-Affinität) |
| 2 | `pytest tests/interfaces -m "not postgres" -q --basetemp .j04_m0_evidence/interfaces` | **Collection ERROR** — `ImportError`: `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` fehlt in `modules.documents.wiring` (`tests/interfaces/test_documents_http_gates.py`) |
| 3 | `pytest tests/modules -m "not postgres" -q --basetemp .j04_m0_evidence/modules` | **346 passed** |
| 4 | `pytest tests/platform -m "not postgres" -q --basetemp .j04_m0_evidence/platform` | **97 passed** |
| 5 | `pytest tests/e2e_cli -m "not postgres" -q --basetemp .j04_m0_evidence/e2e_cli` | **28 passed, 20 skipped** (`not_in_m0` Legacy Documents/Training-CLI) |
| 6 | Fokussierter Checkpoint: `pytest tests/backend/test_openapi_contract.py tests/backend/test_documents_reads_http.py tests/backend/test_documents_concurrency_http.py tests/interfaces/test_action_bar_visibility.py tests/interfaces/test_documents_http_reads.py -m "not postgres" -q --basetemp .j04_m0_evidence/focused` | **25 passed** |
| 7 | `git diff --check` | **Exit 0** (nur CRLF-Hinweise auf stderr, keine conflict-marker-/whitespace-Fehler) |

Rohlogs: `.j04_m0_evidence/*_result.txt`.

### Bewertung der Evidence

- Backend-/Modul-/Plattform-/CLI-Zahlen oben ersetzen ältere widersprüchliche Angaben
  (u. a. frühere pauschale „interfaces grün“- und gemischte Checkpoint-Zählungen).
- Der Concurrency-Thread-Test ist im vollständigen Backend-Lauf einmal rot
  (`sqlite3.ProgrammingError`) und im späteren fokussierten Lauf mitgrün — das ist
  **kein** stabiler Live-Nachweis und kein Zwei-Prozess-Evidence.
- Grüne Same-Process-HTTP-Tests zählen **nicht** als Zwei-Client-Live,
  Backend-Neustart-Live, Packaging- oder Word-COM-Evidence.
- PostgreSQL-Liveklassen wurden bewusst **nicht** ausgeführt.

## Verification (M1/G1 Reparaturlauf)

Ausgeführt am 2026-08-07 im Worktree `QMToolV7-j04-m0` mit
`I:\Projekte\QMToolV7\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
Marker `-m "not postgres"` wo angegeben, jeweils **eigenes** `--basetemp` unter
`.j04_m1r_evidence/` bzw. `.tmp/j04-m1r-*`.

Technischer Fokus dieses Abschnitts (nicht rückwirkend die M0-Tabelle oben ändern):

- Policy-on-Lock-`current` für Policy-Mutationen
- ETag-Fortschreibung Metadata/CR
- atomare `new_version`-Semantik (Tokenverbrauch, `superseded_by_version`, gültiger Nachfolger-ETag)
- 16-ACTION-Abdeckung: Coverage-Index plus separate Public-API-/HTTP-Ausführungs- und Negativtests
  (ohne synthetische Acceptance-Bumps)

Scope-/Hash-Evidence:

- M1R0-Ausgangs-SHA-256-Manifest: `.j04_m1r_evidence/m1r0_baseline_hashes.txt`
- Vergleichsprotokoll M1R5: `.j04_m1r_evidence/m1r5_hash_compare.txt`
- Scope-Aussagen beziehen sich **nur** auf die im Manifest gelisteten freigegebenen Dateien.
  Der Worktree enthält weiterhin umfangreiche **fremde** Dirty-/Untracked-Änderungen außerhalb
  dieses Manifests; diese wurden nicht angefasst und bilden **keinen** `DRIFT_COUNT=0` für den
  gesamten Worktree.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| M1R3a | `pytest tests/modules/test_documents_authorization_matrix.py -q --basetemp .j04_m1r_evidence/m1r3_matrix2` | **17 passed** (historisch vor Evidence-Nachschärfung) |
| M1R3b | `pytest tests/backend/test_documents_authorization_http.py -q --basetemp .j04_m1r_evidence/m1r3_http` | **9 passed** (historisch vor Evidence-Nachschärfung) |
| M1R5-AUTH-MATRIX | `pytest tests/modules/test_documents_authorization_matrix.py -q --basetemp .tmp/j04-m1r-auth` | **17 passed** (historisch vor Evidence-Nachschärfung) |
| M1R5-MODULES | `pytest` explizite Liste aller `tests/modules/test_documents_*.py` `-m "not postgres"` `--basetemp .j04_m1r_evidence/m1r5_modules` | **108 passed** |
| M1R5-HTTP-AUTH-CONC | `pytest tests/backend/test_documents_authorization_http.py tests/backend/test_documents_concurrency_http.py tests/backend/test_documents_p4_p9_http.py tests/backend/test_documents_signed_transitions_http.py -m "not postgres" --basetemp .j04_m1r_evidence/m1r5_auth_conc` | **40 passed** (historisch; Gate-Name bewusst nicht „G3“) |
| M1R5-HTTP-READS | `pytest tests/backend/test_documents_http_api.py tests/backend/test_documents_artifacts_http.py tests/backend/test_documents_reads_http.py tests/backend/test_documents_training_read_http.py tests/backend/test_documents_authorization_http.py -m "not postgres" --basetemp .j04_m1r_evidence/m1r5_http_art` | **33 passed** |
| M1R5-BACKEND | `pytest tests/backend -m "not postgres" -q --basetemp .j04_m1r_evidence/m1r5_backend` | **87 passed** |
| M1R5-SCOPE | `git diff --check`; SHA-256 vs `.j04_m1r_evidence/m1r0_baseline_hashes.txt`; keine neuen `xfail`/Skips; keine synthetischen Acceptance-Bumps | **grün** für Manifest-Scope; fremder Dirty-State außerhalb Manifest unberührt |
| M1R-EVIDENCE | `pytest tests/modules/test_documents_authorization_matrix.py tests/backend/test_documents_authorization_http.py -q --basetemp .j04_m1r_evidence/m1r_evidence_fix` | **30 passed** (nach Public-API-/HTTP-Nachschärfung: Reject-Positiv, Assign/Start/Abort Public+HTTP, `open_source` über Artifacts-API) |

### NOT RUN (weiterhin)

- PostgreSQL-Liveklassen / isolierter PG-16-Testcluster-Nachweis
- Backend-Prozess Live-Smoke (Dev/Lab vs Production Swagger)
- Zwei-Client-Prozess + Backend-Neustart
- Word-COM DOCX→PDF End-to-End
- `packaging/build_onedir.py` + gebauter Client gegen separates Backend
- `scripts/golive_gate.py`
- menschliche Abnahme / Status `Accepted`

## Verification (G3 Interfaces-Wiring + Vertragsbereinigung)

Ausgeführt am 2026-08-07 im Worktree `QMToolV7-j04-m0` mit
`I:\Projekte\QMToolV7\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
jeweils eigenem `--basetemp` unter `.j04_g3_evidence/`.

Technischer Fokus (M0-/M1-Evidence-Zahlen oben unverändert):

- `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` in `modules.documents.wiring`;
  `_should_register_sqlite` nur über Konstante; fehlender Opt-in fail-closed
- Vertragsklärung P9: Backend-HTTP Create positiv; reduzierter CLI blockiert mutierende
  Profile-Befehle (`legacy_not_in_m0`); Interface-Test an denselben Scope angeglichen
  (kein CLI-Produktfreischalten)

| # | Befehl | Ergebnis |
| --- | --- | --- |
| G3-HTTP-GATES | `pytest tests/interfaces/test_documents_http_gates.py -m "not postgres" --basetemp .j04_g3_evidence/final_http_gates` | **10 passed** |
| G3-WIRING-REG | `pytest tests/modules/test_documents_module_ports.py tests/platform/test_documents_bootstrap_provenance.py -m "not postgres" --basetemp .j04_g3_evidence/final_wiring_regression` | **5 passed** |
| G3R-PROFILE-CLI | `pytest tests/interfaces/test_documents_workflow_profile_cli.py -m "not postgres" --basetemp .j04_g3_evidence/profile_cli_contract` | **4 passed** |
| G3R-PROFILE-HTTP | `pytest tests/backend/test_documents_p4_p9_http.py -m "not postgres" --basetemp .j04_g3_evidence/profile_backend_contract` | **8 passed** |
| G3R-PROFILE-E2E | `pytest tests/e2e_cli/test_documents_cli.py -k profile_create_is_blocked_under_reduced_m0_scope -m "not postgres" --basetemp .j04_g3_evidence/profile_cli_e2e` | **1 passed** |
| G3-INTERFACES | `pytest tests/interfaces -m "not postgres" --basetemp .j04_g3_evidence/final_interfaces` | **174 passed** |

## Verification (M2 PyQt fail-closed + OpenAPI/If-Match/428)

Ausgeführt am 2026-08-07 im Worktree `QMToolV7-j04-m0` mit
`I:\Projekte\QMToolV7\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
jeweils eigenem `--basetemp` unter `.j04_m2_evidence/`.

Technischer Fokus:

- Backend liefert `available_actions` verpflichtend; HTTP-Client und PyQt fail-closed
  ohne lokale Policy-/Rollen-Fallbacks; Create nur über Backend-Capability
- OpenAPI: exakte If-Match-required-Menge inkl. 428; create-from-template konditional;
  `ErrorDetail.current_state`; required `available_actions` in State-Response-Schemas
- Snapshot nur über `scripts/export_openapi.py` (Validator prüft die Invarianten)

| # | Befehl | Ergebnis |
| --- | --- | --- |
| M2-IFACE-FOCUS | `pytest tests/interfaces/test_documents_http_client_fail_closed.py tests/interfaces/test_documents_workflow_presenter_filters.py tests/interfaces/test_documents_workflow_selection_soft_degrade.py -q --basetemp .j04_m2_evidence/m25_iface_focus` | **15 passed** |
| M2-IFACE-FULL | `pytest tests/interfaces -m "not postgres" -q --basetemp .j04_m2_evidence/m25_iface_full` | **174 passed** |
| M2-OPENAPI-428 | `pytest tests/backend/test_openapi_contract.py tests/backend/test_documents_concurrency_http.py -q --basetemp .j04_m2_evidence/m25_openapi428` | **34 passed** |
| M2-BACKEND-FULL | `pytest tests/backend -m "not postgres" -q --basetemp .j04_m2_evidence/m25_backend_full` | **97 passed** (pypdf DeprecationWarnings) |
| M2-AUTH-MATRIX | `pytest tests/modules/test_documents_authorization_matrix.py -q --basetemp .j04_m2_evidence/m25_auth_matrix` | **19 passed** |
| M2-EXPORT | `python scripts/export_openapi.py` | **Exit 0** |
| M2-SNAPSHOT | `pytest tests/backend/test_openapi_contract.py::test_openapi_snapshot_is_reproducible -q --basetemp .j04_m2_evidence/m25_snapshot` | **1 passed** |
| M2-DIFFCHECK | `git diff --check` | **Exit 0** (nur CRLF-Hinweise, keine Inhaltsfehler) |

### NOT RUN in M2 (weiterhin)

- isolierte PostgreSQL-16-Testinfrastruktur / Live-Backend-/Swagger-Smoke
- Zwei-Client- und Restart-Test
- Word-COM
- Onedir-Paketierung gegen separaten Backenddienst
- `scripts/golive_gate.py`
- menschliche Abnahme / Status `Accepted`

## Verification (M2R Header-/Kommentarstatus-CAS)

Ausgeführt am 2026-08-07 im Worktree `QMToolV7-j04-m0` mit
`I:\Projekte\QMToolV7\.venv\Scripts\python.exe`, `PYTHONPATH=.`,
jeweils eigenem `--basetemp` unter `.j04_m2r_evidence/`.

Technischer Fokus (M2-Evidence bleibt historisch; diese Zahlen sind **M2R**):

- Header: `_refresh_details` speichert `DocumentHeader.updated_at`; `_update_header`
  reicht `if_match` durch Port/HTTP-Client; fehlender Token fail-closed;
  `doc_type`/`control_class` nicht erneut absenden
- Kommentarstatus: `WorkflowCommentListItem.updated_at` → Listenpayload → PyQt-Zeile →
  `expected_updated_at` → `If-Match`; fehlender Token kein Request; stale → 409
- UI: Action-Key-Mappings; kein `_is_qmb`; Feldgruppen Metadata vs Header korrigiert

| # | Befehl | Ergebnis |
| --- | --- | --- |
| M2R-HEADER-CMT | `pytest tests/interfaces/test_m2r_header_comment_cas_consumers.py -q --basetemp .j04_m2r_evidence/m2r4_header` | **12 passed** |
| M2R-IFACE-FOCUS | `pytest …fail_closed …presenter_filters …soft_degrade …control_action_gates …header_comment_cas… -q --basetemp .j04_m2r_evidence/m2r4_iface_focus` | **30 passed** |
| M2R-IFACE-FULL | `pytest tests/interfaces -m "not postgres" -q --basetemp .j04_m2r_evidence/m2r4_iface_full` | **189 passed** |
| M2R-OPENAPI-428 | `pytest tests/backend/test_openapi_contract.py tests/backend/test_documents_concurrency_http.py -q --basetemp .j04_m2r_evidence/m2r4_openapi` | **34 passed** |
| M2R-BACKEND-FULL | `pytest tests/backend -m "not postgres" -q --basetemp .j04_m2r_evidence/m2r4_backend` | **97 passed** |
| M2R-AUTH-MATRIX | `pytest tests/modules/test_documents_authorization_matrix.py -q --basetemp .j04_m2r_evidence/m2r4_auth` | **19 passed** |
| M2R-EXPORT | `python scripts/export_openapi.py` | **Exit 0** |
| M2R-SNAPSHOT | `pytest …::test_openapi_snapshot_is_reproducible -q --basetemp .j04_m2r_evidence/m2r4_snap` | **1 passed** |
| M2R-DIFFCHECK | `git diff --check` | **Exit 0** |
| M2R-HASHSEED | `PYTHONHASHSEED={0,1,42} pytest tests/interfaces/test_documents_http_client_fail_closed.py` | **3× 3 passed** |

### NOT RUN in M2R (weiterhin)

- isolierte PostgreSQL-16-Testinfrastruktur / Live-Backend-/Swagger-Smoke
- Zwei-Client- und Restart-Test
- Word-COM / Onedir / Golive / menschliche Abnahme

## Gesamtabnahme

Status bleibt `Rejected / follow-up required`.

**Dokumentationsmeilenstein M0:** geschlossen.
**Technischer Meilenstein M1/G1:** Execute-Semantik geschlossen.
**Technischer Meilenstein G3:** Wiring + Interfaces geschlossen.
**Technischer Meilenstein M2:** PyQt fail-closed + OpenAPI/428 geschlossen.
**Technischer Meilenstein M2R:** Header-/Kommentarstatus-CAS Consumer geschlossen (12/30/189/34/97/19).
Das bedeutet **nicht** `Ready for acceptance` und **nicht** `Accepted`.

Live-/Packaging-/Human-Gates bleiben **gesperrt**, bis ausdrücklich freigegeben.
Verbindliche Reihenfolge nach Freigabe:

1. ~~**M1 / G1**~~ — technisch abgeschlossen.
2. ~~**G3**~~ — technisch abgeschlossen.
3. ~~**M2 / G2**~~ — technisch abgeschlossen.
4. ~~**M2R**~~ — technisch abgeschlossen (Header-/Kommentar-CAS).
5. Externe Abnahmemeilensteine: isolierte PostgreSQL-16-Testinfrastruktur → Live-Smoke →
   Zwei-Client/Restart → Word-COM → Onedir-Client gegen separaten Backenddienst → menschliche Abnahme.

## Governance

- `docs/J04_M0_PATH_MATRIX.md` (kanonische Pfad-SoT)
- `docs/J04_M0_ALLOWED_ACTIONS_ANALYSIS.md` (Allowed-Actions-Bestandsaufnahme)
- `docs/MASTER_ORCHESTRATION_ROADMAP.md`
- `docs/contracts/j04-m0-openapi.json` (versionierter Vertrag; Export über `scripts/export_openapi.py`)
