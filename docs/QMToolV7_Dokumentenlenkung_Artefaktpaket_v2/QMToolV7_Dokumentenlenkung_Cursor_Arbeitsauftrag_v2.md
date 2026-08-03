# Arbeitsauftrag für Cursor – Documents-Modul kontrolliert umbauen

## Auftrag

Baue das bestehende Dokumentenlenkungsmodul in `QMToolV7` schrittweise auf das fachliche Sollmodell um. **Kein Greenfield-Neubau, kein zweites Parallelmodul, keine GUI-Neuentwicklung im ersten Schritt.**

Verbindliche Grundlagen:

1. `QMToolV7_Dokumentenlenkung_Sollmodell_v2.md`
2. `QMToolV7_Dokumentenlenkung_Ist_Soll_Umbauplan_v2.md`
3. `QMToolV7_Fachlogik_Dokumentenlenkung_Ausgefüllt_v2.xlsx`
4. `QMToolV7_Dokumentenlenkung_Eventkatalog.md`
5. `QMToolV7_Dokumentenlenkung_Use_Case_Kandidaten.md`
6. `QMToolV7_Dokumentenlenkung_Edge_Cases.md`
7. bestehende P0-Dokumente im Repository, insbesondere `AGENTS.md`, `docs/DOCS_CANONICAL_INDEX.md` und Architekturregeln
8. JSON-Persistenz-Baseline (Reihenfolge): `JSON_STORAGE_INVENTORY.md`, `JSON_STORAGE_OPEN_QUESTIONS.md`, `JSON_VS_DATABASE_ADR.md`, `TARGET_PERSISTENCE_MODEL.md`, `JSON_TO_DATABASE_MIGRATION_PLAN.md`

## Arbeitsweise

1. Zuerst Repository und P0-Dokumente lesen.
2. Danach eine kompakte Gap-Analyse `Ist → Soll` erstellen, mit betroffenen Dateien, Tabellen und Tests.
3. Keine fachlichen Annahmen ergänzen. Unklarheiten als konkrete Rückfrage markieren.
4. Paketweise arbeiten; Fachlogik und Tests vor GUI.
5. Nach jedem Paket Tests ausführen und Ergebnis dokumentieren.
6. Bestehende öffentliche Grenzen (`api.py`, Contracts, Ports) respektieren.
7. Keine Cross-Module-Interna importieren.
8. Vorhandene Artefakt-, Signatur-, Event-, Registry- und Auditlogik wiederverwenden.

## Feste fachliche Entscheidungen

- `DocumentPlan` separat; `PLANNED` verschwindet aus dem Dokumentstatus.
- `IN_PROGRESS` wird fachlich `DRAFT`.
- feste Status: `DRAFT`, `IN_REVIEW`, `IN_APPROVAL`, `APPROVED`, `PUBLISHED`, `EXPIRED`, `ARCHIVED`, `ANNULLED`.
- Workflow endet bei `APPROVED`; Veröffentlichung ist separater Use-Case.
- nur gültige `PUBLISHED`-Versionen dürfen andere Module abrufen.
- maximal eine gültige veröffentlichte Version, eine offene Nachfolgeversion und eine aktive Workflowinstanz.
- Ablehnung führt immer zu `DRAFT`.
- Workflowprofile sind zentral, benannt und versioniert; sie konfigurieren Übergänge, keine frei erfundenen Stufen.
- Modulrollen bestimmen Eignung/Befugnisse; konkrete Workflowzuweisung aktiviert Workflowaktionen.
- Vier-Augen: keine zwei unmittelbar aufeinanderfolgenden Stufen durch dieselbe Person.
- `ADMIN` besitzt keine automatische fachliche Macht; QMB ist fachlicher Leiter.
- alle fachlich relevanten Änderungen und Entscheidungen werden auditiert.
- jeder erfolgreiche Workflow- und Statusübergang publiziert ein spezifisches v2-Domain-Event mit vollständigem Routingpayload.
- fehlende Event-Consumer dürfen eine Fachaktion nicht verhindern; das bestehende zustandsbasierte Dashboard bleibt zunächst erhalten.
- Word-Kommentar-Synchronisierung, PDF-Kommentare, Kommentarlisten/-details und Statusänderungen sind Bestandsfunktionen und dürfen nicht entfernt oder reduziert werden.
- der exzessive Use-Case-Kandidatenkatalog ist kein automatischer Umsetzungsscope.
- kein Löschen historischer Fachdaten im ersten Umbau.

## Reihenfolge der Umsetzung

Arbeite ausschließlich in dieser Reihenfolge, sofern die Gap-Analyse keinen zwingenden technischen Blocker zeigt:

1. Sicherheitsnetz, Tests und Migrationsreport
2. neue Status + kompatibles Read-Model
3. `DocumentPlan`
4. Trennung `Document` / `DocumentVersion`
5. Workflowinstanz, Einreichungsrunde und Entscheidungen
6. versionierte Übergangsprofile
7. Modulrollen und Autorisierung
8. Veröffentlichung, Ablauf und Verlängerung
9. vollständige v2-Eventverträge und Legacy-Mapping
10. Artefakt-/Kommentar-/Auditverknüpfung
11. gelenkte Ausdrucke
12. Consumer-/Projektionsmigration
13. Legacybereinigung

## Stop-Regeln

Vor dem Ändern anhalten und Rückfrage stellen, wenn:

- eine Migration bestehende Daten löschen oder still uminterpretieren würde,
- die vorhandene DB-Struktur nicht sicher migrierbar erscheint,
- ein bestehender öffentlicher Contract gebrochen werden müsste,
- die Signatur- oder Artefaktkette fachlich verändert würde,
- zwei Sollregeln widersprüchlich erscheinen,
- für einen Schritt GUI-Entscheidungen nötig wären.

## Erwartetes Ergebnis des ersten Cursor-Durchlaufs

Noch keinen Komplettumbau durchführen. Zuerst liefern:

1. Datei-/Klassen-/Tabellen-Gap-Analyse
2. Migrationsreihenfolge mit Abhängigkeiten
3. Liste der zu erhaltenden Funktionen
4. Liste notwendiger neuer Entitäten und Ports
5. Testplan je Paket
6. vollständige Ist-Event-Matrix einschließlich aller Workflow-/Statusübergänge und Legacy-Mapping
7. Bestandsnachweis der Word-/PDF-Kommentarfunktionen und notwendige Runden-/Artefaktergänzungen
8. Zuordnung der für Paket 1 relevanten Edge Cases
9. Vorschlag für **Paket 1** mit konkreten Dateien und kleinen, reviewbaren Commits

Erst nach Freigabe mit Paket 1 beginnen.
