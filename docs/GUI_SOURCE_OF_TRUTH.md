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
Auth-/Connection-State, schmaler `/api/v1`-Fetch-Adapter).

Stand WEB01 (Produkt-UI): Der freigegebene Documents/Signature-DMS-Webslice ist in
`webclient/` implementiert und gegen `docs/WEBCLIENT_UX_SPECIFICATION.md` abgenommen.
Der Review-Closeout ist an `runtime_test_candidate_sha`
`e833fad3d3c547021be23214b1adf04a86707eab` in PR #56 gebunden; die zwei erlaubten
GitHub-Codex-Runden sind verbraucht, eine dritte Runde ist ausgeschlossen. Der PR ist noch
nicht gemergt und PILOT00 bleibt separat freizugeben.
Deferred-Themen aus Spec/Matrix (z. B. Notifications, Global Search, generische Jobs,
zentrale Locks oder produktiver Druck) sind **nicht** als geliefert ausgewiesen. Es darf
keine nicht vorhandene Webfunktion als bereits geliefert dargestellt werden.

## Verbindliche Regel

- Neue Endbenutzer-UI, UX und Frontend-Arbeit erfolgen ausschließlich unter `webclient/*`
  (Vue 3 + TypeScript, Vite; Vuetify hinter einer QM-eigenen Komponentenschicht; zentrale SPA).
- Fachmodule liefern **keine** eigenen Frontend-Bundles.
- `interfaces/pyqt/*` und `interfaces/gui/*` (Tk) sind **frozen Legacy/Reference**:
  keine weitere Produktentwicklung, kein zukünftiger Pilotbetrieb, keine neuen PyQt-Contributions.
- Es darf keinen parallelen fachlichen Workflow in PyQt und Web geben.

## Konsequenz für Entwicklung

- WEB00 liefert die zentrale SPA-Shell und den sicheren Browser-Transport.
- WEB01 liefert den ersten vollständigen produktiven DMS-Webworkflow in `webclient/`; spätere
  Webclient-Arbeit baut darauf auf und muss `docs/WEBCLIENT_UX_SPECIFICATION.md` umsetzen.
  Fehlende Pflichtverträge werden vor WEB01 in WCON00 geschlossen; die UI darf keine
  Ersatzverträge oder abweichende Produkt-UX erfinden.
- Historische PyQt-Implementierung und -Tests bleiben als Referenz/Regression erhalten,
  sind aber keine Onboarding-Anweisung für neue Produkt-UI.
- Neue Features: Service/`modules/*/api.py`/HTTP-Vertrag und Tests zuerst; Webclient-Adapter
  nur über `/api/v1`.
- Build-/Smoke-Befehle für PyQt beschreiben den **Legacy-Ist-Pfad**, nicht die Zielarchitektur.
