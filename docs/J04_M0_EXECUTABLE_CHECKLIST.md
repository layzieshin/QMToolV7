# J04-M0 Executable Closure Checklist

Living task list for the J04-M0 executable closure plan. Status values: `TODO` | `PASS` | `BLOCKED` | `FAILED`.

## Repository baseline (CP00 input) — historical snapshot (2026-08-17)

> **Historisch / nicht aktuell:** Dieser Abschnitt dokumentiert den CP00-Eingangsstand
> vor dem ersten Closure-Commit. `HEAD` war damals identisch mit `origin/main`
> (`125709f`). Er darf nicht als aktueller Merge-Readiness-Stand gelesen werden.
> Der verifizierte Stand zum Start des Merge-Readiness-Programms steht in **MR00**
> unter „Current Merge-Readiness Program“. Historische CP00–CP08-, FR- und
> V-Abschnitte bleiben Evidenz und werden nicht rückwirkend umgeschrieben.

| Item | Value |
| --- | --- |
| Branch | `feature/ap-j04-m0` |
| `HEAD` | `125709fedc4c6b719a46cab9c45e4e342e3df241` |
| `origin/main` | `125709fedc4c6b719a46cab9c45e4e342e3df241` |
| Divergence | `0 0` (no local commits ahead/behind) |
| Modified tracked | 94 paths (92 with content diff; 2 stat-only) |
| Untracked (product) | 59 paths under repo root (excl. evidence) |
| Untracked (evidence) | ~3014 paths under `.j04*` (bulk E; ignored after CP00) |

## Checkpoint status

| CP | Title | Status | Commit SHA | Notes |
| --- | --- | --- | --- | --- |
| CP00 | Preserve and classify baseline | PASS | `0a844c2` | 153 A–D paths; 24 smokes green |
| CP01 | Backend ownership, auth, HTTP contracts | PASS | `3f3f7b1` | 77+1 tests green; OpenAPI reproducible; no code fixes |
| CP02 | Client-facing M0 use-case gates | PASS | `c2d6f3d` | 62 focused tests green; no code fixes |
| CP03 | Word COM isolation | PASS | `1993292` | DispatchEx + cleanup + redaction; 24 tests green |
| CP04 | PostgreSQL destructive gate (static/CI) | PASS | `c71c1f1` | 57 static/guard tests; CI ephemer PG16 |
| CP04-R | PG test infra remediation (Slot-2 / major pin) | PASS | `8c273de` | 28 guard/runner tests; PG18 local smoke; **nicht neu implementieren** |
| CP05 | Real-process acceptance harness | PASS | `29ddaa6` | 10 harness+reference tests; final gate NOT RUN |
| CP06 | Onedir packaging preparation | PASS | `ba67126` | 16 packaging tests green; Packaging NOT RUN |
| CP07 | Freeze technical acceptance candidate | PASS | `d19e8b9` | superseded by remediation `8c273de` for `$CandidateSha` |
| CP08 | Final acceptance gate | FAILED | — | PG live **51 passed**; regression **1 failed**; Word **BLOCKED** |
| CP08-R1 | Literal optional documents port in wiring | PASS | `fbea360` | Architecture gate green; constant still exported; **no freeze** |
| CP08-R2 | Realprocess scenario (replace skip stub) | PASS | `30b73e9` | Scenario implemented; live gate **NOT RUN** |
| Word readiness | Word COM `DispatchEx` probe (interactive) | PASS (WR05) | — | Safe mode title confirmed; interactive DispatchEx/Version/Quit PASS; add-ins not causal; DOCX/PDF E2E **NOT RUN** |
| CP08-R3 | Isolate realprocess workspace from pytest basetemp | PASS | `c3d6587` | Test-only; included in FR09 freeze |
| FR09 | Freeze R1+R2+R3 acceptance candidate | PASS | `1a22d38` | 50 focused gates; `$CandidateSha` below; CP08-V3 failed |
| CP08-V3 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at start contract (`pg_bootstrap` / RESET); Word **NOT REACHED** |
| CP08-R4 | Acceptance start contract via PG runner | PASS | `5233b5d` | Runner `--j04-final-acceptance`; guard unchanged; included in FR10 freeze |
| FR10 | Freeze R1–R4 acceptance candidate | PASS | `1bd8aa0` | 83 focused gates; `$CandidateSha` below; CP08-V4 failed |
| CP08-V4 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at `bootstrap_admin_login` (`/auth/me` 409); Word **NOT REACHED** |
| CP08-R5 | Bootstrap-admin `/auth/me` handshake | PASS | `34f39c0` | Harness-only password-change handshake; product auth unchanged; included in FR11 freeze |
| FR11 | Freeze R1–R5 acceptance candidate | PASS | `c263ff5` | 93 focused gates; `$CandidateSha` below; CP08-V5 failed |
| CP08-V5 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at `document_baseline_flow`; bootstrap handshake **PASS**; Word **NOT REACHED** |
| CP08-R6 | Document-create 403 (QMB actor + diagnostics) | PASS | `e28a44d` | Harness-only; Create/Race/Comments/Word-Token use seeded QMB; `require_version_success`; included in FR12 freeze |
| FR12 | Freeze R1–R6 acceptance candidate | PASS | `b63d9a1` | 108 focused gates; `$CandidateSha` below; CP08-V6 failed |
| CP08-V6 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at `etag_concurrency_race` (`TypeError`); document create **PASS**; Word **NOT REACHED** |
| CP08-R7 | ETag-race harness `sorted()` + stable assignment | PASS | `f5dcfa8` | Test-only; `sorted([a, b])`; both race bodies keep editor/reviewer/approver; included in FR13 freeze |
| FR13 | Freeze R1–R7 acceptance candidate | PASS | `cd3a376` | 137 focused gates; `$CandidateSha` below; CP08-V7 failed |
| CP08-V7 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** before artifacts (harness assigned usernames, PG uses UUID `user_id`; route masked 404); etag race **PASS**; Word **NOT REACHED** |
| CP08-R8 | Workflow assignments use `/auth/me` user_id | PASS | `31dc273` | Test-only; role → `user_id` from GET `/auth/me`; baseline + both race bodies; included in FR14 freeze |
| FR14 | Freeze R1–R8 acceptance candidate | PASS | `ed488ed` | 144 focused gates; `$CandidateSha` below; CP08-V8 failed |
| CP08-V8 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** in `training_read_receipt` before out-of-scope reads (`review/accept` sent as editor → 403); artifacts **PASS**; Word **NOT REACHED** |
| CP08-R9 | Document-release actor remediation + scope cut | PASS | _(uncommitted)_ | Test-only; editor/reviewer/approver use separate clients; gate ends at `APPROVED`; ready for controlled commit sequence |
| CP09 | Human acceptance | PASS | `e003b37` / `f7b867d` | Formale Acceptance 2026-08-20; Produkt-Merge `e003b37`; Main-Basis `f7b867d` (Skill only) |

## Current Merge-Readiness Program

Controlled program to take J04-M0 from the historical CP00–CP08 evidence to
technical merge readiness. Historical checkpoint rows above remain evidence and
are not rewritten. This program starts at MR00 and does not skip checkpoints.

CP08-R9 remains a successful **actor-fix** (separate editor/reviewer/approver
clients; fail-closed `require_version_success()` before ETag parse). That does
**not** mean the realprocess harness already covers the full mandatory M0
scope. Training/Reads, Change Requests, and mandatory archive remain out of
the M0 acceptance gate and are still incorrectly mixed into the historical
harness catalog; PDF-comment, signature-required `APPROVED`, content-stream,
and restart-at-`APPROVED` coverage are MR07 work. CP08-V8 is the last live
run. CP08-V9 has **not** been executed.

<!-- J04_M0_MERGE_LEDGER_START -->

Current checkpoint: COMPLETE

| ID | Titel | Status | Start-SHA | Ergebnis/Evidence | Commit |
| --- | --- | --- | --- | --- | --- |
| MR00 | Aktuellen Stand und Ledger etablieren | PASS | `3bf6518` | 6 passed; `build/j04-m0-closure/mr00-results-20260818T103125784Z/junit.xml` | pending user approval |
| MR01 | Duplicate-Create atomar verhindern | PASS | `3bf6518` | 79 passed; `build/j04-m0-closure/mr01-results-20260818T103800332Z/junit.xml` | pending user approval |
| MR02 | Documents-Dateipfade vollständig begrenzen | PASS | `3bf6518` | 52 passed; `build/j04-m0-closure/mr02-results-20260818T104608124Z/junit.xml` | pending user approval |
| MR03 | Autorisierung vor Zustands-/ETag-Offenlegung | PASS | `3bf6518` | 120 passed; `build/j04-m0-closure/mr03-results-20260818T110322811Z/junit.xml` | pending user approval |
| MR04 | Import-CAS und SQLite-Thread-Sicherheit | PASS | `3bf6518` | 80 passed; `build/j04-m0-closure/mr04-results-20260818T111025277Z/junit.xml` | pending user approval |
| MR05 | Signature-Dateien und Scratch-Lebenszyklus härten | PASS | `3bf6518` | 25 passed; `build/j04-m0-closure/mr05-results-20260818T112018936Z/junit.xml` | pending user approval |
| MR06 | DOCX-Kommentarsynchronisation stabilisieren | PASS | `3bf6518` | 71 passed; `build/j04-m0-closure/mr06-results-20260818T112948464Z/junit.xml` | pending user approval |
| MR07 | Realprocess-Harness auf verbindlichen M0-Scope bringen | PASS | `3bf6518` | 75 passed; `build/j04-m0-closure/mr07-results-20260818T135020994Z/junit.xml` | pending user approval |
| MR08 | Gesamte Regression und Candidate Freeze | PASS | `3bf6518` | 988 passed / 20 skipped; freeze regression `build/j04-m0-closure/mr08-freeze-regression-results-20260818T193330926Z/junit.xml`; CandidateSha `4db97ea72ffcb18823cd610599752cc1c8e8716d` | `4db97ea` |
| MR09 | Kontrollierten CP08-V9-Lauf ausführen | PASS | `c003dd9` | CP08-V11 PASS; 18/18 Realprocess-Schritte; 1 passed; `build/j04-m0-closure/mr09-cp08-v11-results-20260819T202601488Z/runner.log` | `254c8ea` |
| MR10 | Packaging, Golive, Human Gate und Merge | PASS | `be8fb01` | MR10-A/A-R1/B PASS; Human-Smoke PASS; 8 passed; `build/j04-m0-closure/mr10-c-closure-20260820T053032181Z/pre-commit-junit.xml` | `254c8ea` |

<!-- J04_M0_MERGE_LEDGER_END -->

### MR00 — Aktuellen Stand und Ledger etablieren

- **Status:** PASS
- **Startzeit:** 2026-08-18T10:26:00Z
- **Endzeit:** 2026-08-18T10:31:26Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Historischen CP00-Baselineabschnitt als Snapshot kennzeichnen,
  den aktuellen Repositoryzustand separat dokumentieren, den maschinenlesbaren
  Merge-Ledger plus Detailvorlage anlegen, den Ledger-Konsistenztest
  implementieren, CP08-R9 als Actor-Fix erhalten und klarstellen, dass der
  gesamte M0-Scope im Harness noch nicht korrekt abgebildet ist. Keine
  Produktdatei verändern.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — historischer Marker, aktueller Stand,
    Ledger, MR-Detailabschnitte
  - `tests/docs/test_docs_consistency.py` — Parser und Konsistenzregeln für den
    markierten Ledger
- **Bewusst nicht geänderte Dateien:** alle Produktdateien; die sieben
  uncommitted R9-Inhaltsdiffs außer diesem Checklist-Dokument;
  `interfaces/pyqt/widgets/signature_placement/label_geometry.py`;
  `modules/training/wiring.py`; `docs/transition/20260818/*`; Evidence unter
  `build/` und `.pytest_cache/`.
- **Implementierte Invarianten:** Ledger nur zwischen
  `J04_M0_MERGE_LEDGER_START` / `J04_M0_MERGE_LEDGER_END`; MR00–MR10 je einmal;
  zulässige Statuswerte; höchstens ein `IN_PROGRESS`; feste Reihenfolge; kein
  späterer `PASS` vor einem offenen früheren Checkpoint; jeder `PASS` mit
  Ergebnis und Evidence unter `build/j04-m0-closure/`; `Current checkpoint`
  = erster offener Checkpoint oder `COMPLETE`.
- **Alle Testversuche:**
  1. 2026-08-18T10:31:25Z — first gate while ledger `IN_PROGRESS` — PASS (`6 passed`; stamp `20260818T103125784Z`)
  2. 2026-08-18T10:32:51Z — confirmation after ledger `PASS` / current `MR01` — PASS (`6 passed`; stamp `20260818T103251842Z`)
- **Genaue Befehle:**

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/mr00-pytest-$stamp"
$Results = "build/j04-m0-closure/mr00-results-$stamp"
New-Item -ItemType Directory -Path $Results | Out-Null
& $Py -m pytest tests/docs/test_docs_consistency.py `
  -q `
  --basetemp $Base `
  --junitxml "$Results/junit.xml" 2>&1 |
  Tee-Object -FilePath "$Results/pytest.log"
```

First run stamp: `20260818T103125784Z`.
- **Passed/Failed/Skipped:** 6 passed / 0 failed / 0 skipped (JUnit `tests="6" failures="0"`)
- **Evidence-Pfade:**
  - `build/j04-m0-closure/mr00-results-20260818T103125784Z/junit.xml`
  - `build/j04-m0-closure/mr00-results-20260818T103125784Z/pytest.log`
  - `build/j04-m0-closure/mr00-pytest-20260818T103125784Z/`
- **Abweichungen:** keine materiellen Abweichungen zur Prompt-Erwartung; siehe
  Tabelle „Aktueller Repositoryzustand“. Prompt-Zahlen wurden am Repository
  nachgeprüft und bestätigt (`HEAD` `3bf6518`, `main` `125709f`, `0 60`,
  sieben Inhaltsdiffs, zwei Stat-only-Dateien, acht Transition-Dokumente,
  kein Remote-Branch/`PR`, CP08-V8 last live, CP08-V9 nicht ausgeführt).
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR00 PASS. Historischer CP00-Stand bleibt Snapshot.
  CP08-R9 bleibt als Actor-Fix erhalten; der Harness bildet den verbindlichen
  M0-Scope noch nicht vollständig ab. Nächster Checkpoint: MR01.

#### Aktueller Repositoryzustand (MR00, verifiziert)

Verifiziert vor der ersten MR00-Änderung. Prompt-Erwartung und Repository
stimmen in den entscheidenden Punkten überein; wo Zahlen aus dem Prompt
stammen, gilt der gemessene Stand.

| Item | Prompt-Erwartung | Gemessen |
| --- | --- | --- |
| Branch | `feature/ap-j04-m0` | `feature/ap-j04-m0` (tracking `origin/main`) |
| `HEAD` | `3bf6518` | `3bf651865c4da2c665d53f2fa83a3672b91b57ef` |
| `HEAD` subject | — | `docs(j04-m0): record CP08-V8 training abort` |
| `main` / `origin/main` | `125709f` | `125709fedc4c6b719a46cab9c45e4e342e3df241` |
| Divergence `main...HEAD` | ~60 ahead, 0 behind | `0 60` (`git rev-list --left-right --count`) |
| Remote `feature/ap-j04-m0` | none | `git ls-remote --heads origin feature/ap-j04-m0` empty |
| PR | none | `gh pr list --head feature/ap-j04-m0` → `[]` |
| Content diffs | 7 R9 files | 7 paths (`git diff --name-only`; `git diff --quiet` false) |
| Stat-only | 2 files | `label_geometry.py`, `modules/training/wiring.py` (`git diff --quiet` exit 0) |
| Untracked transition docs | 8 files | 8 files under `docs/transition/20260818/` |
| Last live CP08 | CP08-V8 | CP08-V8 FAILED at `training_read_receipt`; CandidateSha `ed488ed` |
| CP08-V9 | not executed | no V9 evidence; not started |

Uncommitted content diffs (R9, leave untouched except this checklist):

| Path | Numstat |
| --- | --- |
| `docs/J04_M0_ACCEPTANCE_REPORT.md` | 36 / 11 |
| `docs/J04_M0_EXECUTABLE_CHECKLIST.md` | 45 / 3 before MR00 edits |
| `docs/J04_M0_PATH_MATRIX.md` | 2 / 2 |
| `docs/MASTER_ORCHESTRATION_ROADMAP.md` | 3 / 1 |
| `docs/TRAINING_MODULE_SPEC.md` | 3 / 0 |
| `tests/acceptance/j04_m0_acceptance_scenario.py` | 43 / 43 |
| `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` | 114 / 7 |

Do not stage: the two stat-only files, `build/`, `.pytest_cache/`,
`.j04_m0_audit/`, other evidence trees, or `docs/transition/20260818/` in
implementation commits. Git write actions (commit/push/PR/merge) remain
user-gated.

### MR01 — Duplicate-Create atomar verhindern

- **Status:** PASS
- **Startzeit:** 2026-08-18T10:33:00Z
- **Endzeit:** 2026-08-18T10:40:13Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Zweites `POST /documents/versions/create` darf eine
  bestehende Version nicht per Repository-Upsert auf `PLANNED` zurücksetzen.
  HTTP-Ergebnis für berechtigten Duplicate-Create: 409.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `modules/documents/service.py` — `create_document_version` prüft Existenz
    unter `_mutation_lock` + `_write_transaction` und wirft
    `DocumentConflictError`; `_ensure_document_version` fängt denselben
    Konflikt für interne Import-Ensure-Aufrufe ab
  - `tests/modules/test_documents_service.py` — serieller Duplicate-Create,
    Duplicate nach Workflowstart, paralleler Create
  - `tests/modules/test_documents_infrastructure.py` — eine DB-Version,
    Artefakte und ETag unverändert
  - `tests/backend/test_documents_http_api.py` — HTTP 409 serial + nach Start
  - `tests/backend/test_documents_concurrency_http.py` — paralleler Create
    genau ein 200 und ein 409
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — Ledger/MR01-Dokumentation
  - `tests/docs/test_docs_consistency.py` — unverändert gegenüber MR00, im
    Gate mitgelaufen
- **Bewusst nicht geänderte Dateien:** Repository-Upsert bleibt der
  Zustandsupdate-Pfad; keine neue Create-API, kein HTTP-Mapping-Umbau
  (`DocumentConflictError` war bereits 409); R9-Dateien außer Checklist;
  Stat-only-Dateien; Transition-Dokumente.
- **Implementierte Invarianten:** Existenz von `(document_id, version)` vor
  Insert; bestehender Zustand, Header, Assignments, Artefakte und Event-Token
  unverändert; parallele Creates serialisiert durch den bestehenden Service-Lock.
- **Alle Testversuche:**
  1. 2026-08-18T10:38:00Z — MR01 gate — PASS (`79 passed`)
- **Genaue Befehle:**

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = "20260818T103800332Z"
$Base = "build/j04-m0-closure/mr01-pytest-$stamp"
$Results = "build/j04-m0-closure/mr01-results-$stamp"
& $Py -m pytest `
  tests/docs/test_docs_consistency.py `
  tests/modules/test_documents_service.py `
  tests/modules/test_documents_infrastructure.py `
  tests/backend/test_documents_http_api.py `
  tests/backend/test_documents_concurrency_http.py `
  -q --basetemp $Base --junitxml "$Results/junit.xml"
```

- **Passed/Failed/Skipped:** 79 passed / 0 failed / 0 skipped
- **Evidence-Pfade:**
  - `build/j04-m0-closure/mr01-results-20260818T103800332Z/junit.xml`
  - `build/j04-m0-closure/mr01-results-20260818T103800332Z/pytest.log`
  - `build/j04-m0-closure/mr01-pytest-20260818T103800332Z/`
- **Abweichungen:** `_ensure_document_version` fängt `DocumentConflictError` ab,
  damit Import-Ensure bei einem Race den bestehenden Zustand zurückgibt statt
  den Aufrufer zu 409-en. Keine neue öffentliche Fläche.
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR01 PASS. Duplicate-Create ist atomar und liefert
  409. Nächster Checkpoint: MR02.

### MR02 — Documents-Dateipfade vollständig begrenzen

- **Status:** PASS
- **Startzeit:** 2026-08-18T10:41:00Z
- **Endzeit:** 2026-08-18T10:47:50Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Artifact-, Scratch- und Release-Pfade dürfen rohe
  `document_id`-Werte nicht als Pfadbestandteile verwenden. Fachliche
  `document_id` in API und DB bleibt unverändert.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `modules/documents/storage.py` — Object-Keys
    `objects/<uuid-prefix>/<uuid><suffix>`; Containment vor mkdir/copy;
    Legacy-Keys lesbar
  - `modules/documents/naming.py` — Release-Dateiname bereinigt `document_id`
  - `modules/documents/artifact_ops.py` — Pfadauflösung über
    `resolve_storage_key`; Temp-PDF ohne `document_id`
  - `src/backend/documents_routes.py` — Import-Scratch nur UUID + serverseitige
    Endung unter `scratch/imports`
  - Tests in infrastructure, release-filename, artifacts-api, HTTP-API,
    artifacts-HTTP
- **Bewusst nicht geänderte Dateien:** Signature-Scratch (MR05);
  fachliche `document_id`-Validierung; Repository-Schema.
- **Implementierte Invarianten:** keine Datei außerhalb des Storage-Roots;
  keine `document_id`/Version/Artifact-Typ in neuen Storage-Keys; keine
  `storage_key`/Serverpfade in HTTP-Payloads; Legacy-Keys lesbar.
- **Alle Testversuche:**
  1. 2026-08-18T10:46:08Z — MR02 gate — PASS (`52 passed`)
- **Genaue Befehle:**

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = "20260818T104608124Z"
& $Py -m pytest `
  tests/docs/test_docs_consistency.py `
  tests/modules/test_documents_infrastructure.py `
  tests/modules/test_documents_release_filename.py `
  tests/modules/test_documents_artifacts_api.py `
  tests/backend/test_documents_http_api.py `
  tests/backend/test_documents_artifacts_http.py `
  -q --basetemp "build/j04-m0-closure/mr02-pytest-$stamp" `
  --junitxml "build/j04-m0-closure/mr02-results-$stamp/junit.xml"
```

- **Passed/Failed/Skipped:** 52 passed / 0 failed / 0 skipped
- **Evidence-Pfade:**
  - `build/j04-m0-closure/mr02-results-20260818T104608124Z/junit.xml`
  - `build/j04-m0-closure/mr02-results-20260818T104608124Z/pytest.log`
- **Abweichungen:** `contained_path` ist eine Funktion im bestehenden Storage-Owner,
  kein neues Modul. Backend-Scratch-Containment bleibt in der Route, ohne Import
  von Storage-Interna.
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR02 PASS. Nächster Checkpoint: MR03.

### MR03 — Autorisierung vor Zustands-/ETag-Offenlegung

- **Status:** PASS
- **Startzeit:** 2026-08-18T10:50:00Z
- **Endzeit:** 2026-08-18T11:06:12Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Unsichtbare Dokumente und unberechtigte stale Mutationen
  liefern 404, bevor ETag oder `current_state` offengelegt werden. Berechtigte
  stale Requests bleiben 409. Workflow-Policy bleibt fachlicher Owner.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `modules/documents/service.py` — `get_document_header_for_actor`;
    `mutate_version_if_current` prüft Sichtbarkeit und Aktion vor dem ETag
  - `modules/documents/api.py` — `DocumentsPoolApi.get_header_for_actor`;
    Import-Mutationen setzen `owner_or_privileged=True` und Actor
  - `src/backend/documents_routes.py` — actor-bewusstes `_load_state`; Header
    nur über `get_header_for_actor`; `ValidationError("document version not
    found")` → 404; Template-Create unterscheidet fehlend vs. unsichtbar
  - `tests/modules/test_documents_authorization_matrix.py` — Header/stale
    Actor-Invarianten; unsichtbare Admin-Negativfälle als 404
  - `tests/backend/test_documents_authorization_http.py` — versteckter Header,
    unauthorized stale 404 ohne `current_state`, berechtigter stale 409
- **Bewusst nicht geänderte Dateien:** Training, Reads, Change Requests;
  R9-Harness-Dateien (MR07); Signature-Scratch (MR05); `label_geometry.py`;
  `modules/training/wiring.py`; Transition-Dokumente.
- **Implementierte Invarianten:**
  - Unsichtbare Version/Header: 404 vor If-Match/`current_state`
  - Unberechtigte stale Assign/Import/Kommentar/Workflowmutation: 404 ohne
    `current_state`/`current_etag`
  - Berechtigte stale Mutation: 409 mit `current_state`
  - Sichtbares `APPROVED` bleibt für Observer lesbar
  - Workflow-Policy bleibt Owner der Aktionsprüfung
- **Alle Testversuche:**
  1. `20260818T105629353Z` — FAILED (7): unsichtbare Admin-Akteure erwarteten
     noch 403/`PermissionDeniedError` statt 404/`ValidationError`
  2. `20260818T110322811Z` — PASS
- **Genaue Befehle:** `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest
  tests/docs/test_docs_consistency.py
  tests/modules/test_documents_authorization_matrix.py
  tests/backend/test_documents_authorization_http.py
  tests/backend/test_documents_concurrency_http.py
  tests/backend/test_documents_http_api.py -q --basetemp
  build/j04-m0-closure/mr03-pytest-20260818T110322811Z --junitxml
  build/j04-m0-closure/mr03-results-20260818T110322811Z/junit.xml`
- **Passed/Failed/Skipped:** 120 passed / 0 failed / 0 skipped
- **Evidence-Pfade:**
  `build/j04-m0-closure/mr03-results-20260818T110322811Z/junit.xml`,
  `build/j04-m0-closure/mr03-results-20260818T110322811Z/pytest.log`
- **Abweichungen:** `get_header` bleibt intern für Owner-Pfade bestehen;
  HTTP-GET nutzt nur `get_header_for_actor`. Keine neue öffentliche
  Fach-API-Klasse.
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR03 PASS. Nächster Checkpoint: MR04.

### MR04 — Import-CAS und SQLite-Thread-Sicherheit

- **Status:** PASS
- **Startzeit:** 2026-08-18T11:06:12Z
- **Endzeit:** 2026-08-18T11:12:32Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** PDF/DOCX-Import stempelt das Import-Event in
  `last_event_id`/`last_event_at`/`last_actor_user_id` und persistiert den
  neuen ETag in derselben Write-Transaction. Replay mit altem ETag liefert
  409. Repository-Connections sind threadlokal, ohne `check_same_thread=False`.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `modules/documents/service.py` — Import stempelt und speichert den
    aktualisierten Zustand unter `_write_transaction`
  - `modules/documents/sqlite_repository.py` — `_txn_local` statt
    repositoryweiter Connection; nested reuse nur im selben Thread
  - `tests/modules/test_documents_infrastructure.py` — Import-CAS und
    SQLite-Thread-Invarianten
  - `tests/modules/test_documents_event_contracts.py` — gestempelter Import-Actor
  - `tests/backend/test_documents_http_api.py` — PDF/DOCX-Import-ETag und Replay
  - `tests/backend/test_documents_concurrency_http.py` — paralleler PDF-Import
    200/409
- **Bewusst nicht geänderte Dateien:** Template-Create-CAS (nicht im
  Pflichtgate); Signature-Scratch (MR05); Training; R9-Harness.
- **Implementierte Invarianten:**
  - Erster Import erzeugt neuen ETag und persistiert ihn
  - Replay mit altem ETag: 409, Zustand unverändert
  - Konkurrierende Imports: genau ein 200 und ein 409
  - Read während Write ohne `sqlite3.ProgrammingError`
  - Nested writes desselben Threads teilen die Connection
  - Rollback entfernt die threadlokale Connection
  - Kein `check_same_thread=False`
- **Alle Testversuche:**
  1. `20260818T111025277Z` — PASS
- **Genaue Befehle:** `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest
  tests/docs/test_docs_consistency.py
  tests/modules/test_documents_infrastructure.py
  tests/modules/test_documents_event_order.py
  tests/modules/test_documents_event_contracts.py
  tests/backend/test_documents_http_api.py
  tests/backend/test_documents_concurrency_http.py -q --basetemp
  build/j04-m0-closure/mr04-pytest-20260818T111025277Z --junitxml
  build/j04-m0-closure/mr04-results-20260818T111025277Z/junit.xml`
- **Passed/Failed/Skipped:** 80 passed / 0 failed / 0 skipped
- **Evidence-Pfade:**
  `build/j04-m0-closure/mr04-results-20260818T111025277Z/junit.xml`,
  `build/j04-m0-closure/mr04-results-20260818T111025277Z/pytest.log`
- **Abweichungen:** Service-Lock unverändert. Keine neue öffentliche API.
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR04 PASS. Nächster Checkpoint: MR05.

### MR05 — Signature-Dateien und Scratch-Lebenszyklus härten

- **Status:** PASS
- **Startzeit:** 2026-08-18T11:12:32Z
- **Endzeit:** 2026-08-18T11:20:58Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Signature-Scratch und Upload-Store dürfen den eigenen
  Root nicht verlassen; Klartextreste werden nach Export/Standalone/Workflow
  gelöscht. Kanonische Documents-Input-PDFs bleiben erhalten.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `modules/signature/signature_policy_ops.py` — sicherer PNG-Basename;
    Temp-Pfad gegen TemporaryDirectory-Root
  - `src/backend/signature_routes.py` — Export löscht nach Read; Standalone
    löscht Input/PNG/Output in `finally`; Upload-Store räumt nur den eigenen
    Root auf
  - `modules/documents/sign_intent_builder.py` — Workflow-Output-PDF als UUID
  - `modules/documents/signature_guard.py` — Workflow-PNG/Output nach Store
    und auf Fehlerpfaden löschen
  - `modules/documents/service.py` — `sign_and_store_signed_artifact` räumt
    Scratch auf
  - `tests/modules/test_signature_templates.py` — Filename-Hint Escape
  - `tests/backend/test_signature_http_api.py` — Export/Standalone/Janitor
  - `tests/backend/test_documents_signed_transitions_http.py` — kein
    Workflow-Scratch, SOURCE_PDF bleibt
- **Bewusst nicht geänderte Dateien:** Training; Reads; neues Signature-API;
  kein globaler Janitor; kein neuer Endpunkt.
- **Implementierte Invarianten:**
  - Filename-Hint kann Temp-Root nicht verlassen
  - Export liefert Bytes und hinterlässt keine Datei
  - Standalone Erfolg/Fehler ohne Klartextreste
  - Workflow erzeugt SIGNED_PDF ohne Scratchreste
  - Upload-Store bereinigt nur abgelaufene/verwaiste Dateien im eigenen Root
  - Fremddateien außerhalb des Roots bleiben unangetastet
  - Kanonisches Documents-Input-PDF wird nicht gelöscht
- **Alle Testversuche:**
  1. `20260818T111640820Z` — FAILED (2): Upload-Purge löschte frische Datei
     vor Store-Insert; Workflow-Cleanup lag in `signature_guard`, nicht nur
     in `sign_and_store_signed_artifact`
  2. `20260818T112018936Z` — PASS
- **Genaue Befehle:** `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest
  tests/docs/test_docs_consistency.py
  tests/modules/test_signature_service_v2.py
  tests/modules/test_signature_templates.py
  tests/backend/test_signature_http_api.py
  tests/backend/test_signature_authorization_http.py
  tests/backend/test_documents_signed_transitions_http.py -q --basetemp
  build/j04-m0-closure/mr05-pytest-20260818T112018936Z --junitxml
  build/j04-m0-closure/mr05-results-20260818T112018936Z/junit.xml`
- **Passed/Failed/Skipped:** 25 passed / 0 failed / 0 skipped
- **Evidence-Pfade:**
  `build/j04-m0-closure/mr05-results-20260818T112018936Z/junit.xml`,
  `build/j04-m0-closure/mr05-results-20260818T112018936Z/pytest.log`
- **Abweichungen:** Keine neue öffentliche API. Windows-Unlink mit kurzem
  Retry wegen gehaltener PDF-Handles.
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR05 PASS. Nächster Checkpoint: MR06.

### MR06 — DOCX-Kommentarsynchronisation stabilisieren

- **Status:** PASS
- **Startzeit:** 2026-08-18T11:20:58Z
- **Endzeit:** 2026-08-18T11:32:18Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Stabile Kommentaridentität `(document_id, version,
  context, w:id)`; Autor/Datum/Text sind Inhalt. Legacy-Keys über Kontext/ID
  eindeutig matchen; Status bleibt beim Resync erhalten.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `modules/documents/comment_extractors/docx_comment_reader.py` — Key
    `context|w:id`; deterministische ZIP/`comments.xml`-Fehler
  - `modules/documents/comment_sync_service.py` — Legacy-Match, eindeutige
    `ref_no`, Status-/Audit-Erhalt, keine Duplikat-Löschung
  - `modules/documents/sqlite_repository.py` — Upsert aktualisiert
    Source-Key, Autor, Quelldatum und Text
  - `tests/modules/test_documents_infrastructure.py` — echtes DOCX-ZIP;
    Signaturkette liest gespeichertes SIGNED_PDF statt Scratch
  - `tests/backend/test_documents_p4_p9_http.py` — HTTP-Sync in IN_REVIEW
    idempotent; Observer 404; Converter-Capability gemockt
- **Bewusst nicht geänderte Dateien:** Training; Reads; Change Requests;
  R9-Harness (MR07); kein neuer Kommentar-Service.
- **Implementierte Invarianten:**
  - Wiederholter Sync mit/ohne Datum: ein Kommentar
  - Textänderung bei gleichem `w:id` aktualisiert denselben Kommentar
  - Zwei neue Kommentare haben eindeutige Referenzen
  - Kommentarstatus bleibt erhalten
  - Observer bleibt ausgeschlossen
  - HTTP-Sync in IN_REVIEW idempotent
  - Ungültiges ZIP / fehlende `comments.xml` deterministisch
- **Alle Testversuche:**
  1. `20260818T112642792Z` — FAILED (1): Signaturketten-Test las gelöschte
     Scratch-PDF (MR05-Invariante)
  2. `20260818T112948464Z` — PASS
- **Genaue Befehle:** `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest
  tests/docs/test_docs_consistency.py
  tests/modules/test_documents_infrastructure.py
  tests/backend/test_documents_p4_p9_http.py
  tests/backend/test_documents_authorization_http.py
  tests/backend/test_documents_concurrency_http.py -q --basetemp
  build/j04-m0-closure/mr06-pytest-20260818T112948464Z --junitxml
  build/j04-m0-closure/mr06-results-20260818T112948464Z/junit.xml`
- **Passed/Failed/Skipped:** 71 passed / 0 failed / 0 skipped
- **Evidence-Pfade:**
  `build/j04-m0-closure/mr06-results-20260818T112948464Z/junit.xml`,
  `build/j04-m0-closure/mr06-results-20260818T112948464Z/pytest.log`
- **Abweichungen:** Keine neue öffentliche API. HTTP mockt nur
  `docx_conversion_available`.
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR06 PASS. Nächster Checkpoint: MR07.

### MR07 — Realprocess-Harness auf verbindlichen M0-Scope bringen

- **Status:** PASS
- **Startzeit:** 2026-08-18T12:06:00Z
- **Endzeit:** 2026-08-18T13:50:21Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Pflichtschrittfolge des M0-Realprocess ohne Training,
  Reads, Read Receipts, Change Requests, Archivierung und Word-COM-Schritt;
  signaturpflichtige Übergänge bis `APPROVED`; Artefakt-Content-Stream;
  Restart in `APPROVED`.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `tests/acceptance/j04_m0_acceptance_scenario.py` — 18-Schritt-Katalog
    und Handler (Signaturpflicht, Content-Stream, PDF/DOCX-Kommentare,
    signed review/approval, Restart `APPROVED`)
  - `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — Vertrag
    für Reihenfolge, verbotene Routen, Signatur-Actor, Hash-Header,
    Kommentartrennung, Restart-Status
  - `tests/acceptance/test_j04_m0_realprocess.py` — kein separater
    Word-Schritt; voller Katalog muss PASS sein
  - `tests/backend/test_documents_signed_transitions_http.py` — R1:
    `require_password=True`, Actor-Passwörter, Negativtest ohne Passwort
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — Ledger und MR07-Detail
  - `docs/J04_M0_ACCEPTANCE_REPORT.md` — MR07-Evidence
- **Bewusst nicht geänderte Dateien:** Produktdateien; Training; Reads;
  Change Requests; Lifecycle; PATH_MATRIX/Roadmap/Training-Spec; kein neuer
  Harness-Owner; `test_j04_m0_harness_unit.py` unverändert.
- **Implementierte Invarianten:**
  - Katalog genau 18 Schritte in der verbindlichen Reihenfolge
  - Training, `/documents/reads/*`, Change Requests, Archivierung und
    `word_com_live_boundary` fehlen in Katalog und Handlern
  - alle drei Profilübergänge `signature_required=True`
  - Editor/Reviewer/Approver aktivieren getrennte Signaturassets
  - `signed_editing_complete` fail-closed ohne Sign-Intent, sonst `IN_REVIEW`
  - PDF-Kommentar und idempotenter DOCX-Sync getrennt während `IN_REVIEW`
  - `signed_review_approval` erreicht `APPROVED` und weist SIGNED_PDF sowie
    RELEASED_PDF nach
  - Artefakt-Content: SHA-256, ETag, Content-Length, keine Serverpfade
  - Restart erwartet `APPROVED` und überlebende Editor-/Reviewer-Sessions
- **Alle Testversuche:**
  1. `20260818T121816713Z` — FAILED (1): bekannter lokaler
     `WinError 10053` im Bootstrap-HTTP-Handler
  2. `20260818T121957135Z` — PASS (`73 passed`)
  3. `20260818T122324312Z` — Ledger-PASS-Bestätigung: docs-consistency +
     scenario-unit **43 passed**
- **MR07-R1 Befund:** Sign-Intents sendeten `password: None`. Die produktive
  Signature-Konfiguration hat `require_password=True`; `SignatureExecuteOps`
  lehnt fehlende Passwörter ab. Der MR07-Mock prüfte nur die Existenz von
  `sign_intent`. Der Same-Process-Backendtest setzte `require_password=False`.
- **MR07-R1 Remediation:** verpflichtendes `_sign_intent_body(password)`;
  Actor-Passwörter in Editor-/Reviewer-/Approver-Übergängen;
  `X-Signature-Password` bei Asset-Aktivierung; Mocks prüfen Passwort je
  Actor; Backendtest mit `require_password=True`; Negativtest ohne Passwort.
- **Alle Testversuche (R1):**
  1. `20260818T134857083Z` — FAILED (1): Inspect-Assertion traf den
     Verify-Schritt statt `_activate_signature_asset`
  2. `20260818T134943927Z` — R1-Fokus **53 passed**
  3. `20260818T135020994Z` — vollständiges ursprüngliches MR07-Gate
     **75 passed**
- **Genaue Befehle:** `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest
  tests/docs/test_docs_consistency.py
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py
  tests/backend/test_documents_signed_transitions_http.py
  tests/modules/test_signature_service_v2.py
  -m "not postgres and not j04_final_acceptance" -q --basetemp
  build/j04-m0-closure/mr07-r1-pytest-20260818T134943927Z --junitxml
  build/j04-m0-closure/mr07-r1-results-20260818T134943927Z/junit.xml`
  danach dasselbe ursprüngliche MR07-Gate mit stamp `20260818T135020994Z`.
- **Passed/Failed/Skipped:** 75 passed / 0 failed / 0 skipped (volles MR07-Gate);
  R1-Fokus 53 passed / 0 failed / 0 skipped
- **Evidence-Pfade:**
  `build/j04-m0-closure/mr07-results-20260818T135020994Z/junit.xml`,
  `build/j04-m0-closure/mr07-r1-results-20260818T134943927Z/junit.xml`,
  `build/j04-m0-closure/mr07-r1-results-20260818T134857083Z/junit.xml`
  (R1 Versuch 1),
  `build/j04-m0-closure/mr07-results-20260818T121957135Z/junit.xml`
  (ursprüngliches Katalog-Gate). `build/` ist Evidence/Basetemp, nicht
  gestaged und kein Produktcode.
- **Abweichungen:** Kein Produktcode. Signature-Policy wird nicht abgeschwächt.
  `_wire_signature_module` bleibt `require_password=False` für andere
  Signature-HTTP-Tests; der signed-transition-Backendtest setzt danach
  ausdrücklich `require_password=True`.
  CP08-R9-Actor-Fix bleibt erhalten.
  Live-`import-docx` hängt weiterhin an der bestehenden Converter-Capability
  der Produktschnittstelle; Word-COM-Konvertierung bleibt außerhalb MR07.
- **Commit-SHA:** pending user approval
- **Abschlussbewertung:** MR07 PASS nach R1. Nächster Checkpoint: MR08.

### MR08 — Gesamte Regression und Candidate Freeze

- **Status:** PASS
- **Startzeit:** 2026-08-18T14:07:28Z
- **Endzeit:** 2026-08-18T19:45:28Z
- **Start-SHA:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ziel und Scope:** Nicht-destruktive Regression, CLI-E2E, Architektur-/OpenAPI-
  Verträge und Diff-/Scopeprüfung des uncommitted J04-M0-Standes. Keine
  Produktänderung. Kein PostgreSQL-Live, kein `j04_final_acceptance`, kein
  CP08-V9, kein Word COM, kein Packaging, kein Golive, kein sichtbarer
  PyQt-Smoke. **Freeze pending explicit user approval.**
- **Geänderte Dateien und Verantwortlichkeiten (dieser Checkpoint):**
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — Ledger IN_PROGRESS→FAILED, Ausführungsplan,
    Gate-Evidence, Fehlerklassifikation, MR08-R1-Vorschlag
  - `docs/J04_M0_ACCEPTANCE_REPORT.md` — MR08 begonnen und FAILED, Freeze nicht
    freigegeben, Gesamtstatus NOT_READY
- **Bewusst nicht geänderte Dateien:** alle 36 Inhaltsdiffs außer den zwei
  MR08-Dokumenten; die zwei stat-only Dateien; `docs/transition/20260818/*`;
  Produktcode; Tests; Training; Reads; Change Requests; Archivierung.
- **Ausgangs-HEAD:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef`
- **Divergenz bei Start:** `0 hinter / 60 voraus` gegen `origin/main`
- **Vollständiges Diff-Manifest (36 Inhaltsdiffs gegen HEAD):**

  Produkt / Backend (13):
  1. `modules/documents/api.py`
  2. `modules/documents/artifact_ops.py`
  3. `modules/documents/comment_extractors/docx_comment_reader.py`
  4. `modules/documents/comment_sync_service.py`
  5. `modules/documents/naming.py`
  6. `modules/documents/service.py`
  7. `modules/documents/sign_intent_builder.py`
  8. `modules/documents/signature_guard.py`
  9. `modules/documents/sqlite_repository.py`
  10. `modules/documents/storage.py`
  11. `modules/signature/signature_policy_ops.py`
  12. `src/backend/documents_routes.py`
  13. `src/backend/signature_routes.py`

  Tests (18):
  14. `tests/acceptance/j04_m0_acceptance_scenario.py`
  15. `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py`
  16. `tests/acceptance/test_j04_m0_realprocess.py`
  17. `tests/backend/test_documents_artifacts_http.py`
  18. `tests/backend/test_documents_authorization_http.py`
  19. `tests/backend/test_documents_concurrency_http.py`
  20. `tests/backend/test_documents_http_api.py`
  21. `tests/backend/test_documents_p4_p9_http.py`
  22. `tests/backend/test_documents_signed_transitions_http.py`
  23. `tests/backend/test_signature_http_api.py`
  24. `tests/docs/test_docs_consistency.py`
  25. `tests/modules/test_documents_artifacts_api.py`
  26. `tests/modules/test_documents_authorization_matrix.py`
  27. `tests/modules/test_documents_event_contracts.py`
  28. `tests/modules/test_documents_infrastructure.py`
  29. `tests/modules/test_documents_release_filename.py`
  30. `tests/modules/test_documents_service.py`
  31. `tests/modules/test_signature_templates.py`

  Dokumentation (5):
  32. `docs/J04_M0_ACCEPTANCE_REPORT.md`
  33. `docs/J04_M0_EXECUTABLE_CHECKLIST.md`
  34. `docs/J04_M0_PATH_MATRIX.md`
  35. `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  36. `docs/TRAINING_MODULE_SPEC.md`

  Summe 13+18+5 = 36 Inhaltsdiffs.

- **Ausgeschlossene Dateien (kein Commit, kein Anfassen):**
  - `interfaces/pyqt/widgets/signature_placement/label_geometry.py` (stat-only)
  - `modules/training/wiring.py` (stat-only)
  - `docs/transition/20260818/00_README.md`
  - `docs/transition/20260818/01_IMMEDIATE_MERGE_SEQUENCE.md`
  - `docs/transition/20260818/02_J04_M0_SCOPE_AND_ACCEPTANCE.md`
  - `docs/transition/20260818/03_MASTER_TRANSITION_ROADMAP.md`
  - `docs/transition/20260818/04_BACKEND_MODULE_MIGRATION_PATTERN.md`
  - `docs/transition/20260818/05_DEPENDENCIES_AND_PARALLEL_WORK.md`
  - `docs/transition/20260818/06_FOLLOWUP_PACKAGES.md`
  - `docs/transition/20260818/07_CORRECTIONS_TO_EXISTING_DOCS.md`
- **Testgates (seriell, je eigener UTC-Stamp / basetemp / JUnit):**
  0. Ledger-Konsistenz nach IN_PROGRESS
  1. Verträge und Architektur
  2. CLI-E2E (`tests/e2e_cli`, Marker `not postgres and not j04_final_acceptance`)
  3. Vollständige nicht-live Regression (`pytest -m "not postgres and not j04_final_acceptance"`)
- **Fail-fast-Regeln:** Beim ersten roten Pflichtgate stoppen; keine
  Produkt-/Testkorrektur in MR08; Fehler klassifizieren; Produkt-/Test-/ungeklärter
  Fehler → MR08 FAILED und MR08-R1 vorschlagen; eindeutiger Umgebungsblocker →
  BLOCKED; Current checkpoint bleibt MR08; kein automatischer Retry mit
  geänderter Assertion; kein Freeze, keine Git-Schreibaktion.
- **Acceptance Criteria:**
  - Alle drei Pflichtgates Exit 0, 0 failures, 0 errors
  - Skips vollständig dokumentiert und sachlich begründet
  - Diff-Manifest unverändert außer den zwei MR08-Dokumenten
  - Adversarial Review ohne neue APIs/Parallelpfade/Interna-Imports
  - Freeze nicht gesetzt ohne ausdrückliche Nutzerfreigabe
- **Implementierte Invarianten:** keine Produktinvarianten in diesem Checkpoint;
  Regression darf den uncommitted Stand nicht verändern.
- **Alle Testversuche:**
  0. `20260818T140815286Z` — Ledger-Konsistenz nach IN_PROGRESS — **6 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-ledger-results-20260818T140815286Z/junit.xml`)
  1. `20260818T140907659Z` — Gate 1 Verträge und Architektur — **53 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-contract-results-20260818T140907659Z/junit.xml`,
     `tests="53" failures="0" errors="0" skipped="0"`)
  2. `20260818T140950379Z` — Gate 2 CLI-E2E — **31 passed / 0 failed / 20 skipped**
     (`build/j04-m0-closure/mr08-cli-results-20260818T140950379Z/junit.xml`,
     `tests="51" failures="0" errors="0" skipped="20"`)
     Skips (sachlich, Marker `not_in_m0`, außerhalb reduziertem J04-M0):
     - 16× Legacy local documents CLI workflow
     - 3× Legacy local documents CLI authorization matrix
     - 1× Legacy training flow (`documents_read`/comments Transport)
  3. `20260818T141720756Z` — Gate 3 vollständige nicht-live Regression — **FAILED**
     1208 passed / 1 failed / 0 errors / 20 skipped
     (`build/j04-m0-closure/mr08-regression-results-20260818T141720756Z/junit.xml`,
     `tests="1229" failures="1" errors="0" skipped="20"`)
     Failure:
     `tests/modules/test_documents_authorization_matrix.py::DocumentsAuthorizationMatrixTest::test_open_source_reauthorization_on_artifact_read_path`
     `DocumentConflictError: document version changed since it was loaded`
     Skips: dieselben 20 `not_in_m0` wie Gate 2.
  4. `20260818T143406754Z` — Ledger-Konsistenz nach FAILED — **6 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-failed-ledger-results-20260818T143406754Z/junit.xml`)
     Kein Retry von Gate 3; nur Dokumentationsintegrität.
  5. `20260818T193258134Z` — Ledger-Konsistenz vor Freeze-Docs-Commit — **6 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-freeze-pre-docs-results-20260818T193258134Z/junit.xml`)
  6. `20260818T193330926Z` — Candidate-Freeze-Regression — **PASS**
     Konsole: 988 passed / 20 skipped / 52 deselected / 238 subtests passed.
     JUnit: `tests="1246" failures="0" errors="0" skipped="20" time="697.037"`
     (`build/j04-m0-closure/mr08-freeze-regression-results-20260818T193330926Z/junit.xml`)
- **Genaue Befehle:**

```powershell
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
New-Item -ItemType Directory -Force -Path "build/j04-m0-closure/mr08-ledger-results-$stamp" | Out-Null
.\.venv\Scripts\python.exe -m pytest tests/docs/test_docs_consistency.py -q --basetemp "build/j04-m0-closure/mr08-ledger-pytest-$stamp" --junitxml "build/j04-m0-closure/mr08-ledger-results-$stamp/junit.xml"
# stamp 20260818T140815286Z

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$root = "build/j04-m0-closure"
New-Item -ItemType Directory -Force -Path "$root/mr08-contract-results-$stamp" | Out-Null
.\.venv\Scripts\python.exe -m pytest tests/docs/test_docs_consistency.py tests/interfaces/test_architecture_gates.py tests/modules/test_module_contract_wiring.py tests/platform/test_documents_bootstrap_provenance.py tests/backend/test_openapi_contract.py -m "not postgres and not j04_final_acceptance" -q --basetemp "$root/mr08-contract-pytest-$stamp" --junitxml "$root/mr08-contract-results-$stamp/junit.xml"
# stamp 20260818T140907659Z

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
New-Item -ItemType Directory -Force -Path "$root/mr08-cli-results-$stamp" | Out-Null
.\.venv\Scripts\python.exe -m pytest tests/e2e_cli -m "not postgres and not j04_final_acceptance" -q --basetemp "$root/mr08-cli-pytest-$stamp" --junitxml "$root/mr08-cli-results-$stamp/junit.xml"
# stamp 20260818T140950379Z

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
New-Item -ItemType Directory -Force -Path "$root/mr08-regression-results-$stamp" | Out-Null
.\.venv\Scripts\python.exe -m pytest -m "not postgres and not j04_final_acceptance" -q --basetemp "$root/mr08-regression-pytest-$stamp" --junitxml "$root/mr08-regression-results-$stamp/junit.xml"
# stamp 20260818T141720756Z
```

- **Passed/Failed/Skipped:** Gate 0: 6/0/0; Gate 1: 53/0/0; Gate 2: 31/0/20; Gate 3: 1208/1/20
- **Evidence-Pfade:** `build/j04-m0-closure/mr08-*` (nicht gestaged, kein Produktcode)
- **Fehlerklassifikation (Gate 3):** **2. Testfehler.**
  Der Test hält `state` von `assign_workflow_roles` und ruft danach
  `import_existing_pdf` auf, das seit MR04 `last_event_id` stempelt. Anschließend
  geht `DocumentsWorkflowApi.start_workflow(state, …)` über
  `mutate_version_if_current` und wirft korrekt `DocumentConflictError`.
  Die Artifact-Reautorisierungsprüfungen wurden nicht erreicht. Der Testkörper
  ist gegenüber HEAD unverändert; die Produkt-CAS-Invariante von MR04 ist
  beabsichtigt. Kein Umgebungsfehler, kein Produktregressionsfix in MR08.
- **Adversarial Review:** nicht ausgeführt im ursprünglichen MR08 (Fail-fast nach
  Gate 3). Nach MR08-R1 Gate 3 ausgeführt — siehe Unterabschnitt.
- **Abweichungen:** Ursprüngliches Gate 3 rot; Freeze nicht gesetzt; MR09 nicht begonnen.
- **Commit-SHA:**
  - ProductCommit `$ProductCommit` = `70d4f4c11529b9539856dbdcc7456ea18689bf27` (`70d4f4c`)
  - AcceptanceCommit `$AcceptanceCommit` = `6195637897588ae305f05617659899e9b9a51431` (`6195637`)
  - FreezeCommit / MR08 CandidateSha `$CandidateSha` = `4db97ea72ffcb18823cd610599752cc1c8e8716d` (`4db97ea`)
  - CandidateDocsCommit folgt nach diesem SHA-Eintrag und darf nur die zwei Dokumentdateien enthalten
- **Abschlussbewertung:** **MR08 PASS.** Freeze-Regression PASS. Cumulative review PASS.
  Candidate-Freeze gilt ab `$CandidateSha` `4db97ea`. Nach dem Freeze keine Code-/Teständerung.
  Current checkpoint MR09. MR09 bleibt TODO und ist nicht begonnen. Gesamtstatus NOT_READY.
  Historischer FR14-Candidate `ed488ed` bleibt Historie. `Accepted` ist nicht gesetzt.

#### MR08-R1 — Import-ETag im Artifact-Reautorisierungstest fortschreiben

- **Status:** PASS (Remediation; Parent MR08 bleibt IN_PROGRESS bis Freeze-Freigabe)
- **Startzeit:** 2026-08-18T14:46:26Z
- **Endzeit:** 2026-08-18T15:08:14Z
- **Start-HEAD:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Ausgangsfehler:** Gate 3 `20260818T141720756Z` — 1208 passed / 1 failed /
  20 skipped. JUnit:
  `build/j04-m0-closure/mr08-regression-results-20260818T141720756Z/junit.xml`
  Failure:
  `tests/modules/test_documents_authorization_matrix.py::DocumentsAuthorizationMatrixTest::test_open_source_reauthorization_on_artifact_read_path`
  `DocumentConflictError: document version changed since it was loaded`
- **Nachgewiesene Ursache:** Der Test speichert `state` aus
  `assign_workflow_roles`, ruft `import_existing_pdf` auf (seit MR04 stempelt
  der Import in derselben Write-Transaction einen neuen `last_event_id` und
  gibt den aktualisierten `DocumentVersionState` zurück), verwirft den
  Rückgabewert und übergibt den alten ETag an `start_workflow`.
  `mutate_version_if_current` erkennt den Konflikt korrekt. Die Artifact-
  Reautorisierung wird nicht erreicht. Produkt-CAS ist richtig.
- **Zulässiger Drei-Dateien-Scope:**
  1. `tests/modules/test_documents_authorization_matrix.py` — nur der betroffene
     Testfall
  2. `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — dieser Plan, Fortschritt, Evidence
  3. `docs/J04_M0_ACCEPTANCE_REPORT.md` — MR08-R1-Ergebnis, NOT_READY
- **Explizit ausgeschlossene Produktänderungen:** `modules/documents/*`;
  `mutate_version_if_current`; Import-CAS-Semantik; Reload-/Fallback-Helper;
  neue API/Service/Wrapper; neue Tests außerhalb dieses Falls; abgeschwächte
  Assertions; PostgreSQL; `j04_final_acceptance`; CP08-V9; Word COM; Packaging;
  Golive; PyQt-Smoke; Git-Schreibaktionen; stat-only Dateien; Transition-Docs.
- **Ausgeführte minimale Testkorrektur:** Import-Rückgabewert `imported` verwendet;
  `self.assertNotEqual(imported.last_event_id, state.last_event_id)`;
  `start_workflow(imported, …)`. Kein Reload, kein Fallback, keine
  Repository-Interna. Bestehende Artifact-Assertions vollständig erhalten.
- **Fail-fast-Regeln:** Beim ersten roten Pflichtgate stoppen; keine weitere
  Änderung; kein Gate 3 nach rotem R1-A/B; anderer Gate-3-Fehler → MR08-R1
  FAILED, kein adversarialer Review, MR08-R2 vorschlagen, kein Freeze.
- **Alle Testversuche:**
  0. `20260818T144714476Z` — Ledger-Konsistenz nach R1 IN_PROGRESS — **6 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r1-ledger-results-20260818T144714476Z/junit.xml`)
  1. `20260818T144754849Z` — Gate R1-A einzelner zuvor roter Test — **1 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r1-target-results-20260818T144754849Z/junit.xml`)
  2. `20260818T144816993Z` — Gate R1-B Authorization-/Import-Schicht — **71 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r1-focused-results-20260818T144816993Z/junit.xml`,
     `tests="71" failures="0" errors="0" skipped="0"`)
  3. `20260818T144851070Z` — Gate 3 vollständige nicht-live Regression — **1209 passed / 0 failed / 0 errors / 20 skipped**
     (`build/j04-m0-closure/mr08-r1-regression-results-20260818T144851070Z/junit.xml`,
     `tests="1229" failures="0" errors="0" skipped="20"`)
     Skips (`not_in_m0`): 16 Legacy-Documents-CLI, 3 CLI-Auth-Matrix, 1 Training/`documents_read`
  4. `20260818T151044314Z` — Ledger-Konsistenz nach finaler Dokumentation — **6 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r1-final-ledger-results-20260818T151044314Z/junit.xml`)
- **Passed/Failed/Skipped:** R1-A 1/0/0; R1-B 71/0/0; Gate 3 1209/0/20
- **Evidence-Pfade:** `build/j04-m0-closure/mr08-r1-*` (nicht gestaged, kein Produktcode)
- **Adversarialer Review:** **PASS** (kumulativer 36-Dateien-Diff gegen HEAD).
  Keine neuen Entrypoints, keine neue Public-API-Klasse, kein Service/Wrapper/Helper,
  kein paralleler Persistenzpfad, keine Modul-Internaimporte im Backend,
  Autorisierung in der Documents-Serviceschicht, keine Testabschwächung in R1,
  Training/Reads/CR/Archiv nicht im M0-Gate. Zwei dokumentierte P3-Reste
  (außerhalb MR08-R1, keine Produktänderung):
  1. `artifact_ops.py` Fallback `root / storage_key` wenn `resolve_storage_key`
     fehlt (Produktions-Storage hat die Methode).
  2. Template-Create-Mutate übergibt kein `actor`/`owner_or_privileged` auf dem
     Lock (unsichtbare Versionen 404en vorher; sichtbar-nicht-Owner kann 409
     statt 404 erhalten). **Behoben in MR08-R2.**
  Git: 36 Inhaltsdiffs; Testkorrektur in bereits vorhandener Diff-Datei;
  stat-only ohne Inhaltsdiff; acht Transition-Dokumente untracked; kein Staging.
- **Abweichungen:** keine. Historische Gates 1 und 2 nicht einzeln wiederholt
  (in Gate 3 enthalten).
- **Commit-SHA:** pending user approval — Freeze pending explicit user approval
- **Abschlussbewertung:** Regression PASS after MR08-R1 – Candidate Freeze
  pending explicit user approval. Parent MR08 bleibt IN_PROGRESS. NOT_READY.
  Adversarialer Review nach R1 wieder geöffnet (MR08-R2).

#### MR08-R2 — Template-Create-Autorisierung vor Create und ETag

- **Status:** PASS
- **Startzeit:** 2026-08-18T15:23:52Z
- **Endzeit:** 2026-08-18T15:32:19Z
- **Start-HEAD:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Historie:** MR08-R1 und dessen Regression bleiben historisch PASS.
  Der adversariale Review wird wegen zweier Template-Autorisierungslücken
  wieder geöffnet. MR08-R3 (Artifact-Storage-Fallback) ist nachfolgend und
  **nicht** begonnen.
- **Reproduzierte Fehler:**
  - A bestehendes sichtbares Dokument: sichtbarer Nicht-Owner mit stale ETag
    erhält HTTP 409 inkl. `current_etag`/`current_state`; mit aktuellem ETag
    HTTP 403. Ursache: `_mutate_version_state` ohne `actor` /
    `owner_or_privileged`, ETag vor Owner-Prüfung.
  - B fehlendes Ziel: Observer erzeugt die Version (HTTP 200, wird Owner).
    `/documents/versions/create` lehnt denselben Actor mit HTTP 403 ab.
    Ursache: Missing-Target-Zweig ohne QMB-/Delegated-Create-Policy.
- **Vorhandene Behavior-Owner:**
  - `DocumentsWorkflowApi.create_from_template` (`modules/documents/api.py`)
  - `_mutate_version_state` / `create_from_template`
    (`src/backend/documents_routes.py`)
  - Referenzpolicy: `DocumentsWorkflowApi.create_document_version` (unverändert)
  - Lock: `mutate_version_if_current` (unverändert, nicht abschwächen)
- **Zulässige sechs Dateien:**
  1. `modules/documents/api.py` — bestehende Methode erweitern
  2. `src/backend/documents_routes.py` — Lock-Flag und Actor durchreichen
  3. `tests/backend/test_documents_authorization_http.py` — HTTP-Verträge
  4. `tests/modules/test_documents_authorization_matrix.py` — Public-API-Vertrag
  5. `docs/J04_M0_EXECUTABLE_CHECKLIST.md`
  6. `docs/J04_M0_ACCEPTANCE_REPORT.md`
- **Zielverhalten:**
  - Missing: QMB oder `delegated_create_allowed=True` → Erfolg; sonst HTTP 403;
    keine Version entsteht
  - Existing unsichtbar: HTTP 404 ohne `current_state`/`current_etag`
  - Existing sichtbar Nicht-Owner stale: HTTP 404 ohne Konfliktpayload
  - Existing sichtbar Nicht-Owner aktuell: HTTP 403
  - Existing Owner/QMB stale: HTTP 409 mit Konfliktzustand
  - Existing Owner/QMB aktuell: bestehender Erfolgsweg
- **Implementierungsschritte:**
  1. `create_from_template`: optionale `actor` + `delegated_create_allowed`;
     Actor ableiten; Missing-Target-Create-Policy vor Service-Create
  2. `_mutate_version_state(..., owner_or_privileged=False)` durchreichen
  3. Missing-Target-Route: `actor` + `_delegated_create_allowed`
  4. Existing-Target-Route: `actor` + `owner_or_privileged=True` und Actor an API
- **Tests und Evidence:** Gate R2-A (`-k template or create_from_template`),
  R2-B (Authorization/Concurrency/OpenAPI/Matrix), R2-C Ledger.
  Keine 1209er Vollregression (folgt nach MR08-R3).
- **Fail-fast:** erstes rotes Gate stoppt; MR08-R2 FAILED/BLOCKED; kein R3;
  kein Freeze; keine Git-Schreibaktion.
- **Freeze:** nicht freigegeben. CandidateSha nicht erzeugen.
- **Alle Testversuche:**
  0. `20260818T152445755Z` — Ledger-Konsistenz nach R2 IN_PROGRESS — **6 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r2-ledger-results-20260818T152445755Z/junit.xml`)
  1. `20260818T152657988Z` — Gate R2-A — **FAILED** (1 failed: Public-API-Erfolgspfad ohne `storage_port`; HTTP-Fälle grün). Test um vorhandenen `FileSystemDocumentsStorage` ergänzt.
  2. `20260818T152746610Z` — Gate R2-A Wiederholung — **4 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r2-target-results-20260818T152746610Z/junit.xml`)
  3. `20260818T152830890Z` — Gate R2-B betroffene Backendgrenze — **110 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r2-focused-results-20260818T152830890Z/junit.xml`,
     `tests="110" failures="0" errors="0" skipped="0"`)
  4. `20260818T153303900Z` — Gate R2-C Dokumentkonsistenz — **6 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr08-r2-ledger-final-results-20260818T153303900Z/junit.xml`)
- **Passed/Failed/Skipped:** R2-A 4/0/0; R2-B 110/0/0
- **Evidence-Pfade:** `build/j04-m0-closure/mr08-r2-*` (nicht gestaged, kein Produktcode)
- **Adversarialer Review (nur MR08-R2-Diff):** **PASS** für R2-Scope.
  Autorisierung vor Missing-Create und vor stale ETag im Public-API-/Servicepfad;
  Backend reicht nur `actor`, `_delegated_create_allowed` und `owner_or_privileged`
  durch. Keine neue API-Klasse, Route oder Persistenz. `mutate_version_if_current`
  unverändert. Keine Testabschwächung. Signaturerweiterung von
  `DocumentsWorkflowApi.create_from_template` dokumentiert (keine neue Klasse).
  Gesamtreview bleibt offen bis MR08-R3 (resolver-loser Artifact-Fallback).
- **Abweichungen:** erste R2-A-Ausführung rot wegen fehlendem `storage_port` im
  neuen Modultest; danach grün. Keine 1209er Vollregression (folgt nach R3).
- **Commit-SHA:** pending user approval — Freeze pending explicit user approval
- **Abschlussbewertung:** MR08-R2 PASS. Parent MR08 bleibt IN_PROGRESS.
  Current checkpoint MR08. NOT_READY. Nächster Schritt: MR08-R3.

#### MR08-R3 — Resolver-losen Artifact-Storage-Fallback begrenzen

- **Status:** PASS
- **Startzeit:** 2026-08-18T17:19:08Z
- **Endzeit:** 2026-08-18T19:10:37Z
- **Start-HEAD:** `3bf651865c4da2c665d53f2fa83a3672b91b57ef` (`3bf6518`)
- **Problem und Sicherheitsinvariante:** `resolve_artifact_path` verbindet bei
  fehlendem callable `resolve_storage_key` direkt `root / artifact.storage_key`.
  Ein ausbrechender Key kann den Storage-Root verlassen. Invariante: auch der
  resolver-lose Fallback bleibt durch vorhandenes `contained_path` im Root.
  Ungültige Keys fail-closed → `None`. Resolverpfad bleibt bevorzugt.
- **Bestehender Owner:** `modules/documents/artifact_ops.py` `resolve_artifact_path`
- **Minimaler Dateisatz:**
  1. `modules/documents/artifact_ops.py` — resolver-losen Fallback auf `contained_path`
  2. `tests/modules/test_documents_infrastructure.py` — direkte `resolve_artifact_path`-Verträge
  3. `docs/J04_M0_EXECUTABLE_CHECKLIST.md`
  4. `docs/J04_M0_ACCEPTANCE_REPORT.md`
- **Ausgeschlossene Legacy-Metadatenpfade:** `absolute_path` / `file_path` /
  `path` in `artifact.metadata` bleiben unverändert. `storage.py` unverändert
  (kein `contained_path`-Defekt nachgewiesen). Keine neue Public API, Route,
  Port-Methode, Serviceklasse, Persistenz, Wrapper- oder Helperdatei.
- **Implementierung:** Resolver-loser Fallback ruft `contained_path(root, key)`
  auf und übersetzt `ValueError` nach `None`. Callable `resolve_storage_key`
  bleibt bevorzugt. Legacy-Metadatenauflösung unverändert.
- **Fail-fast:** erstes rotes Pflichtgate stoppt; MR08-R3 FAILED oder BLOCKED;
  kein Review, kein Freeze, keine Git-Schreibaktion; keine Policyabschwächung.
- **Freeze:** ausdrücklich nicht freigegeben. CandidateSha nicht erzeugen.
  Parent MR08 bleibt IN_PROGRESS. MR09/MR10 TODO. Gesamtstatus NOT_READY.
- **Alle Testversuche:**
  0. `20260818T171938978Z` — Ledger-Konsistenz nach R3 IN_PROGRESS — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr08-r3-ledger-results-20260818T171938978Z/junit.xml`)
  1. `20260818T172123561Z` — Gate R3-A `-k resolverless_artifact_path` — **PASS**
     Konsole: 5 passed / 0 failed / 15 deselected / 8 subtests passed.
     JUnit: `tests="13" failures="0" errors="0" skipped="0"`
     (`build/j04-m0-closure/mr08-r3-target-results-20260818T172123561Z/junit.xml`)
  2. `20260818T172135322Z` — Gate R3-B Artifact/Storage/Signatur — **PASS**
     Konsole: 57 passed / 0 failed / 8 subtests passed.
     JUnit: `tests="65" failures="0" errors="0" skipped="0"`
     (`build/j04-m0-closure/mr08-r3-artifact-results-20260818T172135322Z/junit.xml`)
  3. `20260818T172223274Z` — Gate R3-C erster vollständiger nicht-live Lauf — **PASS**
     JUnit: `tests="1246" failures="0" errors="0" skipped="20" time="935.721"`
     timestamp `2026-08-18T19:22:24.193367+02:00` bis `19:37:59.914367+02:00`.
     Dieser Lauf war im vorherigen BLOCKED-Bericht ausgelassen und ist der
     erste vollständige R3-C-Versuch.
     (`build/j04-m0-closure/mr08-r3-regression-results-20260818T172223274Z/junit.xml`)
  4. `20260818T173505528Z` — Gate R3-C zweiter Volltest, überlappend — **nicht als serieller Gate-Lauf verwertbar**
     JUnit: `tests="1246" failures="2" errors="0" skipped="20" time="1028.502"`
     timestamp `2026-08-18T19:35:07.489322+02:00` bis `19:52:15.991322+02:00`.
     Start 763.3 s nach Lauf 3; Überlappung **172.425 s**, während Lauf 3 noch
     172.425 s Restlaufzeit hatte. Failures: WinError 10053 auf
     `test_bootstrap_admin_session_completes_password_change_then_me_200`
     (`127.0.0.1:57413`) und `test_seed_directory_users_stores_user_ids_from_auth_me`
     (`127.0.0.1:57429`). **Nicht** der erste vollständige Versuch.
     (`build/j04-m0-closure/mr08-r3-regression-results-20260818T173505528Z/junit.xml`)
  5. `20260818T175336276Z` — Diagnoseisolierung der zwei überlappenden Failures — **2 passed / 0 failed / 0 errors**
     Kein Produkt- oder Testcode geändert.
     (`build/j04-m0-closure/mr08-r3-c-isolate-results-20260818T175336276Z/junit.xml`)
  6. `20260818T175701619Z` — Ledger-Konsistenz nach irrtümlichem R3 BLOCKED — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr08-r3-ledger-blocked-results-20260818T175701619Z/junit.xml`)
  7. `20260818T175729687Z` — Ledger-Konsistenz nach BLOCKED-Nachtrag — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr08-r3-ledger-final-results-20260818T175729687Z/junit.xml`)
  8. `20260818T185736086Z` — Ledger-Konsistenz nach Historienkorrektur / serial pending — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr08-r3-serial-ledger-results-20260818T185736086Z/junit.xml`)
  9. `20260818T185750907Z` — Gate R3-C serieller Bestätigungslauf — **PASS**
     Konsole: 988 passed / 20 skipped / 52 deselected / 238 subtests passed.
     JUnit: `tests="1246" failures="0" errors="0" skipped="20" time="705.366"`
     timestamp `2026-08-18T20:57:51.746194+02:00`. Kein paralleler Pytest-Prozess.
     Dateihashes vor/nach unverändert.
     (`build/j04-m0-closure/mr08-r3-serial-regression-results-20260818T185750907Z/junit.xml`)
  10. `20260818T191144020Z` — Ledger-Konsistenz nach R3 PASS — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr08-r3-serial-ledger-final-results-20260818T191144020Z/junit.xml`)
- **Passed/Failed/Skipped:** R3-A JUnit 13/0/0; R3-B JUnit 65/0/0; erster R3-C JUnit 1246/0/0/20 skipped; serieller R3-C JUnit 1246/0/0/20 skipped
- **Skip-Gründe (R3-C):** 16× `tests/e2e_cli/test_documents_cli.py` `not_in_m0` Legacy local documents CLI; 3× `tests/e2e_cli/test_documents_cli_authorization_matrix.py` `not_in_m0` Legacy CLI authorization matrix; 1× `tests/e2e_cli/test_training_cli.py` `not_in_m0` training/`documents_read`. 52 deselected: `postgres` oder `j04_final_acceptance`.
- **Evidence-Pfade:** `build/j04-m0-closure/mr08-r3-*` (nicht gestaged)
- **Adversarialer Review:** **PASS** (kumulativer Worktree, nach seriellem R3-C).
  Resolver-loser Fallback nutzt `contained_path`; ausbrechende Keys → `None`;
  callable `resolve_storage_key` bevorzugt; Legacy-Metadatenpfade unverändert;
  MR08-R2-Autorisierung vor Create/ETag erhalten; keine neue Public API/Route/
  API-Klasse/Port-Methode; kein neuer Service/Wrapper/Helper/Entrypoint/
  Persistenzpfad; Backend importiert nur `modules.*.api`; keine Testabschwächung;
  stat-only-Dateien ohne Inhaltsdiff; `docs/transition/20260818/` untracked und
  unberührt.
- **Nächster Schritt:** unabhängige Prüfung des Freeze-Berichts und danach
  separate ausdrückliche Freigabe für den destruktiven MR09-/CP08-V9-Lauf.
  MR09 nicht begonnen.
- **Commit-SHA:** ProductCommit `70d4f4c`; AcceptanceCommit `6195637`;
  MR08 CandidateSha `4db97ea72ffcb18823cd610599752cc1c8e8716d`
- **Abschlussbewertung:** MR08-R3 PASS. Parent MR08 PASS. Candidate-Freeze
  `4db97ea` (MR08-Freeze). Current checkpoint MR09. MR09 TODO. NOT_READY.
  Historischer FR14-Candidate bleibt `ed488ed`. Nach Candidate-Freeze keine
  Code-/Teständerung.

### MR09 — Kontrollierten CP08-V9-Lauf ausführen

- **Status:** BLOCKED
- **Startzeit:** 2026-08-19T06:36:00Z
- **Endzeit:** 2026-08-19T06:38:18Z
- **Start-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`)
- **CandidateSha:** `4db97ea72ffcb18823cd610599752cc1c8e8716d` (`4db97ea`)
- **Lauf-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`) als reiner SHA-Dokument-Follow-up
- **Freigabe:** einmalige destruktive Freigabe liegt vor. Kein zweiter Lauf,
  kein Commit, kein Push, kein PR und kein MR10.
- **Ziel und Scope:** genau ein kontrollierter CP08-V9-Runnerlauf gegen die
  Guard-bestätigte Datenbank `qmtool_j04_destructive_test`; 18 M0-Schritte bis
  `APPROVED` und Restart; read-only Guard-Preflight zuerst.
- **Runnervertrag:** genau ein Vordergrundaufruf von
  `scripts/run_postgres_live_tests.py --j04-final-acceptance --basetemp <frisch>`;
  kein direkter Pytest-Aufruf des Realprocess-Tests, kein zweites Terminal,
  kein Retry bei Fehler oder Tool-Timeout.
- **Erwartete isolierte Datenbankidentität:** database `qmtool_j04_destructive_test`,
  major `18`, port `5432`, marker `j04_m0_destructive_pg16`, `reset_present=False`
  im read-only Preflight; DSN bleibt geheim.
- **Fail-fast:** bei Guard-, Zielidentitäts-, Port-, Prozess- oder Runnerfehler
  sofort BLOCKED/FAILED; kein zweiter Lauf, keine Reparatur, keine Produkt- oder
  Teständerung.
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — MR09-Status, Runnerplan, Evidence
  - `docs/J04_M0_ACCEPTANCE_REPORT.md` — MR09 IN_PROGRESS, Gesamtstatus, Evidence
- **Bewusst nicht geänderte Dateien:** alle Produkt-, Backend-, Acceptance- und
  Testdateien; CandidateSha bleibt unverändert; MR10 bleibt TODO.
- **Implementierte Invarianten:** Current checkpoint bleibt MR09; Gesamtstatus
  bleibt NOT_READY; `Accepted` bleibt unset; kein neuer Freeze in diesem Auftrag.
- **Alle Testversuche:**
  0. `20260819T063744327Z` — Ledger-Konsistenz nach MR09 IN_PROGRESS — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr09-ledger-start-results-20260819T063744327Z/junit.xml`)
  1. `20260819T063818073Z` — read-only Guard-Preflight **BLOCKED vor Guard-Ausführung**
     SyntaxError im Inline-Preflight-Launcher:
     `reset_present = bool(os.environ.get(TEST_RESET_ENV, ").strip())`
     (`build/j04-m0-closure/mr09-cp08-v9-results-20260819T063818073Z/preflight.log`)
- **Genaue Befehle:** kein Runner-Aufruf erfolgt; `scripts/run_postgres_live_tests.py --j04-final-acceptance`
  wurde **nicht** gestartet.
- **Passed/Failed/Skipped:** kein CP08-V9-Pytest-Kind gestartet; 18 Szenarioschritte **NOT RUN**
- **Evidence-Pfade:** `build/j04-m0-closure/mr09-*`
- **Abweichungen:** read-only Preflight scheiterte an einem Shell/Python-
  Startfehler vor der Guard-Prüfung. Kein Reset, kein Runner, kein Port- oder
  Prozessrest, keine Produkt-/Teständerung. Nach Fail-fast kein zweiter Lauf.
- **Commit-SHA:** none in this Auftrag
- **Abschlussbewertung:** MR09 BLOCKED. Erste Fehlerstelle: Preflight-Launcher
  `SyntaxError` vor Guard-Identitätsprüfung. Danach NOT RUN:
  `pg_bootstrap`, `backend_start`, `health_and_openapi`, `bootstrap_admin_login`,
  `seed_directory_users`, `seed_workflow_profile`, `client_process_sessions`,
  `document_baseline_flow`, `etag_concurrency_race`, `artifacts_transport`,
  `signature_verify_password`, `signed_editing_complete`, `pdf_comment_flow`,
  `docx_comment_sync`, `signed_review_approval`, `backend_restart`,
  `persistence_and_session_contract`. Current checkpoint bleibt MR09.
  Gesamtstatus NOT_READY. Kein Retry ohne unabhängige Prüfung.

### MR09-R1 — Read-only Preflight-Launcher über Python-stdin statt `python -c`

- **Status:** FAILED (R1 abgeschlossen)
- **Startzeit:** 2026-08-19T08:21:00Z
- **Endzeit:** 2026-08-19T08:26:16Z (R1)
- **CandidateSha:** `4db97ea72ffcb18823cd610599752cc1c8e8716d` (`4db97ea`)
- **Lauf-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`)
- **Ursache des ersten Fehlers:** Der in MR09 verwendete `python -c`-Einzeiler
  enthielt ein unescaptes Anführungszeichen im Python-Ausdruck
  `os.environ.get(TEST_RESET_ENV, "`.strip())`, das PowerShell vorzeitig aus dem
  String-Literal herausbrechen ließ. Das erzeugte den SyntaxError auf Zeile 6 des
  Python-Codes. Der Fehler trat im Launcher auf, **bevor** der Guard die
  Datenbankidentität prüfte.
- **BLOCKED-Evidence bleibt erhalten:** Versuch 1 aus MR09 (`20260819T063818073Z`)
  wird nicht entfernt oder überschrieben.
- **Kein Runner-Aufruf im ersten Versuch:** `scripts/run_postgres_live_tests.py`
  wurde in MR09 nicht gestartet. Kein Pytest-Kindprozess, kein Guard-Reset,
  kein Realprocess-Workspace, kein Szenarioschritt ausgeführt.
- **Einmalfreigabe:** Die bestehende Freigabe
  „Der einmalige destruktive MR09-/CP08-V9-Lauf gegen die Guard-bestätigte
  Datenbank qmtool_j04_destructive_test ist freigegeben." ist weiterhin ungenutzt.
- **Korrektur:** PowerShell-Single-Quoted-Here-String
  (`$preflightSource = @' ... '@`) wird über stdin an `python -` weitergeleitet;
  kein `python -c` mehr.
- **Keine Produkt- oder Teständerung:** ausschließlich Dokumentation und
  einmaliger Runner-Aufruf nach grünem Preflight.
- **Runnerplan:** genau ein Aufruf von
  `scripts/run_postgres_live_tests.py --j04-final-acceptance --basetemp <frisch>`
  nach vollständig grünem Preflight; bei Fehler kein zweiter Versuch.
- **MR10:** bleibt TODO und wurde nicht begonnen.
- **Gesamtstatus:** NOT_READY — Current checkpoint MR09.
- **Alle Testversuche:**
  0. `20260819T082330286Z` — Ledger-Konsistenz nach MR09-R1 IN_PROGRESS — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr09-r1-ledger-start-results-20260819T082330286Z/junit.xml`)
  1. `20260819T082349151Z` — korrigierter read-only Guard-Preflight über PowerShell-Here-String stdin —
     **PASS** (exitcode 0; database=qmtool_j04_destructive_test, major=18, port=5432,
     marker=j04_m0_destructive_pg16, reset_present=False)
     (`build/j04-m0-closure/mr09-r1-cp08-v9-results-20260819T082349151Z/preflight.log`)
  2. `20260819T082412Z` — einziger CP08-V9-Runner-Aufruf — **FAILED**
     Runner-Exit 1 / pytest 1 failed / 0 skipped
     Schritt 14 `pdf_comment_flow` TimeoutError; Schritte 1–13 pass;
     Schritte 15–18 NOT RUN (docx_comment_sync, signed_review_approval,
     backend_restart, persistence_and_session_contract)
     Workspace: `build/j04-m0-closure/cp08-realprocess-ws/20260819T082412875274Z-89d0b470899242559fde43dbf6ba199c`
     (`build/j04-m0-closure/mr09-r1-cp08-v9-results-20260819T082349151Z/runner.log`)
  3. `20260819T082616676Z` — Ledger-Konsistenz nach MR09-R1 FAILED — **6 passed / 0 failed / 0 skipped / 0 errors**
     (`build/j04-m0-closure/mr09-r1-ledger-final-results-20260819T082616676Z/junit.xml`)
- **Genaue Befehle:** kein zweiter Runner-Aufruf; Einmalfreigabe verbraucht.
- **Abschlussbewertung:** MR09-R1 FAILED. Erste Fehlerstelle: Schritt `pdf_comment_flow`.
  `POST /documents/versions/J04-ACCEPT-DOC/1/comments` endete mit HTTP 200.
  Danach lieferte der unmittelbar folgende GET der PDF_REVIEW-Kommentarliste innerhalb von
  30 Sekunden keine vollständige Response. Da Uvicorn den Access-Log-Eintrag erst nach
  abgeschlossener Response schreibt, ist anhand der bisherigen Evidence offen, ob der GET
  nicht verbunden wurde, vor den Response-Headern blockierte oder beim Lesen des Bodys hing.
  Fehlerklasse: „Acceptance-Interaktions-/Transporttimeout, Ursache offen" —
  ein Produktdefekt ist noch nicht bewiesen.
  Klassifikation: Produkt-/HTTP-/Szenarioassertion → MR09 FAILED. Kein zweiter Lauf,
  keine Reparatur in diesem Auftrag. Current checkpoint bleibt MR09. Gesamtstatus NOT_READY.
  MR10 bleibt TODO. Ein weiterer CP08-Lauf benötigt Remediation, neuen Freeze und neue
  destruktive Freigabe.

### MR09-R2 — pdf_comment_flow-Timeout nicht-destruktiv lokalisieren

- **Status:** PASS
- **Startzeit:** 2026-08-19T10:55:00Z
- **CandidateSha:** `4db97ea72ffcb18823cd610599752cc1c8e8716d` (`4db97ea`) — historisch, unverändert
- **Lauf-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`)
- **Current checkpoint:** MR09 (Parent MR09 bleibt IN_PROGRESS und nicht bestanden)
- **Gesamtstatus:** NOT_READY
- **Ziel:** Timeout-Phase in `pdf_comment_flow` ohne PostgreSQL-Lauf lokalisieren;
  fehlenden Backend-HTTP-Vertrag für POST→GET-Kommentarliste ergänzen;
  AcceptanceHttpClient Timeout-Diagnose präzisieren; alle nicht-live Gates grün.
- **Verbindliche Einschränkungen:**
  - kein PostgreSQL-Reset, kein CP08-/Realprocess-Runner
  - kein direkter Aufruf von `test_j04_m0_realprocess.py`
  - kein Commit, Staging, Freeze, Push, PR
  - `Accepted` bleibt unset; destruktive Freigabe verbraucht
  - MR10 bleibt TODO
- **Erwarteter Dateisatz:**
  - `tests/backend/test_documents_p4_p9_http.py` — neuer Test `test_pdf_comment_create_then_immediate_list_over_http`
  - `tests/acceptance/j04_m0_acceptance_scenario.py` — Timeout-Diagnose in `AcceptanceHttpClient.request`
  - `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — fokussierte Timeout-Unit-Tests
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — MR09-R2-Status
  - `docs/J04_M0_ACCEPTANCE_REPORT.md` — MR09-R2-Status
- **Alle Testversuche:**
  0. `20260819T085741455Z` — Gate A: Docs-Konsistenz nach MR09-R2 IN_PROGRESS — **6 passed**
     (`build/j04-m0-closure/mr09-r2-gate-a-results-20260819T085741455Z/junit.xml`)
  1. SQLite read-only Inspektion — **PASS**: erster Diagnoseversuch gegen `workflow_comments` → `no such table`;
     korrigierte Abfrage gegen `document_workflow_comments` fand 1 PDF_REVIEW-Kommentar persistiert;
     nach Prozessende kein permanenter Lock beobachtbar; transienter Lock während des Realprocess-Requests bleibt möglich
     (`build/j04-m0-closure/mr09-r2-diagnosis-20260819T085750217Z/sqlite-check.log`)
  2. `20260819T085946388Z` — Gate B: neue fokussierte Tests — **6 passed / 0 failed**
     (`test_pdf_comment_create_then_immediate_list_over_http` + 4 Timeout-Unit-Tests + 1 bestehender)
     (`build/j04-m0-closure/mr09-r2-gate-b-results-20260819T085946388Z/junit.xml`)
  3. `20260819T090002819Z` — Gate C: Kommentar-/HTTP-Umfeld — **109 passed / 0 failed / 0 skipped**
     (`build/j04-m0-closure/mr09-r2-gate-c-results-20260819T090002819Z/junit.xml`)
  4. `20260819T090112728Z` — Gate D: vollständige nicht-live Regression — **1251 passed / 0 failed / 20 skipped**
     (`build/j04-m0-closure/mr09-r2-gate-d-results-20260819T090112728Z/junit.xml`)
  5. `20260819T091530457Z` — Gate E: Docs-Konsistenz abschließend — **6 passed**
     (`build/j04-m0-closure/mr09-r2-gate-e-results-20260819T091530457Z/junit.xml`)
- **Geänderte Dateien und Verantwortlichkeiten:**
  - `tests/backend/test_documents_p4_p9_http.py` — neuer Test `test_pdf_comment_create_then_immediate_list_over_http`
  - `tests/acceptance/j04_m0_acceptance_scenario.py` — Timeout-Diagnose in `AcceptanceHttpClient.request`
  - `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — 4 neue Timeout-Unit-Tests
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` / `docs/J04_M0_ACCEPTANCE_REPORT.md` — MR09-R2-Status, historische Korrektur
- **Bewusst nicht geänderte Dateien:** alle Produktdateien, Candidate-SHA, kein Commit, kein Freeze, kein Push
- **Abschlussbewertung MR09-R2 (damaliger IN_PROGRESS-Zustand, jetzt PASS):** Diagnosestand nach R2-Gates:
  - Erster SQLite-Diagnoseversuch verwendete irrtümlich `workflow_comments`
    → `sqlite3.OperationalError: no such table`; danach Schema geprüft;
    korrigierte Abfrage auf `document_workflow_comments` fand 1 PDF_REVIEW-Kommentar
    nach Prozessende persistiert; nach Prozessende kein permanenter Lock beobachtbar;
    transienter Lock während des Realprocess-Requests bleibt nicht ausgeschlossen.
  - `test_pdf_comment_create_then_immediate_list_over_http` (TestClient): prüft Route,
    Service, Autorisierung und SQLite-Persistenz in-process; kein echter Uvicorn-/TCP-/
    PostgreSQL-Realprocess; schließt deterministischen Fehler des In-Process-Pfads aus;
    beweist nicht die Fehlerfreiheit des vollständigen Realprocess-Pfads.
  - Ursache weiterhin offen; Fehler nur im vollständigen urllib→Uvicorn/TCP-Realprocess
    beobachtet; Windows-/Socketeffekt nur Hypothese; kein Produktdefekt bewiesen, aber
    auch nicht abschließend ausgeschlossen.
  - Der Body-Read-Timeouttest fehlte noch in R2; wird in R1 ergänzt.
  - Aktiver CandidateSha: **keiner** — wegen Acceptance-/Teständerungen seit `4db97ea`
    kein neuer Candidate ohne gesonderte Commit-/Freeze-Freigabe.

### MR09-R2-R1 — Body-Read-Timeouttest und Dokumentationspräzisierung

- **Status:** PASS
- **Startzeit:** 2026-08-19T11:34:00Z
- **Lauf-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`)
- **MR09-R2-R1 PASS; MR09-R2 PASS; Parent MR09 IN_PROGRESS und nicht bestanden**
- **Gesamtstatus:** NOT_READY; MR10 TODO; aktiver CandidateSha: keiner
- **Ziel:** fehlenden Body-Read-Timeouttest ergänzen; Dokumentation präzisieren
  (SQLite-Diagnose, TestClient-Grenzen, Ursachenbewertung, Candidate-Status)
- **Erwarteter Dateisatz (R1-Ergänzung):**
  - `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — neuer Test
    `test_acceptance_http_client_timeout_during_body_read_reports_method_path_and_no_secrets`
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` / `docs/J04_M0_ACCEPTANCE_REPORT.md` — R1-Status, Präzisierungen
- **Alle Testversuche (R1):**
  0. `20260819T093636436Z` — Gate R1-A: 5 Timeout + 2 Kommentar-Tests — **7 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r1-gate-a-results-20260819T093636436Z/junit.xml`)
  1. `20260819T093654734Z` — Gate R1-B: Acceptance-Unit + Backend-P4-P9 + Auth-Matrix — **110 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r1-gate-b-results-20260819T093654734Z/junit.xml`)
  2. `20260819T093801180Z` — Gate R1-C: vollständige nicht-live Regression — **1252 passed / 0 failed / 20 skipped**
     (`build/j04-m0-closure/mr09-r2-r1-gate-c-results-20260819T093801180Z/junit.xml`)
  3. `20260819T095101958Z` — Gate R1-D: Docs-Konsistenz — **6 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r1-gate-d-results-20260819T095101958Z/junit.xml`)
- **Geänderte Dateien (R1):**
  - `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — neuer Test
    `test_acceptance_http_client_timeout_during_body_read_reports_method_path_and_no_secrets`
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` / `docs/J04_M0_ACCEPTANCE_REPORT.md` — R1-Status,
    SQLite-Diagnose-Präzisierung, TestClient-Scope, Ursachenbewertung, Candidate-Status
- **Abschlussbewertung MR09-R2-R1 PASS:**
  - 5 Timeout-Unit-Tests vorhanden (war: 4); Body-Read-Phase jetzt auch abgedeckt.
  - Ursache weiterhin offen; Fehler nur im vollständigen Realprocess beobachtet;
    Windows-/Socketeffekt nur Hypothese; kein Produktdefekt bewiesen und nicht ausgeschlossen.
  - Aktiver CandidateSha: **keiner** — Acceptance-/Testdateien seit `4db97ea` geändert;
    neuer Candidate erst nach Commit-/Freeze-Freigabe.
  - Current checkpoint: MR09. Parent MR09 IN_PROGRESS und nicht bestanden.
  - Gesamtstatus NOT_READY. MR10 TODO.
  - Nächster Schritt: MR09-R2-R2 (letzte Test- und Dokumentintegritätskorrektur vor Freeze).

### MR09-R2-R2 — Geheimnisschutz-Volltest und Statuskonsolidierung

- **Status:** PASS
- **Startzeit:** 2026-08-19T12:34:00Z
- **Endzeit:** 2026-08-19T12:51:37Z
- **Lauf-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`)
- **MR09-R2-R2 PASS; MR09-R2-R1 PASS; MR09-R2 PASS; Parent MR09 IN_PROGRESS und nicht bestanden**
- **Gesamtstatus:** NOT_READY; MR10 TODO; aktiver CandidateSha: keiner
- **Ziel:** Body-Read-Timeouttest um POST-Methode und expliziten Geheimnis-Body (`password`/`request-body-secret`)
  erweitern; Statusfelder MR09-R2 und MR09-R2-R1 auf PASS setzen; veralteten Candidate-Abschnitt ersetzen;
  SQLite-Aussagen widerspruchsfrei machen; Pflichtgates R2-A–R2-D seriell ausführen.
- **Verbindliche Einschränkungen:**
  - kein Produkt- oder Harness-Implementierungscode
  - kein PostgreSQL, Reset, CP08 oder Realprocess-Runner
  - kein Commit, Staging, Freeze, Push, PR oder MR10
- **Alle Testversuche (R2-R2):**
  0. `20260819T123823536Z` — Gate R2-A: 5 Timeout + 2 Kommentar-Tests — **7 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r2-gate-a-results-20260819T123823536Z/junit.xml`)
  1. `20260819T123839735Z` — Gate R2-B: Acceptance-Unit + Backend-P4-P9 + Auth-Matrix — **110 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r2-gate-b-results-20260819T123839735Z/junit.xml`)
  2. `20260819T123948029Z` — Gate R2-C: vollständige nicht-live Regression — **1252 passed / 0 failed / 20 skipped**
     (`build/j04-m0-closure/mr09-r2-r2-gate-c-results-20260819T123948029Z/junit.xml`)
  3. `20260819T125137305Z` — Gate R2-D: Docs-Konsistenz — **6 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r2-gate-d-results-20260819T125137305Z/junit.xml`)
- **Geänderte Dateien (R2-R2):**
  - `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — Body-Read-Timeouttest auf POST + Request-Body-Geheimnisschutz erweitert; eine überzählige Leerzeile entfernt
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` / `docs/J04_M0_ACCEPTANCE_REPORT.md` — Statusfelder, Candidate-Abschnitt, SQLite- und Ursachenbewertung konsolidiert
- **Abschlussbewertung MR09-R2-R2 PASS:**
  - Erweiterter Body-Read-Test bestätigt weiter Methode, Pfad, Body-Read-Phase, kein Retry und genau einen `urlopen`-Aufruf.
  - Zusätzlich sind `request-body-secret` und `password` (case-insensitive) nicht in der Fehlermeldung enthalten.
  - MR09-R2-R1 und MR09-R2 stehen formal auf PASS; Parent MR09 bleibt IN_PROGRESS und nicht bestanden.
  - Kein Produktcode, kein PG, kein CP08-Runner, kein Commit, kein Freeze, kein Push, keine PR.
  - `git diff --check` ohne Fehler; Staging leer; aktiver CandidateSha weiterhin **keiner**; historischer MR08-Candidate bleibt `4db97ea`.
  - Nächster Schritt: MR09-R2-R3 (verbliebene Statusinkonsistenz beseitigen + Docs-Konsistenztest).

### MR09-R2-R3 — Statusinkonsistenz beseitigen und Docs-Konsistenztest ergänzen


- **Status:** PASS
- **Startzeit:** 2026-08-19T13:16:00Z
- **Endzeit:** 2026-08-19T13:22:00Z
- **Lauf-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`)
- **MR09-R2-R3 PASS; MR09-R2-R2 PASS; MR09-R2-R1 PASS; MR09-R2 PASS; Parent MR09 IN_PROGRESS und nicht bestanden**
- **Gesamtstatus:** NOT_READY; MR10 TODO; aktiver CandidateSha: keiner
- **Ziel:** Widerspruch zwischen oberer Statuszeile / Candidate-Abschnitt im Acceptance
  Report (R2-R2 noch IN_PROGRESS) und dem Rest (R2-R2 PASS) beseitigen;
  Docs-Konsistenztest ergänzen, der künftig denselben Widerspruch verhindert.
- **Erlaubter Dateisatz:**
  - `docs/J04_M0_ACCEPTANCE_REPORT.md`
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md`
  - `tests/docs/test_docs_consistency.py`
- **Verbindliche Einschränkungen:**
  - kein Produkt- oder Acceptance-Harness-Code
  - kein PostgreSQL, Reset, CP08 oder Realprocess-Runner
  - kein Commit, Staging, Freeze, Push oder PR
- **Alle Testversuche (R2-R3):**
  0. `20260819T131805888Z` — Gate A Probe: Docs-Konsistenz (neuer Test fand echten Defekt → 1 failed, inline behoben)
  1. `20260819T131822493Z` — Gate A: Docs-Konsistenz nach Fix — **7 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r3-gate-a-results-20260819T131822493Z/junit.xml`)
  2. `20260819T131836799Z` — Gate B: Acceptance-Unit + Backend-P4-P9 + Auth-Matrix — **110 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r3-gate-b-results-20260819T131836799Z/junit.xml`)
  3. `20260819T131951762Z` — Gate C: vollständige nicht-live Regression — **1253 passed / 0 failed / 20 skipped**
     (`build/j04-m0-closure/mr09-r2-r3-gate-c-results-20260819T131951762Z/junit.xml`)
- **Neuer Konsistenzvertrag:**
  - `test_acceptance_report_remediation_checkpoint_consistent_with_checklist` in
    `tests/docs/test_docs_consistency.py` leitet den letzten MR09-R2-R\*-Abschnitt
    dynamisch aus der Checklist ab und prüft, dass oberste Statuszeile und erster
    Candidate-Abschnitt des Reports denselben Checkpoint-Namen und -Status tragen
    und kein widersprüchliches PASS/IN_PROGRESS enthalten.
- **Geänderte Dateien (R2-R3):**
  - `tests/docs/test_docs_consistency.py` — neuer Test `test_acceptance_report_remediation_checkpoint_consistent_with_checklist`
  - `docs/J04_M0_ACCEPTANCE_REPORT.md` — Statuszeile und Candidate-Abschnitt auf R2-R3 PASS aktualisiert
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` — R2-R3-Abschnitt und Ledger-Zeile finalisiert
- **Abschlussbewertung MR09-R2-R3 PASS:**
  - Neuer Test hat den echten Defekt (R2-R3 fehlte in Statuszeile) beim ersten Lauf korrekt gefunden.
  - Nach Korrektur alle Gates grün.
  - MR09-R2-R2, R2-R1 und R2 bleiben PASS. Parent MR09 bleibt IN_PROGRESS.
  - Aktiver CandidateSha: keiner; historischer MR08-Candidate: `4db97ea`.
  - Gesamtstatus NOT_READY. MR10 TODO.
  - Nächster Schritt: MR09-R2-R4 (Checkpoint-Status-Zuordnung im Konsistenztest härten).

### MR09-R2-R4 — Checkpoint-Status-Zuordnung im Konsistenztest härten

- **Status:** PASS
- **Startzeit:** 2026-08-19T13:45:00Z
- **Endzeit:** 2026-08-19T14:03:00Z
- **Lauf-SHA:** `c003dd9aa00c1c84026d9c236597c33e84289c27` (`c003dd9`)
- **MR09-R2-R4 PASS; MR09-R2-R3 PASS; MR09-R2-R2 PASS; MR09-R2-R1 PASS; MR09-R2 PASS; Parent MR09 IN_PROGRESS und nicht bestanden**
- **Gesamtstatus:** NOT_READY; MR10 TODO; aktiver CandidateSha: keiner
- **Ziel:** False-positive-Lücke im Konsistenztest schließen: Checkpoint-Status-Prüfung
  muss den Status aus dem checkpoint-spezifischen Kontext (Klausel / Bullet) isolieren,
  damit ein Status aus einem benachbarten Checkpoint die Prüfung nicht erfüllen kann.
  Negativen synthetischen Regressionstest ergänzen.
- **Erlaubter Dateisatz:**
  - `tests/docs/test_docs_consistency.py`
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md`
  - `docs/J04_M0_ACCEPTANCE_REPORT.md`
- **Verbindliche Einschränkungen:**
  - kein Produkt-, Backend- oder Acceptance-Harness-Code
  - kein PostgreSQL, CP08 oder Realprocess
  - kein Commit, Staging, Freeze, Push oder PR
- **Alle Testversuche (R2-R4):**
  0. `20260819T134748986Z` — Gate A: 2 fokussierte Remediation-Tests (positiv + negativ) — **2 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r4-gate-a-results-20260819T134748986Z/junit.xml`)
  1. `20260819T134807780Z` — Gate B: vollständige Docs-Konsistenz — **8 passed / 0 failed**
     (`build/j04-m0-closure/mr09-r2-r4-gate-b-results-20260819T134807780Z/junit.xml`)
  2. `20260819T134832664Z` — Gate C: vollständige nicht-live Regression — **1254 passed / 0 failed / 20 skipped**
     (`build/j04-m0-closure/mr09-r2-r4-gate-c-results-20260819T134832664Z/junit.xml`)
- **Geänderte Dateien (R2-R4):**
  - `tests/docs/test_docs_consistency.py` — Hilfsfunktionen `_extract_checkpoint_clause_from_top_line`,
    `_extract_checkpoint_bullet_from_candidate_section`; Test `test_acceptance_report_remediation_checkpoint_consistent_with_checklist`
    auf Kontext-Isolation umgestellt; neuer negativer Regressionstest
    `test_acceptance_report_remediation_checkpoint_status_not_satisfied_by_neighbour`
  - `docs/J04_M0_EXECUTABLE_CHECKLIST.md` / `docs/J04_M0_ACCEPTANCE_REPORT.md` — R2-R4-Status und Evidence
- **Abschlussbewertung MR09-R2-R4 PASS:**
  - False-positive-Lücke: vorher prüfte der Test `checkpoint in text` und `status in text` getrennt;
    ein Status aus einem benachbarten Bullet konnte die Assertion erfüllen, auch wenn der aktuelle
    Checkpoint keinen eigenen Status trug.
  - Schließung: `_extract_checkpoint_clause_from_top_line` isoliert den semicolonbegrenzten Kontext
    des aktuellen Checkpoints in der Statuszeile; `_extract_checkpoint_bullet_from_candidate_section`
    isoliert den Bullet des aktuellen Checkpoints bis zum nächsten MR09-Bullet. Status wird nur
    innerhalb des isolierten Kontexts geprüft.
  - Synthetischer Negativtest bestätigt, dass PASS aus einem Nachbarbullet die Prüfung für
    MR09-R2-X (IN_PROGRESS) nicht erfüllt.
  - Aktiver CandidateSha: keiner; historischer MR08-Candidate: `4db97ea`.
  - Gesamtstatus NOT_READY. MR10 TODO.
  - Nächster Schritt: Commit-/Candidate-Freeze-Sequenz (Commits 1–4).

### MR09-Freeze — Candidate-Freeze-Sequenz MR09-R2

- **DiagnosticCommit:** `1b0b6b1b21a4907aef00bf2e264000ad7dbece3f`
  (`test(j04-m0): diagnose realprocess comment timeout`)
- **RemediationCommit:** `c4f0c663f4f889f59e1b0bca1b46b21d6b08a57a`
  (`test(j04-m0): record and guard MR09 remediation`)
- **Pre-Freeze-Docs-Gate:** `20260819T150513189Z` — **8 passed / 0 failed**
  (`build/j04-m0-closure/mr09-freeze-pre-docs-results-20260819T150513189Z/junit.xml`)
- **Freeze-Regression-Gate:** `20260819T150534010Z` — **1254 passed / 0 failed / 20 skipped** — Exit 0
  (`build/j04-m0-closure/mr09-freeze-regression-results-20260819T150534010Z/junit.xml`)
- **FreezeCommit:** `08b04e6fe28ee86e71759440236b5ca10711fa1a`
  (`docs(j04-m0): freeze MR09 retry candidate`)
- **CandidateSha:** `08b04e6fe28ee86e71759440236b5ca10711fa1a` (`08b04e6`)
- **Freeze-Ausgangslage:** MR09-R2 bis R2-R4 PASS; Parent MR09 IN_PROGRESS; NOT_READY; kein Push, kein PR, kein CP08-Lauf
- **CP08-V10:** NOT RUN — benötigt neue ausdrückliche Einmalfreigabe
- **Gesamtstatus:** NOT_READY; MR10 TODO; Accepted unset
- **Nächster Schritt:** MR09-Freeze-R1 (docs-only Widerspruchskorrektur), danach separate destruktive CP08-V10-Freigabe

### MR09-Freeze-R1 — Aktiven Candidate-Status konsolidieren

- **Korrektur:** Im ersten Candidate-Abschnitt des Acceptance Reports standen gleichzeitig
  „Es existiert derzeit kein aktiver Candidate" (veraltet) und `08b04e6` als aktiver CandidateSha.
  Die veraltete Aussage wurde entfernt; der Abschnitt führt jetzt genau eine eindeutige
  aktive Candidate-Erklärung.
- **CandidateSha:** `08b04e6fe28ee86e71759440236b5ca10711fa1a` — **unverändert**
- **Freeze-Regression und bisherige Evidence:** unverändert
- **Kein neuer Freeze, keine neue Candidate-Nummer, keine Code- oder Teständerung**
- **Parent MR09:** IN_PROGRESS; CP08-V10: NOT RUN; Gesamtstatus: NOT_READY

### CP08-V10 — Einmaliger destruktiver Lauf (FAILED)

- **Lauf-SHA:** `a15cb3fbb16a277944a8c87500fea7576a1486be`
- **CandidateSha:** `08b04e6fe28ee86e71759440236b5ca10711fa1a` (unverändert)
- **Stamp:** `20260819T155102306Z`
- **Guard-Identität:** `database=qmtool_j04_destructive_test`, `major=18`, `port=5432`, `marker=j04_m0_destructive_pg16`
- **Runner-Exitcode:** 1
- **Workspace:** `build/j04-m0-closure/cp08-realprocess-ws/20260819T135237145371Z-6fb9ce8809cd484a9c9356a33bc89731/`
- **Evidence:** `build/j04-m0-closure/mr09-cp08-v10-results-20260819T155102306Z/runner.log`
- **Schritte 1–13:** PASS
- **Schritt 14 `pdf_comment_flow`:** **FAIL** — GET Kommentar-Endpunkt Timeout vor Response-Headern
- **Schritte 15–18:** NOT RUN (Fail-fast)
- **Einmalfreigabe:** verbraucht; Ergebnis: FAILED
- **Parent MR09:** bleibt IN_PROGRESS und nicht bestanden
- **Current checkpoint:** MR09
- **Gesamtstatus:** NOT_READY; MR10 TODO; Accepted unset
- **Nächster Schritt:** MR09-R3-R1 abgeschlossen (siehe unten); neuer Commit-/Candidate-Freeze erforderlich

### MR09-R3 / MR09-R3-R1 — Harness stdout-Pipe-Backpressure behoben (PASS)

- **Ursache CP08-V10:** Backend-stdout-Pipe wurde erst bei `cleanup` gelesen; Pipe-Buffer lief
  voll (~4076 Bytes) → Backend blockierte → GET-Request timed out vor Response-Headern.
- **Backendlog-Größe CP08-V9 und CP08-V10:** jeweils exakt **4076 Bytes**; beide enden nach
  dem erfolgreichen Kommentar-POST. Dies ist der direkte Nachweis der Backpressure.
- **Produktdefekt:** nicht nachgewiesen.
- **Windows-Socket-Flake:** nicht mehr als abschließende Erklärung gültig.
- **Historischer erster R1-Versuch:** Gate A `20260819T171454220Z` rot — **9 tests / 5 failures / 0 errors**;
  gemeinsame Ursache: `UnboundLocalError` in `_drain_and_log()`.
- **Behebung MR09-R3:** `_BackendStdoutDrainer`-Klasse in `j04_m0_realprocess_harness.py`;
  kontinuierlicher Reader-Thread pro Backendprozess; sofortige Redaktion mit `redact_log_text`
  und Live-Logpersistenz ins PID-Log.
- **Enge Korrektur MR09-R3-R1:** `_drain_and_log()` kehrt im Drainer-Zweig nach Join-/Timeout-/
  Readerfehlerprüfung sofort zurück; nur nicht gestreamte Prozesse lesen dort noch stdout und
  schreiben einmalig ins PID-Log.
- **Geänderter Dateisatz:**
  - `tests/acceptance/j04_m0_realprocess_harness.py`
  - `tests/acceptance/test_j04_m0_harness_unit.py` (9 fokussierte R1-Tests)
- **Gate A0** (`20260819T171454220Z`): **9 tests / 5 failures / 0 errors** — historisch rot
- **Gate A** (`20260819T172254282Z`): **9 passed / 0 failed / 0 errors**
- **Gate B** (`20260819T172314505Z`): **60 passed / 0 failed / 0 errors**
- **Gate C** (`20260819T172346447Z`): **1263 tests / 0 failed / 0 errors / 20 skipped**
- **Kein Commit, kein Staging, kein Candidate-Freeze**
- **Aktiver Candidate:** keiner — `08b04e6` ist historisch ungültig nach Harnessänderung
- **Parent MR09:** IN_PROGRESS; Gesamtstatus: NOT_READY; MR10: TODO; Accepted: unset
- **Nächster Schritt:** neue ausdrückliche Commit-/Candidate-Freeze-Freigabe, danach CP08-V11

### MR09-Freeze-R3 — Candidate-Freeze nach MR09-R3/R1

- **HarnessCommit:** `810f8975284f3d792153b902917e8faf24f3f00f`
  (`test(j04-m0): stream backend acceptance logs`)
- **Pre-Freeze-Docs-Gate:** `20260819T191917758Z` — **8 passed / 0 failed / 0 errors**
- **FreezeCommit / CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885`
  (`docs(j04-m0): freeze MR09 R3 candidate`)
- **Freeze-Regression:** `20260819T192016485Z` — **1263 tests / 0 failed / 0 errors / 20 skipped**
  (`1005 passed, 20 skipped, 52 deselected, 238 subtests passed`)
- **JUnit:** `build/j04-m0-closure/mr09-r3-freeze-regression-20260819T192016485Z/junit.xml`
- **Aktiver CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885` (`254c8ea`)
- **Historischer CP08-V10-Candidate:** `08b04e6` bleibt ausschließlich Historie
- **CP08-V11:** NOT RUN
- **Parent MR09:** IN_PROGRESS und nicht bestanden
- **Gesamtstatus:** NOT_READY; MR10 TODO; Accepted unset

### CP08-V11 — Einmaliger destruktiver Lauf (PASS)

- **Lauf-HEAD:** `be8fb01104cb7d4618627aa81d6f1d71e1d0a98f` (`be8fb01`)
- **CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885` (unverändert)
- **Stamp:** `20260819T202601488Z` (historischer Verzeichnisbezeichner — fälschlich mit `Z`-Suffix,
  tatsächlich lokale Wall-Clock beim Anlegen; Verzeichnis unverändert)
- **Lokale Laufzeit (UTC+2):** 2026-08-19T20:26:10.849+02:00 bis 2026-08-19T20:26:44.992+02:00
- **Entsprechende UTC-Zeit:** 2026-08-19T18:26:10.849Z bis 2026-08-19T18:26:44.992Z
- **Runner-Aufrufe:** exakt **1**
- **Guard-Identität:** `database=qmtool_j04_destructive_test`, `major=18`, `port=5432`, `marker=j04_m0_destructive_pg16`
- **Runner-Exitcode:** **0** (1 passed in 31.68s)
- **Basetemp:** `build/j04-m0-closure/mr09-cp08-v11-results-20260819T202601488Z/basetemp`
- **Evidence:** `build/j04-m0-closure/mr09-cp08-v11-results-20260819T202601488Z/runner.log`
- **Realprocess-Workspace:** `build/j04-m0-closure/cp08-realprocess-ws/20260819T182612961146Z-fab8b6579d6a43d2aeb7f5552f8187ac/`
- **Schritte 1–18:** alle **PASS** (siehe `acceptance-scenario-summary.json`)
- **Backendlog:** `backend-4440.log` **5388 Bytes** (>4076-Byte-Grenze; Drain-Fix wirksam)
- **Preflight:** alle 12 read-only Checks grün (Branch, HEAD, Candidate-Invariante, Staging, Worktree, Prozesse, Port, Env, Basetemp)
- **Cleanup:** Env entfernt; kein pytest/Backend-Rest; Port 8000 frei; Harness-Hashes unverändert
- **Einmalfreigabe:** verbraucht; Ergebnis: **PASS**
- **Parent MR09:** **PASS**
- **Current checkpoint:** **MR10**
- **Gesamtstatus:** NOT_READY; MR10 TODO; Accepted unset
- **Nächster Schritt:** unabhängige Prüfung und Planung von MR10 (nicht automatisch starten)

### MR10 — Packaging, Golive, Human Gate und Merge

- **Status:** PASS (MR10-A PASS; MR10-A-R1 PASS; MR10-B PASS; MR10-C PASS)
- **Startzeit:** 2026-08-19T18:40:21.807Z
- **Endzeit:** 2026-08-20T05:30:32.181Z
- **Start-SHA / Lauf-HEAD:** `be8fb01104cb7d4618627aa81d6f1d71e1d0a98f` (`be8fb01`) — unverändert
- **End-HEAD:** docs-only Closure-Commit (dieser Commit)
- **CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885` (`254c8ea`) — unverändert
- **Gesamtstatus:** ACCEPTED; Accepted (formale menschliche Freigabe 2026-08-20)
- **J04-M0-Produkt-Merge:** `e003b37ecb3ff6a2f878cc0cf6d1b89e8df9ad38` (`e003b37`)
- **Aktuelle Main-Basis:** `f7b867d895566ea8fd0b80a07a6eec3be4cf868a` (`f7b867d`; dazwischen nur Skill-Merge)
- **MR10-B Human-Smoke:** PASS
- **Word-COM-E2E:** nicht verifiziert; separates Conversion-Follow-up

### MR10-A — Technische Release-Gates

- **Status:** PASS (historischer Gate E FAILED; durch MR10-A-R1 behoben)
- **Stamp:** `20260819T184021807Z`
- **Evidence:** `build/j04-m0-closure/mr10-a-technical-20260819T184021807Z/`
- **Preflight:** Branch `feature/ap-j04-m0`, HEAD `be8fb01`, Divergenz 0 behind / 72 ahead;
  CandidateSha..HEAD nur zwei Docs; Staging leer; stat-only + `docs/transition/` unverändert;
  2 fremde Python-Prozesse erfasst (nicht beendet); `packaging/dist_output` und
  `packaging/_pyi_build` innerhalb `I:\Projekte\QMToolV7-j04-m0\packaging`; app.ico vor Build
  `F1C4D46485E2CE1568F93C92BD6D98BC5B972491065E5632CDA9A7AA1D57A996`
- **Gate A** (`gate-a-junit.xml`): **18 passed / 0 failed** — Releaseverträge, Golive-Unit,
  UI-MVP- und PyQt-Navigation-Smoke (nicht-interaktiv)
- **Gate B** (`gate-b-build.log`): Exit **0** — `packaging/build_onedir.py`;
  `OK: bundle clean`, `OK: bundle imports`, `QM-Tool.exe`, `QM-Tool.zip`;
  ZIP **86 241 417 Bytes** SHA-256 `018B56DB881696C4626D2ED0478C3E5F384E97477BE6E15F7ED4CB04982D96A4`;
  EXE **11 099 231 Bytes** SHA-256 `EE40B1C53B768DC75A2F71D3F1A1F216D052702B24BB7D9EDCD0A83689F98229`;
  app.ico nach Build unverändert; keine tracked Inhaltsdiffs außerhalb der Docs
- **Gate C** (`golive-gate.json`): Exit **0**, `ok=true` — alle 7 Top-Level-Checks grün;
  Migration-Gate 10/10 grün
- **Gate D** (`gate-d-junit.xml`): Exit **0** — **1005 passed / 0 failed / 20 skipped /
  52 deselected / 238 subtests passed** in 703.67s; Marker `not postgres and not j04_final_acceptance`
- **Gate D Skips (20):** 16× `not_in_m0` Legacy local documents CLI workflow;
  3× `not_in_m0` Legacy documents CLI authorization matrix;
  1× `not_in_m0` Legacy training flow outside reduced J04-M0 scope
- **Gate D Deselections (52):** postgres-markierte und j04_final_acceptance-markierte Tests
  (bewusst ausgeschlossen — kein PostgreSQL-Reset, kein Realprocess)
- **Gate E** (`gate-e-junit.xml`): **FAILED** — `1 failed / 7 passed`; erste Fehlerstelle
  `tests/docs/test_docs_consistency.py::test_acceptance_report_remediation_checkpoint_consistent_with_checklist`
  wegen fehlendem `MR09-R2-R4`-Verweis in der Top-Statuszeile des Acceptance Reports
- **Bewusst ausgeschlossen:** PostgreSQL-Reset, CP08/Realprocess, sichtbarer PyQt-Human-Smoke,
  Word-COM, Commit/Staging/Push/PR/Merge
- **Abschlussbewertung MR10-A:** PASS (Gates A–D grün; historischer Gate E rot;
  Remediation MR10-A-R1 PASS). Parent MR10 bleibt IN_PROGRESS. MR10-B
  (sichtbarer interaktiver PyQt-Human-Smoke) **NOT RUN**

### MR10-A-R1 — Docs-Konsistenz

- **Status:** PASS
- **Stamp:** `20260819T212617115Z`
- **Evidence:** `build/j04-m0-closure/mr10-a-r1-docs-20260819T212617115Z/`
- **Ursache historischer Gate-E-Fehler:** Die oberste `Current status:`-Zeile des
  Acceptance Reports enthielt keine isolierbare Klausel `MR09-R2-R4 PASS`; der erste
  `Technical acceptance candidate`-Abschnitt war bereits korrekt.
- **Historische rote Gate-E-Evidence:** `build/j04-m0-closure/mr10-a-technical-20260819T184021807Z/gate-e-junit.xml`
  — **1 failed / 7 passed** (unverändert, nicht umklassifiziert)
- **Gates A–D:** **nicht** erneut ausgeführt; historische Evidence bleibt gültig
  unter `build/j04-m0-closure/mr10-a-technical-20260819T184021807Z/`
- **Gate R1-A** (`gate-a-junit.xml`): **8 passed / 0 failed**
- **Gate R1-B** (`gate-b-junit.xml`): **8 passed / 0 failed**
- **Korrektur:** isolierte Klausel `MR09-R2-R4 PASS` in der Top-Statuszeile ergänzt
- **CandidateSha:** `254c8ea8147130c02b5661e2e467b2641ca83885` — unverändert
- **MR10-B:** PASS
- **Abschlussbewertung MR10-A-R1:** PASS. MR10-A formal PASS. Parent MR10 IN_PROGRESS.

### MR10-B — Sichtbarer interaktiver Onedir-Human-Smoke

- **Status:** PASS
- **Stamp:** `20260819T214740696Z`
- **Evidence:** `build/j04-m0-closure/mr10-b-human-20260819T214740696Z/`
- **Vorbereitung:** exakt 1; Guard-bestätigte DB `qmtool_j04_destructive_test`; Backend via Harness; HTTP-Seed QMB/Editor
- **Build-Artefakte:** unverändert (ZIP/EXE/app.ico wie MR10-A)
- **Backend-Health:** HTTP 200 `ok`
- **Menschliche Antwort:** `MR10-B Human-Smoke PASS`
- **Cleanup:** `cleaned_up`; Client-Exit 0; Port 8000 frei; Reset-/Acceptance-Opt-ins nicht gesetzt
- **Word-COM / Produktionslizenz:** nicht verifiziert
- **Nächster Schritt:** MR10-C — lokal abgeschlossen; Fetch/Push/PR nur nach separater Freigabe
- **Gesamtstatus:** READY_FOR_ACCEPTANCE; Accepted unset; CandidateSha unverändert

### MR10-C — Closure und Merge-Vorbereitung

- **Status:** PASS
- **Stamp:** `20260820T053032181Z`
- **Evidence:** `build/j04-m0-closure/mr10-c-closure-20260820T053032181Z/`
- **Formal:** MR10 PASS; Current checkpoint COMPLETE; Gesamtstatus READY_FOR_ACCEPTANCE;
  Acceptance-Report-Status `Ready for acceptance`; Accepted unset;
  CandidateSha `254c8ea8147130c02b5661e2e467b2641ca83885`
- **Commit:** docs-only `docs(j04-m0): close MR10 acceptance gates`; kein Push/PR/Merge
- **Pre-Commit-Docs-Gate:** siehe `pre-commit-junit.xml`
- **Post-Commit-Docs-Gate:** siehe `post-commit-junit.xml`
- **Nicht verifiziert:** Word-COM-E2E (Conversion-Folgepaket); Produktionslizenz-/Deploymentprüfung
- **Übergangspersistenz:** backend-eigene Documents-SQLite bleibt dokumentiert
- **MR10-B-Orchestrator:** Evidence-lokal unter `build/j04-m0-closure/mr10-b-human-20260819T214740696Z/mr10_b_orchestrator.py`;
  durch `.gitignore` ausgeschlossen; keine DSN/hartcodierten Passwörter; kein Produkt-Diff;
  nicht committen; kein Produkt-Helper/Entrypoint

## Classification legend

| Cat | Meaning |
| --- | --- |
| **A** | J04-M0 product code |
| **B** | J04-M0 test code |
| **C** | J04-M0 documentation / contract |
| **D** | Cross-package test fixture (required for J04 tests) |
| **E** | Evidence / cache / basetemp / build output (never stage) |
| **F** | Out of scope |
| **G** | Unclear (blocks CP00 if staged overlap) |

## Modified tracked files (94)

Stat-only (no content diff; refresh index only, **not staged**):

| Path | Cat | Reason |
| --- | --- | --- |
| `interfaces/pyqt/widgets/signature_placement/label_geometry.py` | — | LF/CRLF stat-only (`git diff --quiet` exit 0) |
| `modules/training/wiring.py` | — | LF/CRLF stat-only (`git diff --quiet` exit 0) |

### A — J04-M0 product code (modified)

| Path | Reason |
| --- | --- |
| `interfaces/cli/bootstrap.py` | CLI backend-session bootstrap for M0 |
| `interfaces/cli/commands/documents_commands.py` | Documents CLI scoped to M0 / `legacy_not_in_m0` |
| `interfaces/cli/commands/settings_commands.py` | Settings aligned with backend profile |
| `interfaces/cli/commands/signature_commands.py` | Signature CLI backend transport |
| `interfaces/cli/commands/users_commands.py` | User admin via backend |
| `interfaces/cli/parsers/documents_parsers.py` | Parser updates for reduced M0 scope |
| `interfaces/gui/main.py` | Legacy Tk fail-closed for documents under J04-M0 |
| `interfaces/pyqt/contributions/common.py` | Shared PyQt backend session wiring |
| `interfaces/pyqt/contributions/documents_pool_view.py` | Documents pool HTTP consumer |
| `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py` | Workflow actions fail-closed on `available_actions` |
| `interfaces/pyqt/contributions/documents_workflow/core_mixin.py` | Workflow core HTTP transport |
| `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py` | Selection soft-degrade |
| `interfaces/pyqt/contributions/documents_workflow_view.py` | Workflow view backend wiring |
| `interfaces/pyqt/contributions/settings_sections/profile_section.py` | Profile manager backend scope |
| `interfaces/pyqt/contributions/settings_sections/signature_settings_section.py` | Signature settings backend |
| `interfaces/pyqt/main.py` | PyQt entry backend profile |
| `interfaces/pyqt/presenters/documents_signature_ops.py` | Signature ops via HTTP |
| `interfaces/pyqt/presenters/documents_workflow_filter_presenter.py` | Filter presenter fail-closed |
| `interfaces/pyqt/presenters/documents_workflow_presenter.py` | Workflow presenter backend reads |
| `interfaces/pyqt/runtime/host.py` | Runtime host backend profile |
| `interfaces/pyqt/sections/action_bar.py` | Action bar server-driven visibility |
| `interfaces/pyqt/sections/detail_drawer.py` | Detail drawer backend state |
| `interfaces/pyqt/sections/filter_bar.py` | Filter bar backend integration |
| `interfaces/pyqt/shell/main_window.py` | Main window session coordinator |
| `interfaces/pyqt/shell/session_coordinator.py` | Session token provider |
| `interfaces/pyqt/widgets/audit_log_helpers.py` | Audit helpers backend scope |
| `interfaces/pyqt/widgets/document_create_wizard.py` | Create wizard capability gate |
| `interfaces/pyqt/widgets/force_password_change_dialog.py` | Auth flow alignment |
| `interfaces/pyqt/widgets/pdf_viewer_dialog.py` | Artifact read via HTTP IDs |
| `interfaces/pyqt/widgets/reject_reason_dialog.py` | Workflow mutation tokens |
| `interfaces/pyqt/widgets/signature_placement/options_mixin.py` | Signature placement |
| `interfaces/pyqt/widgets/signature_placement/placement_dialog.py` | Signature placement |
| `interfaces/pyqt/widgets/signature_preview_panel.py` | Signature preview |
| `interfaces/pyqt/widgets/signature_request_form.py` | Signature request |
| `interfaces/pyqt/widgets/signature_sign_wizard.py` | Sign wizard backend |
| `interfaces/pyqt/widgets/validity_extension_dialog.py` | Lifecycle extend_validity |
| `interfaces/pyqt/widgets/workflow_profile_wizard.py` | Profile create HTTP |
| `modules/documents/api.py` | Public documents API extensions |
| `modules/documents/comment_permissions.py` | Comment authorization |
| `modules/documents/comment_service.py` | Comment service |
| `modules/documents/comment_sync_service.py` | Comment sync |
| `modules/documents/contracts.py` | Documents contracts |
| `modules/documents/docx_to_pdf.py` | DOCX→PDF (Word COM owner) |
| `modules/documents/errors.py` | Structured errors / redaction |
| `modules/documents/eventing.py` | Domain events |
| `modules/documents/module.py` | Module registration |
| `modules/documents/repository.py` | Repository layer |
| `modules/documents/service.py` | Documents service / policy-on-lock |
| `modules/documents/sqlite_repository.py` | Backend-owned SQLite |
| `modules/documents/storage.py` | Artifact storage |
| `modules/documents/validation.py` | Validation |
| `modules/documents/wiring.py` | `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` |
| `modules/documents/workflow_use_cases.py` | Workflow use cases |
| `modules/signature/api.py` | Signature public API |
| `modules/signature/module.py` | Signature module |
| `modules/signature/service.py` | Signature service |
| `modules/signature/signature_policy_ops.py` | Policy operations |
| `modules/signature/template_use_cases.py` | Template use cases |
| `modules/signature/wiring.py` | Signature wiring |
| `modules/training/released_document_catalog_reader.py` | Training read-only documents |
| `modules/usermanagement/api.py` | Usermanagement API for backend auth |
| `qm_platform/runtime/backend_bootstrap.py` | Backend composition root |
| `qm_platform/runtime/bootstrap.py` | Client/runtime bootstrap |
| `qm_platform/runtime/lifecycle.py` | Lifecycle / backend profile |
| `src/backend/api.py` | Backend public surface |
| `src/backend/bootstrap.py` | Backend startup |
| `src/backend/user_admin_routes.py` | User admin HTTP routes |

### B — J04-M0 test code (modified)

| Path | Reason |
| --- | --- |
| `tests/backend/test_auth_api_postgres_live.py` | PG live auth (marker `postgres`) |
| `tests/backend/test_m6_postgres_live.py` | PG live M6 |
| `tests/e2e_cli/test_database_commands.py` | CLI e2e adjustments |
| `tests/e2e_cli/test_documents_cli.py` | Documents CLI M0 scope |
| `tests/e2e_cli/test_documents_cli_authorization_matrix.py` | CLI auth matrix |
| `tests/e2e_cli/test_training_cli.py` | Training CLI scope |
| `tests/interfaces/test_architecture_gates.py` | Architecture gates |
| `tests/interfaces/test_documents_workflow_presenter_filters.py` | Presenter filters |
| `tests/interfaces/test_documents_workflow_profile_cli.py` | Profile CLI contract |
| `tests/interfaces/test_ui_mvp_smoke.py` | UI smoke |
| `tests/modules/test_documents_authorization_matrix.py` | 16-action matrix |
| `tests/modules/test_documents_infrastructure.py` | Infrastructure |
| `tests/modules/test_documents_module_ports.py` | Module ports / wiring |
| `tests/modules/test_documents_registry_invariants.py` | Registry invariants |
| `tests/modules/test_training_module_ports.py` | Training ports |
| `tests/modules/usermanagement/test_m7_audit_evidence_live.py` | M7 PG live |
| `tests/modules/usermanagement/test_m8_cutover_prep.py` | M8 cutover prep |
| `tests/modules/usermanagement/test_postgres_repositories_live.py` | PG repos live |
| `tests/modules/usermanagement/test_postgres_schema_live.py` | PG schema live |
| `tests/platform/test_core_database_migrations.py` | Platform migrations |
| `tests/platform/test_documents_bootstrap_provenance.py` | Bootstrap provenance |

### C — J04-M0 documentation / contract (modified)

| Path | Reason |
| --- | --- |
| `docs/MASTER_ORCHESTRATION_ROADMAP.md` | J04-M0 roadmap status |
| `docs/QMToolV7_Dokumentenlenkung_Artefaktpaket_v2/JSON_TO_DATABASE_MIGRATION_PLAN.md` | Migration plan J04 context |

### D — Cross-package test fixtures (modified)

| Path | Reason |
| --- | --- |
| `tests/conftest.py` | Shared pytest fixtures for backend HTTP / session tests across layers |
| `tests/modules/incident_management_test_support.py` | Incident fixtures reused by documents authorization tests |

## Untracked product files (59) — all staged as A/B/C/D

### A — product (untracked)

| Path |
| --- |
| `interfaces/clients/auth_messages.py` |
| `interfaces/clients/backend_identity.py` |
| `interfaces/clients/backend_session.py` |
| `interfaces/clients/documents_http.py` |
| `interfaces/clients/documents_http_ports.py` |
| `interfaces/clients/http_transport.py` |
| `interfaces/clients/signature_http.py` |
| `interfaces/clients/signature_http_ports.py` |
| `modules/documents/actor_context.py` |
| `modules/documents/capabilities.py` |
| `modules/documents/sign_intent_builder.py` |
| `modules/documents/state_transport.py` |
| `modules/documents/workflow_policy.py` |
| `modules/signature/transport_dto.py` |
| `qm_platform/runtime/client_runtime_profile.py` |
| `scripts/export_openapi.py` |
| `src/backend/documents_routes.py` |
| `src/backend/signature_routes.py` |

### B — tests (untracked)

| Path |
| --- |
| `tests/backend/test_documents_artifacts_http.py` |
| `tests/backend/test_documents_authorization_http.py` |
| `tests/backend/test_documents_concurrency_http.py` |
| `tests/backend/test_documents_http_api.py` |
| `tests/backend/test_documents_p4_p9_http.py` |
| `tests/backend/test_documents_reads_http.py` |
| `tests/backend/test_documents_signed_transitions_http.py` |
| `tests/backend/test_documents_training_read_http.py` |
| `tests/backend/test_openapi_contract.py` |
| `tests/backend/test_signature_authorization_http.py` |
| `tests/backend/test_signature_http_api.py` |
| `tests/backend/test_user_directory_api.py` |
| `tests/interfaces/test_action_bar_visibility.py` |
| `tests/interfaces/test_auth_messages.py` |
| `tests/interfaces/test_backend_identity.py` |
| `tests/interfaces/test_backend_identity_hotspots.py` |
| `tests/interfaces/test_backend_session_client.py` |
| `tests/interfaces/test_documents_http_client_fail_closed.py` |
| `tests/interfaces/test_documents_http_gates.py` |
| `tests/interfaces/test_documents_http_reads.py` |
| `tests/interfaces/test_documents_http_workflow_port_stubs.py` |
| `tests/interfaces/test_documents_workflow_profile_manager_gate.py` |
| `tests/interfaces/test_documents_workflow_selection_soft_degrade.py` |
| `tests/interfaces/test_gui_documents_fail_closed.py` |
| `tests/interfaces/test_home_fail_closed_documents.py` |
| `tests/interfaces/test_m2r_control_action_gates.py` |
| `tests/interfaces/test_m2r_header_comment_cas_consumers.py` |
| `tests/interfaces/test_m3_prelive_token_controls.py` |
| `tests/interfaces/test_pyqt_backend_profile_scope.py` |
| `tests/interfaces/test_pyqt_session_coordinator.py` |
| `tests/postgres/compose.yaml` |
| `tests/postgres/init/001_test_cluster_marker.sql` |
| `tests/postgres/manage.ps1` |
| `tests/postgres/README.md` |
| `tests/postgres_destructive_guard.py` |
| `tests/postgres_live_support.py` |
| `tests/test_postgres_destructive_guard.py` |

### C — documentation / contract (untracked)

| Path |
| --- |
| `docs/J04_M0_ACCEPTANCE_REPORT.md` |
| `docs/J04_M0_ALLOWED_ACTIONS_ANALYSIS.md` |
| `docs/J04_M0_PATH_MATRIX.md` |
| `docs/J04_M0_EXECUTABLE_CHECKLIST.md` |
| `docs/contracts/j04-m0-openapi.json` |

## E — Evidence / cache (never stage)

Bulk patterns (all contents under these roots):

| Pattern | Count (approx.) | Reason |
| --- | --- | --- |
| `.j04_final_focused_basetemp/**` | 9 | Pytest basetemp from prior focused runs |
| `.j04_g3_evidence/**` | ~120+ | G3 milestone raw logs and basetemps |
| `.j04_g_modules2_basetemp/**` | ~800+ | Module test basetemps |
| `.j04_m0_evidence/**` | varies | M0 verification logs |
| `.j04_m1r_evidence/**` | varies | M1R verification logs |
| `.j04_m2_evidence/**` | varies | M2 verification logs |
| `.j04_m2r_evidence/**` | varies | M2R verification logs |
| Other `.j04*` dirs | varies | Historical/local evidence |

Also excluded: `.env`, `*.db`, `*.sqlite`, `build/j04-m0-closure/` (runtime output), `.venv/`.

Historical evidence in prior reports is **not** current CP00 evidence.

## F / G — none identified

No path classified **F** (out of scope) or **G** (unclear). All modified/untracked product paths map to A–D.

## CP00 acceptance criteria

- [x] Every modified/untracked path classified A–G with rationale
- [x] No E/F/G path staged
- [x] No secrets, `.env`, DBs, or raw logs staged
- [x] Stat-only files confirmed (`label_geometry.py`, `wiring.py`)
- [x] Focused architecture/contract smokes green (24 passed)
- [x] Checklist and acceptance report updated
- [x] Staged file list contains only confirmed J04-M0 baseline (A–D)

## CP00 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/platform/test_documents_bootstrap_provenance.py `
  tests/modules/test_documents_module_ports.py `
  tests/interfaces/test_documents_http_gates.py `
  tests/backend/test_openapi_contract.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp00
```

Result: **24 passed** (2026-08-17, `build/j04-m0-closure/cp00`)

## CP02 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/backend/test_documents_artifacts_http.py `
  tests/backend/test_signature_http_api.py `
  tests/backend/test_signature_authorization_http.py `
  tests/backend/test_documents_training_read_http.py `
  tests/backend/test_documents_p4_p9_http.py `
  tests/interfaces/test_documents_http_reads.py `
  tests/interfaces/test_documents_workflow_profile_manager_gate.py `
  tests/interfaces/test_action_bar_visibility.py `
  tests/interfaces/test_m2r_control_action_gates.py `
  tests/interfaces/test_m2r_header_comment_cas_consumers.py `
  tests/interfaces/test_pyqt_backend_profile_scope.py `
  tests/modules/test_documents_authorization_matrix.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp02
```

Result: **62 passed** (2026-08-17, `build/j04-m0-closure/cp02`)

## CP02 acceptance criteria

- [x] All M0 vertical slices use existing HTTP/public-API paths
- [x] PyQt actions remain server-driven and fail-closed
- [x] Training has no documents workflow/artifact logic ownership
- [x] Profile manager has no local mutation path
- [x] Out-of-scope findings documented as follow-ups (historical report sections)
- [x] Documentation and tests align (62/62 green; no fixes required)

## CP03 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/modules/test_docx_to_pdf.py `
  tests/interfaces/test_docx_conversion_worker.py `
  tests/backend/test_documents_p4_p9_http.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp03
```

Result: **24 passed** (2026-08-17, `build/j04-m0-closure/cp03`)

## CP03 acceptance criteria

- [x] Production code uses isolated own Word instance (`DispatchEx`)
- [x] Cleanup affects only self-created COM objects
- [x] Success and error paths covered by mock-based tests
- [x] Error output redacted (paths, COM repr)
- [x] No real Word E2E in this checkpoint
- [x] No changes to running Word sessions (mock-only)

## CP04 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/test_postgres_destructive_guard.py `
  tests/modules/usermanagement/test_postgres_schema_static.py `
  tests/modules/usermanagement/test_postgres_migration_gate.py `
  tests/modules/usermanagement/test_m7_audit_evidence_static.py `
  tests/modules/usermanagement/test_m8_cutover_prep.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp04
```

Result: **57 passed** (2026-08-17, `build/j04-m0-closure/cp04`)

## CP04 acceptance criteria

- [x] Every destructive path centrally guarded (`require_approved_admin_dsn`)
- [x] Runtime/lab DSNs cannot pass the guard (unit-tested)
- [x] No secrets in staged config/docs
- [x] CI service is ephemeral and marker-bound
- [x] `pg_dump`/`pg_restore` remain M8-only (static prep tests pass)
- [x] **PG16 LIVE NOT RUN** locally
- [x] Config/docs only in CP04 commit (no product code)

## CP05 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/backend/test_documents_http_api.py `
  -k "two_clients_and_restart_readback or version_read_after_restart or harness" `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp05
```

Result: **10 passed** (2026-08-17, `build/j04-m0-closure/cp05`)

## CP05 acceptance criteria

- [x] Harness uses real separate processes (client workers; backend launch verified via mock + canonical `-m src.backend`)
- [x] Separate `QMTOOL_HOME` paths for backend and two clients
- [x] Cleanup terminates only tracked PIDs
- [x] Logs redacted before write under `build/j04-m0-closure/`
- [x] Final test requires marker + explicit opt-in (excluded in CP05 run)
- [x] Full realprocess test **NOT RUN** in CP05

## CP06 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/packaging/test_bundle_excludes_secrets.py `
  tests/packaging/test_j04_m0_onedir_contract.py `
  tests/interfaces/test_backend_session_client.py `
  tests/interfaces/test_pyqt_backend_profile_scope.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp06
```

Result: **16 passed** (2026-08-17, `build/j04-m0-closure/cp06`)

## CP06 acceptance criteria

- [x] Existing onedir owner covers J04-M0 runtime imports (hidden-import list extended)
- [x] Bundle verifier rejects secrets, local DBs, `.env`, evidence artifacts
- [x] `QMTOOL_BACKEND_URL` remains runtime configuration (contract test)
- [x] No parallel/onefile build path introduced
- [x] **Packaging NOT RUN** documented
- [x] Static contract test added (gap not fully covered by prior tests)
- [x] No new product entrypoint/port/API

## CP07 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/docs/test_document_control_artifact_package.py `
  tests/backend/test_openapi_contract.py::test_openapi_snapshot_is_reproducible `
  tests/test_postgres_destructive_guard.py `
  tests/interfaces/test_architecture_gates.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp07
$Py -m pytest tests/packaging/test_j04_m0_onedir_contract.py -q `
  --basetemp build/j04-m0-closure/cp07-packaging
```

Result: **60 passed** + **5 passed** (2026-08-17)

## CP07 acceptance criteria

- [x] CP00–CP06 committed and documented
- [x] No unresolved F/G files overlapping the candidate
- [x] Historical evidence is not presented as the current pass
- [x] Remaining live/packaging/human gates documented as **NOT RUN**
- [x] Worktree clean except the two known stat-only files
- [x] `$CandidateSha` recorded: `8c273de4e33837dbca44464172db1033de476399` (`8c273de`) — remediation after CP07 freeze

## CP04-R verification (adopted — other agent, do not re-implement)

Verified 2026-08-17 on `feature/ap-j04-m0` @ `8c273de`:

| Item | Value |
| --- | --- |
| Slot 1 (Lab, unchanged) | `192.168.0.4:5432` / `qmtool_test` |
| Slot 2 (destructive) | `127.0.0.1:5432` / PostgreSQL **18.4** |
| Test DB | `qmtool_j04_destructive_test` |
| Admin | `qmtool_j04_test_admin` |
| Marker | `j04_m0_destructive_pg16` (unchanged string) |
| `QMTOOL_PG_TEST_EXPECTED_MAJOR` | local **18**, CI **16**, default **16** |
| Floor | PostgreSQL **>= 16** |
| RESET | not persisted; injected only in pytest child via runner |

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest tests/test_postgres_destructive_guard.py tests/test_run_postgres_live_tests.py -q `
  --basetemp build/j04-m0-closure/cp04r-verify
```

Result: **28 passed** (closure verification 2026-08-17)

Commit: `8c273de` — `test(j04-m0): pin destructive PG major via env for local PG18 smoke`

## CP08 preconditions (next open checkpoint)

- [x] Product `$CandidateSha` = `8c273de` (doc follow-up `94fb480` only)
- [x] Worktree clean except known stat-only files
- [x] Slot-2 PG18 preflight: major=18, marker valid, port 5432
- [x] Port 8000 free
- [ ] Word available (COM isolation already in product)
- [ ] Explicit opt-in before `j04_final_acceptance` full run
- [ ] Human gate remains separate (CP09)

## CP08 execution order (FAILED — candidate NOT_READY)

Per gate rules: **no product/test fixes during CP08**. One regression failure aborts the gate.

| Step | Gate | Status | Evidence |
| --- | --- | --- | --- |
| 1 | PostgreSQL live (`run_postgres_live_tests.py`, PG18 / `EXPECTED_MAJOR=18`) | **PASS** | **51 passed**; preflight major=18; `build/j04-m0-closure/cp08-pg-live-runner-clean.log` |
| 2 | Full `j04_final_acceptance` real-process E2E | **NOT RUN** | Opt-in not set; harness scenario still `pytest.skip` stub |
| 3 | Word COM live E2E | **BLOCKED** | `CO_E_SERVER_EXEC_FAILURE` — Word cannot start in this session |
| 4 | Onedir build + bundle verify | **NOT RUN** | Blocked by gate abort after step 5 failure |
| 5 | Full non-destructive regression | **FAILED** | `test_module_wiring_hard_get_ports_are_declared_as_required_ports` — `modules/documents/wiring.py` non-literal `get_port` |
| 6 | `scripts/golive_gate.py` | **NOT RUN** | — |
| 7 | Human acceptance prep | **NOT RUN** | CP09 |

### CP08 regression failure (blocks gate)

```
FAILED tests/modules/test_module_contract_wiring.py::test_module_wiring_hard_get_ports_are_declared_as_required_ports
AssertionError: modules\documents\wiring.py uses non-literal get_port
```

Cause: `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` constant passed to `container.get_port()` in
`modules/documents/wiring.py` (J04 baseline product code). Requires a **post-gate remediation
checkpoint** — not an in-gate fix.

Log: `build/j04-m0-closure/cp08-regression.log`

## CP08-R1 verification (wiring literal port)

Minimal product fix only. `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` remains exported for
tests/composition roots. Architecture test unchanged. **No freeze.**

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/modules/test_module_contract_wiring.py `
  tests/modules/test_documents_module_ports.py `
  tests/interfaces/test_documents_http_gates.py `
  tests/platform/test_documents_bootstrap_provenance.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp08-r1
```

Result: **16 passed** (2026-08-17)

Remaining after R1:

1. CP08-R2 — implement full real-process scenario (remove `pytest.skip` stub) — **PASS (implementation only)**
2. Word COM readiness in an interactive session — **WR03 DispatchEx PASS** (see WR03 below); freeze not started this turn
3. New technical freeze — **next** (R1+R2 including docs HEAD) after this report is accepted
4. Second full CP08 attempt — **blocked until freeze**

## Word COM readiness probe (2026-08-17)

Minimal probe only — **no DOCX/PDF E2E**, no termination of pre-existing Word sessions.

| Item | Result |
| --- | --- |
| Method | `win32com.client.DispatchEx("Word.Application")` + `pythoncom.CoInitialize()` (matches product CP03) |
| Controlled quit | Attempted on owned instance only (`word.Quit()` in `finally`) |
| Pre-existing WINWORD | PIDs **15936**, **23944** — **not terminated** |
| Post-probe WINWORD | **15936**, **23944** still present; transient PID **22184** appeared during failed start |
| HRESULT | **0x80080005** (`CO_E_SERVER_EXEC_FAILURE`) |
| Status | **BLOCKED** — Word cannot be started from this agent shell session |
| Evidence | `build/j04-m0-closure/word-com-readiness/probe-result.json` (local, not committed) |

Classification: interactive Windows/COM environment failure, **not** a new product deviation.
`e8a015c` is documentation only. Overall closure status: **`NOT_READY`**.

Re-probe **must** run in a normal interactive desktop PowerShell (not the agent shell).
On **PASS** only, in this order:

1. Document readiness in checklist and report
2. Freeze R1+R2 including documentation HEAD
3. Record the new `$CandidateSha`
4. Start exactly one second CP08 run against that SHA

Until then: no freeze, no second CP08.

## WR03 — Safe mode + add-in isolation (2026-08-17)

WR02 leftover PID was already gone. No pre-existing WINWORD at WR03 start. **No DOCX/PDF E2E.**

### Safe mode

| Item | Result |
| --- | --- |
| Command | `C:\Program Files\Microsoft Office\Root\Office16\WINWORD.EXE /safe` |
| PID | **21364** (started by this probe; later stopped) |
| Title | **`Microsoft Word (Abgesicherter Modus)`** |
| Responding | True |
| Status | **PASS** |

### Add-in inventory and isolation order

Autoload (`LoadBehavior=3`) third-party first, then HKCU demand-load copies:

1. Acrobat PDFMaker (HKLM + WOW6432Node `LoadBehavior=3`; HKCU `2`)
2. Citavi Word Add-In 6.17 (WOW6432Node `LoadBehavior=3`; HKCU `2`)
3. OneNote (HKCU `8` / `0`) — not changed

| Action | Result |
| --- | --- |
| HKLM `LoadBehavior` 3→0 (Acrobat, Citavi) | **BLOCKED** — registry access denied (no elevation) |
| HKCU Acrobat + Citavi `LoadBehavior`→0, then `DispatchEx` | **PASS** Word 16.0 |
| A: Acrobat=0, Citavi=2 | **PASS** |
| B: Acrobat=2, Citavi=0 | **PASS** |
| C: both restored HKCU=2 | **PASS** |
| HKCU restored to snapshot | Acrobat=2, Citavi=2 |

**Add-in effect:** not causal in this session. `DispatchEx` succeeded with original HKCU values after a clean safe-mode quit and empty WINWORD list. HKLM autoload entries remain `3`.

Evidence (local, not committed): `build/j04-m0-closure/word-com-readiness/wr03-result.json`

Freeze and second CP08 were **not** started in WR03.


## WR05 — Interactive Word COM readiness (PASS)

WR03 recovery was followed by a successful `DispatchEx('Word.Application')` probe in the normal
interactive desktop session 1. Office version `16.0.17932.20884` was readable, the owned
instance was quit, and the original HKCU add-in values were restored. No DOCX/PDF E2E was run.

Readiness is **PASS** for the COM boundary only. The prior agent-context `0x80080005` attempt is
historical evidence; it does not change the successful interactive result. FR08 must now freeze
R1, R2, and the documentation before CP08-V2.

## FR08 — Remediated acceptance candidate freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), WR05 documentation (`034425f`), and the
current technical tree. The focused gates are **46 passed**. The frozen candidate is
`fe172c9fc3b5753b9b6d4b9b1a1d026760257c37` (`fe172c9`). No product or test changes are allowed
after this freeze. CP08-V2 remains **NOT STARTED**.

## CP08-V2 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `fe172c9fc3b5753b9b6d4b9b1a1d026760257c37`.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 guard preflight; **51 passed** |
| Full real-process E2E | **FAILED/ABORTED** — `WinError 5` prevented pytest basetemp use and cleanup |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** — first mandatory step after PG stopped the gate |

No repair was performed during CP08-V2. Status remains **`NOT_READY`**; no retry is allowed
without a bounded remediation checkpoint and a new technical freeze.

## CP08-R3 — Basetemp / workspace isolation (test-only)

Observed CP08-V2 abort: **`WinError 5`** on pytest basetemp use and cleanup. Child-process file
locks under `tmp_path` remain a **plausible** cause, not a proven one. R3 decouples the
long-lived workspace from pytest `tmp_path` without claiming a root-cause proof.

Workspace helper in `tests/acceptance/j04_m0_realprocess_harness.py`:

```text
build/j04-m0-closure/cp08-realprocess-ws/<UTC-timestamp>-<uuid>/
```

Path is `resolve()`-enforced under `repo_root()/build/j04-m0-closure/`. Existing paths are never
reused or deleted. Full-gate test no longer takes `tmp_path`. `pytest.ini` default basetemp
unchanged.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r3-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **18 passed** (`build/j04-m0-closure/cp08-r3-20260817T125918964Z`). No `PermissionError` /
WinError 5 on start or cleanup.

Fail-closed: **1 skipped**, exit 0 (`cp08-r3-skip-20260817T125934013Z`).

**No freeze. No CP08-V3.** R3 PASS is not Freeze, CP08-V3, or ACCEPTED.

CP08-R3 commit: `c3d6587` — `test(j04-m0): isolate realprocess workspace from pytest basetemp`

## FR09 — R1+R2+R3 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), WR05 documentation
(`034425f`), and the freeze documentation. Focused gates are **50 passed**
(`build/j04-m0-closure/freeze-r3-20260817T171311893Z`): R1 16, R3 harness/scenario 18,
Word isolation 16 (`test_docx_to_pdf.py` + `test_docx_conversion_worker.py`). FR08 reported
46 on the pre-R3 set. The frozen candidate is
`1a22d3809683d16ad9354d609f6ce2d2af7c053a` (`1a22d38`). No product or test changes are
allowed after this freeze. CP08-V3 was executed once against this candidate and **FAILED**.
Overall status remains **`NOT_READY`**. `ACCEPTED` is not set.

## CP08-V3 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `1a22d3809683d16ad9354d609f6ce2d2af7c053a`.
Lauf-SHA at gate start: `57d87d46012ea2ed12c95fc7c1bca54bd200595b` (FR09 SHA-record docs only;
`git diff 1a22d38..57d87d4` is the two documentation files). Gate policy: no repair and no
retry after the first red mandatory step.

The documented start command was **direct pytest**. That is inconsistent with the PostgreSQL
safety model: the PG runner injects `QMTOOL_PG_TEST_RESET` only into its pytest child after
read-only preflight. A separately started pytest process does not receive that injection.
`prepare_live_environment()` requires RESET because it is destructive; the guard is correct
and must not be weakened or bypassed with a global/automatic RESET.

Stop point: `pg_bootstrap`. Backend start and Word COM were **not reached**. CP08-V3 has
**no Word-COM result**. Historical Word-readiness issues are not the cause of this run.
Status is **`NOT_READY` because of the acceptance start contract**.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 guard preflight; **51 passed**; `build/j04-m0-closure/cp08-v3-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at start contract / `pg_bootstrap` (RESET unset in the separate pytest process) |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** — Word not reached |

No repair was performed during CP08-V3. `ACCEPTED` is not set.

## CP08-R4 — Acceptance start contract (PG runner)

Test-only. Extends the existing runner; does not change the destructive guard.

The full realprocess gate must be started as:

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$env:QMTOOL_PG_TEST_EXPECTED_MAJOR = "18"
$env:QMTOOL_J04_FINAL_ACCEPTANCE = "I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN"
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-pytest-$stamp"
$Py scripts/run_postgres_live_tests.py `
  --j04-final-acceptance `
  --basetemp $Base
```

RESET remains child-only after preflight. The runner does not set Word COM live.
Loose `pytest tests/acceptance/test_j04_m0_realprocess.py` is rejected by the runner
(exit 4) so the unsupported start path cannot be mixed into default live targets.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r4-$stamp"
$Py -m pytest `
  tests/test_run_postgres_live_tests.py `
  tests/test_postgres_destructive_guard.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **51 passed** (`build/j04-m0-closure/cp08-r4-20260817T182342311Z`).

**No freeze. No CP08 retry.** Overall **`NOT_READY`** at R4 close: start contract remediating;
Word not in scope for that checkpoint.

CP08-R4 commit: `5233b5d` — `test(j04-m0): route realprocess gate through PG live runner`

## FR10 — R1–R4 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), WR05 documentation (`034425f`), and the freeze documentation. Focused gates are
**83 passed** (`build/j04-m0-closure/freeze-r4-20260817T182715064Z`): FR09 set plus R4 runner
and destructive-guard tests. The frozen candidate is
`1bd8aa0f026249cd8e635d4a3c3ad34857ea953e` (`1bd8aa0`). No product or test changes are
allowed after this freeze. CP08-V4 was executed once and **FAILED** at
`bootstrap_admin_login`. Word COM was **not reached**. Overall **`NOT_READY`**: after the
start-contract remediation there is not yet a successful CP08 run. Historical CP08-V3 aborted
on the acceptance start contract, not Word COM. `ACCEPTED` is not set.

## CP08-V4 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `1bd8aa0f026249cd8e635d4a3c3ad34857ea953e`.
Lauf-SHA: `fd3aeb8`. Realprocess via `--j04-final-acceptance`. No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v4-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at `bootstrap_admin_login` — `POST /auth/login` 200, `GET /auth/me` **409**. Start contract (`pg_bootstrap`) **PASS**. Word **not reached**. Workspace `20260817T183206770668Z-3da54ae0ec944243aeab4f6f96c132a3` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

## CP08-R5 — Bootstrap-admin `/auth/me` handshake (test-only)

CP08-V4 stopped at `bootstrap_admin_login` after `POST /auth/login` **200** and `GET /auth/me` **409**.
The V4 fail log did not capture the 409 body. Investigation (read-only, then harness-only fix):

| # | Check | Finding |
| --- | --- | --- |
| 1 | 409 body / backend log | Uvicorn: login 200 then `/auth/me` 409. Product mapping: `PasswordChangeRequiredError` → `{"detail":{"error":"password_change_required","message":"password change required"}}`. Other 409s (`user_exists`, `last_active_admin`) are not typical of `GET /auth/me`. |
| 2 | Authorization header | `AcceptanceHttpClient.request_raw(..., auth=True)` sends `Authorization: Bearer {token}` after login. A missing token would be **401**, not 409. |
| 3 | Owner | `GET /auth/me` → `require_user_context_normal` (`password_change_allowed=False`) → `um_api.resolve_session` → `session_ops.py` raises if `user.must_change_password`. Transport has no domain logic. |
| 4 | Session / bootstrap admin | Login persisted a session (otherwise 401). `bootstrap_first_admin` sets `must_change_password=True`. **Not weakened.** |
| 5 | Coverage gap | `tests/backend/test_auth_api.py` and postgres-live auth tests **expect** login 200 → `/auth/me` 409 → change-password 204 → `/auth/me` 200. Realprocess expected `/auth/me` 200 immediately. Gap is the scenario handshake, not product auth. |
| 6 | Smallest test | Mock HTTP reproducing that handshake (`complete_bootstrap_admin_session`). A full OS-process backend test is CP08 itself. |

Decision: **harness/testdata, not product.** No Word, packaging, PG-guard, or RESET change.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r5-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  tests/backend/test_auth_api.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **28 passed** (`build/j04-m0-closure/cp08-r5-20260817T195540932Z`). Ambient J04/Word opt-ins unset before the run.

**No freeze. No CP08 retry in this checkpoint.** Overall **`NOT_READY`** at R5 close: handshake remediating;
Word not in scope for that checkpoint.

CP08-R5 commit: `34f39c0` — `test(j04-m0): complete bootstrap admin password-change handshake`

## FR11 — R1–R5 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), R5 (`34f39c0` / docs `164a7c9`), WR05 documentation (`034425f`), and the freeze
documentation. Focused gates are **93 passed**
(`build/j04-m0-closure/freeze-r5-20260817T195901962Z`): FR10 set plus R5 handshake tests and
`tests/backend/test_auth_api.py`. The frozen candidate is
`c263ff550a81eccfc5bb68f2ffd2e030e8e51427` (`c263ff5`). No product or test changes are
allowed after this freeze. CP08-V5 was executed once and **FAILED** at
`document_baseline_flow`. The R5 bootstrap handshake **held**. Word COM was **not reached**.
Overall **`NOT_READY`**: there is not yet a successful CP08 run. Historical CP08-V3 aborted
on the acceptance start contract, not Word COM. CP08-V4 start contract **held**. `ACCEPTED`
is not set.

## CP08-V5 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `c263ff550a81eccfc5bb68f2ffd2e030e8e51427`.
Lauf-SHA: `05aed9f`. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set.
No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v5-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at `document_baseline_flow` — `version payload missing etag`. Backend log: `POST /documents/versions/create` **403**. R5 handshake **PASS** (`POST /auth/login` 200, `GET /auth/me` 409, `POST /auth/change-password` 204, `GET /auth/me` 200). Start contract **PASS**. Word **not reached**. Workspace `20260817T200418444108Z-8540fb06cf7846699a99cac847f51887` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

## CP08-R6 — Document-create 403 (test-only)

CP08-V5 stopped at `document_baseline_flow`. Backend log: `POST /documents/versions/create` **403**.
The fail log only said `version payload missing etag`. Investigation (read-only V5 evidence + code):

| # | Check | Finding |
| --- | --- | --- |
| 1 | 403 body | Not in V5 fail log. Product mapping: `PermissionDeniedError` → `{"detail":{"error":"forbidden",...}}`. |
| 2 | Actor | Create used `ctx.tokens["admin"]` (`j04acceptadmin`, Admin). QMB user was already seeded and used for the workflow profile. |
| 3 | Owner | `documents.api.create_document_version` requires effective QMB or delegated create. `_delegated_create_allowed` is unset in the acceptance run. Transport has no domain logic. |
| 4 | Coverage gap | HTTP fixtures call `set_user_qmb("admin", True)` then create as admin. Realprocess did not. Authorization tests create as `qmb`. |

Decision: **harness actor + diagnostics, not product.** Bootstrap admin is not granted QMB. Failures now include `status=` and `error=` before etag parse.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r6-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  tests/backend/test_documents_authorization_http.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **36 passed** (`build/j04-m0-closure/cp08-r6-20260818T042343176Z`). Ambient J04/Word opt-ins unset.

**No freeze. No CP08 retry in this checkpoint.** Overall **`NOT_READY`** at R6 close. Word not in scope. `ACCEPTED` is not set.

CP08-R6 commit: `e28a44d` — `test(j04-m0): use seeded QMB for document create and surface 403`

## FR12 — R1–R6 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), R5 (`34f39c0` / docs `164a7c9`), R6 (`e28a44d` / docs `1f72451`), WR05
documentation (`034425f`), and the freeze documentation. Focused gates are **108 passed**
(`build/j04-m0-closure/freeze-r6-20260818T042711993Z`): FR11 set plus R6 handshake/create tests
and `tests/backend/test_documents_authorization_http.py`. The frozen candidate is
`b63d9a16f87e8e9a12942d41101ee793d1fbb209` (`b63d9a1`). No product or test changes are
allowed after this freeze. CP08-V6 was executed once and **FAILED** at
`etag_concurrency_race`. Document create **PASS**. Word COM was **not reached**.
Overall **`NOT_READY`**: there is not yet a successful CP08 run. `ACCEPTED` is not set.

## CP08-V6 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `b63d9a16f87e8e9a12942d41101ee793d1fbb209`.
Lauf-SHA: `049c0fd`. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set.
No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v6-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at `etag_concurrency_race` — harness `TypeError` (`sorted expected 1 argument, got 2`). R6 create **PASS** (`POST /documents/versions/create` 200, import/assign/start 200). Race HTTP on backend log: assign-roles **200** then **409**. Word **not reached**. Workspace `20260818T043346608779Z-d3a488be334042e7ab81a38da5b9ffb7` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

## CP08-R7 — ETag-race harness (test-only)

CP08-V6 reached `etag_concurrency_race`. Backend assign-roles race was **200** then **409**.
The harness then raised `TypeError`: `sorted expected 1 argument, got 2` from
`sorted(int, int)`. That is a harness bug, not a product deviation. The fail detail was only
`TypeError` because the generic except stores `type(exc).__name__`.

Fix: `evaluate_etag_race_payloads()` passes both statuses as one iterable to `sorted()`.
Contract remains `[200, 409]`. Both worker bodies use `ETAG_RACE_STABLE_ASSIGNMENT`
(`editor` / `reviewer` / `approver`); `observer` is no longer a race winner. Product auth,
PG, Word, and packaging are unchanged.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r7-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/backend/test_documents_concurrency_http.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **54 passed** (`build/j04-m0-closure/cp08-r7-20260818T045911092Z`). Ambient J04/Word
opt-ins unset. `git diff --check` on the two test files: exit 0. Independent review confirmed
the R7 content diff and code; evidence contents were ACL-blocked in that review session.

CP08-R7 commit: `f5dcfa8` — `test(j04-m0): fix etag race harness evaluation`

Docs SHA record: `ae5be41` — `docs(j04-m0): record CP08-R7 SHA`

## FR13 — R1–R7 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), R5 (`34f39c0` / docs `164a7c9`), R6 (`e28a44d` / docs `1f72451`), R7 (`f5dcfa8` /
docs `ae5be41`), WR05 documentation (`034425f`), and the freeze documentation. Focused gates
are **137 passed** (`build/j04-m0-closure/freeze-r7-20260818T051722279Z`): FR12 set plus
`tests/backend/test_documents_concurrency_http.py` and the R7 race-evaluation tests.
The frozen candidate is `cd3a3769c4d3b470f227bb25464785926b9584db` (`cd3a376`). No product
or test changes are allowed after this freeze. CP08-V7 was executed once and **FAILED** at
`artifacts_transport`. ETag race **PASS**. Word COM was **not reached**. Overall
**`NOT_READY`**: there is not yet a successful CP08 run. `ACCEPTED` is not set.

Worktree at freeze: only the two confirmed stat-only files
(`interfaces/pyqt/widgets/signature_placement/label_geometry.py`,
`modules/training/wiring.py`).

## CP08-V7 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `cd3a3769c4d3b470f227bb25464785926b9584db`.
Lauf-SHA: `45df9d6`. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set.
No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v7-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at `artifacts_transport` — `GET /documents/versions/J04-ACCEPT-DOC/1/artifacts` **404** `not_found` / `document version not found`. R7 race **PASS** (`one winner and one 409 on shared etag`; backend assign-roles **200** then **409**). Document create **PASS**. Word **not reached**. Workspace `20260818T052422861269Z-eeb566a9bf8e40ef804915b28ded29ae` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

CP08-V7 failed **before** artifact transport on a harness identity error, not a missing
document or a product artifact defect. Document create, PDF import, workflow start, and
the R7 race held. `documents.db` contained `J04-ACCEPT-DOC/1` and the `SOURCE_PDF`
artifact. Assignments stored the login names `editor` / `reviewer` / `approver`.
PostgreSQL user ids are UUIDs. Visibility compares `actor_user_id` to those assignment
values, so the IN_PROGRESS version was correctly invisible to the editor. The documents
route masks that as `404 document version not found` and never calls the artifact API.

## CP08-R8 — Workflow assignments use `/auth/me` user_id (test-only)

After each role login the harness calls `GET /auth/me`, validates `username`, and stores
`user_id`. Baseline `assign-roles` and both R7 race workers send those user ids. The race
contract remains `[200, 409]`. Training receipt compares the stored editor `user_id`, not
the login name. Product authorization, PG, Word, and packaging are unchanged.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r8-$stamp"
$Results = "build/j04-m0-closure/cp08-r8-results-$stamp"
New-Item -ItemType Directory -Force -Path $Results | Out-Null
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/backend/test_documents_authorization_http.py `
  tests/backend/test_documents_artifacts_http.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base `
  --junitxml "$Results/junit.xml" 2>&1 |
  Tee-Object -FilePath "$Results/pytest.log"

$pytestExit = $LASTEXITCODE
if ($pytestExit -ne 0) {
    throw "CP08-R8 focus tests failed with exit $pytestExit"
}
```

Result: **42 passed** (`build/j04-m0-closure/cp08-r8-results-20260818T055709926Z/junit.xml`,
`tests="42" failures="0"`). Pytest log:
`build/j04-m0-closure/cp08-r8-results-20260818T055709926Z/pytest.log`. Ambient J04/Word
opt-ins unset. `git diff --check` on the four R8 files: exit 0.

CP08-R8 commit: `31dc273` — `test(j04-m0): use authenticated user ids in acceptance workflow`

Docs SHA record: `83b7b1a` — `docs(j04-m0): record CP08-R8 SHA`

## FR14 — R1–R8 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), R5 (`34f39c0` / docs `164a7c9`), R6 (`e28a44d` / docs `1f72451`), R7 (`f5dcfa8` /
docs `ae5be41`), R8 (`31dc273` / docs `83b7b1a`), WR05 documentation (`034425f`), and the
freeze documentation. Focused gates are **144 passed**
(`build/j04-m0-closure/freeze-r8-results-20260818T061803564Z/junit.xml`, `tests="144"
failures="0"`): FR13 set plus R8 `user_id` / race / receipt regressions. Pytest log:
`build/j04-m0-closure/freeze-r8-results-20260818T061803564Z/pytest.log`. The frozen
candidate is `ed488ede47063c22ec0b8b9d2a72be25224f6098` (`ed488ed`). No product or test
changes are allowed after this freeze. CP08-V8 was executed once and **FAILED** at
`training_read_receipt`. Artifacts **PASS**. Word COM was **not reached**. Overall
**`NOT_READY`**: there is not yet a successful CP08 run. `ACCEPTED` is not set.

Worktree at freeze: only the two confirmed stat-only files
(`interfaces/pyqt/widgets/signature_placement/label_geometry.py`,
`modules/training/wiring.py`).

## CP08-V8 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `ed488ede47063c22ec0b8b9d2a72be25224f6098`.
Lauf-SHA: `0cb4179`. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set.
No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v8-pg-live-runner.log` |
| Full real-process E2E | **FAILED** in `training_read_receipt` before any out-of-scope read/receipt calls — harness `review/accept` was sent with the editor token and got **403**. The later `version payload missing etag` was secondary diagnostics. R8 artifacts **PASS** (`artifacts listed count=1`). Race **PASS**. Word **not reached**. Workspace `20260818T062441411509Z-3b4e870e746e4d50a646dce4e8d935a1` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

CP08-V8 failed **before** any out-of-scope read / receipt calls. After successful
`editing-complete`, the scenario step kept one client pinned to the editor token. Although the
step passed reviewer and approver headers, `request_raw()` overwrote `Authorization` from
`self._token`, so `review/accept` was sent as the editor and correctly rejected with **403**.
The later `version payload missing etag` was only secondary harness diagnostics. R8,
artifact transport, signature, and product authorization held.

## CP08-R9 — Document-release actor remediation + scope cut (test-only)

The realprocess scenario now uses separate authenticated clients for editor, reviewer, and
approver in `document_release_flow`. `editing-complete`, `review/accept`, and
`approval/accept` each fail closed through `require_version_success()` before reading an
ETag, so future 403s surface with action, status, and redacted error code instead of
`missing etag`. J04-M0 now proves release-state completion through public Documents-APIs only;
training consumers and read-receipt integration remain a separate follow-up package.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r9-$stamp"
$Results = "build/j04-m0-closure/cp08-r9-results-$stamp"
New-Item -ItemType Directory -Force -Path $Results | Out-Null
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/backend/test_documents_authorization_http.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base `
  --junitxml "$Results/junit.xml" 2>&1 |
  Tee-Object -FilePath "$Results/pytest.log"
```

Result: **41 passed** (`build/j04-m0-closure/cp08-r9-scope-results-20260818T082720948Z/junit.xml`,
`tests="41" failures="0"`). Pytest log:
`build/j04-m0-closure/cp08-r9-scope-results-20260818T082720948Z/pytest.log`. `git diff --check`
on the seven R9 files: exit 0.

**No freeze. No CP08-V9. No commit** until explicit approval. R9 is now scope-corrected and
technically ready for the controlled commit sequence. Overall **`NOT_READY`**.
Word still **not reached**. `ACCEPTED` is not set.

## CP08-R2 remediation specification (real-process scenario)

Test-only scope. Replaces the `pytest.skip` stub with an ordered scenario in
`tests/acceptance/j04_m0_acceptance_scenario.py`. **No freeze.** PG live, full
`j04_final_acceptance` execution, Word COM live, and Onedir remain **NOT RUN** in R2.

### PG test environment and admin bootstrap

| Item | Contract |
| --- | --- |
| Guard | `preflight_isolated_postgres_target()` before any destructive work |
| Admin DSN | `QMTOOL_PG_TEST_ADMIN_DSN` from gitignored `.env`; never logged |
| Reset | `QMTOOL_PG_TEST_RESET` injected only for the pytest child / backend env |
| Provision | `prepare_live_environment()` + `migrate_usermanagement_schema(migrator_dsn)` |
| Runtime DSN | Backend receives `QMTOOL_PG_DSN = runtime_dsn` only (never admin DSN) |
| Bootstrap admin | `QMTOOL_BOOTSTRAP_ADMIN_USERNAME/PASSWORD` on first backend start; first `/auth/me` is 409 `password_change_required` until `POST /auth/change-password` (CP08-R5 handshake) |
| Directory users | Created via `POST /users` after bootstrap session is usable (`/auth/me` 200); user `qmb` has `is_qmb=True` |
| Document create | `POST /documents/versions/create` uses the seeded QMB token (CP08-R6); Admin is not treated as QMB |

### Two separate client processes and sessions

| Item | Contract |
| --- | --- |
| Homes | `client1-home` / `client2-home` under harness workspace |
| Processes | `j04_m0_client_worker.py` subprocesses only |
| Sessions | In-memory Bearer per worker; output uses `token_fingerprint` only |
| Proof | Distinct `QMTOOL_HOME` paths and token fingerprints in step `client_process_sessions` |

### ETag concurrency synchronization

| Item | Contract |
| --- | --- |
| Pattern | Two workers issue the same `If-Match` assign-roles mutation in parallel |
| Bodies | Both send `user_id` values from `GET /auth/me` (CP08-R8); not login usernames; no `observer` |
| Expected | Exactly one HTTP **200** and one HTTP **409**; harness `sorted([status_a, status_b])` |
| Transport | Worker `--action http` (no shared in-process `TestClient`) |

### M0 HTTP coverage (orchestrator + workers)

| Area | Step | Reference alignment |
| --- | --- | --- |
| Health/OpenAPI | `health_and_openapi` | Dev `/health`, `/openapi.json` |
| Artifacts | `artifacts_transport` | No `storage_key` in list/metadata |
| Signature | `signature_verify_password` | Import PNG + `/signature/verify-password` |
| Document release | `document_release_flow` | Approve to `APPROVED`; no training/read-receipt calls in J04-M0 gate |
| Comments / CR / lifecycle | `comments_lifecycle_change_requests` | Comment, change request, archive |
| Document baseline | `document_baseline_flow` | Create → import PDF → assign → start |

### Backend restart and persistence/session contract

| Item | Contract |
| --- | --- |
| Restart | `harness.stop_process("backend")` then start new backend on same `backend-home` |
| Documents | SQLite under backend home survives restart (`ARCHIVED` readback) |
| Sessions | Pre-restart Bearer tokens remain valid via `GET /auth/me` (PG-backed sessions) |
| Step | `persistence_and_session_contract` |

### Fail-closed preconditions, redaction, PID cleanup

| Item | Contract |
| --- | --- |
| Opt-in | `QMTOOL_J04_FINAL_ACCEPTANCE=I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN` |
| Port | `127.0.0.1:8000` must be free before backend start |
| PIDs | Harness tracks and terminates **only** self-spawned processes |
| Logs | `redact_log_text()` on all harness/scenario logs under `build/j04-m0-closure/` |
| Abort | First failing required step stops the scenario (`FAIL` result) |

### Word COM live boundary (explicitly not R2 execution)

| Item | Contract |
| --- | --- |
| Env | `QMTOOL_J04_WORD_COM_LIVE=I_UNDERSTAND_THIS_IS_A_REAL_WORD_COM_RUN` |
| R2 | Step `word_com_live_boundary` returns **SKIP** with documented reason |
| CP08 | Requires interactive Windows session; real `import-docx` only when opt-in set |
| Product | Uses existing `DispatchEx` isolation from CP03; no new COM entrypoint |

### CP08-R2 verification (implementation only)

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp08-r2
$Py -m pytest tests/acceptance/test_j04_m0_realprocess.py -m "j04_final_acceptance" -q
```

Result: **15 passed** + final gate **1 skipped** without opt-in (2026-08-17)

Changed files (test-only):

- `tests/acceptance/j04_m0_acceptance_scenario.py` — ordered scenario orchestrator
- `tests/acceptance/j04_m0_client_worker.py` — `--action http` for worker mutations
- `tests/acceptance/j04_m0_realprocess_harness.py` — `stop_process()` for restart step
- `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — focused scenario unit tests
- `tests/acceptance/test_j04_m0_realprocess.py` — calls `run_acceptance_scenario()`

## MR-FIX-R1 — Review-Fix Verification Checkpoint

- **Status:** PASS
- **Startzeit:** 2026-08-20T09:55:00+02:00
- **Endzeit:** 2026-08-20T10:11:45+02:00
- **Start-SHA / Branch:** `9cee1ddf78c39f88dcf582fab79cea10146953ed` auf `feature/ap-j04-m0`
- **Remote-Head:** `origin/feature/ap-j04-m0` = `9cee1ddf78c39f88dcf582fab79cea10146953ed`
- **Ziel und Scope:** ausschließlich Verifikation der PR-24-Review-Fixes; kein Commit, kein Push,
  keine PR-/Conversation-Aktion, keine Produktentscheidung außerhalb des bestätigten Vertragsumfangs.
- **Preflight:**
  - Worktree/Staging erfasst; Review-Fix-Dateien vollständig gelistet
  - Fremdänderungen `interfaces/pyqt/widgets/signature_placement/label_geometry.py`,
    `modules/training/wiring.py` und `docs/transition/` unverändert belassen
  - kein paralleler Pytest-Prozess
- **Change-Manifest dieses Checkpoints:**
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
- **Alle Testversuche:**
  1. Gate A — `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py::test_acceptance_document_create_with_qmb_token_returns_etag`
     mit `--basetemp build/mr-fix-r1/gate-a-basetemp` — **1 passed**
     (`build/mr-fix-r1/gate-a-junit.xml`)
  2. Gate B — `tests/docs/test_docs_consistency.py -v`
     mit `--basetemp build/mr-fix-r1/gate-b-basetemp` — **8 passed**
     (`build/mr-fix-r1/gate-b-junit.xml`)
  3. Gate C — fokussierte Review-Fix-Suite in einem frischen seriellen Prozess
     mit `--basetemp build/mr-fix-r1/gate-c-basetemp` — **94 passed, 1 warning**
     (`build/mr-fix-r1/gate-c-junit.xml`)
  4. Gate D — `pytest -m "not postgres and not j04_final_acceptance"`
     mit `--basetemp build/mr-fix-r1/gate-d-basetemp` — **1048 passed, 20 skipped, 7 warnings**
     (`build/mr-fix-r1/gate-d-junit.xml`)
- **WinError-10053-Klassifikation:** im früher roten Gesamtlauf historisch vorhanden; Gate A reproduzierte
  den Fehler im Einzelprozess **nicht**. Kein neuer Socket-/Cleanup- oder `WinError 5`-Umgebungseffekt in MR-FIX-R1.
- **Vertragliche Klarstellung:**
  - neue öffentliche `document_id`-Werte sind URL-sicher
  - Legacy-Slash-IDs bleiben unverändert und außerhalb des aktuellen HTTP-Routenvertrags
  - vollständige HTTP-Erreichbarkeit von Legacy-Slash-IDs erfordert separaten Option-B-Auftrag
- **Abschlussbewertung:** MR-FIX-R1 PASS. Review-Fix-Stand technisch verifiziert; Git-Schreibaktionen
  und erneute Reviewer-Bestätigung bleiben separate Folgeschritte.

### Formal Acceptance — J04-M0

- **Status:** PASS (`Accepted`)
- **Erteilt:** 2026-08-20 — ausdrückliche menschliche Freigabe
- **J04-M0-Produkt-Merge:** `e003b37ecb3ff6a2f878cc0cf6d1b89e8df9ad38` (`e003b37`, PR #24)
- **Aktuelle Main-Basis:** `f7b867d895566ea8fd0b80a07a6eec3be4cf868a` (`f7b867d`, PR #25 Skill only)
- **Zwischen den SHAs:** ausschließlich Skill-Merge; keine weitere J04-M0-Produktänderung
- **Historische Evidence:** frühere `Accepted unset`-Stellen in MR09/MR10-Zwischenständen unverändert
- **Nicht Bestandteil:** Word-COM-E2E, Produktionslizenz/Deployment, Branch-Cleanup, automatischer Merge dieses Docs-PRs

