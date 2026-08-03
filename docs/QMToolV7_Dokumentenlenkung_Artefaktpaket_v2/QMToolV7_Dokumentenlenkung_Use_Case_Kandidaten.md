# QMToolV7 – Exzessiver Use-Case-Kandidatenkatalog

**Stand:** 2026-08-03
**Zweck:** Auswahlmaterial zur fachlichen Prüfung. Diese Liste ist absichtlich breiter als der verbindliche Kernkatalog.

> Cursor darf aus diesem Katalog ohne ausdrückliche Freigabe keinen zusätzlichen Umsetzungsscope ableiten.

**Umfang:** 211 Kandidaten.

## Planung

### CAND-001 – Plan duplizieren
- **Kurzbeschreibung:** Einen vorhandenen Planungseintrag als Ausgangspunkt kopieren.
- **Primärakteur:** Planersteller/QMB
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-002 – Plan einem anderen Bearbeiter übergeben
- **Kurzbeschreibung:** Verantwortung für einen noch unverbindlichen Plan übertragen.
- **Primärakteur:** Planersteller/QMB
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-003 – Plan nach Fachbereich filtern
- **Kurzbeschreibung:** Planungsliste auf organisatorischen Kontext einschränken.
- **Primärakteur:** Planersteller/QMB
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-004 – Plan aus abgelehntem Investitionsbedarf schließen
- **Kurzbeschreibung:** Plan mit begründetem Abschluss ohne Dokumenterzeugung beenden.
- **Primärakteur:** Planersteller/QMB
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-005 – Plan mit gewünschtem Fertigstellungstermin versehen
- **Kurzbeschreibung:** Unverbindlichen Zieltermin dokumentieren.
- **Primärakteur:** Planersteller/QMB
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-006 – Plan auf doppelte Dokumentenidee prüfen
- **Kurzbeschreibung:** Ähnliche offene Pläne oder bestehende Dokumente anzeigen.
- **Primärakteur:** Planersteller/QMB
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

## Dokumentanlage und Kennung

### CAND-007 – Nächste freie interne Kennung reservieren
- **Kurzbeschreibung:** Kennung unter Konkurrenz sicher auswählen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-008 – Manuelle Altdokument-Kennung übernehmen
- **Kurzbeschreibung:** Legacykennung mit Formatabweichung kontrolliert importieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-009 – Reservierung einer Kennung verfallen lassen
- **Kurzbeschreibung:** Temporäre Reservierung bei abgebrochener Anlage freigeben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-010 – Dokumentenart beim Anlegen vorschlagen
- **Kurzbeschreibung:** Art aus Plan oder Kennungsschema vorbelegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-011 – Externe Kennung mit variabler Stellenzahl erzeugen
- **Kurzbeschreibung:** EXT-Schema 2/3-stellig konfigurieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-012 – Doppelte Kennung bei Parallelzugriff verhindern
- **Kurzbeschreibung:** DB-seitige Eindeutigkeit und verständliche Fehlermeldung.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-013 – Dokument ohne Plan direkt anlegen
- **Kurzbeschreibung:** Berechtigter Schnellpfad direkt zu DRAFT.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-014 – Bestandsdokument mit bereits veröffentlichter Fassung importieren
- **Kurzbeschreibung:** Legacyübernahme mit klarer Historie.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-015 – Dokumentidentität zusammenführen
- **Kurzbeschreibung:** Irrtümlich doppelt angelegte Identitäten fachlich behandeln.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

## Metadaten

### CAND-016 – Kurzbeschreibung ändern
- **Kurzbeschreibung:** Dokumentgebundene Beschreibung ohne neue Version korrigieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-017 – Fachbereich ändern
- **Kurzbeschreibung:** Organisatorische Zuordnung mit Audit ändern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-018 – Standort ändern
- **Kurzbeschreibung:** Standortbezug mit historischem Snapshot ändern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-019 – Regulatorischen Geltungsbereich ändern
- **Kurzbeschreibung:** Scope mit Begründung aktualisieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-020 – Dokumentenart korrigieren
- **Kurzbeschreibung:** Falsche Art durch QMB korrigieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-021 – Owner ändern
- **Kurzbeschreibung:** Verantwortung interner Dokumente übertragen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-022 – Herausgeber externes Dokument pflegen
- **Kurzbeschreibung:** Hersteller/Herausgeber aktualisieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-023 – Metadatenänderung mit Sammelbegründung
- **Kurzbeschreibung:** Mehrere Felder in einer fachlichen Aktion ändern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-024 – Historischen Metadatensnapshot anzeigen
- **Kurzbeschreibung:** Version im damaligen organisatorischen Kontext darstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-025 – Metadatenänderung zurücknehmen
- **Kurzbeschreibung:** Fehlkorrektur als neue auditierte Korrektur berichtigen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

## Quellen und Artefakte

### CAND-026 – Interne DOCX importieren
- **Kurzbeschreibung:** Bearbeitbare Quelle als aktuelles Artefakt speichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-027 – Externe PDF importieren
- **Kurzbeschreibung:** Unveränderte Fremdquelle speichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-028 – DOCX aus kontrollierter Vorlage erzeugen
- **Kurzbeschreibung:** Vorlage kopieren und versionsbezogen speichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-029 – Aktuelle Quelle ersetzen
- **Kurzbeschreibung:** Neue Bearbeitungsdatei mit Historie aktiv setzen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-030 – DOCX in PDF konvertieren
- **Kurzbeschreibung:** Feste Fassung für Workflow erzeugen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-031 – PDF-Konvertierung wiederholen
- **Kurzbeschreibung:** Technischen Fehler ohne neue Fachentscheidung beheben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-032 – Artefaktintegrität per Hash prüfen
- **Kurzbeschreibung:** Manipulation/Dateifehler erkennen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-033 – Fehlendes Artefakt melden
- **Kurzbeschreibung:** Metadaten vorhanden, Datei physisch nicht auffindbar.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-034 – Artefakt herunterladen
- **Kurzbeschreibung:** Berechtigten Zugriff auf Quelle oder Auditfassung erlauben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-035 – Originaldateinamen anzeigen
- **Kurzbeschreibung:** Nachvollziehbarkeit des Imports gewährleisten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-036 – Vorläufiges PDF löschen
- **Kurzbeschreibung:** Nicht benötigte technische Zwischenartefakte bereinigen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-037 – Ablehnungs-PDF dauerhaft markieren
- **Kurzbeschreibung:** Tatsächlich bewertete Fassung als Evidence erhalten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-038 – Finale PDF neu materialisieren
- **Kurzbeschreibung:** Speicherwiederherstellung bei identischem Hash.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-039 – PDF-Wasserzeichen optional erzeugen
- **Kurzbeschreibung:** Spätere Gimmick-/Kennzeichnungsfunktion vorbereiten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Optional / später
- **Auswahlstatus:** Zur Auswahl

## Versionierung und Änderungen

### CAND-040 – Version 1 anlegen
- **Kurzbeschreibung:** Erste sichtbare Version im DRAFT erzeugen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-041 – Nachfolgeversion aus aktuellem DOCX erzeugen
- **Kurzbeschreibung:** Inhaltliche Basis kopieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-042 – Nachfolgeversion extern durch PDF-Import anlegen
- **Kurzbeschreibung:** Neue Herstellerfassung aufnehmen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-043 – Offene Nachfolgeversion anzeigen
- **Kurzbeschreibung:** Doppelanlage verhindern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-044 – Nie eingereichten DRAFT verwerfen
- **Kurzbeschreibung:** Version und Kennungsreservierung freigeben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-045 – Änderungsanlass erfassen
- **Kurzbeschreibung:** Pflichtbegründung der Version dokumentieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-046 – Änderungseintrag anlegen
- **Kurzbeschreibung:** Konkrete Änderung beschreiben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-047 – Änderungseintrag korrigieren
- **Kurzbeschreibung:** Im DRAFT mit Audit anpassen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-048 – Änderungseintrag einem Kapitel zuordnen
- **Kurzbeschreibung:** Optionale Strukturreferenz pflegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-049 – Änderungseintrag für Einreichung auswählen
- **Kurzbeschreibung:** Rundenspezifischen Change-Scope definieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-050 – Nicht enthaltenen Änderungseintrag begründen
- **Kurzbeschreibung:** Offene Änderung transparent zurückstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-051 – Eingefrorenen Change-Scope anzeigen
- **Kurzbeschreibung:** Reviewer sieht genau den eingereichten Umfang.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-052 – Korrekturfassung nach ANNULLED anlegen
- **Kurzbeschreibung:** Gleiche sichtbare Version mit neuer technischer ID.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-053 – Archiviertes Dokument reaktivieren
- **Kurzbeschreibung:** Neue Version aus historischer Grundlage erzeugen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-054 – Versionshistorie vollständig anzeigen
- **Kurzbeschreibung:** Alle Fassungstypen inklusive annullierter Records darstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

## Workflowprofile

### CAND-055 – Workflowprofil anlegen
- **Kurzbeschreibung:** Neues Profil mit festen Stufen/konfigurierbaren Übergängen erstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-056 – Workflowprofil versionieren
- **Kurzbeschreibung:** Änderung als neue unveränderliche Profilversion speichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-057 – Alte Profilversion kopieren
- **Kurzbeschreibung:** Bestehende Version als Entwurfsbasis nutzen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-058 – Profil deaktivieren
- **Kurzbeschreibung:** Keine neue Verwendung, Historie erhalten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-059 – Standardprofil einer Dokumentenart zuordnen
- **Kurzbeschreibung:** Artbezogene Voreinstellung pflegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-060 – Dokumentbezogene Profilabweichung setzen
- **Kurzbeschreibung:** Geeignetes anderes Profil wählen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Optional / später
- **Auswahlstatus:** Zur Auswahl

### CAND-061 – Reviewübergang deaktivieren
- **Kurzbeschreibung:** Direkten Pfad zu Approval konfigurieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-062 – Approvalübergang deaktivieren
- **Kurzbeschreibung:** Direkten Abschluss nach Review konfigurieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-063 – Direkte Freigabe aus DRAFT konfigurieren
- **Kurzbeschreibung:** Minimalprofil explizit abbilden.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-064 – ONE_OF_POOL konfigurieren
- **Kurzbeschreibung:** Eine Entscheidung aus dem Pool genügt.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-065 – ALL_ASSIGNED konfigurieren
- **Kurzbeschreibung:** Alle konkret Zugewiesenen müssen zustimmen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-066 – Signaturpflicht pro Übergang konfigurieren
- **Kurzbeschreibung:** Signaturbedarf exakt festlegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-067 – Stufenfrist konfigurieren
- **Kurzbeschreibung:** Optionales due_at ableiten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-068 – revoke_if_changed pro Stufe setzen
- **Kurzbeschreibung:** Rückrollwirkung von Laufzeitänderungen definieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-069 – Vier-Augen-Regel aktivieren
- **Kurzbeschreibung:** Keine unmittelbar aufeinanderfolgenden Aktionen derselben Person.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-070 – Profilvalidierung durchführen
- **Kurzbeschreibung:** Unmögliche oder unvollständige Konfiguration blockieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

## Workflowausführung

### CAND-071 – Workflowrollen vollständig zuweisen
- **Kurzbeschreibung:** Editor/Reviewer/Approver-Pools festlegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-072 – Workflow atomar starten
- **Kurzbeschreibung:** Profil-Snapshot und Zuweisungen fixieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-073 – Workflowstart abbrechen
- **Kurzbeschreibung:** Ohne Teilzustand im DRAFT bleiben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-074 – Entwurf zur Prüfung einreichen
- **Kurzbeschreibung:** DRAFT zu IN_REVIEW.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-075 – Entwurf direkt zur Freigabe einreichen
- **Kurzbeschreibung:** DRAFT zu IN_APPROVAL.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-076 – Entwurf direkt freigeben
- **Kurzbeschreibung:** DRAFT zu APPROVED im passenden Profil.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-077 – Review annehmen
- **Kurzbeschreibung:** IN_REVIEW zu IN_APPROVAL.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-078 – Review abschließen ohne Approval
- **Kurzbeschreibung:** IN_REVIEW zu APPROVED.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-079 – Review ablehnen
- **Kurzbeschreibung:** IN_REVIEW zu DRAFT.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-080 – Approval annehmen
- **Kurzbeschreibung:** IN_APPROVAL zu APPROVED.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-081 – Approval ablehnen
- **Kurzbeschreibung:** IN_APPROVAL zu DRAFT.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-082 – APPROVED zurücknehmen
- **Kurzbeschreibung:** APPROVED zu DRAFT vor Veröffentlichung.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-083 – Workflow begründet abbrechen
- **Kurzbeschreibung:** Aktive Instanz schließen und DRAFT herstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-084 – Neue Einreichungsrunde starten
- **Kurzbeschreibung:** Nach Ablehnung erneut einreichen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-085 – Nicht tätig gewordenen Reviewer ersetzen
- **Kurzbeschreibung:** Offene Prüfung übertragen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-086 – Nicht tätig gewordenen Approver ersetzen
- **Kurzbeschreibung:** Offene Freigabe übertragen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-087 – Laufzeitregel ändern und zurückrollen
- **Kurzbeschreibung:** Betroffene Stufe neu aktivieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-088 – Fristüberschreitung markieren
- **Kurzbeschreibung:** Event ohne Statuswechsel erzeugen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-089 – Aktive Workflowinstanz anzeigen
- **Kurzbeschreibung:** Profil, Runde, Aufgaben und Entscheidungen darstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-090 – Abgeschlossene Workflowinstanz anzeigen
- **Kurzbeschreibung:** Historische Nachweise bereitstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

## Entscheidungen und Signaturen

### CAND-091 – Editor-Signatur ausführen
- **Kurzbeschreibung:** Übergangssignatur auf aktuelle PDF anwenden.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-092 – Reviewer-Signatur ausführen
- **Kurzbeschreibung:** Kumulative Signaturkette fortsetzen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-093 – Approver-Signatur ausführen
- **Kurzbeschreibung:** Finale Signaturkette erzeugen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-094 – Signatur abbrechen
- **Kurzbeschreibung:** Status unverändert lassen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-095 – Signaturfehler behandeln
- **Kurzbeschreibung:** Keine Teilentscheidung persistieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-096 – Falschen Signer blockieren
- **Kurzbeschreibung:** Konkrete Zuweisung und Identität prüfen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-097 – Teilzustimmung bei ALL_ASSIGNED speichern
- **Kurzbeschreibung:** Zwischenstand ohne Stufenwechsel dokumentieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-098 – Letzte Zustimmung bei ALL_ASSIGNED auswerten
- **Kurzbeschreibung:** Stufenwechsel atomar auslösen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-099 – Erste Ablehnung bei ALL_ASSIGNED auswerten
- **Kurzbeschreibung:** Stufe sofort ablehnen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-100 – Entscheidung widerrufen nach QMB-Regeländerung
- **Kurzbeschreibung:** Historie erhalten und Aufgabe neu öffnen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-101 – Entscheidungsdetail anzeigen
- **Kurzbeschreibung:** Actor, Zeit, Grund, Signatur und Artefakt anzeigen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

## Veröffentlichung und Gültigkeit

### CAND-102 – APPROVED veröffentlichen
- **Kurzbeschreibung:** Explizit zu PUBLISHED wechseln.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-103 – Vorgängerversion atomar archivieren
- **Kurzbeschreibung:** Doppelveröffentlichung verhindern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-104 – Finale PDF benennen
- **Kurzbeschreibung:** DocumentID_Titel.pdf erzeugen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-105 – Aktuelle PUBLISHED-Version abrufen
- **Kurzbeschreibung:** Nur gültige aktive Fassung liefern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-106 – Ablaufwarnung erzeugen
- **Kurzbeschreibung:** QMB vor valid_until informieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-107 – PUBLISHED automatisch ablaufen lassen
- **Kurzbeschreibung:** Zu EXPIRED wechseln.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-108 – Verpassten Ablauf nach Systemstillstand nachholen
- **Kurzbeschreibung:** Schedulerlücke korrigieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-109 – PUBLISHED-Gültigkeit verlängern
- **Kurzbeschreibung:** Status bleibt PUBLISHED.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-110 – EXPIRED-Gültigkeit verlängern
- **Kurzbeschreibung:** Zu PUBLISHED zurückkehren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-111 – Dritte und letzte Verlängerung durchführen
- **Kurzbeschreibung:** next_review_at danach leer lassen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-112 – Vierte Verlängerung ablehnen
- **Kurzbeschreibung:** Neue Version verlangen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-113 – Review-Ergebnis 'inhaltliche Änderung nötig' behandeln
- **Kurzbeschreibung:** Nachfolgeversion statt Verlängerung anlegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-114 – Publikation zum Grenzzeitpunkt ablehnen
- **Kurzbeschreibung:** Keine Veröffentlichung bei bereits abgelaufener Freigabe.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-115 – Aktive Version über Referenz auflösen
- **Kurzbeschreibung:** Dokumentenkennung zu PUBLISHED-Version.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

## Archivierung und Annullierung

### CAND-116 – DRAFT begründet archivieren
- **Kurzbeschreibung:** Nicht weitergeführte gelenkte Fassung historisieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-117 – Aktiven Workflow vor Archivierung beenden
- **Kurzbeschreibung:** Offene Aufgaben sauber schließen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-118 – APPROVED archivieren
- **Kurzbeschreibung:** Nicht veröffentlichte Freigabe zurückziehen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-119 – PUBLISHED als obsolet archivieren
- **Kurzbeschreibung:** Aktive Fassung bewusst entfernen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-120 – EXPIRED archivieren
- **Kurzbeschreibung:** Abgelaufene Fassung endgültig schließen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-121 – Version annullieren
- **Kurzbeschreibung:** Unzulässige konkrete Fassung terminal markieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-122 – Korrekturfassung nach Annullierung erzeugen
- **Kurzbeschreibung:** Neue technische Fassung anlegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-123 – Archivierungsgrund anzeigen
- **Kurzbeschreibung:** Historische Ursache transparent machen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-124 – Aufbewahrungsfrist setzen
- **Kurzbeschreibung:** Optionalen Prüfzeitpunkt definieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-125 – Aufbewahrungsfrist fällig melden
- **Kurzbeschreibung:** QMB-Entscheidung auslösen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-126 – Aufbewahrung verlängern
- **Kurzbeschreibung:** Fälligkeitszeitpunkt verschieben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-127 – Physische Löschung beantragen
- **Kurzbeschreibung:** Spätere Option, derzeit nicht durchführen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Optional / später
- **Auswahlstatus:** Zur Auswahl

## Kommentare

### CAND-128 – Word-Kommentare synchronisieren
- **Kurzbeschreibung:** DOCX-Kommentare in Records überführen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-129 – Word-Kommentarquelle erneut synchronisieren
- **Kurzbeschreibung:** Bestehende Quellschlüssel aktualisieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-130 – Fehlenden Word-Kommentar markieren
- **Kurzbeschreibung:** Nicht automatisch löschen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-131 – PDF-Kommentar an Seite anlegen
- **Kurzbeschreibung:** Seitenbezug speichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-132 – PDF-Kommentar mit Positionsanker anlegen
- **Kurzbeschreibung:** Anchor-JSON speichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-133 – Kommentare nach Kontext filtern
- **Kurzbeschreibung:** DOCX_EDIT/PDF_REVIEW/PDF_APPROVAL trennen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-134 – Kommentardetail öffnen
- **Kurzbeschreibung:** Volltext und Herkunft anzeigen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-135 – Kommentar erledigen
- **Kurzbeschreibung:** Status RESOLVED setzen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-136 – Kommentar reaktivieren
- **Kurzbeschreibung:** Status ACTIVE setzen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-137 – Kommentar inaktiv setzen
- **Kurzbeschreibung:** Status INACTIVE mit Grund.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-138 – Kommentar an Runde binden
- **Kurzbeschreibung:** SubmissionRound-Bezug herstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-139 – Kommentare einer abgelehnten Runde anzeigen
- **Kurzbeschreibung:** Evidence-Kontext sichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-140 – Kommentare bei neuer Version nicht kopieren
- **Kurzbeschreibung:** Versionsgrenze einhalten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-141 – Kommentarberechtigung je Workflowphase prüfen
- **Kurzbeschreibung:** Bestehende Zugriffskontrolle erhalten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-142 – Kommentar-Blockerregeln später ergänzen
- **Kurzbeschreibung:** Optionaler zukünftiger Scope.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Optional / später
- **Auswahlstatus:** Zur Auswahl

## Rollen und Berechtigungen

### CAND-143 – Documents-Modulrolle anlegen
- **Kurzbeschreibung:** Konfigurierbare Rolle definieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-144 – Aktionserlaubnis einer Modulrolle zuordnen
- **Kurzbeschreibung:** Feingranulare Permission pflegen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-145 – Modulrolle Benutzer zuweisen
- **Kurzbeschreibung:** Eligibility aktivieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-146 – Modulrolle entziehen
- **Kurzbeschreibung:** Aktive Zuweisungen vorher prüfen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-147 – QMB-Selbstzuweisung mit Adminfreigabe
- **Kurzbeschreibung:** Optionalen Schutzschalter umsetzen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-148 – Workflowstarter aus Eligible-Pool auswählen
- **Kurzbeschreibung:** Nur geeignete Benutzer anbieten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-149 – Konkrete Workflowzuweisung prüfen
- **Kurzbeschreibung:** Aktion nicht nur wegen Modulrolle erlauben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-150 – Vier-Augen-Verstoß blockieren
- **Kurzbeschreibung:** Aufeinanderfolgende Stufen prüfen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-151 – ADMIN ohne Modulrolle blockieren
- **Kurzbeschreibung:** Keine automatische Fachmacht.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-152 – Benutzerdeaktivierung bei aktiver Aufgabe blockieren
- **Kurzbeschreibung:** Ersatz verlangen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-153 – Historischen inaktiven Actor anzeigen
- **Kurzbeschreibung:** Audit darf Benutzer nicht verlieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-154 – Berechtigungsänderung auditieren
- **Kurzbeschreibung:** Wer, was, wann, warum erfassen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

## Gelenkte Kopien

### CAND-155 – Gelenkte Ausdrucke global aktivieren
- **Kurzbeschreibung:** Feature-Schalter setzen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-156 – Mehrere Kopien in einem Job drucken
- **Kurzbeschreibung:** Je Kopie Nummer vergeben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-157 – Kopienzähler je Version starten
- **Kurzbeschreibung:** Bei 1 beginnen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-158 – Kopie sichtbar kennzeichnen
- **Kurzbeschreibung:** Dokument-ID, Version, Kopiennummer darstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-159 – Druckauftrag aus anderem Modul annehmen
- **Kurzbeschreibung:** source_module protokollieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-160 – Druck ungültiger Fassung blockieren
- **Kurzbeschreibung:** Keine Nummern verbrauchen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-161 – Rückruf bei Nachfolgepublikation starten
- **Kurzbeschreibung:** Offene Kopien ermitteln.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-162 – Kopie als zurückgerufen markieren
- **Kurzbeschreibung:** Ergebnis protokollieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-163 – Kopie als vernichtet markieren
- **Kurzbeschreibung:** Ergebnis protokollieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-164 – Kopie als nicht gefunden markieren
- **Kurzbeschreibung:** Grund verpflichtend.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-165 – Rückruf gesammelt abschließen
- **Kurzbeschreibung:** Summen und Restfälle sichern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-166 – Rückruf trotz fehlender Kopie schließen
- **Kurzbeschreibung:** Begründung erfassen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-167 – Spätere Abweichung aus fehlender Kopie erzeugen
- **Kurzbeschreibung:** Noch nicht Teil des Kernumbaus.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Optional / später
- **Auswahlstatus:** Zur Auswahl

## API, Events und Integrationen

### CAND-168 – Übergangsevent für jeden Stufenwechsel publizieren
- **Kurzbeschreibung:** Uniformen Payload bereitstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-169 – Aufgabenrouting im Event transportieren
- **Kurzbeschreibung:** Zielnutzer/-pool und required_action angeben.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-170 – Legacy-v1 und Soll-v2 parallel publizieren
- **Kurzbeschreibung:** Consumer schrittweise migrieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-171 – Eventvertrag versionieren
- **Kurzbeschreibung:** Breaking Changes vermeiden.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-172 – Correlation-ID durch Workflowkette führen
- **Kurzbeschreibung:** Zusammengehörige Events verbinden.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-173 – Causation-ID setzen
- **Kurzbeschreibung:** Folgeevent auf Ursache beziehen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-174 – Subscriberfehler isolieren
- **Kurzbeschreibung:** Fachzustand nicht unkontrolliert zurückrollen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-175 – Event ohne Subscriber tolerieren
- **Kurzbeschreibung:** Fachaktion bleibt erfolgreich.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-176 – Transactional Outbox später ergänzen
- **Kurzbeschreibung:** Dauerhafte Zustellung optional vorbereiten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Optional / später
- **Auswahlstatus:** Zur Auswahl

### CAND-177 – Dashboardaufgaben aus aktuellem Zustand laden
- **Kurzbeschreibung:** Bestehendes Read-Model erhalten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-178 – Eventprojektion für Dashboard ergänzen
- **Kurzbeschreibung:** Späteren Consumer ermöglichen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-179 – Training bei Veröffentlichung informieren
- **Kurzbeschreibung:** Schulungslogik extern auslösen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-180 – Registry bei Veröffentlichung aktualisieren
- **Kurzbeschreibung:** Aktive Version projizieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-181 – Registry bei Ablauf/Archivierung aktualisieren
- **Kurzbeschreibung:** Aktive Version entfernen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-182 – API-Zugriff auf APPROVED blockieren
- **Kurzbeschreibung:** Nur PUBLISHED liefern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-183 – API-Zugriff auf EXPIRED blockieren
- **Kurzbeschreibung:** Kein normales Lesen/Drucken.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-184 – Verweigerten Zugriff eventieren
- **Kurzbeschreibung:** Audit- und Securitynachweis.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

## Audit und Nachweise

### CAND-185 – Plananlage auditieren
- **Kurzbeschreibung:** Actor und Inhalt erfassen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-186 – Metadatenkorrektur auditieren
- **Kurzbeschreibung:** Alt/Neu/Grund erfassen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-187 – Artefaktimport auditieren
- **Kurzbeschreibung:** Dateiname, Hash, Größe und Actor.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-188 – Workflowstart auditieren
- **Kurzbeschreibung:** Profil-Snapshot und Zuweisungen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-189 – Einreichung auditieren
- **Kurzbeschreibung:** Runde, Change-Scope und Artefakt.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-190 – Entscheidung auditieren
- **Kurzbeschreibung:** Actor, Ergebnis, Grund und Signatur.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-191 – Statuswechsel auditieren
- **Kurzbeschreibung:** Alt/Neu und Transition.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-192 – Publikation auditieren
- **Kurzbeschreibung:** Zeit, PDF und Vorgänger.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-193 – Verlängerung auditieren
- **Kurzbeschreibung:** Zähler, Grund und Review-Ergebnis.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-194 – Kopienausgabe auditieren
- **Kurzbeschreibung:** Job und Einzelnummern.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-195 – Kopienrückruf auditieren
- **Kurzbeschreibung:** Einzelergebnisse und Abschluss.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-196 – Berechtigungsänderung auditieren
- **Kurzbeschreibung:** Rolle und Genehmigung.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-197 – Verweigerten Zugriff auditieren
- **Kurzbeschreibung:** Actor, Zweck und Grund.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

### CAND-198 – Auditexport je Dokument erzeugen
- **Kurzbeschreibung:** Vollständige Nachweiskette zusammenstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Prüfen
- **Auswahlstatus:** Zur Auswahl

## Migration und Administration

### CAND-199 – PLANNED-Pläne migrieren
- **Kurzbeschreibung:** Bestandsstatus kontrolliert auf DocumentPlan abbilden.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-200 – IN_PROGRESS nach DRAFT migrieren
- **Kurzbeschreibung:** Statusmapping durchführen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-201 – APPROVED-Bestand klassifizieren
- **Kurzbeschreibung:** Freigegeben vs tatsächlich veröffentlicht unterscheiden.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-202 – Released-PDFs PUBLISHED zuordnen
- **Kurzbeschreibung:** Artefaktlage prüfen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-203 – Legacyprofile als Profilversionen seed-en
- **Kurzbeschreibung:** Bestehende JSON-Profile überführen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-204 – Legacyassignments Workflowinstanzen zuordnen
- **Kurzbeschreibung:** Rollenhistorie erhalten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-205 – Legacyevents mappen
- **Kurzbeschreibung:** v1/v2-Bezug dokumentieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-206 – Kommentardaten migrieren
- **Kurzbeschreibung:** Word/PDF-Records vollständig erhalten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-207 – Read-Receipts erhalten
- **Kurzbeschreibung:** Trainingsevidenz nicht verlieren.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-208 – Migrationsreport erzeugen
- **Kurzbeschreibung:** Jede automatische und manuelle Entscheidung auflisten.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-209 – Unklare Datensätze blockieren
- **Kurzbeschreibung:** Keine stille Uminterpretation.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-210 – Migration wiederaufnehmen
- **Kurzbeschreibung:** Idempotente Schritte ermöglichen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl

### CAND-211 – Rollback vor Produktivfreigabe
- **Kurzbeschreibung:** Technisches Rückfallkonzept bereitstellen.
- **Primärakteur:** System/QMB/Workflowakteur
- **Erste Einordnung:** Kernnah
- **Auswahlstatus:** Zur Auswahl
