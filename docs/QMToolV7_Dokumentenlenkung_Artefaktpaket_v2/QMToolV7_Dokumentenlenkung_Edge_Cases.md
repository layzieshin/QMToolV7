# QMToolV7 – Edge-Case-Katalog Dokumentenlenkung

**Stand:** 2026-08-03
**Zweck:** Test- und Designcheckliste für die ausgewählten Use Cases.

**Umfang:** 96 Edge Cases.

| ID | Bereich | Edge Case | Risiko | Erwartetes Verhalten | Testart | Kritikalität |
|---|---|---|---|---|---|---|
| EDGE-001 | Planung | Plan wird parallel zweimal konvertiert | Doppelte Dokumentidentität/Version | Nur eine Konvertierung gewinnt; zweite erhält Konflikt, Plan wird nicht doppelt gelöscht. | Hoch | Concurrency |
| EDGE-002 | Planung | Planlöschung scheitert nach Dokumenterzeugung | Plan und Dokument gleichzeitig sichtbar | Gesamttransaktion zurückrollen oder idempotent als bereits konvertiert markieren. | Hoch | Transaktion |
| EDGE-003 | Kennung | Zwei Benutzer fordern gleichzeitig nächste freie Kennung an | Doppelte Kennung | DB-Unique + Reservierung; Verlierer erhält neue Auswahl. | Hoch | Concurrency |
| EDGE-004 | Kennung | Nie eingereichter DRAFT wird verworfen, während ein zweiter Prozess ihn einreicht | Kennung fälschlich freigegeben | Optimistic locking; genau eine Aktion erfolgreich. | Hoch | Concurrency |
| EDGE-005 | Kennung | Legacykennung verletzt neues Format | Bestandsverlust oder stilles Umschreiben | Als Legacy-Ausnahme mit Audit übernehmen, nicht automatisch umbenennen. | Hoch | Migration |
| EDGE-006 | Version | Zwei Nachfolgeversionen werden parallel angelegt | Mehr als eine offene Version | DB-Invariante und Konfliktfehler. | Hoch | Concurrency |
| EDGE-007 | Version | Nachfolgeversion wird aus falschem historischen DOCX erzeugt | Falscher Inhalt | Basisversion und Artefakt-ID explizit prüfen/protokollieren. | Hoch | Fachregel |
| EDGE-008 | Version | ANNULLED-Korrekturfassung nutzt gleiche sichtbare Nummer | Eindeutigkeitskonflikt | Eindeutigkeit auf technischer ID; sichtbare Nummer plus Fassungstyp zulassen. | Hoch | Datenmodell |
| EDGE-009 | Version | Titeländerung nach PUBLISHED versucht | Unkontrollierte Inhaltsänderung | Blockieren; neue Version verlangen. | Hoch | Statusregel |
| EDGE-010 | Änderungen | Änderungseintrag wird während Einreichung parallel bearbeitet | Eingefrorener Scope inkonsistent | Version/ETag prüfen; Einreichung bei Konflikt abbrechen. | Hoch | Concurrency |
| EDGE-011 | Änderungen | Kein Änderungseintrag bei Version >1 | Unklarer Revisionsgrund | Einreichung blockieren oder bewusste 'keine inhaltliche Änderung'-Erklärung verlangen. | Mittel | Fachregel |
| EDGE-012 | Artefakte | DOCX-Dateiendung korrekt, Inhalt beschädigt | Konvertierungsfehler | Import prüfen; Fehler ohne Statusänderung und ohne aktuelles Artefakt. | Hoch | Validierung |
| EDGE-013 | Artefakte | PDF hat falschen MIME-Type oder ist verschlüsselt | Nicht verarbeitbares Fremddokument | Import ablehnen oder explizite Kompatibilitätsprüfung verlangen. | Mittel | Validierung |
| EDGE-014 | Artefakte | Dateispeicherung erfolgreich, DB-Commit scheitert | Verwaiste Datei | Aufräumen oder als orphan markieren; keine fachliche Referenz. | Hoch | Transaktion |
| EDGE-015 | Artefakte | DB-Commit erfolgreich, Datei fehlt | Unbrauchbarer Dokumentstand | Transaktion so schneiden, dass Artefakt vor Commit verifiziert ist; Recovery-Alarm. | Hoch | Transaktion |
| EDGE-016 | Artefakte | Hash identisch, Dateiname anders | Doppelimport | Fachlich erlauben oder als identische Quelle erkennen; keine stille Ersetzung. | Niedrig | Idempotenz |
| EDGE-017 | Workflow | Workflowstart mit leerem erforderlichem Pool | Unbearbeitbarer Workflow | Start vollständig blockieren. | Hoch | Validierung |
| EDGE-018 | Workflow | Zugewiesener Benutzer besitzt Modulrolle beim Start, verliert sie vor Aktion | Unberechtigte Entscheidung | Entzug vorher blockieren oder Zuweisung atomar ersetzen. | Hoch | Autorisierung |
| EDGE-019 | Workflow | Benutzer wird während Signatur deaktiviert | Unklare Identität | Vor Commit erneut Autorisierung/Aktivstatus prüfen. | Hoch | Concurrency |
| EDGE-020 | Workflow | Gleiche Person ist Editor und Reviewer bei Vier-Augen | Regelverletzung | Zuweisung möglich, aber konkrete aufeinanderfolgende Aktion blockieren. | Hoch | Autorisierung |
| EDGE-021 | Workflow | Gleiche Person ist Editor und Approver, Reviewer war andere Person | Regel zulässig? | Nach beschlossener Regel zulassen, da nicht unmittelbar aufeinanderfolgend. | Mittel | Fachregel |
| EDGE-022 | Workflow | ALL_ASSIGNED: letzter Zustimmer und gleichzeitige Ablehnung | Widersprüchlicher Stufenabschluss | Serialisieren; erste persistierte finale Entscheidung entscheidet, zweite Konflikt. | Hoch | Concurrency |
| EDGE-023 | Workflow | ONE_OF_POOL: zwei Zustimmungen nahezu gleichzeitig | Doppelte Übergänge/Events | Nur erste erfüllt Übergang; zweite als bereits abgeschlossen ablehnen/idempotent behandeln. | Hoch | Concurrency |
| EDGE-024 | Workflow | Review wird akzeptiert, PDF-Artefakterzeugung scheitert | Status ohne nächste Beweisfassung | Kein Statuswechsel; Entscheidung nicht finalisieren. | Hoch | Transaktion |
| EDGE-025 | Workflow | Ablehnung ohne Grund | Unvollständiger Nachweis | Ablehnung blockieren. | Hoch | Validierung |
| EDGE-026 | Workflow | Workflow wird archiviert, während Reviewer entscheidet | Historie/Statuskonflikt | Optimistic locking; eine Aktion gewinnt, andere erhält Konflikt. | Hoch | Concurrency |
| EDGE-027 | Workflow | QMB ändert Reviewerpool nach bereits erfolgter Reviewentscheidung | Unklare Rückwirkung | Nur mit definierter revoke_if_changed-Regel; sonst Änderung blockieren. | Hoch | Fachregel |
| EDGE-028 | Workflow | Profilversion wird deaktiviert, während Instanz läuft | Laufender Workflow unbrauchbar | Snapshot bleibt wirksam; Deaktivierung nur für neue Instanzen. | Hoch | Invariante |
| EDGE-029 | Workflow | Profil enthält zyklischen/ungültigen Übergang | Endlosschleife | Profilvalidierung blockiert Aktivierung. | Hoch | Validierung |
| EDGE-030 | Workflow | Direktpfad DRAFT→APPROVED ohne Approverrolle konfiguriert | Unklare Entscheidung | Profil muss definieren, wer den Übergang ausführt; sonst ungültig. | Hoch | Profilregel |
| EDGE-031 | Workflow | Stufenfrist wird nach Überschreitung verlängert | Doppeltes/überholtes Event | Neuen Friststand versionieren; alte Überschreitung bleibt historisch. | Mittel | Event |
| EDGE-032 | Workflow | Scheduler war mehrere Tage aus | Verpasste Deadline-/Expiry-Events | Beim Start alle fälligen Zustände idempotent nachholen. | Hoch | Recovery |
| EDGE-033 | Signatur | Benutzer bricht Signaturdialog ab | Teilstatus | Status und Entscheidungen unverändert; temporäre PDF ggf. bereinigen. | Hoch | Fehlerpfad |
| EDGE-034 | Signatur | Signaturdatei erzeugt, danach Statuscommit scheitert | Verwaiste signierte PDF | Nicht als current markieren; Recovery/Aufräumen. | Hoch | Transaktion |
| EDGE-035 | Signatur | Falsches Ausgangsartefakt wird signiert | Ungültige Kette | Artifact-ID/Hash gegen erwartete Kette prüfen. | Hoch | Integrität |
| EDGE-036 | Signatur | Signaturmodul liefert Erfolg, Datei fehlt | Falscher Erfolgsstatus | Übergang abbrechen; Datei/Hash zwingend verifizieren. | Hoch | Integrität |
| EDGE-037 | Publikation | Zwei QMB veröffentlichen zwei Versionen gleichzeitig | Zwei PUBLISHED-Versionen | DB-Invariante/Transaktion verhindert Doppelaktivität. | Hoch | Concurrency |
| EDGE-038 | Publikation | Vorgängerarchivierung scheitert nach neuer Publikation | Zwei aktive Fassungen | Gesamttransaktion zurückrollen. | Hoch | Transaktion |
| EDGE-039 | Publikation | valid_until ist exakt jetzt | Grenzfall aktiv/abgelaufen | Einheitliche Regel: valid_from <= now < valid_until; Publikation ablehnen. | Hoch | Zeitregel |
| EDGE-040 | Publikation | Finale PDF fehlt oder Hash stimmt nicht | Öffentliche Fassung unbrauchbar | Publikation blockieren. | Hoch | Integrität |
| EDGE-041 | Publikation | Trainingsconsumer fehlt | Keine Schulungsaufgabe | Publikation bleibt fachlich gültig; Eventvertrag vorhanden; spätere Projektion möglich abschließen oder muss klaren Recovery-Status setzen | Transaktion | Hoch |
| EDGE-042 | Review | Reviewer kommentiert falsches PDF-Artefakt | Kommentar falsch zugeordnet | Artefakt muss zur aktiven Runde/Stufe gehören | Validierung | Hoch |
| EDGE-043 | Approval | Approver akzeptiert, finale Signatur fehlt | Unvollständige Freigabe | Kein APPROVED-Übergang | Invariante | Hoch |
| EDGE-044 | Approval | Approval wird abgeschlossen, valid_until liegt bereits in Vergangenheit | Nicht publizierbar | APPROVED darf entstehen, Publish später blockiert; Regel klar testen | Businessregel | Mittel |
| EDGE-045 | APPROVED | QMB veröffentlicht und nimmt gleichzeitig zurück | Race | Genau eine Aktion gewinnt; nach Publish keine Rücknahme zu DRAFT | Concurrency | Hoch |
| EDGE-046 | Publikation | Zwei Nachfolgeversionen versuchen gleichzeitig zu publishen | Doppel-PUBLISHED | Unique Invariante; genau eine Transaktion gewinnt | Concurrency | Hoch |
| EDGE-047 | Publikation | Vorgängerarchivierung scheitert | Zwei aktive Fassungen | Gesamte Publikation zurückrollen | Transaktion | Hoch |
| EDGE-048 | Publikation | Released-PDF-Kopie scheitert | PUBLISHED ohne Datei | Gesamte Publikation zurückrollen | Transaktion | Hoch |
| EDGE-049 | Publikation | valid_until entspricht exakt now | Grenzfall | Nicht veröffentlichen; Intervall halb-offen now < valid_until | Zeitgrenze | Hoch |
| EDGE-050 | Publikation | Titel enthält unzulässige Dateinamenzeichen | Dateierzeugung schlägt fehl oder Dateiname ist unsicher | Definiertes, reproduzierbares Dateinamensmapping verwenden; fachlicher Titel bleibt unverändert. | Integration | Mittel |
| EDGE-051 | Kommentare | Word-Sync wird zweimal mit unveränderter DOCX ausgeführt | Doppelte Kommentare | Upsert über stabilen source_comment_key; idempotent. | Hoch | Idempotenz |
| EDGE-052 | Kommentare | Word ändert interne Kommentar-ID nach Dateiüberarbeitung | Alter und neuer Kommentar doppelt | Heuristik nicht still anwenden; als neuer Kommentar plus Quellabweichung markieren. | Mittel | Datenqualität |
| EDGE-053 | Kommentare | Word-Kommentar wurde in DOCX gelöscht | Auditverlust | Record nicht löschen; als source_missing/inactive prüfen. | Hoch | Historie |
| EDGE-054 | Kommentare | Word-Autor ist 'unknown' | Quellautor könnte fälschlich als Audit-Actor behandelt werden | Als unbestätigte Quellmetadaten speichern; synchronisierenden Benutzer als Audit-Actor führen. | Audit | Mittel |
| EDGE-055 | Gültigkeit | EXPIRED hat bereits aktuelle PUBLISHED-Nachfolge | Alte Fassung wieder aktiv | Verlängerung zu PUBLISHED blockieren | Invariante | Hoch |
| EDGE-056 | Archivierung | Version mit aktivem Workflow wird direkt archiviert | Offene Aufgaben | Abbruch und automatisch umhängen. | Hoch | Artefaktbezug |
| EDGE-057 | Kommentare | Kommentarstatus wird parallel geändert | Verlorenes Update | Optimistic locking und Konfliktmeldung. | Mittel | Concurrency |
| EDGE-058 | Kommentare | Kommentar einer alten Runde wird in neuer Runde als aktiv angezeigt | Falsche Aufgabe | Runden-/Artefaktkontext klar filtern; Historie separat anzeigen. | Hoch | Fachregel |
| EDGE-059 | Kommentare | Historischenullierung während Dateiübertragung | Datei eventuell ausgeliefert | Statusprüfung vor und nach Auflösung/Cachingstrategie | Security | Hoch |
| EDGE-060 | Kommentare | Word-Sync liefert denselben Quellschlüssel zweimal | Duplikate | Deterministisch ablehnen/zusammenführen und Fehler melden | Validierung | Mittel |
| EDGE-061 | Kommentare | Word-Autor fehlt oder ist 'unknown' | Actorverwechslung | Als Quellmetadatum markieren, nicht als Audit-Actor | Audit | Mittel |
| EDGE-062 | Kommentare | Word-Kommentar wurde gelöscht | Historie verschwindet | Record nicht löschen; als source_missing/inaktiv markieren oder unverändert historisch halten | Businessregel | Hoch |
| EDGE-063 | Kommentare | Word-Kommentar-ID ändert sich nach Office-Speichern | Scheinbares Duplikat | Heuristik Fachtransaktion korrumpieren. | Hoch | Robustheit |
| EDGE-064 | Events | Doppeltes Event wird verarbeitet | Doppelte Dashboardaufgabe | Consumer idempotent über event_id/Business-Key. | Hoch | Idempotenz |
| EDGE-065 | Events | v1 und v2 werden parallel publiziert | Doppelte Reaktion | Consumer-Versionen klar trennen; keine doppelte Projektion. | Mittel | Migration |
| EDGE-066 | Events | Eventpayload enthält veraltete Assignments | Aufgabe an falschen Benutzer | Payload aus committed Snapshot erzeugen. | Hoch | Konsistenz |
| EDGE-067 | Events | Correlation-ID wechselt innerhalb einer Publikationstransaktion | Nachweiskette bricht | Gleiche correlation_id für Publish, Vorgängerarchiv, Recall. | Mittel | Audit |
| EDGE-068 | Events | Eventname beschreibt Übergang, to_status stimmt nicht | Consumerfehler | Schema-/Invariantentest je Event. | Hoch | Vertrag |
| EDGE-069 | Dashboard | Eventconsumer war beim Übergang nicht aktiv | Aufgabe fehlt in Projektion | Bestehende State-based Read-API liefert Aufgabe trotzdem. | Hoch | Readmodel |
| EDGE-070 | Dashboard | Benutzer hat Modulrolle, aber keine konkrete Zuweisung | Zu viele Aufgaben | Nur konkret zugewiesene Workflowaufgaben anzeigen. | Hoch | Autorisierung |
| EDGE-071 | Dashboard | QMB sieht alle Aufgaben oder nur Eskalationen | Unklarer Scope | Fachregel im Read-Model explizit festlegen; nicht aus ADMIN ableiten. | Mittel | Fachregel |
| EDGE-072 | Kopien | Zwei Druckjobs vergeben gleiche Kopiennummer | Doppelte Papierkopie-ID | DB-Unique je Version und atomarer Zähler. | Hoch | Concurrency |
| EDGE-073 | Kopien | Druck scheitert nach Nummernvergabe | Nummernlücke/unklare Kopie | Jobstatus FAILED; Policy: Nummer bleibt als nicht ausgegeben oder Transaktion vor Ausgabe schneiden. | Hoch | Transaktion |
| EDGE-074 | Kopien | Version läuft zwischen Prüfung und Ausgabe ab | Ungültige Kopie | Status in derselben Transaktion/kurz vor Ausgabe erneut prüfen. | Hoch | Zeitregel |
| EDGE-075 | Kopien | Rückruf wird abgeschlossen, obwohl Kopie unbearbeitet ist | Falscher Abschluss | Nur erlauben, wenn jede Kopie Ergebnis hat oder explizite Sammelbegründung vorliegt. | Hoch | Validierung |
| EDGE-076 | Kopien | Kopie nicht gefunden ohne Grund | Unvollständiger Nachweis | Abschluss blockieren. | Hoch | Validierung |
| EDGE-077 | Berechtigung | ADMIN führt Fachaktion ohne Modulrolle aus | Umgehung | Service blockiert unabhängig von GUI. | Hoch | Autorisierung |
| EDGE-078 | Berechtigung | QMB entzieht sich selbst die letzte notwendige Modulrolle | Modul könnte fachlich nicht mehr administrierbar sein | Optionalen Admin-Freigabeschutz anwenden oder Entzug blockieren, solange kein anderer QMB die Funktion besitzt. | Autorisierung | Mittel |
| EDGE-079 | API | Direkte Artefakt-ID umgeht aktive Dokumentprüfung | Security Bypass | Öffentliche API prüft Kontext; interne QMB-API getrennt | Security | Hoch |
| EDGE-080 | API | Cache liefert nach Ablauf alte PDF | Ungültiger Zugriff | Cache invalidieren/kurze TTL und Statusprüfung | Security | Hoch |
| EDGE-081 | API | Consumer fragt konkrete alte Versionsnummer an | Historische Offenlegung | Öffentliche aktive API verweigert; separate Audit-API nur berechtigt | Autorisierung | Hoch |
| EDGE-082 | Events | Fachtransaktion rollt zurück, Event wurde vorher publiziert | Geisterevent | Event erst nach Commit oder Outbox verwenden | Transaktion | Hoch |
| EDGE-083 | Events | Commit erfolgreich, Prozess stirbt vor Publish | Fehlendes Event | Aktueller Bus kann dies nicht garantieren; Outbox als spätere Lösung dokumentieren | Delivery | Hoch |
| EDGE-084 | Events | Subscriber wirft Ausnahme | Fachaktion/andere Consumer betroffen | Fehler isolieren oder klare Publish-Policy; Fachzustand nicht inkonsistent machen | Robustheit | Hoch |
| EDGE-085 | Events | Dasselbe Event wird erneut zugestellt | Doppelte Aufgabe | Consumer idempotent via event_id/idempotency_key | Idempotenz | Hoch |
| EDGE-086 | Events | Eventpayload enthält deaktivierten target_user | Unzustellbare Aufgabe | Read-Model/Consumer prüft aktuelle Zulässigkeit und QMB erhält Ausnahme | Businessregel | Mittel |
| EDGE-087 | Events | Legacy-v1 und v2 erzeugen doppelte Consumerwirkung | Doppelte Aufgabe | Consumer-Migrationsflag/Idempotenz und correlation_id | Migration | Hoch |
| EDGE-088 | Events | Correlation-ID wechselt innerhalb einer Einreichungsrunde | Nachweiskette bricht | Request-/Workflowkontext konsequent weiterreichen | Audit | Mittel |
| EDGE-089 | Migration | PLANNED-Datensatz enthält bereits Artefakte/Workflowdaten | Kein einfacher Plan | Als Ausnahme reporten; nicht still in DocumentPlan verschieben | Migration | Hoch |
| EDGE-090 | Migration | APPROVED-Bestand hat Released-PDF und wurde praktisch veröffentlicht | Status unklar | Regelbasierter Report und manuelle Bestätigung, keine stille Annahme | Migration | Hoch |
| EDGE-091 | Migration | APPROVED-Bestand hat kein finales PDF | Unvollständiger Datensatz | Nicht zu PUBLISHED migrieren; Fehlerliste | Migration | Hoch |
| EDGE-092 | Migration | Mehrere APPROVED-Versionen erscheinen aktiv | Invariante verletzt | Migration stoppen/Datensatz manuell klären | Migration | Hoch |
| EDGE-093 | Migration | Legacykommentar verweist auf fehlende Version | Orphan | Erhalten und als Migrationsabweichung markieren | Migration | Mittel |
| EDGE-094 | Migration | Legacyevent hat Actor 'system' statt echten Benutzer | Auditqualität | Quellstatus erhalten; nicht als belastbaren menschlichen Actor ausgeben | Migration | Mittel |
| EDGE-095 | Migration | Migration wird nach Teilerfolg erneut gestartet | Duplikate | Idempotente Marker und Wiederaufnahme | Recovery | Hoch |
| EDGE-096 | Migration | Neue Version und alter Client schreiben parallel | Schema-/Semantikmix | Kompatibilitätsfenster und Feature-Gate; keine halb migrierten Use Cases | Migration | Hoch |
