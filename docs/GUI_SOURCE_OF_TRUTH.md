# GUI Source Of Truth

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

Die einzige aktive GUI-Quelle für QMToolV7 ist:

- `interfaces/pyqt/*`

## Verbindliche Regel

- Neue GUI-Features, Refactorings und UX-Arbeit erfolgen ausschließlich im PyQt-Baum.
- `interfaces/gui/*` (Tk MVP) bleibt nur für Legacy-/Kompatibilitätstests bestehen.
- Es darf keine fachliche GUI-Weiterentwicklung in parallelen GUI-Bäumen geben.

## Konsequenz für Entwicklung

- Navigation, Contributions und Widgets werden nur in `interfaces/pyqt` gepflegt.
- Build und Test fokussieren auf den PyQt-Entry (`python -m interfaces.pyqt`) sowie `dist/QmToolPyQt.exe`.
