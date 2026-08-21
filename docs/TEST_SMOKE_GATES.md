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
- In einem ausdrücklich freigegebenen AP-029-Makro ist höchstens eine klar abgegrenzte
  Remediation-Runde je Checkpoint zulässig. Danach beginnt eine neue vollständige Gatesequenz;
  ein zweites nicht-grünes Ergebnis stoppt das Makro.

Technische Gates ersetzen keine menschliche Pilotfreigabe.

## Gate-Gruppen (AP-029)

| Gruppe | Zweck | Beispiele |
| --- | --- | --- |
| Governance / Docs | Kanonische Verträge und Ledger | `tests/docs/test_docs_consistency.py` |
| Macro tooling / reviewer | TOOL00 Agent-/Skill-Vertrag, Snapshot und read-only Review | `tests/docs/test_cursor_macro_workflow.py` + nativer Reviewer-Smoke |
| PostgreSQL foundation | PG00 Runner/Ownership/Org/Audit/Blob contracts | platform/migration gates (defined in PG00) |
| Web foundation | WEB00 SPA shell, `/api/v1`, Cookie/CSRF | web/HTTP contract gates (defined in WEB00; **not implemented yet**) |
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

### PostgreSQL / persistence package
- Gates laut `docs/DATABASE_EVOLUTION_POLICY.md` und PG00/OPS00 Evidence-Verträgen.
- Ist SQLite migration gate bleibt für Legacy-Stores relevant bis Cutover:
  `.\.venv\Scripts\python.exe scripts/database_migration_gate.py --output build/database-migration-gate-output.json`

### Web foundation / DMS web slice (after WEB00/WEB01 exist)
- Contract and foundation commands will be recorded in the owning checkpoint evidence.
- Do not invent npm/Vite commands here before WEB00 lands them in-repo.

### Legacy PyQt regression (historical only)
- `.\.venv\Scripts\python.exe -m pytest tests/interfaces -q`
- Optional historical navigation smoke:
  `.\.venv\Scripts\python.exe -m pytest tests/interfaces/test_pyqt_navigation_smoke.py -q`
- These protect frozen desktop paths; they are **not** onboarding for new product UI.

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
