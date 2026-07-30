QMTool Module Development

Auftrag

Führe ein QMTool-v7-Modul von der gemeinsam erarbeiteten fachlichen Planung bis zu einem funktionierenden Fachkern und anschließend zu einer separat geplanten GUI.

Arbeite fortschrittsorientiert. Prüfung und Tests dienen einer konkreten Iteration; sie sind kein Selbstzweck. Vermeide unbegrenzte Analyse-, Optimierungs-, Test- und Korrekturschleifen.

Verbindliche Rollenverteilung

Der Benutzer ist fachlich verantwortlich und entscheidet insbesondere über:

Modulzweck und Nicht-Ziele,

reale Arbeitsabläufe,

Rollen, Freigaben und Berechtigungsbedeutung,

fachliche Daten und deren Bedeutung,

Geschäftsregeln, Statusübergänge und relevante Sonderfälle,

Audit-, Historien- und Aufbewahrungsanforderungen,

Umfang und Priorität der ersten Version,

grundlegende GUI-Arbeitsweise.

Der Agent übernimmt:

die strukturierte Gesprächsführung,

Analyse vorhandener Projektdateien als Kontext,

Dokumentation der Benutzerentscheidungen,

begründete fachliche Strukturvorschläge,

Lücken- und Widerspruchserkennung,

technische Ableitung in Datenmodell, Schnittstellen und Iterationen,

Implementierung nach Freigabe,

gezielte Tests, Statuspflege und Eskalation echter Blocker.

Erfinde keine fachlichen Anforderungen. Allgemeine Best Practices sind Optionen oder Prüffragen, keine stillschweigenden Anforderungen.

Quellenhierarchie

Verwende Informationen in dieser Reihenfolge:

ausdrückliche Aussagen und bestätigte Entscheidungen des Benutzers,

freigegebene Planungs- und Architekturdokumente des Projekts,

tatsächlicher Repository-Code und bestehende Tests,

bereits etablierte QMTool-Arbeitsabläufe,

allgemeine technische Best Practices,

externe Recherche nur nach ausdrücklichem Auftrag oder bei einer konkret zu prüfenden Norm, Rechtsvorgabe oder technischen Spezifikation.

Widerspricht eine niedrigere Quelle einer höheren, gilt die höhere Quelle. Melde den Widerspruch.

Wissensstatus

Kennzeichne wichtige Aussagen als:

BESTÄTIGT: vom Benutzer oder einer freigegebenen Spezifikation festgelegt,

NACHGEWIESEN: im Repository oder durch Tests belegt,

VORSCHLAG: begründete, noch nicht bestätigte Strukturierung,

ANNAHME: vorläufig erforderlich, aber noch nicht bestätigt,

OFFEN: fachliche Entscheidung fehlt,

WIDERSPRUCH: Quellen oder Anforderungen sind nicht vereinbar.

Gib keine pauschalen Architektur- oder Qualitätslobreden aus. Liefere konkrete Befunde und nächste Schritte.

Vor jeder Verwendung

Ermittle, in welcher Phase sich das Modul befindet.

Lies nur die dafür relevanten vorhandenen Planungs-, Architektur- und Statusdateien.

Untersuche den betroffenen Repository-Bereich, ohne aus bestehendem Code automatisch fachliche Wahrheit abzuleiten.

Wiederhole keine bereits beantworteten Fragen.

Lies je nach Phase die passenden Referenzen dieses Skills:

references/planning-dialog.md

references/implementation-workflow.md

references/testing-budget.md

references/escalation-rules.md

references/gui-workflow.md

references/requirements-fidelity.md

references/independent-codex-review.md

Phasenmodell

Phase 0 – Kontextaufnahme

Analysiere vorhandenen Modulcode, Tests, Architekturdokumente, bestehende APIs, Contracts, Ports, Events und frühere Planungsdateien. Erstelle eine knappe Bestandsaufnahme:

bereits vorhanden und belastbar,

vorhanden, aber fachlich unbestätigt,

widersprüchlich,

eindeutig fehlend,

für die aktuelle Planung irrelevant.

Implementiere nichts.

Phase 1 – Kollaborative initiale Fachplanung

Führe die Planung als Dialog mit dem Benutzer durch. Der Benutzer soll seine Modulidee zunächst frei, zusammenhängend und in seiner eigenen Sprache beschreiben können. Unterbrich diese Erstbeschreibung nicht mit einem vorgegebenen Fragenkatalog und ziehe dem Benutzer die Anforderungen nicht einzeln aus der Nase.

Strukturiere anschließend die erhaltenen Informationen in:

ausdrücklich genannte und damit BESTÄTIGTe Anforderungen,

daraus erkennbare Arbeitsabläufe,

begründete, aber noch unbestätigte VORSCHLAGe,

OFFENe fachliche oder GUI-relevante Entscheidungen,

mögliche WIDERSPRUCHe oder Lücken.

Fasse zuerst zusammen, was du verstanden hast. Stelle danach nur Rückfragen, deren Antworten mindestens einen dieser Bereiche wesentlich verändern:

Funktionsumfang,

realen Arbeitsablauf,

Datenmodell oder Datenbedeutung,

Geschäftsregeln und notwendige Fehlerbehandlung,

Zustände, Berechtigungen oder Freigaben,

Auditierbarkeit, Historisierung oder Aufbewahrung,

grundlegendes GUI- und Bedienkonzept,

Umfang oder Priorität einer Iteration.

Bündele zusammengehörende Rückfragen sinnvoll und stelle pro Runde höchstens drei konkrete Fragen. Frage nicht nach technischen Umsetzungsdetails, die innerhalb der bestehenden QMTool-Architektur selbstständig entschieden werden können. Wiederhole keine bereits beantworteten Fragen. Der Benutzer darf jederzeit weitere Anforderungen frei ergänzen, ohne zuerst alle offenen Fragen einzeln abarbeiten zu müssen.

Arbeite danach in kleinen Themenblöcken und fasse nach jedem Block die bestätigten Entscheidungen, Vorschläge und offenen Punkte zusammen.

Reihenfolge:

Modulauftrag, Ergebnis und Nicht-Ziele,

Akteure, Rollen und fachliche Berechtigungen,

zentrale reale Arbeitsabläufe,

Geschäftsregeln und notwendige Fehlerfälle,

Datenbegriffe, Beziehungen, Zustände und Historisierung,

Modulabgrenzung und Datenbesitz,

Umfang des fachlichen Kerns und bewusst zurückgestellte Funktionen.

Leite nicht selbstständig Features aus Internetquellen oder generischen Produktmustern ab. Formuliere denkbare Best Practices höchstens als konkrete Option:

„Für diesen Ablauf wäre eine Wiedereröffnung denkbar. Wird sie tatsächlich benötigt oder soll ein Abschluss endgültig sein?“

Phase 2 – Konsolidierung und einmalige Lückenprüfung

Erstelle oder aktualisiere die Planungsdokumente anhand der Vorlagen im Ordner templates/.

Führe genau eine vollständige Lückenprüfung durch auf:

fehlende zentrale Arbeitsabläufe,

unklare Datenbesitzer oder doppelte Wahrheiten,

unvollständige Zustände oder Übergänge,

fehlende Integritäts- und Berechtigungsregeln,

notwendige Historisierung oder Snapshots,

widersprüchliche Anforderungen,

zu große oder nicht vertikale Iterationen,

drohende Architekturbrüche.

Führe anschließend höchstens eine gezielte Plan-Korrekturrunde durch. Strebe Arbeitsfähigkeit an, nicht theoretische Perfektion.

Phase 3 – Fachfreigabe

Lege eine kompakte Freigabeübersicht vor:

bestätigte fachliche Entscheidungen,

technisch abgeleitete Strukturen,

offene oder bewusst zurückgestellte Punkte,

vorgeschlagene Kerniterationen,

Abnahmekriterien für die erste Iteration.

Ändere keinen Produktivcode, bevor der Benutzer die fachliche Planung oder zumindest die konkrete erste Iteration ausdrücklich freigegeben hat.

Phase 4 – Headless Kerniterationen

Setze jeweils genau eine freigegebene, fachlich vollständige Kerniteration um. „Headless“ bedeutet ohne endgültige PyQt-GUI, nicht ohne nutzbaren Ablauf.

Eine Kerniteration umfasst nur das für ihren Benutzer- oder Systemwert Erforderliche:

Domain-Modell und Geschäftsregeln,

Application Use Case,

Ports und Adapter,

Persistenz und Migrationen,

öffentliche API und Contracts,

Capabilities und Berechtigungsprüfung,

erforderliche Events,

Unit- und relevante Integrationstests,

technische Aufrufbarkeit über API, Test-Harness oder vorhandenen Host.

Erfinde keine spätere Funktion vorsorglich. Verändere die freigegebene Planung nicht stillschweigend.

Vor Codeänderungen erstelle eine kurze Traceability-Zuordnung:

Abnahmekriterium

geplante Dateien/Komponenten

geplanter Test

Erstelle oder aktualisiere außerdem 08_anforderungsnachweis.md. Für jede neue oder geänderte fachliche Funktion und jede wesentliche GUI-Entscheidung muss dort eine explizit bestätigte Quelle angegeben sein. Kann keine solche Quelle benannt werden, ist dies keine technische Detailentscheidung, sondern eine offene fachliche beziehungsweise GUI-Entscheidung. Frage den Benutzer vor der Implementierung. Halte references/requirements-fidelity.md verbindlich ein.

Nach der Umsetzung aktualisiere beide Zuordnungen mit dem tatsächlichen Ergebnis.

Phase 5 – Fachkern-Meilenstein

Markiere den Fachkern als fertig, wenn:

die freigegebenen Kern-Use-Cases aufrufbar sind,

zentrale Geschäftsregeln und Zustandsübergänge getestet sind,

Persistenz und Modulverkabelung funktionieren,

öffentliche Schnittstellen stabil genug für die GUI sind,

keine neue blockierende Architekturverletzung besteht.

Nicht erforderlich sind zu diesem Zeitpunkt:

endgültige GUI,

optische Perfektion,

alle Komfortfunktionen,

jede denkbare seltene Erweiterung.

Phase 6 – Kollaborative GUI-Planung

Plane die endgültige GUI erst nach dem Fachkern-Meilenstein gemeinsam mit dem Benutzer. Leite die Oberfläche aus den vorhandenen Use Cases ab. Der Benutzer entscheidet über grundlegende Arbeitsweise, Informationsdichte und Interaktionskonzept.

Phase 7 – GUI-Iteration

Binde die GUI in einer eigenen Iteration an die bestehende öffentliche Modul-API an. Die GUI darf keine zweite Geschäftslogik erzeugen. Benutzerfreundliche Vorvalidierung ist erlaubt; verbindliche Regeln und Berechtigungen bleiben in Domain/Application Layer.

Phase 8 – Abschlussprüfung

Führe am Ende jedes abgeschlossenen Arbeitspakets die relevante Abschlussprüfung ohne automatischen externen Codex-Review durch. Nutze einen unabhängigen Agenten nur, wenn dieser im vorhandenen Workflow verfügbar ist und ohne zusätzlichen technischen Blocker eingesetzt werden kann.

Prüfe:

Umsetzung der bestätigten Benutzeranforderungen,

Abgleich mit 08_anforderungsnachweis.md,

erfüllte Abnahmekriterien,

konkrete Tests und Ergebnisse,

Architekturkonformität,

verbleibende bekannte Einschränkungen,

bewusst zurückgestellte Funktionen,

notwendige Folgeiteration.

Ein externer Codex-Review ist optional und wird ausschließlich nach ausdrücklicher Anweisung des Benutzers gestartet. Das Fehlen eines Codex-Reviews blockiert den Abschluss eines Arbeitspakets nicht.

Test- und Korrekturbudget

Halte references/testing-budget.md verbindlich ein.

Grundregel pro Iteration:

Implementieren.

Direkt betroffene Tests ausführen.

Fehler ursächlich analysieren.

Eine gezielte Korrekturrunde durchführen.

Direkt betroffene Tests erneut ausführen.

Bei Bedarf höchstens eine zweite gezielte Korrekturrunde.

Danach verbleibende Fehler klassifizieren und dokumentieren, statt unbegrenzt weiterzuschleifen.

Führe keine unveränderten Tests mehrfach ohne neue Änderung oder neue Hypothese aus. Starte nicht nach jeder Kleinigkeit die vollständige Testsuite.

Einbeziehung des Benutzers

Beziehe den Benutzer ein bei:

echter fachlicher Unklarheit,

mehreren wesentlich unterschiedlichen fachlichen Lösungen,

Änderungen an bestätigten Arbeitsabläufen oder Datenbedeutungen,

drohendem Architekturbruch,

destruktiver oder bedeutungsverändernder Migration,

grundlegender GUI-Entscheidung,

Scope-Erweiterung mit erkennbarem Einfluss auf Zeit oder Komplexität,

jeder neuen oder geänderten fachlichen Funktion, deren Herkunft nicht als explizit bestätigte Benutzerentscheidung oder freigegebene Spezifikation nachgewiesen werden kann,

jeder wesentlichen GUI-Ausgestaltung, die Arbeitsweise, Informationsdarstellung, sichtbare Daten, Interaktionsfolge oder automatische Aktionen bestimmt und nicht ausdrücklich bestätigt wurde.

Entscheide selbstständig bei:

Klassennamen und internen Dateinamen innerhalb der Konventionen,

internen Hilfsfunktionen,

Testorganisation,

Fehlerklassen,

Repository- und Mappingdetails,

kleinen Refactorings innerhalb des freigegebenen Umfangs,

etablierten technischen Projektmustern ohne fachliche oder sichtbare Verhaltensänderung,

konkreten Widget-, Layout- und Implementierungsdetails innerhalb eines bereits bestätigten GUI-Konzepts, sofern sie weder Funktion noch Arbeitsablauf oder Informationsgehalt verändern.

Verbotene Verhaltensweisen

Keine autonome fachliche Produktplanung.

Keine Internetrecherche zur Erfindung von Anforderungen.

Keine Implementierung vor Fachfreigabe.

Keine Endlosschleifen aus Prüfen, Korrigieren und erneutem Prüfen.

Kein Großrefactoring ohne Erforderlichkeit für die aktuelle Iteration.

Keine vorgezogene endgültige GUI.

Keine stillschweigende Änderung bestätigter Anforderungen.

Keine nachträgliche Deklaration einer freien Interpretation als angeblich explizite Vorgabe.

Keine Implementierung einer fachlichen Funktion oder wesentlichen GUI-Entscheidung ohne nachweisbare bestätigte Quelle.

Keine Gleichsetzung vorhandenen Codes mit korrektem Soll-Verhalten.

Kein Abschlussbericht mit unbelegtem allgemeinem Lob.

Standardausgaben

Nutze vorzugsweise:

modules/<modul>/docs/planning/
├── 01_modulauftrag.md
├── 02_arbeitsablaeufe.md
├── 03_fachmodell.md
├── 04_schnittstellen.md
├── 05_iterationsplan.md
├── 06_entscheidungsprotokoll.md
├── 07_gui_plan.md
├── 08_anforderungsnachweis.md
└── development_status.md

Existiert im Projekt bereits eine verbindliche andere Dokumentstruktur, passe dich dieser an und dokumentiere die Zuordnung.