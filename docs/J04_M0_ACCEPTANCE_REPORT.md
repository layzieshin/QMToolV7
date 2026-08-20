# J04-M0 Acceptance Report

## Status

Current status: `Ready for acceptance` — **MR00–MR10 PASS; MR09-R2-R4 PASS; MR10-A PASS; MR10-B Human-Smoke PASS; Current checkpoint COMPLETE; aktiver CandidateSha `254c8ea8147130c02b5661e2e467b2641ca83885`; Gesamtstatus READY_FOR_ACCEPTANCE; Accepted unset; FR14 freeze `ed488ed` remains historical**

Allowed values: `Draft` | `Ready for acceptance` | `Accepted` | `Rejected / follow-up required`

`Accepted` bleibt ausschließlich dem menschlichen Abnahmeprozess vorbehalten.
`Ready for acceptance` darf erst nach den Final-/Live-/Packaging-Gates (Meilensteine 3–8)
gesetzt werden.

> **Historische Evidence:** Abschnitte „Verification (Meilenstein 0)“ bis „Verification (M2R)“
> unten dokumentieren frühere Teilläufe (2026-08-06/07) mit teils widersprüchlichen oder
> unvollständigen Rohlogs unter `.j04_*_evidence/`. Diese Zahlen sind **nicht** der aktuelle
> Closure-Lauf. Aktuelle Evidence entsteht unter `build/j04-m0-closure/` ab CP00.
> `build/` enthält Evidence und Pytest-Basetemps; sie sind nicht gestaged und kein
> Produktcode.

## Technical acceptance candidate

Aktiver CandidateSha: **`254c8ea8147130c02b5661e2e467b2641ca83885`** (`254c8ea`) —
`docs(j04-m0): freeze MR09 R3 candidate`.

Dieser Freeze ersetzt den historischen CP08-V10-Candidate `08b04e6` für künftige
nicht-destruktive Bewertung. Der destruktive CP08-V11-Lauf ist **PASS**
(Stamp `20260819T202601488Z`; alle 18 Realprocess-Schritte).

`4db97ea72ffcb18823cd610599752cc1c8e8716d` (`4db97ea`) ist ausschließlich der
historische **MR08-Candidate-Freeze** und für weitere CP08-Läufe ungültig.

Verlauf seit `4db97ea`:

- **MR09-R1** hat den Guard-Preflight erfolgreich passiert und genau einen
  destruktiven Runner gestartet. Dieser Runner ist bei Schritt 14 `pdf_comment_flow`
  mit einem `TimeoutError` fehlgeschlagen.
- **MR09-R2** und **MR09-R2-R1** haben die nicht-destruktive Diagnose und
  Instrumentierung abgeschlossen (**PASS**).
- **MR09-R2-R2** hat Test- und Dokumentintegritätskorrekturen abgeschlossen (**PASS**).
- **MR09-R2-R3** hat verbliebene Statusinkonsistenz beseitigt und durch einen
  Docs-Konsistenztest abgesichert (**PASS**).
- **MR09-R2-R4** hat die Checkpoint-Status-Zuordnung im Konsistenztest gehärtet
  und die False-positive-Lücke durch einen synthetischen Regressionstest geschlossen
  (**PASS**).
- **FreezeCommit** `08b04e6fe28ee86e71759440236b5ca10711fa1a` (`08b04e6`):
  `docs(j04-m0): freeze MR09 retry candidate` — Freeze-Regression-Gate grün —
  1254 passed / 0 failed / 20 skipped; stamp `20260819T150534010Z`.
- **Parent MR09** ist **PASS** (CP08-V11 bestanden).

CP08-V10: **FAILED** (historisch) — Schritt 14 `pdf_comment_flow` Timeout (Lauf `a15cb3f`, Stamp `20260819T155102306Z`).
MR09-R3 hat die Ursache (stdout-Pipe-Backpressure im Harness) behoben.
CP08-V11: **PASS** — alle 18 Realprocess-Schritte grün (Lauf-HEAD `be8fb01`, Stamp `20260819T202601488Z`).
Gesamtstatus: **READY_FOR_ACCEPTANCE**. `ACCEPTED` ist nicht gesetzt.
Current checkpoint: **COMPLETE**.

Historical FR14 freeze `ed488ede47063c22ec0b8b9d2a72be25224f6098` (`ed488ed`)
remains history only.

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

## WR05 — Interactive Word COM readiness (PASS)

The recovery was completed in the normal interactive desktop session 1. No DOCX/PDF E2E was
run and no existing Word session was taken over.

| Check | Result |
| --- | --- |
| Office installation | Office LTSC Professional Plus 2024 x64, build `16.0.17932.20884` |
| Safe-mode recovery | **PASS**; Word started visibly and closed normally |
| Add-ins | Acrobat PDFMaker/Citavi HKCU values restored to snapshot; OneNote unchanged; no causal effect found |
| `DispatchEx('Word.Application')` | **PASS**; `Word.Version` readable as `16.0` |
| Cleanup | Owned COM instance quit; no existing session was adopted |
| DOCX/PDF E2E | **NOT RUN** (remains a CP08-V2 gate) |
| Readiness | **PASS** for the interactive COM boundary |

The failed agent-context probe (`0x80080005`) and its targeted orphan cleanup remain historical
evidence. The successful interactive result is recorded in local evidence under
`build/j04-m0-closure/word-com-readiness/` (not committed). Overall status remains
`NOT_READY` until FR08 and the single CP08-V2 run complete.

## FR08 — Remediated acceptance candidate freeze

The freeze tree contains R1 (`fbea360`), R2 (`30b73e9`), WR05 documentation (`034425f`), and
the known unchanged stat-only files. The following checkpoint commit freezes this technical
candidate; its full SHA is recorded in the documentation-only follow-up immediately after the
commit. No product or test changes are permitted after this freeze.

| Item | Status |
| --- | --- |
| Focused gates | **46 passed** (`build/j04-m0-closure/freeze-r2-elevated-verify`) |
| Word readiness | **PASS** (interactive WR03/WR05); DOCX/PDF E2E **NOT RUN** |
| Candidate SHA | **`fe172c9fc3b5753b9b6d4b9b1a1d026760257c37` (`fe172c9`)** |
| CP08-V2 | **NOT STARTED** |

## CP08-V2 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `fe172c9fc3b5753b9b6d4b9b1a1d026760257c37`.
Gate policy was applied: no repair and no continuation after the first blocked mandatory step.

| Step | Result |
| --- | --- |
| 1. PostgreSQL live | **PASS** — guard preflight major 18; **51 passed** |
| 2. Full real-process E2E | **FAILED/ABORTED** — pytest could not use the selected basetemp because of `WinError 5` access denied; cleanup also failed. No reliable scenario result was accepted. |
| 3. Word COM live, 4. Onedir, 5. Regression, 6. Golive, 7. visible client | **NOT RUN** (gate stopped at step 2) |

No product or test repair was made during the gate. The candidate remains **`NOT_READY`**; a new
remediation checkpoint and new freeze are required before any CP08 retry.

## Verification (CP08-R3 — isolate realprocess workspace)

Test-only. Observed CP08-V2 failure: pytest basetemp **`WinError 5`** on use and cleanup.
Child-process locks are a plausible explanation, not proven. Full-gate workspace is now
`build/j04-m0-closure/cp08-realprocess-ws/<UTC-timestamp>-<uuid>/` via
`allocate_realprocess_workspace()` (`resolve()` under closure evidence root; never reuse/delete).

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R3-FOCUS | harness + scenario unit + realprocess excluded marker; fresh `--basetemp` | **18 passed** (`cp08-r3-20260817T125918964Z`) |
| CP08R3-SKIP | `j04_final_acceptance` without opt-in; fresh `--basetemp` | **1 skipped**, exit 0 |
| CP08R3-DIFFCHECK | `git diff --check` | **Exit 0** (CRLF warnings only on known stat-only files) |

No freeze. No CP08-V3. **R3 PASS ≠ Freeze / CP08-V3 / ACCEPTED.**

CP08-R3 commit: `c3d6587` — `test(j04-m0): isolate realprocess workspace from pytest basetemp`

## FR09 — R1+R2+R3 technical freeze

The freeze tree contains R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), WR05 documentation
(`034425f`), and the known unchanged stat-only files. The following checkpoint commit freezes
this technical candidate; its full SHA is recorded in the documentation-only follow-up
immediately after the commit. No product or test changes are permitted after this freeze.

| Item | Status |
| --- | --- |
| Focused gates | **50 passed** (`build/j04-m0-closure/freeze-r3-20260817T171311893Z`) |
| Word readiness | **PASS** (interactive WR03/WR05); DOCX/PDF E2E **NOT RUN** |
| Candidate SHA | **`1a22d3809683d16ad9354d609f6ce2d2af7c053a` (`1a22d38`)** |
| CP08-V3 | **FAILED** (see below) |
| `ACCEPTED` | **not set** |

## CP08-V3 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `1a22d3809683d16ad9354d609f6ce2d2af7c053a`.
Gate policy was applied: no repair and no continuation after the first failed mandatory step.

The run did **not** fail because the operator “used pytest wrong” in an undocumented way.
Repository acceptance documentation prescribed a **direct pytest** invocation. That start
contract is inconsistent with the PostgreSQL safety model:

- The documented realprocess command does not go through `scripts/run_postgres_live_tests.py`.
- The PG runner injects `QMTOOL_PG_TEST_RESET` only after a successful read-only preflight
  and **only** into its pytest child. The value is not left behind for a separately started
  pytest process.
- `prepare_live_environment()` correctly requires the RESET opt-in because it performs
  destructive schema and role operations. The guard must not be weakened and RESET must not
  be set automatically or globally.

Observed stop: `pg_bootstrap` (RESET missing). Backend start and Word COM were **not reached**.
CP08-V3 therefore produced **no Word evidence**. Historical Word-readiness findings are not
the cause of this run.

| Step | Result |
| --- | --- |
| 1. PostgreSQL live | **PASS** — guard preflight major 18; **51 passed**; evidence `build/j04-m0-closure/cp08-v3-pg-live-runner.log` |
| 2. Full real-process E2E | **FAILED** at start contract / `pg_bootstrap` (`QMTOOL_PG_TEST_RESET` unset in the separate pytest process). Evidence: `build/j04-m0-closure/cp08-v3-realprocess.log`, basetemp `build/j04-m0-closure/cp08-v3-pytest-20260817T171915206Z` |
| 3. Word COM live, 4. Onedir, 5. Regression, 6. Golive, 7. visible client | **NOT RUN** (gate stopped at step 2; Word not reached) |

No product or test repair was made during the gate. At abort the candidate was **`NOT_READY`**.
Word COM was **not reached** and is not the cause. After CP08-R4 the start contract is
repaired; remaining **`NOT_READY`** is because a new freeze and a successful CP08 run were
still outstanding at that point. **`ACCEPTED` was not set.**

## Verification (CP08-R4 — acceptance start contract)

Test-only. The realprocess gate must start through the existing PG runner
(`--j04-final-acceptance` + fresh `--basetemp`). RESET remains child-only after preflight.
The runner does not set Word COM live opt-in. Guard and `prepare_live_environment()` are
unchanged.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R4-CONTRACT | runner + destructive-guard + harness/scenario unit; fresh `--basetemp` | **51 passed** (`cp08-r4-20260817T182342311Z`) |

**No freeze. No CP08 retry.** Next allowed sequence after this checkpoint is accepted:
new technical freeze, then exactly one CP08 run. A Word step may be judged only from
evidence of a run that actually reached it.

## FR10 — R1–R4 technical freeze

The freeze tree contains R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d`,
docs `63dda17`), WR05 documentation (`034425f`), and the known unchanged stat-only files.
The following checkpoint commit freezes this technical candidate; its full SHA is recorded
in the documentation-only follow-up immediately after the commit. No product or test changes
are permitted after this freeze.

| Item | Status |
| --- | --- |
| Focused gates | **83 passed** (`build/j04-m0-closure/freeze-r4-20260817T182715064Z`) |
| Word readiness | **PASS** (interactive WR03/WR05); DOCX/PDF E2E **NOT RUN** |
| Candidate SHA | **`1bd8aa0f026249cd8e635d4a3c3ad34857ea953e` (`1bd8aa0`)** |
| CP08-V4 | **FAILED** (see below) |
| `ACCEPTED` | **not set** |

## CP08-V4 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `1bd8aa0f026249cd8e635d4a3c3ad34857ea953e`.
Lauf-SHA at gate start: `fd3aeb8bd81bb6b48a8dda0f41dc0613cae9f209` (FR10 SHA-record docs only).
Gate policy: no repair and no continuation after the first failed mandatory step.
Realprocess started through `scripts/run_postgres_live_tests.py --j04-final-acceptance`.

The start contract held: `preconditions` and `pg_bootstrap` **PASS**. Backend started and
health/openapi **PASS**. Stop at `bootstrap_admin_login`: backend log shows `POST /auth/login`
HTTP 200 then `GET /auth/me` HTTP **409**. Word COM was **not reached** and is not a finding
of this run. Pre-existing WINWORD PID 4756 was present and **not** terminated.

| Step | Result |
| --- | --- |
| 1. PostgreSQL live | **PASS** — preflight major 18; **51 passed**; `build/j04-m0-closure/cp08-v4-pg-live-runner.log` |
| 2. Full real-process E2E | **FAILED** at `bootstrap_admin_login` (`GET /auth/me` 409 after login 200). Workspace `build/j04-m0-closure/cp08-realprocess-ws/20260817T183206770668Z-3da54ae0ec944243aeab4f6f96c132a3` |
| 3. Word COM live, 4. Onedir, 5. Regression, 6. Golive, 7. visible client | **NOT RUN** (gate stopped at step 2; Word not reached) |

Overall **`NOT_READY`**: after the start-contract remediation and FR10 freeze there is no
successful CP08 run. Historical CP08-V3 aborted on the acceptance start contract, not Word
COM. **`ACCEPTED` was not set.**

Overall **`NOT_READY`**: after the start-contract remediation there is not yet a successful
CP08 run. Historical CP08-V3 aborted on the acceptance start contract, not Word COM.

## Verification (CP08-R5 — bootstrap-admin handshake)

Test-only. Product bootstrap still sets `must_change_password=True`. The realprocess step
`bootstrap_admin_login` now completes login → `/auth/me` 409 `password_change_required` →
`POST /auth/change-password` 204 → `/auth/me` 200, and later admin re-logins use the changed
password. Failures include a redacted response body. Product auth, Word, packaging, and the
PG guard are unchanged.

| # | Check | Finding |
| --- | --- | --- |
| 1 | 409 body | Product: `password_change_required`. V4 harness did not log the body; R5 failures include a redacted body. |
| 2 | Token header | Login token is sent as `Authorization: Bearer`; missing token would be 401. |
| 3 | Owner | `session_ops` `must_change_password` via `require_user_context_normal`. |
| 4 | Persistence | Login 200 means a session was issued; bootstrap admin remains `must_change_password=True` until change-password. |
| 5 | Coverage gap | Auth API tests already expect the 409 handshake; realprocess did not. |
| 6 | Smallest test | Mock HTTP `complete_bootstrap_admin_session` (not a second live CP08). |

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R5-HANDSHAKE | scenario/harness/realprocess unit + `test_auth_api`; fresh `--basetemp`; J04/Word opt-ins unset | **28 passed** (`cp08-r5-20260817T195540932Z`) |

**No freeze. No CP08 retry in this checkpoint.** Next allowed sequence after this checkpoint is accepted:
new technical freeze, then exactly one CP08 run. A Word step may be judged only from
evidence of a run that actually reached it.

CP08-R5 commit: `34f39c0`

## FR11 — R1–R5 technical freeze

The freeze tree contains R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d`,
docs `63dda17`), R5 (`34f39c0`, docs `164a7c9`), WR05 documentation (`034425f`), and the known
unchanged stat-only files. The following checkpoint commit freezes this technical candidate;
its full SHA is recorded in the documentation-only follow-up immediately after the commit. No
product or test changes are permitted after this freeze.

| Item | Status |
| --- | --- |
| Focused gates | **93 passed** (`build/j04-m0-closure/freeze-r5-20260817T195901962Z`) |
| Word readiness | **PASS** (interactive WR03/WR05); DOCX/PDF E2E **NOT RUN** |
| Candidate SHA | **`c263ff550a81eccfc5bb68f2ffd2e030e8e51427` (`c263ff5`)** |
| CP08-V5 | **FAILED** (see below) |
| `ACCEPTED` | **not set** |

## CP08-V5 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `c263ff550a81eccfc5bb68f2ffd2e030e8e51427`.
Lauf-SHA at gate start: `05aed9ff7b7f4dc431543fcbb915326e3eec4fd6` (FR11 SHA-record docs only).
Gate policy: no repair and no continuation after the first failed mandatory step.
Realprocess started through `scripts/run_postgres_live_tests.py --j04-final-acceptance`.
Word COM live opt-in was set; the Word step was **not reached**.

The start contract and R5 bootstrap handshake held: `preconditions`, `pg_bootstrap`,
`backend_start`, `health_and_openapi`, `bootstrap_admin_login` **PASS**. Backend log shows
`POST /auth/login` 200, `GET /auth/me` 409, `POST /auth/change-password` 204, `GET /auth/me`
200, then directory seed and workflow profile **PASS**. Stop at `document_baseline_flow`:
backend log shows `POST /documents/versions/create` HTTP **403**. The harness fail log only
says `version payload missing etag` (no status/body). Word COM was **not reached** and is not
a finding of this run.

| Step | Result |
| --- | --- |
| 1. PostgreSQL live | **PASS** — preflight major 18; **51 passed**; `build/j04-m0-closure/cp08-v5-pg-live-runner.log` |
| 2. Full real-process E2E | **FAILED** at `document_baseline_flow` (`POST /documents/versions/create` 403; harness: missing etag). Workspace `build/j04-m0-closure/cp08-realprocess-ws/20260817T200418444108Z-8540fb06cf7846699a99cac847f51887` |
| 3. Word COM live, 4. Onedir, 5. Regression, 6. Golive, 7. visible client | **NOT RUN** (gate stopped at step 2; Word not reached) |

Overall **`NOT_READY`**: after FR11 there is no successful CP08 run. Historical CP08-V3 aborted
on the acceptance start contract, not Word COM. R5 handshake is proven in this run.
**`ACCEPTED` was not set.**

## Verification (CP08-R6 — document-create QMB actor)

Test-only. Product create still requires effective QMB. The realprocess step
`document_baseline_flow` now uses the seeded `qmb` token. Non-200 version responses fail with
`status=` and `error=` before etag parse. Product authorization is unchanged.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R6-CREATE | scenario/harness/realprocess unit + documents authorization HTTP; fresh `--basetemp`; J04/Word opt-ins unset | **36 passed** (`cp08-r6-20260818T042343176Z`) |

**No freeze. No CP08 retry in this checkpoint.** Next allowed sequence: new technical freeze, then exactly one CP08 run.

CP08-R6 commit: `e28a44d`

## FR12 — R1–R6 technical freeze

The freeze tree contains R1–R5 plus R6 (`e28a44d`, docs `1f72451`), WR05 documentation, and the
known unchanged stat-only files. The following checkpoint commit freezes this technical
candidate; its full SHA is recorded immediately after. No product or test changes are permitted
after this freeze.

| Item | Status |
| --- | --- |
| Focused gates | **108 passed** (`build/j04-m0-closure/freeze-r6-20260818T042711993Z`) |
| Word readiness | **PASS** (interactive WR03/WR05); DOCX/PDF E2E **NOT RUN** |
| Candidate SHA | **`b63d9a16f87e8e9a12942d41101ee793d1fbb209` (`b63d9a1`)** |
| CP08-V6 | **FAILED** (see below) |
| `ACCEPTED` | **not set** |

## CP08-V6 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `b63d9a16f87e8e9a12942d41101ee793d1fbb209`.
Lauf-SHA at gate start: `049c0fd`. Gate policy: no repair and no continuation after the first
failed mandatory step. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set;
the Word step was **not reached**.

R6 document create held: `POST /documents/versions/create` **200**, then import-pdf, assign-roles
and start **200**. Stop at `etag_concurrency_race`: fail log `sorted expected 1 argument, got 2`
(`sorted(int, int)` instead of a two-item iterable). Backend log shows the two race
assign-roles as **200** and **409**. The pytest detail was only `TypeError` because the generic
except stores `type(exc).__name__`. Word COM was **not reached**.

| Step | Result |
| --- | --- |
| 1. PostgreSQL live | **PASS** — preflight major 18; **51 passed**; `build/j04-m0-closure/cp08-v6-pg-live-runner.log` |
| 2. Full real-process E2E | **FAILED** at `etag_concurrency_race` (`TypeError` / `sorted` arity). Workspace `build/j04-m0-closure/cp08-realprocess-ws/20260818T043346608779Z-d3a488be334042e7ab81a38da5b9ffb7` |
| 3. Word COM live, 4. Onedir, 5. Regression, 6. Golive, 7. visible client | **NOT RUN** (gate stopped at step 2; Word not reached) |

Overall **`NOT_READY`**. R6 create is proven in this run. **`ACCEPTED` was not set.**

## Verification (CP08-R7 — etag race harness)

Test-only. Product race in V6 already returned HTTP 200 and 409. The abort was
`sorted(int, int)`. Both race bodies now keep the seeded editor/reviewer/approver assignment.
Unit tests drive `_step_etag_concurrency_race` with fake workers for 200/409, 409/200, and
200/200. Product authorization is unchanged.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R7-RACE | scenario/harness unit + documents concurrency HTTP; fresh `--basetemp`; J04/Word opt-ins unset | **54 passed** (`cp08-r7-20260818T045911092Z`) |
| CP08R7-DIFFCHECK | `git diff --check` on the two R7 test files | **Exit 0** |

Independent review confirmed the R7 content diff and code. Evidence contents were ACL-blocked
in that review session; **54 passed** is recorded from the generated R7 evidence path.

CP08-R7 commit: `f5dcfa8`

Docs SHA record: `ae5be41`

## FR13 — R1–R7 technical freeze

The freeze tree contains R1–R6 plus R7 (`f5dcfa8`, docs `ae5be41`), WR05 documentation, and the
known unchanged stat-only files. The following checkpoint commit freezes this technical
candidate; its full SHA is recorded immediately after. No product or test changes are permitted
after this freeze.

| Item | Status |
| --- | --- |
| Focused gates | **137 passed** (`build/j04-m0-closure/freeze-r7-20260818T051722279Z`) |
| Word readiness | **PASS** (interactive WR03/WR05); DOCX/PDF E2E **NOT RUN** |
| Candidate SHA | **`cd3a3769c4d3b470f227bb25464785926b9584db` (`cd3a376`)** |
| CP08-V7 | **FAILED** (see below) |
| `ACCEPTED` | **not set** |

## CP08-V7 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `cd3a3769c4d3b470f227bb25464785926b9584db`.
Lauf-SHA at gate start: `45df9d6`. Gate policy: no repair and no continuation after the first
failed mandatory step. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set;
the Word step was **not reached**.

R7 etag race held: backend assign-roles **200** then **409**; harness detail
`one winner and one 409 on shared etag`. Document create **held**. Stop at
`artifacts_transport`: `GET /documents/versions/J04-ACCEPT-DOC/1/artifacts` **404**
`{"detail":{"error":"not_found","message":"document version not found"}}`. Word COM was
**not reached**.

| Step | Result |
| --- | --- |
| 1. PostgreSQL live | **PASS** — preflight major 18; **51 passed**; `build/j04-m0-closure/cp08-v7-pg-live-runner.log` |
| 2. Full real-process E2E | **FAILED** at `artifacts_transport` (HTTP 404 `not_found`). Workspace `build/j04-m0-closure/cp08-realprocess-ws/20260818T052422861269Z-eeb566a9bf8e40ef804915b28ded29ae` |
| 3. Word COM live, 4. Onedir, 5. Regression, 6. Golive, 7. visible client | **NOT RUN** (gate stopped at step 2; Word not reached) |

Overall **`NOT_READY`**. R7 race is proven in this run. **`ACCEPTED` was not set.**

CP08-V7 failed **before** artifact transport on a harness identity error. Document version
and `SOURCE_PDF` existed. Assignments stored login names `editor` / `reviewer` / `approver`.
PostgreSQL user ids are UUIDs. Visibility compared `actor_user_id` to those values, so the
IN_PROGRESS version was correctly invisible to the editor. The route masked that as
`404 document version not found` and did not invoke the artifact API.

## Verification (CP08-R8 — workflow user_id assignments)

Test-only. After each role login the harness calls `GET /auth/me`, validates `username`, and
stores `user_id`. Baseline and both race `assign-roles` bodies use those ids, never login
usernames. Training receipt matches the stored editor `user_id`. Race contract remains
`[200, 409]`. Product authorization is unchanged.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R8-IDS | scenario unit + documents authorization HTTP + documents artifacts HTTP; fresh `--basetemp`; JUnit + log outside basetemp; J04/Word opt-ins unset | **42 passed** (`cp08-r8-results-20260818T055709926Z/junit.xml`, `tests="42" failures="0"`) |
| CP08R8-DIFFCHECK | `git diff --check` on the four R8 files | **Exit 0** |

**No freeze and no CP08-V8 at this documentation checkpoint.** Word remains not reached.

CP08-R8 commit: `31dc273`

Docs SHA record: `83b7b1a`

## FR14 — R1–R8 technical freeze

The freeze tree contains R1–R7 plus R8 (`31dc273`, docs `83b7b1a`), WR05 documentation, and the
known unchanged stat-only files. The following checkpoint commit freezes this technical
candidate; its full SHA is recorded immediately after. No product or test changes are permitted
after this freeze.

| Item | Status |
| --- | --- |
| Focused gates | **144 passed** (`build/j04-m0-closure/freeze-r8-results-20260818T061803564Z/junit.xml`) |
| Word readiness | **PASS** (interactive WR03/WR05); DOCX/PDF E2E **NOT RUN** |
| Candidate SHA | **`ed488ede47063c22ec0b8b9d2a72be25224f6098` (`ed488ed`)** |
| CP08-V8 | **FAILED** (see below) |
| `ACCEPTED` | **not set** |

## CP08-V8 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `ed488ede47063c22ec0b8b9d2a72be25224f6098`.
Lauf-SHA at gate start: `0cb4179`. Gate policy: no repair and no continuation after the first
failed mandatory step. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set;
the Word step was **not reached**.

R8 artifacts held: `artifacts listed count=1`. Race **held**. Signature **held**. Stop inside
`training_read_receipt`, but **before** any out-of-scope training read / receipt calls. After successful
`editing-complete`, the scenario step kept one client pinned to the editor token. Although it
passed reviewer and approver headers, `request_raw()` overwrote `Authorization` from
`self._token`, so `review/accept` was sent as the editor and correctly rejected with **403**.
The later `version payload missing etag` was only secondary harness diagnostics. Word COM was
**not reached**.

| Step | Result |
| --- | --- |
| 1. PostgreSQL live | **PASS** — preflight major 18; **51 passed**; `build/j04-m0-closure/cp08-v8-pg-live-runner.log` |
| 2. Full real-process E2E | **FAILED** at `training_read_receipt` (`review/accept` 403; harness missing etag). Workspace `build/j04-m0-closure/cp08-realprocess-ws/20260818T062441411509Z-3b4e870e746e4d50a646dce4e8d935a1` |
| 3. Word COM live, 4. Onedir, 5. Regression, 6. Golive, 7. visible client | **NOT RUN** (gate stopped at step 2; Word not reached) |

Overall **`NOT_READY`**. R8 artifacts and product authorization are proven in this run.
**`ACCEPTED` was not set.**

## Verification (CP08-R9 — scope-corrected release flow)

Test-only. The realprocess gate now proves document release flow only: separate authenticated
clients for editor, reviewer, and approver, ending at `APPROVED`. `editing-complete`,
`review/accept`, and `approval/accept` each fail closed through `require_version_success()`
before ETag parsing, so a 403 now surfaces with action, HTTP status, and redacted error code
instead of `missing etag`. Training consumers and read-receipt integration are explicitly out
of scope for J04-M0 acceptance.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| CP08R9-SCOPE | scenario unit + documents authorization HTTP; fresh `--basetemp`; JUnit + log outside basetemp; J04/Word opt-ins unset | **41 passed** (`cp08-r9-scope-results-20260818T082720948Z/junit.xml`, `tests="41" failures="0"`) |
| CP08R9-DIFFCHECK | `git diff --check` on the seven R9 files | **Exit 0** |

An earlier actor-only verification hit an environmental `WinError 10053` in a local test HTTP
handler before the retry succeeded; the current scope-corrected run above is green.

R9 is now technically ready for the controlled commit sequence. Word remains not reached.

## Verification (MR07 — Realprocess harness M0 catalog)

Test- and documentation-only. The acceptance catalog is now exactly 18 M0 steps.
Training, `/documents/reads/*`, read receipts, change requests, archive, and the
Word COM live boundary are gone from catalog and handlers. Workflow transitions
require signatures. Artifact content is downloaded and hashed. Restart expects
`APPROVED`. The CP08-R9 actor split (separate editor/reviewer/approver clients)
is kept.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| MR07-GATE-1 | focused MR07 pytest; stamp `20260818T121816713Z` | **FAILED (1)** — `WinError 10053` in bootstrap HTTP handler (`mr07-results-20260818T121816713Z/junit.xml`, `tests="73" failures="1"`) |
| MR07-GATE-2 | same command; stamp `20260818T121957135Z` | **73 passed** (`mr07-results-20260818T121957135Z/junit.xml`, `tests="73" failures="0"`) |
| MR07-LEDGER | docs-consistency + scenario-unit after ledger PASS; stamp `20260818T122324312Z` | **43 passed** (`mr07-ledger-results-20260818T122324312Z/junit.xml`, `tests="43" failures="0"`) |
| MR07-DIFFCHECK | `git diff --check` | **Exit 0** |

Not run in MR07: PostgreSQL reset, CP08-V9, Word COM conversion, packaging, freeze, commit, push, PR.

Known remainder (not an MR07 product change): live `import-docx` still depends on the existing backend converter-capability check. Native `word/comments.xml` sync is covered over HTTP in the harness; a real Word-COM conversion run stays outside MR07 (MR09/MR10). `DocumentsPoolApi.get_header_for_actor()` remains an MR03 extension of an existing public surface. Internal legacy storage-key reads remain a limited compatibility remainder.

## Verification (MR07-R1 — signature passwords under require_password=True)

MR07 catalog evidence above is retained. Review found that `_sign_intent_body` sent
`password: None` while production signature settings default to `require_password=True`.
`SignatureExecuteOps` rejects a missing password. The MR07 HTTP mock only checked that
`sign_intent` existed; the same-process backend test had set `require_password=False`.

Remediation is test-only: required `_sign_intent_body(password: str)`, actor passwords on
editor/reviewer/approver transitions, `X-Signature-Password` on asset activation, mocks
assert the password per actor, and the backend signed-transition tests run with
`require_password=True`. Signature policy is not weakened.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| MR07-R1-1 | focused R1 pytest; stamp `20260818T134857083Z` | **FAILED (1)** — inspect hit verify-step instead of `_activate_signature_asset` (`mr07-r1-results-20260818T134857083Z/junit.xml`, `tests="53" failures="1"`) |
| MR07-R1-2 | same R1 command; stamp `20260818T134943927Z` | **53 passed** (`mr07-r1-results-20260818T134943927Z/junit.xml`, `tests="53" failures="0"`) |
| MR07-GATE-RERUN | original MR07 gate; stamp `20260818T135020994Z` | **75 passed** (`mr07-results-20260818T135020994Z/junit.xml`, `tests="75" failures="0"`) |
| MR07-R1-DIFFCHECK | `git diff --check` | **Exit 0** |

Not run in MR07-R1: PostgreSQL reset, CP08-V9, Word COM, packaging, freeze, commit, push, PR, MR08.

## Verification (MR08 — non-destructive regression; freeze not approved)

MR08 started 2026-08-18T14:07:28Z and ended 2026-08-18T14:30:27Z on HEAD `3bf6518`.
Scope was contracts, CLI-E2E, and full non-live regression plus diff/scope review.
No product change. Gate 3 failed; candidate freeze is **not** approved. Overall
status remains **`NOT_READY`**. Adversarial review was not started (fail-fast).

| # | Befehl | Ergebnis |
| --- | --- | --- |
| MR08-LEDGER | docs-consistency after IN_PROGRESS; stamp `20260818T140815286Z` | **6 passed** (`mr08-ledger-results-20260818T140815286Z/junit.xml`, `tests="6" failures="0"`) |
| MR08-G1 | contracts/architecture; stamp `20260818T140907659Z` | **53 passed / 0 failed / 0 skipped** (`mr08-contract-results-20260818T140907659Z/junit.xml`) |
| MR08-G2 | CLI-E2E `tests/e2e_cli`; stamp `20260818T140950379Z` | **31 passed / 0 failed / 20 skipped** (`mr08-cli-results-20260818T140950379Z/junit.xml`); skips: 16 legacy documents CLI, 3 auth matrix, 1 training `not_in_m0` |
| MR08-G3 | full non-live `pytest -m "not postgres and not j04_final_acceptance"`; stamp `20260818T141720756Z` | **FAILED** 1208 passed / 1 failed / 20 skipped (`mr08-regression-results-20260818T141720756Z/junit.xml`); `test_open_source_reauthorization_on_artifact_read_path` → `DocumentConflictError` |
| MR08-FAILED-LEDGER | docs-consistency after FAILED; stamp `20260818T143406754Z` | **6 passed** (`mr08-failed-ledger-results-20260818T143406754Z/junit.xml`); not a Gate-3 retry |

Classification: **test error** (stale `state` after MR04 import CAS).

## Verification (MR08-R1 — test-only ETag remediation; freeze not approved)

**Regression PASS after MR08-R1 – Candidate Freeze pending explicit user approval.**
Overall status remains **`NOT_READY`**. Product CAS, import, and workflow were
not changed. The test now uses the import return value and asserts the ETag
advanced. Adversarial review of the 36-file diff: **PASS** with two P3
remainders outside R1 scope (unsandboxed `storage_key` join fallback;
template-create mutate without `owner_or_privileged` on the lock). Freeze is
**not** approved.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| MR08-R1-LEDGER | docs-consistency after R1 IN_PROGRESS; stamp `20260818T144714476Z` | **6 passed** (`mr08-r1-ledger-results-20260818T144714476Z/junit.xml`) |
| MR08-R1-A | single previously red test; stamp `20260818T144754849Z` | **1 passed / 0 failed / 0 skipped** (`mr08-r1-target-results-20260818T144754849Z/junit.xml`) |
| MR08-R1-B | authorization + infrastructure; stamp `20260818T144816993Z` | **71 passed / 0 failed / 0 skipped** (`mr08-r1-focused-results-20260818T144816993Z/junit.xml`) |
| MR08-R1-G3 | full non-live regression; stamp `20260818T144851070Z` | **1209 passed / 0 failed / 20 skipped** (`mr08-r1-regression-results-20260818T144851070Z/junit.xml`); skips: 16 legacy documents CLI, 3 auth matrix, 1 training `not_in_m0` |
| MR08-R1-FINAL-LEDGER | docs-consistency after R1 closeout; stamp `20260818T151044314Z` | **6 passed** (`mr08-r1-final-ledger-results-20260818T151044314Z/junit.xml`) |

## Verification (MR08-R2 — template-create authorization; freeze not approved)

**MR08-R2 PASS.** Template-create authorization now runs in
`DocumentsWorkflowApi.create_from_template` before missing-target create and,
for existing targets, under the lock via `owner_or_privileged=True` before the
ETag compare. Adversarial review of the R2 diff is PASS; the overall review
stays open until MR08-R3. No candidate freeze. Overall **`NOT_READY`**.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| MR08-R2-LEDGER | docs-consistency after R2 IN_PROGRESS; stamp `20260818T152445755Z` | **6 passed** (`mr08-r2-ledger-results-20260818T152445755Z/junit.xml`) |
| MR08-R2-A1 | template/create_from_template; stamp `20260818T152657988Z` | **FAILED** 1 failed (module success path missing storage_port) |
| MR08-R2-A2 | template/create_from_template retry; stamp `20260818T152746610Z` | **4 passed / 0 failed / 0 skipped** (`mr08-r2-target-results-20260818T152746610Z/junit.xml`) |
| MR08-R2-B | authorization + concurrency + OpenAPI + matrix; stamp `20260818T152830890Z` | **110 passed / 0 failed / 0 skipped** (`mr08-r2-focused-results-20260818T152830890Z/junit.xml`) |
| MR08-R2-C | docs-consistency after R2 closeout; stamp `20260818T153303900Z` | **6 passed** (`mr08-r2-ledger-final-results-20260818T153303900Z/junit.xml`) |

## Verification (MR08-R3 — resolver-less artifact storage fallback; freeze not approved)

**MR08-R3 PASS.** Parent **MR08 PASS.** Candidate-Freeze is `4db97ea72ffcb18823cd610599752cc1c8e8716d`
(`4db97ea`). Historical FR14 candidate remains `ed488ed`. Current checkpoint **MR09**
(TODO, not started). Overall **`NOT_READY`**. After Candidate-Freeze no code/test change.

| # | Befehl | Ergebnis |
| --- | --- | --- |
| MR08-R3-LEDGER | docs-consistency after R3 IN_PROGRESS; stamp `20260818T171938978Z` | **6 passed** (`mr08-r3-ledger-results-20260818T171938978Z/junit.xml`) |
| MR08-R3-A | `-k resolverless_artifact_path`; stamp `20260818T172123561Z` | **PASS** 5 passed / 8 subtests; JUnit `tests="13" failures="0" errors="0"` (`mr08-r3-target-results-20260818T172123561Z/junit.xml`) |
| MR08-R3-B | artifact/storage/signature; stamp `20260818T172135322Z` | **PASS** 57 passed / 8 subtests; JUnit `tests="65" failures="0" errors="0"` (`mr08-r3-artifact-results-20260818T172135322Z/junit.xml`) |
| MR08-R3-C1 | first complete non-live regression; stamp `20260818T172223274Z` | **PASS** JUnit `tests="1246" failures="0" errors="0" skipped="20" time="935.721"` (`mr08-r3-regression-results-20260818T172223274Z/junit.xml`); previously omitted from the BLOCKED report |
| MR08-R3-C2 | overlapping second full run; stamp `20260818T173505528Z` | **not serial** overlap 172.425 s with C1; JUnit `tests="1246" failures="2" errors="0" skipped="20" time="1028.502"` (`mr08-r3-regression-results-20260818T173505528Z/junit.xml`); WinError 10053; not the first complete attempt |
| MR08-R3-C-ISO | isolate the two overlapping failures; stamp `20260818T175336276Z` | **2 passed** (`mr08-r3-c-isolate-results-20260818T175336276Z/junit.xml`); no product/test change |
| MR08-R3-LEDGER-BLOCKED | docs-consistency after mistaken R3 BLOCKED; stamp `20260818T175701619Z` | **6 passed** (`mr08-r3-ledger-blocked-results-20260818T175701619Z/junit.xml`) |
| MR08-R3-LEDGER-FINAL | docs-consistency after BLOCKED closeout note; stamp `20260818T175729687Z` | **6 passed** (`mr08-r3-ledger-final-results-20260818T175729687Z/junit.xml`) |
| MR08-R3-SERIAL-LEDGER | docs-consistency after history correction; stamp `20260818T185736086Z` | **6 passed** (`mr08-r3-serial-ledger-results-20260818T185736086Z/junit.xml`) |
| MR08-R3-C-SERIAL | serial confirmation non-live regression; stamp `20260818T185750907Z` | **PASS** 988 passed / 20 skipped / 52 deselected / 238 subtests; JUnit `tests="1246" failures="0" errors="0" skipped="20" time="705.366"` (`mr08-r3-serial-regression-results-20260818T185750907Z/junit.xml`); no concurrent pytest |
| MR08-R3-SERIAL-LEDGER-FINAL | docs-consistency after R3 PASS; stamp `20260818T191144020Z` | **6 passed** (`mr08-r3-serial-ledger-final-results-20260818T191144020Z/junit.xml`) |
| MR08-FREEZE-PRE-DOCS | docs-consistency before freeze docs commit; stamp `20260818T193258134Z` | **6 passed** (`mr08-freeze-pre-docs-results-20260818T193258134Z/junit.xml`) |
| MR08-FREEZE-REGRESSION | serial candidate freeze regression; stamp `20260818T193330926Z` | **PASS** 988 passed / 20 skipped / 52 deselected / 238 subtests; JUnit `tests="1246" failures="0" errors="0" skipped="20" time="697.037"` (`mr08-freeze-regression-results-20260818T193330926Z/junit.xml`) |

ProductCommit `70d4f4c11529b9539856dbdcc7456ea18689bf27`. AcceptanceCommit
`6195637897588ae305f05617659899e9b9a51431`. FreezeCommit / CandidateSha
`4db97ea72ffcb18823cd610599752cc1c8e8716d`.

## Verification (MR09 / CP08-V9 — destructive real acceptance, once only)

**MR09 IN_PROGRESS (R1).** CandidateSha stays `4db97ea72ffcb18823cd610599752cc1c8e8716d`
and follow-up SHA remains `c003dd9aa00c1c84026d9c236597c33e84289c27`. The single
authorized destructive run did **not** start in MR09: the read-only preflight
launcher hit a local `SyntaxError` (unescaped quote in `python -c`) before the
guard identity check could complete. No reset was injected, no runner child was
started, port 8000 stayed free, and no pytest process remained. Fail-fast: no
retry, no product/test change, no MR10.

**MR09-R1** corrected the launcher to use a PowerShell single-quoted here-string
piped to `python -` (stdin). Preflight passed (exitcode 0, all 5 identity fields
confirmed). The single authorized runner was invoked exactly once. Runner exited 1:
step 14 `pdf_comment_flow` failed with `TimeoutError`. Steps 1–13 passed; steps
15–18 (`docx_comment_sync`, `signed_review_approval`, `backend_restart`,
`persistence_and_session_contract`) are NOT RUN. Einmalfreigabe is now consumed.
No second run, no product/test fix, no MR10. Classification: Produkt-/HTTP-/
Szenarioassertion → **MR09 FAILED (R1)**. Current checkpoint MR09-R2 (parent MR09
IN_PROGRESS). A further CP08 run requires remediation, new freeze, and new explicit
destructive authorization.

**Precision correction (MR09-R2):** The prior summary stated "Backend-Log endet nach
diesem Request — kein weiterer HTTP-Aufruf ankam vor dem Timeout." That statement
is not supported by evidence. `POST .../comments` completed with HTTP 200. The
immediately following `GET .../comments?context=PDF_REVIEW` did not deliver a
complete response within 30 seconds. Because Uvicorn writes an access-log entry only
after the response is fully sent, the absence of a log entry does not prove that the
GET never reached the server; the GET may have connected but blocked before response
headers, or it may have timed out while reading the body. The failure class is
therefore: **"Acceptance-Interaktions-/Transporttimeout, Ursache offen"** — a product
defect is not yet proven.

**MR09-R2 (PASS):** non-destructive localisation completed.

SQLite read-only inspection (`documents.db` from workspace
`20260819T082412875274Z-...`): first attempt queried `workflow_comments` →
`sqlite3.OperationalError: no such table`. After schema inspection via `sqlite_master`,
corrected query against `document_workflow_comments` found 1 `PDF_REVIEW` comment
persisted for J04-ACCEPT-DOC v1 (`select_completed_ok`). After process end: no
permanent lock observable. A transient lock or blockade during the live Realprocess
request cannot be excluded.

New backend contract test `test_pdf_comment_create_then_immediate_list_over_http`
(TestClient, no mocks for service/repository): POST comment → HTTP 200 with comment_id;
immediate GET list → HTTP 200 with same comment_id and PDF_REVIEW context — passes
reliably in-process. This confirms the route and service path are correct.

`AcceptanceHttpClient.request` extended: `TimeoutError` and `URLError(TimeoutError)`
before response headers → `ScenarioFailure` with method, path, "vor Response-Headern";
`TimeoutError` during `response.read` → "beim Lesen des Response-Bodys"; no secrets
in message; timeout remains 30s; no retry. Four new unit tests pass.

All Gates passed: A (6), B (6), C (109), D (1251 / 0 failed / 20 skipped), E (6).

**SQLite diagnosis — full account (including first failed attempt):**
First attempt queried `workflow_comments` → `sqlite3.OperationalError: no such table:
workflow_comments`. Schema was then inspected (`sqlite_master`). Corrected query used
`document_workflow_comments`, found 1 PDF_REVIEW comment for J04-ACCEPT-DOC v1,
completed without blockade after process end. This rules out a **permanent** lock
after process exit. A **transient** lock during the live Realprocess request cannot
be excluded.

**TestClient scope:** `test_pdf_comment_create_then_immediate_list_over_http` exercises
route, service, authorization, and SQLite persistence in-process. It does not use a
real uvicorn process, TCP socket, or PostgreSQL. It rules out a deterministic defect
in the tested in-process code path. It does **not** prove correctness of the complete
real-process product path.

**Cause assessment:** Cause remains open. The failure was observed only in the full
urllib→uvicorn/TCP Realprocess scenario. A Windows/socket effect is a hypothesis
only. A product defect is not proven, but is also not conclusively excluded. The new
timeout-phase instrumentation in `AcceptanceHttpClient.request` will localise the
failure to "vor Response-Headern" or "beim Lesen des Response-Bodys" in a future
Realprocess run.

**Candidate status:** `4db97ea` remains the historical MR08 CandidateSha. Because
Acceptance and test files have been modified since `4db97ea`, there is currently
**no active Candidate** for a further CP08 run. A new CandidateSha requires a
separate Commit/Freeze authorization.

**MR09-R2-R1 (PASS):** added missing Body-Read-Timeout unit test
(`test_acceptance_http_client_timeout_during_body_read_reports_method_path_and_no_secrets`).
Five timeout unit tests now present (was: four). All R1 gates passed:
A (7), B (110), C (1252 / 0 failed / 20 skipped), D (6).
No product code changed, no PG, no CP08, no commit, no freeze.
Active CandidateSha: **none** — Acceptance and test files modified since `4db97ea`;
new Candidate requires separate Commit/Freeze authorization.

**MR09-R2-R2 (PASS):** extended the Body-Read-Timeout test to use POST method with
secret body `{"password": "request-body-secret"}`; asserted neither `request-body-secret`
nor `password` (case-insensitive) appear in the error message while preserving the
existing assertions for method, path, body-read phase, token secrecy, Authorization,
Bearer, and exactly one `urlopen` call. Status fields are now consistent
(MR09-R2 PASS, MR09-R2-R1 PASS; parent MR09 still IN_PROGRESS / not passed).

| # | Befehl | Ergebnis |
| --- | --- | --- |
| MR09-LEDGER-START | docs-consistency after MR09 IN_PROGRESS; stamp `20260819T063744327Z` | **6 passed** (`mr09-ledger-start-results-20260819T063744327Z/junit.xml`) |
| MR09-PREFLIGHT | read-only guard preflight; stamp `20260819T063818073Z` | **BLOCKED before guard** (`mr09-cp08-v9-results-20260819T063818073Z/preflight.log`); local preflight launcher `SyntaxError`, no reset, no runner |
| MR09-R1-LEDGER-START | docs-consistency after MR09-R1 IN_PROGRESS; stamp `20260819T082330286Z` | **6 passed** (`mr09-r1-ledger-start-results-20260819T082330286Z/junit.xml`) |
| MR09-R1-PREFLIGHT | corrected read-only guard preflight via stdin; stamp `20260819T082349151Z` | **PASS** exitcode 0; database=qmtool_j04_destructive_test, major=18, port=5432, marker=j04_m0_destructive_pg16, reset_present=False (`mr09-r1-cp08-v9-results-20260819T082349151Z/preflight.log`) |
| MR09-R1-RUNNER | single CP08-V9 runner call; stamp `20260819T082412Z` | **FAILED** exit 1 / 1 failed; step 14 `pdf_comment_flow` TimeoutError; steps 1–13 pass; steps 15–18 NOT RUN; workspace `cp08-realprocess-ws/20260819T082412875274Z-89d0b470899242559fde43dbf6ba199c` (`mr09-r1-cp08-v9-results-20260819T082349151Z/runner.log`) |
| MR09-R1-LEDGER-FINAL | docs-consistency after runner; stamp `20260819T082616676Z` | **6 passed** (`mr09-r1-ledger-final-results-20260819T082616676Z/junit.xml`) |
| MR09-R2-GATE-A | docs-consistency after R2 IN_PROGRESS; stamp `20260819T085741455Z` | **6 passed** (`mr09-r2-gate-a-results-20260819T085741455Z/junit.xml`) |
| MR09-R2-SQLITE | read-only SQLite inspection of persisted workspace; stamp `20260819T085750217Z` | **PASS** — first query `workflow_comments` → no such table; corrected query `document_workflow_comments` found 1 PDF_REVIEW comment; after process end: no permanent lock; transient lock not excluded (`mr09-r2-diagnosis-20260819T085750217Z/sqlite-check.log`) |
| MR09-R2-GATE-B | focused new tests; stamp `20260819T085946388Z` | **6 passed** (`mr09-r2-gate-b-results-20260819T085946388Z/junit.xml`) |
| MR09-R2-GATE-C | comment/HTTP environment suite; stamp `20260819T090002819Z` | **109 passed / 0 failed** (`mr09-r2-gate-c-results-20260819T090002819Z/junit.xml`) |
| MR09-R2-GATE-D | full non-live regression; stamp `20260819T090112728Z` | **1251 passed / 0 failed / 20 skipped** (`mr09-r2-gate-d-results-20260819T090112728Z/junit.xml`) |
| MR09-R2-GATE-E | final docs-consistency; stamp `20260819T091530457Z` | **6 passed** (`mr09-r2-gate-e-results-20260819T091530457Z/junit.xml`) |
| MR09-R2-R1-GATE-A | focused: 5 timeout + 1 backend + 1 comment; stamp `20260819T093636436Z` | **7 passed** (`mr09-r2-r1-gate-a-results-20260819T093636436Z/junit.xml`) |
| MR09-R2-R1-GATE-B | acceptance unit + backend p4-p9 + auth matrix; stamp `20260819T093654734Z` | **110 passed / 0 failed** (`mr09-r2-r1-gate-b-results-20260819T093654734Z/junit.xml`) |
| MR09-R2-R1-GATE-C | full non-live regression; stamp `20260819T093801180Z` | **1252 passed / 0 failed / 20 skipped** (`mr09-r2-r1-gate-c-results-20260819T093801180Z/junit.xml`) |
| MR09-R2-R1-GATE-D | docs-consistency; stamp `20260819T095101958Z` | **6 passed** (`mr09-r2-r1-gate-d-results-20260819T095101958Z/junit.xml`) |
| MR09-R2-R2-GATE-A | focused: 5 timeout + 2 comment tests; stamp `20260819T123823536Z` | **7 passed / 0 failed** (`mr09-r2-r2-gate-a-results-20260819T123823536Z/junit.xml`) |
| MR09-R2-R2-GATE-B | acceptance unit + backend p4-p9 + auth matrix; stamp `20260819T123839735Z` | **110 passed / 0 failed** (`mr09-r2-r2-gate-b-results-20260819T123839735Z/junit.xml`) |
| MR09-R2-R2-GATE-C | full non-live regression; stamp `20260819T123948029Z` | **1252 passed / 0 failed / 20 skipped** (`mr09-r2-r2-gate-c-results-20260819T123948029Z/junit.xml`) |
| MR09-R2-R2-GATE-D | docs-consistency; stamp `20260819T125137305Z` | **6 passed / 0 failed** (`mr09-r2-r2-gate-d-results-20260819T125137305Z/junit.xml`) |
| MR09-R2-R3-GATE-A-PROBE | docs-consistency probe (test found real defect, then fixed); stamp `20260819T131805888Z` | **1 failed** (new test correctly caught R2-R3 absent from top status line; fixed inline) |
| MR09-R2-R3-GATE-A | docs-consistency after fix; stamp `20260819T131822493Z` | **7 passed / 0 failed** (`mr09-r2-r3-gate-a-results-20260819T131822493Z/junit.xml`) |
| MR09-R2-R3-GATE-B | acceptance unit + backend p4-p9 + auth matrix; stamp `20260819T131836799Z` | **110 passed / 0 failed** (`mr09-r2-r3-gate-b-results-20260819T131836799Z/junit.xml`) |
| MR09-R2-R3-GATE-C | full non-live regression; stamp `20260819T131951762Z` | **1253 passed / 0 failed / 20 skipped** (`mr09-r2-r3-gate-c-results-20260819T131951762Z/junit.xml`) |
| MR09-R2-R3-GATE-D | docs-consistency after PASS finalization; stamp `20260819T133304090Z` | **7 passed / 0 failed** (`mr09-r2-r3-gate-d-results-20260819T133304090Z/junit.xml`) |
| MR09-R2-R4-GATE-A | focused remediation tests (positive + negative); stamp `20260819T134748986Z` | **2 passed / 0 failed** (`mr09-r2-r4-gate-a-results-20260819T134748986Z/junit.xml`) |
| MR09-R2-R4-GATE-B | full docs-consistency (8 tests); stamp `20260819T134807780Z` | **8 passed / 0 failed** (`mr09-r2-r4-gate-b-results-20260819T134807780Z/junit.xml`) |
| MR09-R2-R4-GATE-C | full non-live regression; stamp `20260819T134832664Z` | **1254 passed / 0 failed / 20 skipped** (`mr09-r2-r4-gate-c-results-20260819T134832664Z/junit.xml`) |
| MR09-R2-R4-GATE-D | docs-consistency after PASS finalization; stamp `20260819T140502984Z` | **8 passed / 0 failed** (`mr09-r2-r4-gate-d-results-20260819T140502984Z/junit.xml`) |

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
| CP08-R3 | PASS | `c3d6587` isolate realprocess workspace | `a421005` |
| FR09 | PASS | `1a22d38` freeze R1+R2+R3 | `57d87d4` |
| CP08-V3 | FAILED | — (start-contract abort; Word not reached) | `de7e82d` |
| CP08-R4 | PASS | `5233b5d` start-contract runner | `63dda17` |
| FR10 | PASS | `1bd8aa0` freeze R1–R4 | `fd3aeb8` |
| CP08-V4 | FAILED | — (bootstrap_admin_login /auth/me 409; Word not reached) | `5aff642` |
| CP08-R5 | PASS | `34f39c0` bootstrap-admin handshake | `164a7c9` |
| FR11 | PASS | `c263ff5` freeze R1–R5 | `05aed9f` |
| CP08-V5 | FAILED | — (document_baseline_flow; create 403 / missing etag; Word not reached) | `eb968d6` |
| CP08-R6 | PASS | `e28a44d` QMB actor + create 403 diagnostics | `1f72451` |
| FR12 | PASS | `b63d9a1` freeze R1–R6 | `049c0fd` |
| CP08-V6 | FAILED | — (etag_concurrency_race TypeError; create 200; Word not reached) | `bd769ba` |
| CP08-R7 | PASS | `f5dcfa8` etag race `sorted()` + stable assignment | `ae5be41` |
| FR13 | PASS | `cd3a376` freeze R1–R7 | `45df9d6` |
| CP08-V7 | FAILED | — (harness username assignments; 404 mask; race 200/409; Word not reached) | `63a000d` |
| CP08-R8 | PASS | `31dc273` workflow assignments use `/auth/me` user_id | `83b7b1a` |
| FR14 | PASS | `ed488ed` freeze R1–R8 | `0cb4179` |
| CP08-V8 | FAILED | — (training_read_receipt; review/accept 403; artifacts PASS; Word not reached) | this documentation |
| CP08-R9 | PASS | _(uncommitted)_ scope-corrected document release flow | this documentation |

### Remaining gates (explicitly NOT RUN)

| Gate | Status |
| --- | --- |
| Isolated PostgreSQL live (Slot-2 PG18 local / CI PG16) | **CP04-R PASS** (guard+runner); full live suites **NOT RUN** (CP08) |
| M8 `pg_dump`/`pg_restore` live drill | **NOT RUN** |
| Full `j04_final_acceptance` real-process E2E | **FAILED** (CP08-V8) at `training_read_receipt` before out-of-scope reads |
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
| **P3C** | Training Documents-Read | **Done (HTTP Same-Process, follow-up only)** | Nicht Teil des J04-M0-Acceptance-Gates |
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

## MR09-R3 / MR09-R3-R1 — Harness stdout-Pipe-Backpressure behoben (PASS)

**Ursachenbewertung CP08-V10:**
- Das Backendlog von CP08-V9 ist exakt **4076 Bytes** groß.
- Das Backendlog von CP08-V10 ist ebenfalls exakt **4076 Bytes** groß.
- Beide Logs enden unmittelbar nach `POST /documents/versions/J04-ACCEPT-DOC/1/comments 200 OK`.
- Der nachfolgende GET-Aufruf (`pdf_comment_flow`) timed out vor den Response-Headern.
- Der Harness startete das Backend mit `stdout=subprocess.PIPE` — die Pipe wurde erst bei
  `stop_process`/`cleanup` gelesen, nicht kontinuierlich.
- Ein Windows-PIPE-Buffer läuft nach ausreichend Backend-Output (>4 KiB) voll; der Backend-
  Prozess blockiert dann beim nächsten `write()`, kann keine neuen HTTP-Requests mehr
  bearbeiten, und der Client erhält nie die Response-Header.
- **Die stdout-Pipe-Backpressure im Acceptance-Harness ist die führende und konkret belegte
  Ursache.** Die bisherige allgemeine Windows-Socket-Hypothese ist nicht mehr als abschließende
  Erklärung gültig.
- **Ein Produktdefekt im Kommentarpfad ist nicht nachgewiesen.**

**Historischer erster R1-Fehlversuch:**
- Gate A `20260819T171454220Z` endete rot: **9 tests / 5 failures / 0 errors**.
- Alle fünf Failures hatten dieselbe Ursache:
  `UnboundLocalError: cannot access local variable 'output' where it is not associated with a value`.
- Ursache: `_drain_and_log()` fiel im Backend-Drainer-Zweig nach Join/Fehlerprüfung
  fälschlich weiter in den Nicht-Drainer-Schreibpfad und referenzierte dort `output`,
  obwohl Live-Logpersistenz im Drainer-Zweig bereits abgeschlossen war.

**Behebung MR09-R3:**
- `_BackendStdoutDrainer`-Klasse in `j04_m0_realprocess_harness.py` eingebaut: liest die
  Backend-PIPE kontinuierlich in einem Daemon-Thread, redigiert jede Zeile sofort mit
  `redact_log_text` und schreibt sie sofort in das PID-bezogene Log.
- `start_backend` startet den Drainer unmittelbar nach `Popen`.
- `stop_process`/`cleanup` joinen den Thread (Timeout `_READER_JOIN_TIMEOUT`), prüfen
  `is_alive()` verbindlich und propagieren Reader-Fehler als `HarnessError`.
- Client-Worker-Prozesse erhalten keinen Drainer; ihr `communicate()`-JSON-Protokoll bleibt
  unverändert.

**Eng begrenzte Korrektur MR09-R3-R1:**
- `_drain_and_log()` trennt die Verantwortlichkeiten jetzt sichtbar:
  Backend-Drainer-Zweig: Thread abschließen, Alive-/Timeout- und Readerfehler prüfen,
  dann **sofort zurückkehren**.
- Nur Prozesse **ohne** Drainer lesen dort verbliebene stdout und schreiben sie ins PID-Log.
- Keine erneute oder überschreibende Backend-Logpersistenz im Drainer-Zweig.

**Geänderter Dateisatz:**
1. `tests/acceptance/j04_m0_realprocess_harness.py` — Drainer-Klasse und Harness-Erweiterung
2. `tests/acceptance/test_j04_m0_harness_unit.py` — 9 neue/geschärfte Tests
   (Backpressure, Live-Logsichtbarkeit, Redaction, Client-Worker-Abgrenzung,
   Stop/Cleanup, Backend-Restart, Join-Timeout, Reader-Fehler)

**Gate-Ergebnisse:**

| Gate | Stamp | Ergebnis |
| --- | --- | --- |
| A0 – historischer erster R1-Versuch | `20260819T171454220Z` | **9 tests / 5 failures / 0 errors** — `UnboundLocalError` in `_drain_and_log()` |
| A – kompletter R1-Fokus | `20260819T172254282Z` | **9 passed / 0 failed / 0 errors** |
| B – Acceptance-Infrastruktur | `20260819T172314505Z` | **60 passed / 0 failed / 0 errors** |
| C – vollständige nicht-live Regression | `20260819T172346447Z` | **1263 tests / 0 failed / 0 errors / 20 skipped** |

**Freeze-Commits und technische Candidate-Evidence:**
- HarnessCommit: `810f8975284f3d792153b902917e8faf24f3f00f` —
  `test(j04-m0): stream backend acceptance logs`
- FreezeCommit / aktiver CandidateSha: `254c8ea8147130c02b5661e2e467b2641ca83885` —
  `docs(j04-m0): freeze MR09 R3 candidate`
- Pre-Freeze-Docs-Gate: `20260819T191917758Z` — **8 passed / 0 failed / 0 errors**
- Freeze-Regression: `20260819T192016485Z` —
  **1263 tests / 0 failed / 0 errors / 20 skipped**,
  `1005 passed, 20 skipped, 52 deselected, 238 subtests passed`, Laufzeit `0:17:55`,
  JUnit `build/j04-m0-closure/mr09-r3-freeze-regression-20260819T192016485Z/junit.xml`

**Status:** MR09-R3-R1 **PASS**. MR09-R3 **PASS**.
**Aktiver Candidate:** `254c8ea8147130c02b5661e2e467b2641ca83885` (`254c8ea`).
`08b04e6` bleibt ausschließlich historischer CP08-V10-Candidate.
CP08-V11: **PASS** (Stamp `20260819T202601488Z`; alle 18 Realprocess-Schritte).
**Parent MR09:** PASS. **Gesamtstatus:** NOT_READY. MR10: TODO. Accepted: unset.

## CP08-V10 — Final acceptance attempt (FAILED / NOT_READY)

**Lauf-SHA:** `a15cb3fbb16a277944a8c87500fea7576a1486be` (HEAD zum Laufzeitpunkt)
**CandidateSha:** `08b04e6fe28ee86e71759440236b5ca10711fa1a`
**Stamp:** `20260819T155102306Z`
**Runner-Exitcode:** 1
**Guard-Identität:** `database=qmtool_j04_destructive_test`, `major=18`, `port=5432`, `marker=j04_m0_destructive_pg16`, `reset_present=False`
**Workspace:** `build/j04-m0-closure/cp08-realprocess-ws/20260819T135237145371Z-6fb9ce8809cd484a9c9356a33bc89731/`
**Evidence:** `build/j04-m0-closure/mr09-cp08-v10-results-20260819T155102306Z/runner.log`

| Schritt | Name | Status | Detail |
| --- | --- | --- | --- |
| 1 | preconditions | PASS | port free; pg preflight ok major=18 |
| 2 | pg_bootstrap | PASS | isolated PG schema migrated |
| 3 | backend_start | PASS | backend ready status=200 |
| 4 | health_and_openapi | PASS | health and dev openapi reachable |
| 5 | bootstrap_admin_login | PASS | bootstrap admin session user=j04acceptadmin |
| 6 | seed_directory_users | PASS | directory users seeded and login verified |
| 7 | seed_workflow_profile | PASS | workflow profile ready code=j04_accept_flow_profile |
| 8 | client_process_sessions | PASS | two client processes with distinct homes and token fingerprints |
| 9 | document_baseline_flow | PASS | document J04-ACCEPT-DOC in progress etag=a92036dd-b7ea-43... |
| 10 | etag_concurrency_race | PASS | one winner and one 409 on shared etag |
| 11 | artifacts_transport | PASS | artifact content verified id=337bd3e3... sha256=f3efecf350... |
| 12 | signature_verify_password | PASS | editor, reviewer, and approver signature assets active and verified |
| 13 | signed_editing_complete | PASS | signed editing-complete fail-closed then reached IN_REVIEW |
| **14** | **pdf_comment_flow** | **FAIL** | **GET /documents/versions/J04-ACCEPT-DOC/1/comments?context=PDF_REVIEW timed out vor Response-Headern** |
| 15 | docx_comment_sync | NOT RUN | — |
| 16 | signed_review_approval | NOT RUN | — |
| 17 | backend_restart | NOT RUN | — |
| 18 | persistence_and_session_contract | NOT RUN | — |

**Erste Fehlerstelle:** Schritt 14 `pdf_comment_flow` — GET auf Kommentar-Endpunkt Timeout vor Response-Headern.
Der POST-Aufruf (Kommentar-Erstellung) hatte in MR09-R2 erfolgreich persistiert (SQLite-Diagnose bestätigt).
Der nachfolgende GET-Aufruf zum Listen der Kommentare timed out konsistent — dies ist dieselbe Fehlerklasse
wie in MR09-R1.

**Endzustand:** FAIL. Schritte 1–13 grün, Schritt 14 ist blockierendes Fail-fast.
APPROVED, SIGNED_PDF, RELEASED_PDF, Restart, Session-Persistenz: **NOT REACHED**.

**Parent MR09:** IN_PROGRESS und nicht bestanden.
**Current checkpoint:** MR09.
**Gesamtstatus:** NOT_READY. MR10: TODO. Accepted: unset.

**Cleanup nach Lauf:**
- `QMTOOL_J04_FINAL_ACCEPTANCE`: entfernt aus Elternprozess ✓
- `QMTOOL_PG_TEST_RESET`: nicht gesetzt ✓
- Pytest-Prozesse: 0 ✓
- Port 8000: TimeWait (kein aktiver Listener) — sachlich erwartet nach Backend-Shutdown ✓

**Einmalfreigabe:** verbraucht (Runner wurde gestartet). Neue Remediation (MR09-R3) und neue
ausdrückliche Einmalfreigabe erforderlich vor einem weiteren CP08-Lauf.

## CP08-V11 — Final acceptance attempt (PASS / NOT_READY)

**Lauf-HEAD:** `be8fb01104cb7d4618627aa81d6f1d71e1d0a98f` (`be8fb01`)
**CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885` (`254c8ea`) — unverändert
**Stamp:** `20260819T202601488Z` (historischer Verzeichnisbezeichner — fälschlich mit `Z`-Suffix,
tatsächlich lokale Wall-Clock beim Anlegen; Verzeichnis unverändert)
**Lokale Laufzeit (UTC+2):** 2026-08-19T20:26:10.849+02:00 bis 2026-08-19T20:26:44.992+02:00
**Entsprechende UTC-Zeit:** 2026-08-19T18:26:10.849Z bis 2026-08-19T18:26:44.992Z
**Runner-Aufrufe:** exakt **1**
**Runner-Exitcode:** **0**
**Guard-Identität:** `database=qmtool_j04_destructive_test`, `major=18`, `port=5432`, `marker=j04_m0_destructive_pg16`
**Preflight (read-only, vor Opt-in):** Branch `feature/ap-j04-m0`, HEAD `be8fb01`, Divergenz 0 behind / 72 ahead;
CandidateSha ist Vorfahr von HEAD; CandidateSha..HEAD nur zwei Docs; Staging leer; keine Inhaltsdiffs
außer stat-only + `docs/transition/`; kein pytest; Port 8000 frei; Env-Variablen nicht gesetzt;
frischer Basetemp existierte noch nicht.
**Basetemp:** `build/j04-m0-closure/mr09-cp08-v11-results-20260819T202601488Z/basetemp`
**Evidence:** `build/j04-m0-closure/mr09-cp08-v11-results-20260819T202601488Z/runner.log`
**Realprocess-Workspace:** `build/j04-m0-closure/cp08-realprocess-ws/20260819T182612961146Z-fab8b6579d6a43d2aeb7f5552f8187ac/`
**Scenario summary:** `…/logs/acceptance-scenario-summary.json` (18/18 pass)

| Schritt | Name | Status | Detail |
| --- | --- | --- | --- |
| 1 | preconditions | PASS | port free; pg preflight ok major=18 |
| 2 | pg_bootstrap | PASS | isolated PG schema migrated |
| 3 | backend_start | PASS | backend ready status=200 |
| 4 | health_and_openapi | PASS | health and dev openapi reachable |
| 5 | bootstrap_admin_login | PASS | bootstrap admin session user=j04acceptadmin |
| 6 | seed_directory_users | PASS | directory users seeded and login verified |
| 7 | seed_workflow_profile | PASS | workflow profile ready code=j04_accept_flow_profile |
| 8 | client_process_sessions | PASS | two client processes with distinct homes and token fingerprints |
| 9 | document_baseline_flow | PASS | document J04-ACCEPT-DOC in progress |
| 10 | etag_concurrency_race | PASS | one winner and one 409 on shared etag |
| 11 | artifacts_transport | PASS | artifact content verified |
| 12 | signature_verify_password | PASS | editor, reviewer, and approver signature assets active and verified |
| 13 | signed_editing_complete | PASS | signed editing-complete fail-closed then reached IN_REVIEW |
| 14 | pdf_comment_flow | PASS | PDF_REVIEW comment created |
| 15 | docx_comment_sync | PASS | DOCX_EDIT comment sync idempotent |
| 16 | signed_review_approval | PASS | signed review/approval reached APPROVED with SIGNED_PDF and RELEASED_PDF |
| 17 | backend_restart | PASS | backend process restarted on same backend home |
| 18 | persistence_and_session_contract | PASS | document persisted in APPROVED; PG-backed sessions survived restart |

**Erste Fehlerstelle:** keine — vollständiger PASS aller 18 Schritte.

**Backendlog-Drain-Nachweis:**
- CP08-V9/V10 Backendlog jeweils exakt **4076 Bytes** (Pipe-Backpressure vor Fix).
- CP08-V11 `backend-4440.log`: **5388 Bytes** — wächst über die frühere 4076-Byte-Grenze hinaus;
  Schritt 14 `pdf_comment_flow` und nachfolgende Schritte sind im Log sichtbar.
- Restart-Backend `backend-24208.log`: **469 Bytes**.

**Endzustand:** PASS. Alle 18 Realprocess-Schritte grün; APPROVED, SIGNED_PDF, RELEASED_PDF,
Restart und Session-Persistenz erreicht.

**Parent MR09:** **PASS**.
**Current checkpoint:** **MR10**.
**Gesamtstatus:** NOT_READY. MR10: TODO. Accepted: unset.

**Cleanup nach Lauf:**
- `QMTOOL_J04_FINAL_ACCEPTANCE`: entfernt aus Elternprozess ✓
- `QMTOOL_PG_TEST_RESET`: nicht gesetzt ✓
- Pytest-Prozesse: 0 ✓
- Port 8000: frei (kein aktiver Listener) ✓
- Harness- und Harness-Unit-Datei-Hashes unverändert ✓
- Candidate-Produkt-, Backend-, Acceptance- und Testdateien unverändert ✓

**Einmalfreigabe:** verbraucht. Kein zweiter CP08-V11-Lauf. Nächster Schritt: MR10-B (Human-Smoke) — **NOT RUN**.

## MR10-A — Technische Release-Gates (PASS)

**Stamp:** `20260819T184021807Z`
**Evidence:** `build/j04-m0-closure/mr10-a-technical-20260819T184021807Z/`
**Remediation:** MR10-A-R1 PASS (`20260819T212617115Z`)
**Start-/End-HEAD:** `be8fb01104cb7d4618627aa81d6f1d71e1d0a98f` (unverändert)
**CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885` (unverändert)

| Gate | Ergebnis | Evidence |
| --- | --- | --- |
| A — Releaseverträge | **18 passed / 0 failed** (19.84s) | `gate-a-junit.xml` |
| B — Onedir-Build | Exit **0** (~120s); bundle clean + imports OK | `gate-b-build.log` |
| C — Golive | Exit **0**; `ok=true` | `golive-gate.json` |
| D — Nicht-live Regression | **1005 passed / 20 skipped / 52 deselected** (703.67s) | `gate-d-junit.xml` |
| E — Docs-Konsistenz | **FAILED** — `test_acceptance_report_remediation_checkpoint_consistent_with_checklist` | `gate-e-junit.xml` |

**Build-Artefakte (Gate B):**
- `packaging/dist_output/QM-Tool/` — vorhanden
- `packaging/dist_output/QM-Tool.zip` — **86 241 417 Bytes**, SHA-256 `018B56DB…`
- `packaging/dist_output/QM-Tool/QM-Tool.exe` — **11 099 231 Bytes**, SHA-256 `EE40B1C5…`
- `packaging/icons/app.ico` — SHA-256 vor/nach Build `F1C4D464…` (unverändert)
- Keine `.env`, SQLite/DB, Private Keys, Secrets, CP08- oder interne Evidence-Dateien im Kundenbundle

**Gate D — Skips:** 20× `not_in_m0` (Legacy CLI/training außerhalb reduziertem M0-Scope).
**Gate D — Deselections:** 52× postgres + j04_final_acceptance (bewusst ausgeschlossen).

**Gate E Fehlerstelle (historisch):** `tests/docs/test_docs_consistency.py::test_acceptance_report_remediation_checkpoint_consistent_with_checklist` —
die Current-Status-Zeile erwähnte den letzten MR09-Remediation-Checkpoint `MR09-R2-R4` nicht.
**Remediation MR10-A-R1:** Klausel `MR09-R2-R4 PASS` ergänzt; R1-A und R1-B grün.

**Word-COM-E2E:** nicht verifiziert; separates Conversion-Follow-up.

**Parent MR10:** IN_PROGRESS. **MR10-B Human-Smoke:** PASS.
**Gesamtstatus:** NOT_READY. **Accepted:** unset.

## MR10-A-R1 — Docs-Konsistenz (PASS)

**Stamp:** `20260819T212617115Z`
**Evidence:** `build/j04-m0-closure/mr10-a-r1-docs-20260819T212617115Z/`
**Gate R1-A:** **8 passed / 0 failed** (`gate-a-junit.xml`)
**Gate R1-B:** **8 passed / 0 failed** (`gate-b-junit.xml`)
**Historische rote Gate-E-Evidence:** `mr10-a-technical-20260819T184021807Z/gate-e-junit.xml` — unverändert

## MR10-B — Sichtbarer Onedir-Human-Smoke (PASS)

**Stamp:** `20260819T214740696Z`
**Evidence:** `build/j04-m0-closure/mr10-b-human-20260819T214740696Z/`
**Lauf-HEAD / CandidateSha:** `be8fb01` / `254c8ea` — unverändert
**Testvorbereitungen:** exakt 1
**Guard:** `database=qmtool_j04_destructive_test`, `major=18`, `port=5432`, `marker=j04_m0_destructive_pg16`, `reset_present=False` vor Reset
**EXE:** `packaging/dist_output/QM-Tool/QM-Tool.exe` — 11 099 231 Bytes, SHA-256 `EE40B1C53B768DC75A2F71D3F1A1F216D052702B24BB7D9EDCD0A83689F98229`
**Backend-Health:** HTTP 200, `status=ok`
**Backend-HOME:** `…/mr10-b-human-20260819T214740696Z/workspace/backend-home`
**Client-HOME:** `…/mr10-b-human-20260819T214740696Z/workspace/client-home`
**Menschliche Antwort:** `MR10-B Human-Smoke PASS` (ausdrücklich; EXE-Exitcode 0 allein zählt nicht als PASS)
**Erste Abweichung:** keine
**Cleanup:** Orchestrator `phase=cleaned_up`, Exit 0; Client-Exit 0; kein Listener auf 8000; Env-Opt-ins nicht gesetzt
**Word-COM / Produktionslizenz:** nicht verifiziert; Folgepakete
**Nächster Schritt:** MR10-C lokal abgeschlossen; Fetch/Push/PR nur nach separater Freigabe.

## MR10-C — Closure und Merge-Vorbereitung (PASS)

**Stamp:** `20260820T053032181Z`
**Evidence:** `build/j04-m0-closure/mr10-c-closure-20260820T053032181Z/`
**CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885` (`254c8ea`) — unverändert
**Current checkpoint:** COMPLETE
**Gesamtstatus:** READY_FOR_ACCEPTANCE
**Acceptance-Report-Status:** `Ready for acceptance`
**Accepted:** unset (Human-Smoke ist kein Merge-Accept)

**Technische Zusammenfassung:**
- CP08-V11: PASS, 18/18 Schritte
- MR10-A: Releaseverträge, Onedir/ZIP, Bundle-/Importprüfung, Golive, nicht-live Regression — PASS
- MR10-A-R1: Docs-Konsistenz PASS
- MR10-B: Human-Smoke PASS; Nutzerantwort ausdrücklich; Cleanup PASS
- CandidateSha..Closure-HEAD: ausschließlich die beiden Dokument-Owner

**Nicht verifiziert:** Word-COM-E2E (Conversion-Folgepaket); Produktionslizenz-/Deploymentprüfung (Folgepaket).
**Übergangspersistenz:** backend-eigene Documents-SQLite bleibt dokumentiert.

**MR10-B-Prozessabweichung:** Evidence-lokales `mr10_b_orchestrator.py` unter `build/` (gitignore);
keine DSN oder hartcodierten Passwörter; kein Produkt-/Candidate-Diff; nicht committen;
kein Produkt-Helper oder neuer Entrypoint.

Historische rote Evidence (u. a. CP08-V10, MR10-A Gate E) bleibt erhalten und nicht umgeschrieben.

## MR-FIX-R1 — Review-Fix Verification Checkpoint (PASS)

**Stamp:** `20260820T075936Z`
**Evidence:** `build/mr-fix-r1/`
**Scope:** reiner Verifikations-Checkpoint für PR-24-Review-Fixes; keine Produktentscheidung über den bereits
bestätigten Vertragsumfang hinaus; kein Commit, kein Push, keine PR-/Conversation-Aktion.

**Preflight:** Branch `feature/ap-j04-m0`; lokales `HEAD` und `origin/feature/ap-j04-m0` beide
`9cee1ddf78c39f88dcf582fab79cea10146953ed`; Fremdänderungen in
`interfaces/pyqt/widgets/signature_placement/label_geometry.py`, `modules/training/wiring.py`
und `docs/transition/` unverändert belassen; kein paralleler Pytest-Prozess.

**Gates:**
- Gate A — `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py::test_acceptance_document_create_with_qmb_token_returns_etag`
  mit frischem `--basetemp` und JUnit — **PASS** (`build/mr-fix-r1/gate-a-junit.xml`)
- Gate B — `tests/docs/test_docs_consistency.py` mit frischem `--basetemp` und JUnit — **PASS**
  (`build/mr-fix-r1/gate-b-junit.xml`)
- Gate C — fokussierte Review-Fix-Suite (Template-Event-/ETag, DOCX/DOTX/DOCT, Backend-CAS/Auth,
  Client-Encoding, URL-ID-Validierung) in einem frischen seriellen Prozess — **PASS**
  (`build/mr-fix-r1/gate-c-junit.xml`)
- Gate D — `pytest -m "not postgres and not j04_final_acceptance"` mit frischem `--basetemp` und JUnit —
  **PASS** (`build/mr-fix-r1/gate-d-junit.xml`)

**WinError-10053-Nachweis:** der zuvor rote Acceptance-Einzeltest aus Gate A reproduzierte den früheren
`ConnectionAbortedError [WinError 10053]` im isolierten Einzelprozess **nicht**. MR-FIX-R1 enthält
deshalb keinen neuen Socket-Fehlernachweis; der frühere Sammellauf bleibt historische Evidence.

**Vertragliche Klarstellung:**
- Neue öffentliche `document_id`-Werte sind auf URL-unreserved ASCII beschränkt.
- Bestehende Legacy-Slash-IDs bleiben fachlich unverändert und werden nicht stillschweigend migriert.
- Die vollständige HTTP-Erreichbarkeit solcher Legacy-Slash-IDs bleibt **außerhalb** des aktuellen
  HTTP-Routenvertrags. Falls sie gefordert wird, ist ein separater Auftrag für Option B
  (Route-/OpenAPI-Anpassung) erforderlich.

**Review-Fix-Dateien unter Verifikation:**
- `modules/documents/contracts.py`
- `modules/documents/service.py`
- `modules/documents/validation.py`
- `interfaces/clients/documents_http.py`
- `tests/backend/test_documents_authorization_http.py`
- `tests/backend/test_documents_concurrency_http.py`
- `tests/backend/test_documents_http_api.py`
- `tests/interfaces/test_documents_http_client_fail_closed.py`
- `tests/modules/test_documents_event_contracts.py`
- `tests/modules/test_documents_infrastructure.py`

## Governance

- `docs/J04_M0_PATH_MATRIX.md` (kanonische Pfad-SoT)
- `docs/J04_M0_ALLOWED_ACTIONS_ANALYSIS.md` (Allowed-Actions-Bestandsaufnahme)
- `docs/MASTER_ORCHESTRATION_ROADMAP.md`
- `docs/contracts/j04-m0-openapi.json` (versionierter Vertrag; Export über `scripts/export_openapi.py`)
