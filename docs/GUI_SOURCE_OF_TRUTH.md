# GUI Source Of Truth

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
Canonical product UX: `docs/WEBCLIENT_UX_SPECIFICATION.md`
Contract gaps: `docs/WEBCLIENT_UX_CONTRACT_GAP_MATRIX.md` (P1)

Die einzige **neue** UI-Source-of-Truth für QMToolV7 ist:

- `webclient/*`

Stand WEB00 (Foundation): `webclient/` enthält die Vue/TS/Vite-**Foundation** (Shell,
Auth-/Connection-State, schmaler `/api/v1`-Fetch-Adapter). Volle Produkt-UI und DMS-Workflow
(WEB01) sind **noch nicht** implementiert. Es darf keine nicht vorhandene Webfunktion als
bereits geliefert dargestellt werden.

## Verbindliche Regel

- Neue Endbenutzer-UI, UX und Frontend-Arbeit erfolgen ausschließlich unter `webclient/*`
  (Vue 3 + TypeScript, Vite; Vuetify hinter einer QM-eigenen Komponentenschicht; zentrale SPA).
- Fachmodule liefern **keine** eigenen Frontend-Bundles.
- `interfaces/pyqt/*` und `interfaces/gui/*` (Tk) sind **frozen Legacy/Reference**:
  keine weitere Produktentwicklung, kein zukünftiger Pilotbetrieb, keine neuen PyQt-Contributions.
- Es darf keinen parallelen fachlichen Workflow in PyQt und Web geben.

## Konsequenz für Entwicklung

- WEB00 liefert die zentrale SPA-Shell und den sicheren Browser-Transport; produktive
  Endbenutzerfunktionen jenseits Login/Shell folgen in WEB01+.
- WEB01 und spätere Webclient-Arbeit müssen `docs/WEBCLIENT_UX_SPECIFICATION.md` umsetzen.
  Fehlende Pflichtverträge werden vor WEB01 in WCON00 geschlossen; die UI darf keine
  Ersatzverträge oder abweichende Produkt-UX erfinden.
- Historische PyQt-Implementierung und -Tests bleiben als Referenz/Regression erhalten,
  sind aber keine Onboarding-Anweisung für neue Produkt-UI.
- Neue Features: Service/`modules/*/api.py`/HTTP-Vertrag und Tests zuerst; Webclient-Adapter
  erst nach WEB00 und nur über `/api/v1`.
- Build-/Smoke-Befehle für PyQt beschreiben den **Legacy-Ist-Pfad**, nicht die Zielarchitektur.
