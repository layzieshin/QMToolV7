# AP-007 MVP-Audit-Actor-Gap-Matrix

## Status
- Arbeitspaket: AP-007
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Migration: nein

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` auf `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md` zur Existenzprüfung.
  - `ReadFile` für `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`, `docs/AP-004_USER_CONTEXT_ADR.md`, `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`, `docs/AP-006_AUDIT_ACTOR_ADR.md`, `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`, `docs/MASTER_ORCHESTRATION_ROADMAP.md`, `AGENTS.md` und `.cursor/rules/00-agent-workflow.mdc`.
  - `rg` nach `actor_user_id`, `actor_role`, `emit_audit`, `audit_logger`, `AuditLogger`, `EventEnvelope.create`, `actor=`, `correlation_id`, `causation_id`, `"system"` und `"unknown"`.
  - `rg` nach `get_current_user()`, `current_user.json`, `SessionStore` und `session_file`.
  - `ReadFile` gezielter Hotspots in Documents, Incident/CAPA, Training, Usermanagement, Logging und Events.
- Geprüfte Bereiche:
  - `qm_platform/logging/*`
  - `qm_platform/events/*`
  - `modules/usermanagement/*`
  - `modules/documents/*`
  - `modules/incident_management/*`
  - `modules/training/*`
  - `interfaces/cli/*`
  - `interfaces/pyqt/*`
  - `tests/*`
  - freigegebene ADR-/Roadmap-/Regeldateien
- Ausgeschlossene Bereiche:
  - Keine absichtlich ausgeschlossenen Bereiche innerhalb des freigegebenen Scopes.
  - Phase-2-Module wurden nicht vorgezogen.
- Datum der Analyse: 2026-06-26

## Zusammenfassung
- Gesamtzahl relevanter Actor-Fundstellen: 21
- Anzahl Kategorie A: 6
- Anzahl Kategorie B: 8
- Anzahl Kategorie C: 7
- Anzahl Kategorie D: 6
- Anzahl Kategorie E: 7

Hinweis: Kategorie D zählt MVP-Gap-Zeilen je Bereich, nicht zusätzliche Code-Fundstellen. AP-003/AP-006/AP-006A wurden nicht blind kopiert; die Tabellen enthalten auditrelevante Kernstellen für MVP-Audit-Exports.

## Kategorie A — Belastbare Actor-Quellen

| Datei | Zeile | Fundstelle | Actor-Quelle | Nachweisstatus | Begründung | betroffener MVP-Bereich |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/documents/workflow_use_cases.py` | 205 | `actor_user_id: str` in `accept_review` | expliziter Service-Parameter | belastbar nach Quellklassifikation | Reviewer muss explizit übergeben werden; Service prüft Zuordnung zur Reviewer-Liste. | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 247 | `actor_user_id: str` in `reject_review` | expliziter Service-Parameter | belastbar nach Quellklassifikation | Reviewer wird als Actor und Audit-Actor genutzt; keine Zieluser-Ableitung. | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 280 | `actor_user_id: str` in `accept_approval` | expliziter Service-Parameter | belastbar nach Quellklassifikation | Approver wird explizit übergeben und gegen Zuordnung/Four-Eyes-Regel geprüft. | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 341 | `actor_user_id: str` in `reject_approval` | expliziter Service-Parameter | belastbar nach Quellklassifikation | Approver wird explizit übergeben; Actor ist nicht Zielobjekt. | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 446 | `actor_user_id: str` in `extend_annual_validity` | expliziter nicht-leerer Service-Parameter | belastbar nach Quellklassifikation | Gültigkeitsverlängerung verlangt explizit `actor_user_id`; fehlender Actor wird validiert. | Dokumentenlenkung |
| `modules/training/manual_assignment_service.py` | 23 | `grant_manual_assignment(... granted_by: str)` | expliziter Service-Parameter `granted_by` | belastbar nach Quellklassifikation | Manuelle Zuweisung trennt Zieluser (`user_id`) und ausführende Quelle (`granted_by`). | Schulung, Kompetenz & Befugnisse |

## Kategorie B — Eingeschränkte Actor-Quellen

| Datei | Zeile | Fundstelle | Actor-Quelle | Einschränkung | Risiko | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- | --- |
| `qm_platform/logging/audit_logger.py` | 15 | `emit(... actor: str, ...)` | freier Actor-String | Logger validiert Quelle nicht. | Export kann Actor belastbarer darstellen, als er ist. | Actor-Quelle vor Logging klassifizieren oder Exportstatus ergänzen. |
| `qm_platform/events/event_envelope.py` | 27 | `actor_user_id: str | None = None` | optionaler Event-Actor | Transportfeld ohne erzwungene Quelle. | Events können ohne Actor oder mit unklarer Quelle entstehen. | Event-/Audit-Kontext-Matrix definieren. |
| `modules/documents/workflow_use_cases.py` | 95 | `actor=str(actor_user_id or updated.owner_user_id or "system")` | Parameter, Owner-Fallback oder `system` | Fallback kann Ziel-/Owner- oder Systemersatz sein. | Rollen-/Workflow-Zuweisung wirkt ggf. belastbar trotz unklarer Quelle. | Documents-Fallbacks vor Export klassifizieren. |
| `modules/documents/workflow_use_cases.py` | 142 | `actor=str(actor_user_id or updated.owner_user_id or "system")` | Parameter, Owner-Fallback oder `system` | Start-Workflow erlaubt Fallback, wenn Actor fehlt. | Interaktive Aktion könnte ohne ausführenden User erscheinen. | Actor-Pflicht für auditrelevante Workflow-Starts prüfen. |
| `modules/incident_management/service.py` | 53 | `_user()` ruft `get_current_user()` | lokaler Current User | Service zieht User implizit aus Usermanagement. | CAPA/Incident-Audit hängt an lokaler Session statt explizitem Kontext. | Incident-Use-Cases in Service-Actor-Matrix aufnehmen. |
| `modules/incident_management/incident_ops.py` | 74 | `eventing.emit_audit(... actor=auth.user_id(user))` | Userobjekt aus Service-Facade | Actor ist explizit im Ops-Aufruf, Quelle aber upstream implizit. | Incident-Meldungen eingeschränkt bis UserContext/Request-Kontext geklärt ist. | Quelle an Servicegrenze klären. |
| `qm_platform/logging/log_backup_service.py` | 34 | `actor: str = "system"` | System-Fallback | Nur belastbar, wenn Backup system-/jobinitiiert ist. | Userausgelöste Backups könnten als System erscheinen. | System-Actor-Policy und Namensschema entscheiden. |
| `modules/training/api.py` | 146 | `current_user = self._um.get_current_user()` | lokaler Current User für Training-Admin | Training-Admin-Operationen verwenden impliziten Current User. | Schulungs-/Befugnisnachweise eingeschränkt bis expliziter Kontext vorliegt. | Training-Use-Cases in Actor-Matrix aufnehmen. |

## Kategorie C — Legacy oder nicht belastbar

| Datei | Zeile | Fundstelle | nicht belastbarer Mechanismus | Risiko für MVP-Audit-Export | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- |
| `modules/usermanagement/user_admin_ops.py` | 51 | `actor_user_id=user.user_id` bei Useranlage | Zieluser als Actor | Adminanlage/Selbstregistrierung kann falschen ausführenden Actor zeigen. | Zieluser als Target/Subject trennen; Selbstregistrierung separat entscheiden. |
| `modules/usermanagement/user_admin_ops.py` | 164 | `actor_user_id=updated.user_id` bei QMB-Flag-Änderung | geänderter User als Actor | QMB-/Rollenänderung kann geänderten User statt ausführenden Admin/QMB ausweisen. | Vor belastbarem Export als Gap markieren. |
| `modules/usermanagement/user_admin_ops.py` | 225 | `actor_user_id = user[0] if user else None` bei Passwortänderung | Zieluser oder fehlender Actor | Passwortänderung trennt ausführenden Actor nicht sicher vom betroffenen User. | Passwort-Use-Case semantisch klären. |
| `modules/documents/comment_extractors/docx_comment_reader.py` | 99 | `author_token = ... or "unknown"` | `unknown` als Import-Autor-Fallback | Import-/DOCX-Autor darf nicht als Audit Actor erscheinen. | Als Import-Metadatum/legacy markieren. |
| `interfaces/gui/main.py` | 48 | `return self.usermanagement.get_current_user()` | Legacy-GUI-Current-User-Quelle | Legacy/Test-Pfad kann Actor über lokale Session liefern. | Legacy separat ausweisen, nicht als Zielzustand nutzen. |
| `interfaces/pyqt/contributions/training_sections/user_actions_section.py` | 99 | `actor_user_id=current_user.user_id` | GUI-Adapterzustand aus `get_current_user()` | Training-Read-/Comment-Flows bekommen Actor aus lokaler GUI-Session. | Später über UserContext/Servicegrenze absichern. |
| `modules/documents/pdf_read_tracking_service.py` | 99 | `EventEnvelope.create(... payload=payload)` ohne Actor | kein Actor im Read-Tracking-Event | Lesebestätigung/Read-Session-Event ist für Nachweispaket nicht voll actor-belastbar. | Read-Receipt-Actor-Anforderung separat prüfen. |

## Kategorie D — MVP-Use-Case-Gaps

| MVP-Bereich | betroffener Use Case oder Flow | aktueller Actor-Status | Gap | Blocker für belastbaren Audit-Export: ja/nein/offen | spätere Behandlung |
| --- | --- | --- | --- | --- | --- |
| Dokumentenlenkung | Workflow-Rollen, Start/Abort/Archivierung mit optionalem Actor und Fallbacks | eingeschränkt | Teilweise `owner_user_id`/`system`-Fallback statt zwingendem ausführendem Actor. | offen/ja für voll belastbare Exporte | Documents-Actor-Parameter-Matrix erstellen. |
| Lesebestätigung / Kenntnisnahme | Read-Session/Receipt-Events | legacy/eingeschränkt | Event kann ohne `actor_user_id` entstehen; Receipt enthält User, aber Actor-Nachweis ist nicht explizit. | ja | Read-Receipt-Actor-Anforderung definieren. |
| Schulung, Kompetenz & Befugnisse | Training-Admin, manuelle Zuweisung, User-Actions | gemischt | Manuelle Zuweisung explizit, andere Training-Admin-Flows über `get_current_user()`. | offen | Training-Actor-Status je Use Case klassifizieren. |
| Aufgaben- und Fristenmanagement | Aufgaben-/Fristenmodul noch nicht detailliert vorhanden | offen | Actor-Anforderung für Zuweisung, Abschluss und Eskalation noch nicht spezifiziert. | offen | Bei MVP-Schnitt Actor/Target-Semantik vorziehen. |
| Fehler / Abweichungen / CAPA light | Incident, CAPA, Wirksamkeitsprüfung | eingeschränkt | Ops nutzen `auth.user_id(user)`, aber Service-Facade zieht User implizit aus `get_current_user()`. | ja für Backend/Multiuser-Export | Incident/CAPA-Service-Kontext vorbereiten. |
| Audit-Export / Nachweispaket | Zusammenführung von AuditLogger/EventEnvelope/Readmodels | eingeschränkt/legacy | Freie Actor-Strings, unterschiedliche Actor-Felder, fehlende Quelle/Status, teils fehlende Correlation/Causation. | ja | Export darf Status `belastbar/eingeschränkt/legacy` nicht verschweigen. |

## Kategorie E — Supervisor-Entscheidung nötig

| Datei | Zeile | Fundstelle | Grund der Unklarheit | benötigte Entscheidung |
| --- | ---: | --- | --- | --- |
| `modules/documents/workflow_use_cases.py` | 95 | `actor_user_id or updated.owner_user_id or "system"` | Unklar, ob Owner-Fallback fachlich als ausführender Actor gelten darf. | Owner-Fallback als Actor verbieten, erlauben oder legacy markieren. |
| `modules/documents/workflow_use_cases.py` | 435 | `actor=str(actor_user_id or "system")` | Archivierung kann ohne Actor als `system` erscheinen. | Klären, ob Archivierung immer menschlichen Actor braucht. |
| `modules/usermanagement/user_admin_ops.py` | 51 | `actor_user_id=user.user_id` | Selbstregistrierung vs. Adminanlage nicht unterscheidbar genug. | Actor/Target-Regel je Usermanagement-Use-Case. |
| `qm_platform/logging/log_backup_service.py` | 34 | `actor: str = "system"` | Backup kann system- oder userinitiiert sein. | System-Actor-Policy für Backups. |
| `qm_platform/events/event_envelope.py` | 35 | `correlation_id=correlation_id or str(uuid4())` | Correlation existiert, wird aber bei fehlender Übergabe neu erzeugt. | Entscheiden, ob Correlation für Audit-Export Pflicht und durchgereicht sein muss. |
| `modules/documents/comment_extractors/docx_comment_reader.py` | 99 | `or "unknown"` | DOCX-Autor ist Importmetadatum, kann aber in Exporten missverstanden werden. | Darstellung von Legacy-/Import-Autoren festlegen. |
| `tests/*` | diverse | Fake-User, `actor_user_id="system"`, Actor-Strings | Testnähe nicht automatisch produktiv relevant. | Test-/Legacy-Policy aus AP-002A anwenden. |

## Kritischste Gaps
1. `modules/usermanagement/user_admin_ops.py:51`: Useranlage nutzt Zieluser als Actor; blockiert belastbare Admin-/Userverwaltungsnachweise.
2. `modules/usermanagement/user_admin_ops.py:164`: QMB-Flag-Änderung nutzt geänderten User als Actor; kritisch für Rollen-/QMB-Nachweise.
3. `modules/incident_management/service.py:53`: Incident/CAPA bezieht Actor implizit über `get_current_user()`; blockierend für Backend/Multiuser-Nachweise.
4. `modules/documents/pdf_read_tracking_service.py:99`: Read-Tracking-Event ohne Actor; kritisch für Lesebestätigung/Nachweispaket.
5. `modules/documents/workflow_use_cases.py:95`: Documents-Rollenvergabe mit Owner-/System-Fallback; potenziell nicht belastbar.
6. `modules/documents/workflow_use_cases.py:435`: Archivierung kann als `system` erscheinen; Auditfrage bei fachlicher Archivierung.
7. `qm_platform/logging/audit_logger.py:15`: Freier Actor-String ohne Quellenvalidierung; übergreifendes Export-Risiko.
8. `qm_platform/events/event_envelope.py:27`: Event-Actor optional; fehlende Actor-Felder können in Nachweisketten auftreten.
9. `modules/documents/comment_extractors/docx_comment_reader.py:99`: `unknown`-Importautor muss als Metadatum, nicht Actor, markiert werden.
10. `modules/training/api.py:146`: Training-Admin-Use-Cases hängen an implizitem Current User; relevant für Kompetenz-/Befugnisnachweise.

## Offene Supervisor-Entscheidungen
- Darf `owner_user_id` jemals als Actor-Fallback gelten, oder ist das immer eingeschränkt/legacy?
- Welche Documents-Workflow-Aktionen müssen zwingend einen expliziten Actor haben?
- Wie werden Useranlage, Selbstregistrierung, Passwortänderung und QMB-Flag-Änderung zwischen Actor und Target getrennt?
- Welche System-Actor-Fälle sind für Backups, Lifecycle-Events und technische Jobs im MVP zulässig?
- Sind `correlation_id` und `causation_id` für MVP-Audit-Exports Pflicht oder nur empfohlen?
- Wie werden `unknown` und Import-/DOCX-Autoren in Nachweispaketen gekennzeichnet?
- Welche Test-/Legacy-Funde dürfen ignoriert, markiert oder später bereinigt werden?

## Vorschlag für spätere Paketierung

| Paketname | Ziel | Scope | Risiko | erforderliche Vorentscheidung |
| --- | --- | --- | --- | --- |
| Audit-Actor-Fundklassifikation MVP-Use-Cases | Alle MVP-Use-Case-Actorquellen mit `belastbar/eingeschränkt/legacy` auf vollständige Matrix bringen. | Documents, Read-Receipt, Training, Incident/CAPA, Usermanagement, AuditLogger/EventEnvelope. | niedrig bis mittel, rein analytisch möglich. | Nachweisstatus-Vokabular bestätigen. |
| Service-Actor-Parameter-Matrix | Je Service-Use-Case Actor, Target/Subject, System Actor und Correlation/Causation definieren. | Zuerst Documents und Incident/CAPA, danach Training/Read-Receipt. | mittel, weil spätere API-/Servicegrenzen vorbereitet werden. | Actor/Target-Regeln und System-Actor-Policy. |
| Kleinstes Implementierungsvorbereitungspaket Audit Actor | Für genau einen MVP-Use-Case Implementierungsplan mit Tests/Gates vorbereiten, ohne direkt umzusetzen. | Kandidat: Read-Receipt oder Usermanagement-QMB-Flag, je nach Supervisorpriorität. | mittel, weil API-/Service-Signaturen berührt werden könnten. | Separate Freigabe für Implementierungsvorbereitung und gewählten Use Case. |

Keines dieser Pakete ist mit AP-007 gestartet.

## Auswirkungen auf Audit-Export / Nachweispaket
- Bereits tragfähig wirkt:
  - Einige Documents-Workflow-Aktionen mit verpflichtendem `actor_user_id` und Service-Prüfung, insbesondere Review/Approval und Gültigkeitsverlängerung, sofern die Quelle später als belastbar klassifiziert wird.
  - Training-Manuelle-Zuweisung trennt Zieluser und `granted_by` grundsätzlich nachvollziehbar.
- Eingeschränkt bleibt:
  - AuditLogger als freier Actor-String.
  - EventEnvelope mit optionalem `actor_user_id`.
  - Documents-Fallbacks auf Owner/System.
  - Incident/CAPA über implizites `get_current_user()`.
  - Training-Admin-Flows über implizites `get_current_user()`.
- Vor belastbarem Export zwingend zu adressieren:
  - Zieluser-as-Actor in Usermanagement-Events.
  - Read-Tracking/Lesebestätigung ohne expliziten Actor im Event.
  - Darstellung von `unknown` und Import-Autoren als Legacy-/Metadatum.
  - Nachweisstatus in Exporten, damit eingeschränkte/legacy Actor nicht als voll belastbar erscheinen.

## Ausgeführte Gates
- Such-/Analysekommandos:
  - `Glob` Existenzprüfung für `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md` -> Datei existierte nicht.
  - `ReadFile` der freigegebenen ADR-/Roadmap-/Regeldateien -> erfolgreich.
  - `rg`-Suchen nach Actor-/Audit-/Event-/Current-User-Mustern -> erfolgreich.
  - `ReadFile` zentraler Hotspots in Documents, Incident/CAPA, Training, Usermanagement, Logging und Events -> erfolgreich.
- Ergebnis:
  - Gap-Matrix erstellt.
  - Keine Testsuite ausgeführt, weil AP-007 ein Analyse-/Inventarpaket ist.
  - Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein rein analytisches Paket `Audit-Actor-Fundklassifikation MVP-Use-Cases` freigegeben wird; keine Implementierung automatisch starten.
