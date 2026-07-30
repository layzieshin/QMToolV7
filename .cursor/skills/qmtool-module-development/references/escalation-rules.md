# Eskalationsregeln

## Benutzerentscheidung erforderlich

Unterbreche den autonomen Ablauf nur bei mindestens einem dieser Fälle:

### Fachliche Unklarheit

- Bedeutung eines Datums, Status oder Vorgangs ist nicht eindeutig.
- Zwei fachlich verschiedene Abläufe sind plausibel.
- Eine bestehende Benutzerentscheidung müsste geändert werden.
- Audit-, Freigabe- oder Historienverhalten ist unklar.

### Drohender Architekturbruch

- Zugriff auf fremde Modulinterna scheint erforderlich.
- Eine öffentliche Schnittstelle müsste grundlegend erweitert werden.
- Eine zyklische fachliche Abhängigkeit entsteht.
- Fachlogik müsste in GUI, Backend-Host oder Plattform verschoben werden.

### Destruktiver Eingriff

- Datenverlust oder Bedeutungsänderung bestehender Daten,
- nicht rückwärtskompatible Migration,
- Entfernung einer öffentlichen API oder eines Contracts,
- Änderung eines freigegebenen Status- oder Berechtigungsmodells.

### Grundlegende GUI- oder Funktionsentscheidung

- wesentlich unterschiedliche Arbeitsmodelle, etwa Workspace gegen Dialog,
- deutliche Unterschiede bei Informationsdichte oder Rollenführung,
- notwendige Abweichung von bestätigten Arbeitsabläufen,
- neue, geänderte oder weggelassene fachliche Funktion ohne explizit bestätigte Quelle,
- sichtbare Daten, automatische Aktionen, Standards oder Interaktionsfolgen ohne bestätigte GUI-Entscheidung.

## Keine Benutzerentscheidung erforderlich

Entscheide innerhalb der Projektkonventionen selbst bei:

- internen Namen,
- Aufteilung kleiner Hilfsfunktionen,
- Mapping- und Repositorydetails,
- Testdateistruktur,
- Fehler- und Result-Typen,
- lokalen Refactorings,
- technischen Anpassungen ohne fachliche Auswirkung,
- etablierten GUI- und Implementierungsmustern innerhalb eines bereits bestätigten Bedienkonzepts, sofern sie weder Funktion noch sichtbaren Informationsgehalt verändern.

## Format einer Eskalation

```text
ENTSCHEIDUNG ERFORDERLICH
Kontext:
Warum die bisherige Planung nicht ausreicht:
Option A – Konsequenz:
Option B – Konsequenz:
Empfehlung:
Welche konkrete Entscheidung benötigt wird:
```

Stelle keine offene, abstrakte Frage, wenn eine konkrete Entscheidungsalternative formuliert werden kann.
