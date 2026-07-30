# Implementierungsworkflow für Kerniterationen

## Vorbedingungen

Eine Implementierung beginnt nur mit:

- freigegebenem Iterationsumfang,
- beschriebenem Arbeitsablauf,
- relevanten Geschäftsregeln,
- Abnahmekriterien,
- geklärten blockierenden Fachfragen.

## Ist-Analyse

Vor Änderungen:

1. Betroffene Dateien und Tests identifizieren.
2. Bestehende Implementierung auf Wiederverwendbarkeit prüfen.
3. Altcode nicht automatisch als Soll-Zustand behandeln.
4. Bereits bestehende Fehler soweit möglich vom Iterationsrisiko trennen.
5. Keine angrenzenden Module vorsorglich refactoren.
6. Für jede neue oder geänderte fachliche Funktion und wesentliche GUI-Entscheidung den Herkunftsnachweis nach `requirements-fidelity.md` prüfen.

## Empfohlene Reihenfolge

1. Contracts für den freigegebenen Use Case,
2. Domain-Objekte, Zustände und Invarianten,
3. Application Use Case,
4. benötigte Ports,
5. Persistenzadapter und Migration,
6. öffentliche Modul-API,
7. Capabilities und Berechtigungen,
8. Events und Runtime-Verkabelung,
9. technischer Aufrufpfad oder Test-Harness,
10. Unit- und Integrationstests.

Die Reihenfolge darf an bestehende Projektmuster angepasst werden, solange keine GUI-zentrierte Geschäftslogik entsteht.

## Anforderungstreue vor der Umsetzung

Aktualisiere `08_anforderungsnachweis.md`. Eine tatsächliche Funktion oder wesentliche GUI-Ausgestaltung darf nur umgesetzt werden, wenn sie als `EXPLIZIT_BESTAETIGT` nachgewiesen ist. Rein technische Notwendigkeiten und bestehende Projektmuster dürfen selbstständig entschieden werden, solange sie Funktion, Datenbedeutung und sichtbaren Arbeitsablauf nicht verändern.

Fehlt die explizite Quelle, frage den Benutzer vor der Codeänderung. Verwende den späteren Codex-Review nicht, um diese Pflicht nachträglich zu ersetzen.

## Scope-Schutz

Implementiere nur:

- explizit freigegebene Anforderungen,
- technisch zwingende Voraussetzungen,
- notwendige Integritäts-, Sicherheits- und Fehlerfälle.

Nicht automatisch implementieren:

- hypothetische Erweiterungspunkte,
- generische Frameworks für nur einen Use Case,
- zusätzliche Statuswerte „für später“,
- Reports, Exporte oder Benachrichtigungen ohne Freigabe,
- endgültige GUI vor dem Fachkern-Meilenstein.

## Planabweichung

Kann der Plan nicht sinnvoll umgesetzt werden, dokumentiere vor der Abweichung:

```text
PLANABWEICHUNG
Auslöser:
Betroffene bestätigte Entscheidung:
Technische oder fachliche Konsequenz:
Empfohlene Lösung:
Benutzerentscheidung erforderlich: ja/nein
```

Kleine interne Implementierungsdetails benötigen keine Planabweichung.

## Abschluss einer Iteration

Dokumentiere:

- umgesetzte Abnahmekriterien,
- geänderte Dateien,
- relevante Tests und Ergebnisse,
- offene nicht blockierende Punkte,
- bekannte Altfehler außerhalb des Umfangs,
- nächsten freigegebenen oder vorgeschlagenen Schritt.
