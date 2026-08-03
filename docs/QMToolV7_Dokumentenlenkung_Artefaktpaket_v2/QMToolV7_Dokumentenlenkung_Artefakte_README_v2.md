# Artefaktpaket Dokumentenlenkung – Nachschärfung v2

**Stand:** 2026-08-03

## Empfohlene Reihenfolge für Cursor

1. `QMToolV7_Dokumentenlenkung_Cursor_Arbeitsauftrag_v2.md`
2. `QMToolV7_Dokumentenlenkung_Sollmodell_v2.md`
3. `QMToolV7_Dokumentenlenkung_Ist_Soll_Umbauplan_v2.md`
4. `QMToolV7_Dokumentenlenkung_Eventkatalog.md`
5. `QMToolV7_Dokumentenlenkung_Entscheidungsmodell_v2.yaml`
6. `QMToolV7_Fachlogik_Dokumentenlenkung_Ausgefüllt_v2.xlsx`
7. `QMToolV7_Dokumentenlenkung_Use_Case_Kandidaten.md`
8. `QMToolV7_Dokumentenlenkung_Edge_Cases.md`
9. `JSON_STORAGE_INVENTORY.md`
10. `JSON_STORAGE_OPEN_QUESTIONS.md`
11. `JSON_VS_DATABASE_ADR.md`
12. `TARGET_PERSISTENCE_MODEL.md`
13. `JSON_TO_DATABASE_MIGRATION_PLAN.md`

## J00-Abnahmeprotokoll

- Inventur-Suche und Diff dokumentiert in `JSON_STORAGE_INVENTORY.md` (Abschnitt J00-Verifikation) inkl. kopierbarer `rg`-Befehle.
- OQ-01 bis OQ-09 als vollstaendige, korrekt abgegrenzte offene Punkte bestaetigt; in J00 nicht entschieden. Offene Inventarziele: J29/J31 → OQ-02, J39 → OQ-07.
- Manifest nach Dokumentaenderungen vollstaendig neu erzeugt; Paket-Test absichert Hashes, Referenzen und Pflichtverweise auf alle fünf JSON-Baseline-Dateien.
- Runtime unveraendert; kein Start von J01+.
- **Supervisor-Freigabe: erteilt am 2026-08-03 nach Staging-, Manifest- und Gate-Pruefung**

### Baseline-Hinweis: Trailing-Whitespace-Bereinigung

Fuenf gelieferte Ursprungs-Markdown-Dateien wurden in J00 **nur** am Zeilenende von Leerzeichen bereinigt (`rstrip` von Space/Tab), damit `git diff --cached --check` gruen ist. **Keine inhaltliche Aenderung.** Alte Hashes entsprechen dem gelieferten Artefaktpaket vor der Bereinigung; neue Hashes stehen im regenerierten Manifest.

| Datei | SHA-256 vor Bereinigung | SHA-256 nach Bereinigung |
|---|---|---|
| `QMToolV7_Dokumentenlenkung_Edge_Cases.md` | `6b84e11a0f243b866b0fca25c173320c34bde3b5ce55dfb3bf331bd4fe0ebb40` | `839e804a3f9b1c146f4194178dd4f101c6a018923aed3bae388adcc3114e03ac` |
| `QMToolV7_Dokumentenlenkung_Eventkatalog.md` | `3bdeb931668ba64a9ba8dd6e6d4241247295e4b0143f1960cc28244638612917` | `9be3fceb5936c7169b2be860cbd70998fb25509bb1e14e152933a58eeac08782` |
| `QMToolV7_Dokumentenlenkung_Ist_Soll_Umbauplan_v2.md` | `4042734aebe722009e6b2f2b56e15e120bc30f93b3bd97187ed00c2496d6033f` | `32a7387c6eaefa6bf58dbc2d9386b9605e6a3b0c55f5e80cb8a919267d976782` |
| `QMToolV7_Dokumentenlenkung_Sollmodell_v2.md` | `dd9ebbfb5dbb4e78e5b541411c6cd6b748dd77423e7bfa2e10314a6ef286a579` | `a2a23b1f9a0e2169b3a9650ae021362a24c558e24769c84627b8d249e8ddb863` |
| `QMToolV7_Dokumentenlenkung_Use_Case_Kandidaten.md` | `5b111ab284f72241f079a02242aa7f1fce1da596e389694be84e962216ca1b77` | `eacff2689ae1368fd24de45cabd98a171d4d85ab6c038763b3614f9b02f4188c` |

## Umfang

- 50 verbindliche Kern-Use-Cases
- 211 zusätzliche Use-Case-Kandidaten zur fachlichen Auswahl
- 96 Edge Cases
- 61 ausführliche v2-Domain-Events plus 6 API-Fähigkeiten
- eigener Kommentarbestand für Word- und PDF-Kommentare

## Leitplanken

- kein Greenfield-Neubau
- Kandidatenliste ist kein automatischer Umsetzungsscope
- jeder Workflow-/Statusübergang erhält ein Event
- fehlende Consumer blockieren keine Fachaktion
- aktueller EventBus ist nicht dauerhaft; Dashboard bleibt zunächst zustandsbasiert
- bestehende Word-/PDF-Kommentare dürfen nicht entfernt oder reduziert werden
