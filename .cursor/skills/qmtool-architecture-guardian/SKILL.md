---
name: qmtool-architecture-guardian
description: Evidenzbasierte Prüfung und gezielte Absicherung der tatsächlichen QMTool-v7-Architektur. Verwenden, wenn Importgrenzen, öffentliche Modulflächen, Ports, Contracts, Runtime-Verkabelung, GUI-/Host-Grenzen, zirkuläre Abhängigkeiten oder bestehende Architekturtests geprüft werden sollen. Der Skill liefert konkrete Fundstellen statt allgemeinem Lob, führt standardmäßig nur einen begrenzten Auditdurchlauf aus und verändert Code oder Regeln nur auf ausdrücklichen Auftrag.
---

# QMTool Architecture Guardian

## Auftrag

Prüfe, ob der tatsächliche Repository-Code die freigegebenen Architekturregeln einhält. Unterscheide klar zwischen vorgesehener Architektur und nachgewiesener Implementierung.

## Quellen

1. freigegebene Architektur- und Projektregeln,
2. tatsächlicher Repository-Code,
3. bestehende Architektur-, Modul- und Integrationstests,
4. dokumentierte Ausnahmen,
5. allgemeine Architekturprinzipien nur zur Einordnung.

Erfinde keine neue Architektur während eines Audits.

## Standardmodus

Führe einen Auditdurchlauf ohne Codeänderung durch. Prüfe gezielt:

- Imports zwischen Fachmodulen,
- Zugriffe auf fremde Interna,
- Imports von `interfaces` oder Backend-Hosts durch Fachmodule,
- fachliche Rückabhängigkeiten aus der Plattform,
- zirkuläre Abhängigkeiten,
- direkte Nutzung von globalem Container/Service Locator,
- öffentliche APIs und Contracts auf interne Domain-/ORM-Typen,
- vom konsumierenden Modul definierte Ports,
- `required_ports` und Runtime-Verkabelung,
- Geschäftslogik in GUI oder Backend-Host,
- Berechtigungsprüfung nur in der GUI,
- vorhandene Architekturtests und erkennbare Schutzlücken.

Lies `references/audit-process.md` und `references/architecture-test-guidance.md`.

## Befundstatus

Verwende:

- `ERFÜLLT`: Regel wurde konkret geprüft und kein Verstoß gefunden,
- `VERLETZT`: konkreter Verstoß mit Fundstelle,
- `TEILWEISE`: Regel wird nur in Teilen eingehalten,
- `NICHT NACHGEWIESEN`: vorhandene Informationen reichen nicht,
- `NICHT ANWENDBAR`: Regel betrifft den geprüften Bereich nicht,
- `DOKUMENTIERTE AUSNAHME`: bewusste, freigegebene Ausnahme.

## Ausgabeanforderungen

Jeder relevante Befund enthält:

- Regel,
- Status,
- konkrete Datei und möglichst Zeile/Symbol,
- Risiko,
- kleinste sinnvolle Maßnahme,
- Dringlichkeit,
- Zuordnung zu aktuellem oder separatem Arbeitsumfang.

Keine Aussagen wie „sehr sauber“, „extrem durchdacht“ oder „besser als erwartet“ ohne messbaren Nachweis.

## Begrenzung

- Ein vollständiger Auditdurchlauf.
- Bei unklaren Treffern eine gezielte Nachprüfung.
- Keine wiederholte Vollprüfung ohne Code- oder Regeländerung.
- Keine automatische Behebung aller Befunde.
- Keine Großrefactorings aus einem Audit heraus.

## Architekturtests

Wenn der Benutzer ausdrücklich die Absicherung verlangt:

1. Architekturregel präzise aus den Projektquellen ableiten.
2. Positiv- und Negativbeispiele bestimmen.
3. Bestehende Ausnahmen dokumentieren.
4. Einen gezielten Test implementieren.
5. Test einmal gegen den aktuellen Bestand ausführen.
6. Befunde klassifizieren; nicht in unbegrenzte Reparaturschleifen geraten.

Bevorzuge mehrere kleine, verständliche Tests gegenüber einem undurchsichtigen Meta-Framework.

## Benutzerentscheidung erforderlich

Frage den Benutzer nur, wenn:

- zwei widersprüchliche Architekturquellen existieren,
- eine gefundene Abhängigkeit möglicherweise bewusst ist,
- eine Behebung die öffentliche API oder das Datenmodell verändert,
- eine dokumentierte Ausnahme neu bewertet werden muss,
- ein Architekturtest bestehendes Verhalten in großem Umfang blockieren würde.

## Standarddokument

Nutze `templates/architecture_audit.md` oder die bestehende Projektdokumentstruktur.
