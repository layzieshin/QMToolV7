# Architektur-Auditprozess

## 1. Umfang festlegen

Bestimme den konkreten Prüfbereich:

- gesamtes Repository,
- ein Modul,
- ein geänderter Branch/Commit,
- eine bestimmte Regelklasse.

## 2. Regeln extrahieren

Erstelle eine kurze Prüfliste aus den verbindlichen Projektquellen. Keine stillschweigende Erweiterung um persönliche Präferenzen.

## 3. Statische Befunde

Prüfe unter anderem:

- absolute und relative Imports,
- dynamische Imports soweit erkennbar,
- Typreferenzen in Contracts und APIs,
- Zugriffe auf Repositorys/ORM außerhalb des Eigentümermoduls,
- Containerzugriffe,
- Host- und GUI-Abhängigkeiten.

## 4. Laufzeit- und Testbefunde

Prüfe:

- Portregistrierung und `required_ports`,
- relevante Architekturtests,
- Integrationstests der Modulgrenzen,
- zirkuläre Abhängigkeiten beim Import/Start.

## 5. Risiko priorisieren

### Hoch

- Datenintegrität, Sicherheits- oder Berechtigungsgrenze betroffen,
- direkte fremde Persistenz-/ORM-Nutzung,
- zyklische fachliche Abhängigkeit,
- Host/GUI als einzige Träger verbindlicher Fachlogik.

### Mittel

- übergroße öffentliche Fläche,
- versteckte Containerkopplung,
- fehlende automatisierte Absicherung einer häufig verletzten Regel.

### Niedrig

- Konventionsabweichung ohne aktuelle Kopplungswirkung,
- Dokumentationslücke,
- isolierte technische Unsauberkeit.

## 6. Bericht

Trenne:

- neue Verletzungen,
- bestehende Altlasten,
- dokumentierte Ausnahmen,
- nicht nachweisbare Regeln,
- empfohlene nächste kleine Maßnahmen.
