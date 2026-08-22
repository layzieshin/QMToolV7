# GUI Source Of Truth

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`

Die einzige **neue** UI-Source-of-Truth für QMToolV7 ist:

- `webclient/*`

Stand GOV00 / vor WEB00: das Verzeichnis und die produktive Web-UI sind **noch nicht
implementiert**. Es darf keine nicht vorhandene Webfunktion als bereits geliefert
dargestellt werden.

## Verbindliche Regel

- Neue Endbenutzer-UI, UX und Frontend-Arbeit erfolgen ausschließlich unter `webclient/*`
  (Vue 3 + TypeScript, Vite; Vuetify hinter einer QM-eigenen Komponentenschicht; zentrale SPA).
- Fachmodule liefern **keine** eigenen Frontend-Bundles.
- `interfaces/pyqt/*` und `interfaces/gui/*` (Tk) sind **frozen Legacy/Reference**:
  keine weitere Produktentwicklung, kein zukünftiger Pilotbetrieb, keine neuen PyQt-Contributions.
- Es darf keinen parallelen fachlichen Workflow in PyQt und Web geben.

## Konsequenz für Entwicklung

- Bis WEB00 existiert kein neuer produktiver Endbenutzerclient.
- Historische PyQt-Implementierung und -Tests bleiben als Referenz/Regression erhalten,
  sind aber keine Onboarding-Anweisung für neue Produkt-UI.
- Neue Features: Service/`modules/*/api.py`/HTTP-Vertrag und Tests zuerst; Webclient-Adapter
  erst nach WEB00 und nur über `/api/v1`.
- Build-/Smoke-Befehle für PyQt beschreiben den **Legacy-Ist-Pfad**, nicht die Zielarchitektur.
