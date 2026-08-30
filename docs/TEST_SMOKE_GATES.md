# Test And Smoke Gates

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`

Verpflichtende Vorher/Nachher-Gates für Governance-, Architektur-, Persistenz- und UI-Pakete.

## First-red Semantik

- Beim ersten roten oder blockierten **Pflichtgate** keine späteren Pflichtgates starten.
- Parent-Checkpoint bleibt `FAILED` oder `BLOCKED` (kein PASS durch spätere Grüns).
- Nur nie gestartete Schritte als `NOT RUN` melden.
- Bereits ausgeführte Gates mit ihrem echten Ergebnis berichten.
- Keine Retries zur Verdeckung, keine abgeschwächten Assertions, keine verlängerten Timeouts
  als Ersatz für einen Fix.
- In einem ausdrücklich freigegebenen AP-029-Makro sind höchstens zwei klar abgegrenzte
  Remediation-Runden je Checkpoint zulässig. Danach beginnt jeweils eine neue vollständige
  Gatesequenz; ein weiterer normaler FAIL führt genau einmal in den Escalation Review.

Technische Gates ersetzen keine menschliche Pilotfreigabe.

## Gate-Gruppen (AP-029)

| Gruppe | Zweck | Beispiele |
| --- | --- | --- |
| Governance / Docs | Kanonische Verträge und Ledger | `tests/docs/test_docs_consistency.py` |
| Product UX governance | UX00 P0/P1 links, D01–D92 disposition, contract-gap ownership | focused UX00 docs tests + full `tests/docs` |
| Macro tooling / reviewer | TOOL00 Agent-/Skill-Vertrag, Snapshot und read-only Review | `tests/docs/test_cursor_macro_workflow.py` + nativer Reviewer-Smoke |
| PostgreSQL foundation | PG00 Runner/Ownership/Org/Audit/Blob contracts | platform/migration gates (defined in PG00) |
| Web foundation | WEB00 SPA shell, `/api/v1`, Cookie/CSRF | web/HTTP contract gates (see WEB00 section below) |
| Web contract completion | WCON00 closes only UX00-classified WEB01 blockers | module/API/OpenAPI contract and negative boundary gates |
| DMS web slice | WEB01 Documents/Signature workflow | focused + broader web/API gates |
| Operations | OPS00 service/HTTPS/backup/restore/export | restore drill, packaging/deployment when authorized |
| Pilot | PILOT00/PILOT01 readiness + human smoke | security/restore/human approval — separate from automated green |
| Legacy PyQt regression | Historical desktop regression only | `tests/interfaces` PyQt suites — **not** a future product human-smoke gate |

Treat real-process, restore, packaging/deployment, and human-pilot evidence as **distinct**
evidence levels. Do not promote TestClient green to real-process or human acceptance.

## Paket-Gate (allgemein)

1. Vor Änderung: relevante Tests ausführen und Ergebnis notieren.
2. Nach Änderung: dieselben Tests erneut ausführen.
3. Abweichung: Failures klassifizieren (neu vs. bereits vorhanden).
4. Smoke: für **neue** Endbenutzer-UI erst nach WEB00 die Web-Foundation-/Role-Smokes;
   PyQt-Human-Smoke ist kein zukünftiges Produktgate.

## Empfohlene Testmatrix

### Docs / Governance Paket
- `.\.venv\Scripts\python.exe -m pytest tests/docs -q`
- Konsistenzcheck gegen Entry-Points und AP-029-Ledger.

### Webclient product UX governance (UX00)

- Focused: canonical P0/P1 links, D01–D92 disposition and every required contract-gap owner in
  `tests/docs/test_docs_consistency.py`.
- Broader: `.\.venv\Scripts\python.exe -m pytest tests/docs -q`.
- Additionally prove that no tracked path outside the UX00 allowlist changed.
- PostgreSQL, backend, browser and PyQt runtime suites are `N/A` for the Docs-only diff, not PASS.

### PostgreSQL / persistence package
- Gates laut `docs/DATABASE_EVOLUTION_POLICY.md` und PG00/OPS00 Evidence-Verträgen.
- Ist SQLite migration gate bleibt für Legacy-Stores relevant bis Cutover:
  `.\.venv\Scripts\python.exe scripts/database_migration_gate.py --output build/database-migration-gate-output.json`

### Web foundation (WEB00 — `webclient/` + `/api/v1` Cookie/CSRF)

Prerequisites: Node.js **20.11.x** (see `webclient/.nvmrc`); backend test container or live backend for integration smoke.

```powershell
# Backend HTTP contract (Cookie/CSRF, Bearer token CLI path, OpenAPI)
.\.venv\Scripts\python.exe -m pytest tests\backend\test_auth_api.py tests\backend\test_openapi_contract.py -q

# OpenAPI snapshot reproducibility
.\.venv\Scripts\python.exe scripts\export_openapi.py
.\.venv\Scripts\python.exe -m pytest tests\backend\test_openapi_contract.py::test_openapi_snapshot_is_reproducible -q

# Retargeted in-repo HTTP consumers
.\.venv\Scripts\python.exe -m pytest tests\interfaces\test_backend_session_client.py -q

# Webclient Vitest (shell + Web Storage negativetest)
cd webclient
npm ci
npm test

# Real-browser HTTPS smoke (Playwright Chromium + ephemeral self-signed TLS gateway)
# Serves SPA same-origin with /api/v1; not OPS00 production HTTPS.
npx playwright install chromium
npm run smoke:browser
cd ..
```

Controlled HTTPS browser-smoke evidence is recorded under `build/ap-029-web00/` (ephemeral local TLS; not OPS00 production).

### Webclient contract completion (WCON00 — after UX00 and OPS00 PASS)

WCON00 must name exact tests for each approved contract change. Its minimum gate includes the
affected public module tests, backend HTTP/OpenAPI contract tests, negative authorization/error
paths, reproducible OpenAPI/client generation and architecture/docs gates. WCON00 may not add
WEB01 screens or absorb deferred notifications, jobs, global search, locks or print.

Current contract suites that normally form part of the focused selection include:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\backend\test_documents_http_api.py `
  tests\backend\test_documents_concurrency_http.py `
  tests\backend\test_documents_artifacts_http.py `
  tests\backend\test_signature_http_api.py `
  tests\backend\test_openapi_contract.py -q
```

### DMS web slice (WEB01 — after WCON00 and INT00 PASS)

```powershell
# Existing backend contracts used by the slice
.\.venv\Scripts\python.exe -m pytest `
  tests\backend\test_auth_api.py `
  tests\backend\test_documents_http_api.py `
  tests\backend\test_documents_authorization_http.py `
  tests\backend\test_documents_concurrency_http.py `
  tests\backend\test_documents_artifacts_http.py `
  tests\backend\test_signature_http_api.py `
  tests\backend\test_openapi_contract.py -q

# WEB01 components and production build
cd webclient
npm ci
npm test
npm run build

# Controlled real-browser path; exact WEB01 E2E targets are owned by WEB01
npm run test:e2e
cd ..
```

WEB01 evidence must cover two actor sessions, server-provided actions, ETag conflict, comments,
PDF preview versus controlled download, signature reauthentication, audit/history and restart.
Legacy `tests/interfaces`/PyQt suites may remain regression signals but are not WEB01 onboarding,
product acceptance or browser evidence.

### Track B SRP prep/splits / module-platform
- `.\.venv\Scripts\python.exe -m pytest tests/modules -q`
- `.\.venv\Scripts\python.exe -m pytest tests/platform -q`

### Database schema or persistence package (Ist SQLite + future PG)

- `.\.venv\Scripts\python.exe scripts/database_migration_gate.py --output build/database-migration-gate-output.json`
- `.\.venv\Scripts\python.exe -m pytest tests/platform/test_database_evolution.py tests/platform/test_core_database_migrations.py tests/e2e_cli/test_database_commands.py -q`
- `.\.venv\Scripts\python.exe scripts/golive_gate.py --output build/golive-gate-output.json`
- A migration above V1 requires the immediately preceding version fixture and
  explicit data-retention coverage.

## Nachweisformat

Für jedes Paket im PR-/Änderungsprotokoll:
- Paketname / Checkpoint-ID
- Vorher-Resultat
- Nachher-Resultat
- Erster roter Schritt (oder keiner)
- NOT RUN Schritte
- Offene Altfehler (falls vorhanden)
- Evidence-Pfade (JUnit/JSON)
- Human/Pilot-Status getrennt von technischen Gates

## Aktueller Stand (historischer Snapshot, 2026-04)

Die folgenden Zahlen stammen aus einem früheren Gate-Run und dienen nur als Referenz.
Für aktuelle Verifikation immer die Befehle in `.cursor/rules/00-agent-workflow.mdc` und CI ausführen.

- `.\.venv\Scripts\python.exe -m pytest tests/modules -q` -> 60 passed (1 known pypdf deprecation warning)
- `.\.venv\Scripts\python.exe -m pytest tests/platform -q` -> 25 passed
- `.\.venv\Scripts\python.exe -m pytest tests/interfaces -q` -> 8 passed
- Win32-DB-Lock-Flakes in den betroffenen Modultests wurden durch explizites Connection-Closing behoben.

## One-Run Abschluss (historische GUI-Notiz)

- Historische PyQt-UX-Notizen und Packaging-Sanity bleiben als Legacy-Referenz erhalten.
- Packaging-Sanity (Ist): `.\.venv\Scripts\python.exe packaging/build_onedir.py`;
  `packaging/verify_bundle_imports.py` bestätigt `fitz`/PyMuPDF im Bundle.

## Role-Smoke (Legacy PyQt, historical)

- Ausgeführt (historisch): `.\.venv\Scripts\python.exe -m pytest tests/interfaces/test_pyqt_navigation_smoke.py -q`
- Ergebnis (historisch): `3 passed`
- Dies ist **kein** zukünftiges Produkt-Human-Smoke-Gate für Web/Pilot.
