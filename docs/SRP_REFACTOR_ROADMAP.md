# SRP Refactor Roadmap

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md` and P0 docs

Dieses Dokument priorisiert Verbesserungen am Single Responsibility Principle (SRP) ohne fachliche Verhaltensänderung.

## Leitlinien

- Kein Business-Behavior-Change durch SRP-Refactor.
- Öffentliche Service-/API-Signaturen nur ändern, wenn explizit in Track B freigegeben.
- GUI bleibt Adapter-Schicht: keine neuen Fachregeln in Callbacks.

## Hotspots (PyQt)

1. `interfaces/pyqt/contributions/documents_workflow_view.py`
2. `interfaces/pyqt/shell/main_window.py`
3. `interfaces/pyqt/contributions/audit_logs_view.py`
4. `interfaces/pyqt/contributions/settings_view.py`
5. `interfaces/pyqt/contributions/users_view.py`
6. `interfaces/pyqt/contributions/signature_view.py`

## Hotspots (Core)

1. `qm_platform/runtime/lifecycle.py`
2. `modules/documents/service.py`
3. `modules/signature/service.py`
4. `modules/usermanagement/service.py`

## Refactor-Schnitte (Zielbild)

### Track A (low risk, GUI-first)

- Audit-Logs splitten in:
  - technical log reader/parsing
  - functional summary builder
  - admin health reporter
- Signatur-Workspace splitten in:
  - sign use-case helper (template vs fixed)
  - view-spezifische Dialog/Feedback-Logik
- Settings-Bereiche schrittweise in presenter/guard/io-helpers trennen.
- Users-Admin in presenter- und view-Verantwortung trennen.

### Track B (höheres Risiko, Backend/Runtime)

- Lifecycle in Policy/Orchestrierung/Port-Invariants zerlegen.
- DocumentsService intern in workflow/artifacts/query Domänensegmente trennen.
- UserManagement Session-Persistenz separieren.
- Composition Roots (`modules/*/module.py`) in Wiring-Bausteine aufteilen.

## Reihenfolge

1. Doku synchronisieren
2. Track-A low-risk Splits
3. Track-B vorbereitende Splits (ohne API-Change)
4. Tiefe Track-B Splits (mit erweitertem Test-Gate)

## Qualitätskriterien

- Vorher/Nachher-Tests pro Arbeitspaket.
- Role-Smoke nach GUI-Splits (Admin/QMB/User).
- Expliziter Check: keine neue Fachlogik im UI-Code.
