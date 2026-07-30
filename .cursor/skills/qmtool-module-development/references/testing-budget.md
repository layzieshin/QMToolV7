# Test- und Korrekturbudget

## Ziel

Tests sollen Fehler erkennen und Fortschritt absichern, nicht die Entwicklung in unbegrenzten Schleifen festhalten.

## Pro Kerniteration

### Lauf 1 – zielgerichtet

Führe nur direkt betroffene Unit- und Integrationstests aus.

### Korrekturrunde 1

- Ursache bestimmen,
- gezielt korrigieren,
- betroffene Tests erneut ausführen.

### Korrekturrunde 2 – nur bei begründeter Aussicht

Eine zweite Runde ist erlaubt, wenn:

- der Fehler verstanden ist,
- die Korrektur lokal begrenzt ist,
- kein neuer Fachentscheid nötig ist.

Danach keine automatische weitere Schleife.

## Nach zwei erfolglosen Korrekturrunden

Klassifiziere den Fehler:

### Blockierend

Beispiele:

- Modul oder Migration nicht ausführbar,
- Datenintegrität verletzt,
- zentraler Use Case nicht nutzbar,
- Berechtigung oder zentrale Invariante unwirksam,
- neue relevante Architekturverletzung.

Die Iteration ist nicht abschließbar. Erstelle einen knappen Blockerbericht.

### Nicht blockierend

Beispiele:

- kosmetischer oder peripherer Fehler,
- Fehler in unverändertem Altbereich,
- nicht benötigte Komfortfunktion,
- bekannte Einschränkung ohne Einfluss auf den freigegebenen Use Case.

Dokumentiere ihn und setze den planmäßigen Fortschritt fort.

### Ungeklärter Altfehler

Bestimme soweit möglich:

- bestand er bereits vorher,
- wurde er von der Iteration berührt,
- verhindert er das fachliche Ergebnis.

Keine umfassende Altlastensanierung ohne eigenen Auftrag.

## Teststufen

### Während der Implementierung

Nur betroffene Tests oder einzelne Testdateien.

### Ende einer Kerniteration

Gesamte Modultests plus relevante Integrations- und Architekturtests.

### Fachkern-Meilenstein

Einmal die relevanten Modul-, Integrations- und Architekturtestbereiche.

### Nach GUI-Integration

Einmal relevante Interface-, Modul-, Plattform- und Architekturregression.

## Verboten

- gleiche unveränderte Tests ohne neue Änderung erneut starten,
- vollständige Testsuite nach jeder Kleinigkeit,
- Tests verändern, nur damit eine falsche Implementierung grün wird,
- Großrefactoring zur Beseitigung eines nicht blockierenden Nebenfehlers,
- „bis alles perfekt ist“ ohne festes Erfolgskriterium weiterarbeiten.
