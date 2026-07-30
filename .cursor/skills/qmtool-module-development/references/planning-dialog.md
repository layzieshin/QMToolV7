# Geführter Planungsdialog

## Ziel

Der Agent strukturiert das fachliche Wissen des Benutzers. Er ersetzt es nicht.

## Gesprächsregeln

- Stelle Fragen in thematisch kleinen Gruppen, üblicherweise zwei bis vier Fragen.
- Frage nur, was für den nächsten Planungsschritt erforderlich ist.
- Wiederhole keine beantworteten Fragen.
- Fasse nach jedem Block Entscheidungen, offene Punkte und mögliche Widersprüche zusammen.
- Trenne Nutzerentscheidung, Repository-Befund und eigenen Vorschlag sichtbar.
- Vergib für bestätigte fachliche und GUI-Entscheidungen stabile IDs, damit spätere Implementierung und Codex-Review ihre Herkunft nachvollziehen können.
- Gib bei komplexen Entscheidungen höchstens drei deutlich unterschiedliche Optionen mit Konsequenzen.
- Verwende keine abstrakten Architekturfragen, wenn eine konkrete Arbeitsablauffrage möglich ist.

Schlecht:

> „Welche Entitäten und Aggregate benötigt das Modul?“

Besser:

> „Was legt ein Benutzer zuerst an? Welche Angaben müssen dabei bereits feststehen, und welche entstehen erst bei der späteren Bearbeitung?“

## Themenblöcke

### 1. Modulauftrag

Kläre:

- Welches konkrete Problem löst das Modul?
- Wer arbeitet damit?
- Welches fachliche Ergebnis soll entstehen?
- Was geschieht heute ohne das Modul?
- Was gehört ausdrücklich nicht hinein?

### 2. Arbeitsabläufe

Ermittle pro zentralem Vorgang:

- Auslöser,
- Akteur,
- Vorbedingungen,
- Eingaben,
- Normalablauf,
- Ergebnis,
- notwendige Fehlerfälle,
- Folgeaktionen.

### 3. Fachregeln

Kläre insbesondere:

- Was muss immer gelten?
- Was darf nach Freigabe oder Abschluss nicht mehr verändert werden?
- Welche Aktionen benötigen welche fachliche Berechtigung?
- Welche Fälle müssen aus Auditgründen nachvollziehbar bleiben?
- Wann ist ein Vorgang ungültig, überfällig, zurückgewiesen oder abgeschlossen?

### 4. Datenmodell

Leite Datenbegriffe aus bestätigten Arbeitsabläufen ab. Stelle sie als Vorschlag zur Prüfung vor. Kläre:

- eindeutige Identität,
- Pflicht- und optionale Daten,
- Beziehungen und Kardinalitäten,
- Datenbesitz,
- Zustände,
- Historisierung, Versionierung und Snapshots,
- Archivierung und Löschung.

### 5. Umfang

Trenne:

- zwingender Fachkern,
- sinnvolle spätere Erweiterung,
- reine Komfortfunktion,
- ausdrücklich ausgeschlossen.

## Abschluss eines Planungsblocks

Nutze eine kompakte Form:

```text
BESTÄTIGT
- ...

VORSCHLAG
- ...

OFFEN
- ...

NÄCHSTER PLANUNGSSCHRITT
- ...
```
