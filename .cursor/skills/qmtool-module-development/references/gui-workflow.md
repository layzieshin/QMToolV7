# GUI-Workflow nach dem Fachkern

## Voraussetzung

Beginne die endgültige GUI-Planung erst, wenn:

- Kern-Use-Cases implementiert und technisch aufrufbar sind,
- öffentliche API und Contracts ausreichend stabil sind,
- zentrale Regeln unabhängig von der GUI getestet sind.

## Gemeinsame GUI-Planung

Lege dem Benutzer die vorhandenen Use Cases und Rollen vor. Kläre gemeinsam:

- welche Aufgabe der Benutzer jeweils erledigt,
- welche Informationen dabei gleichzeitig sichtbar sein müssen,
- welche Aktionen häufig oder selten sind,
- wo Listen-, Detail-, Master-Detail- oder Dialogdarstellung sinnvoll ist,
- welche Unterschiede zwischen Rollen bestehen,
- welche Fehler und Status sichtbar kommuniziert werden müssen.

Entscheide nicht allein über grundlegendes Bedienkonzept, Informationsdichte, sichtbare Daten, automatische Aktionen oder die Reihenfolge des Benutzerablaufs. Dokumentiere jede bestätigte wesentliche GUI-Entscheidung mit einer GUI-Entscheidungs-ID in `06_entscheidungsprotokoll.md` und `08_anforderungsnachweis.md`.

## GUI-Architektur

- GUI ruft öffentliche Modul-API beziehungsweise vorgesehene Application-Schnittstellen auf.
- Keine direkten Zugriffe auf interne Repositorys oder ORM-Modelle.
- Keine verbindliche Geschäftsregel ausschließlich im Widget.
- Capability-Prüfung in der GUI dient Darstellung und Bedienbarkeit; die Anwendungsschicht prüft verbindlich erneut.
- Keine zweite fachliche Zustandsmaschine im ViewModel.

## GUI-Iteration

Umfasse:

- Workspace, Views und Dialoge,
- Presenter/ViewModel nach bestehendem Projektmuster,
- Contract-Mapping,
- Lade-, Fehler- und Leerzustände,
- rollen- und capabilityabhängige Aktionen,
- relevante Interface- und Integrationstests.

Konkrete technische Widget-, Layout- und Presenterdetails dürfen autonom gewählt werden, wenn sie einem bestätigten GUI-Konzept oder einem bestehenden Projektmuster folgen und weder Funktion noch Informationsgehalt verändern.

## Abschluss

Prüfe jeden GUI-Ablauf gegen den bereits implementierten fachlichen Use Case. Eine GUI darf keinen neuen fachlichen Ablauf stillschweigend einführen.
