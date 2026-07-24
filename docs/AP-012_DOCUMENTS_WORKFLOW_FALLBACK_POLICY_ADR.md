# AP-012 Documents-Workflow-Fallback-Policy ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Migration: nein

## Kontext
- Bezug auf AP-009: `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md` identifiziert optionale Documents-Workflow-Actor und Fallback-Ketten auf Owner/`system` als zentrale Gaps in Rollenvergabe, Workflow-Start, Editing-Abschluss, Abbruch, Archivierung und DOCX->PDF-Erzeugung.
- Bezug auf AP-010: `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md` trennt Read-Receipt-Actor, Zieluser und System Actor und verbietet Owner, Zieluser, GUI-/CLI-Zustand, lokale Current-User-Quelle und `unknown` als belastbare Actor-Ersatzquellen.
- Bezug auf AP-011: `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` zeigt, dass Review/Approval/Gültigkeitsverlängerung teilweise tragfähige explizite Actor-Felder besitzen, während Workflow-Rollen, Start, Editing, Abort, Archivierung, Kommentar-/DOCX-Sync und technische Artefaktfolgeprozesse eingeschränkt oder legacy bleiben.
- MVP-Audit-Export-/Nachweispaket-Relevanz: Workflow-Ereignisse in der Dokumentenlenkung sind audit- und nachweisnah. Exporte dürfen Fallback-Actor nicht belastbarer darstellen, als ihre Quelle erlaubt.
- Geltende Architekturregeln:
  - Audit Actor darf nicht aus Zieluser, Owner-Fallback, GUI/CLI-Zustand, lokalem Current User oder `unknown` als belastbarer Nachweis entstehen.
  - `system` ist nur für echte systeminitiierte Vorgänge zulässig.
  - Services bleiben fachliche Grenze für auditrelevante Documents-Use-Cases.
  - GUI, CLI und Backend dürfen Kontext transportieren oder anzeigen, aber nicht final fachlich bestimmen.
  - Diese ADR ist ein reines Dokumentations-/Entscheidungspaket; keine Implementierung, keine API-Änderung, keine Event-Schema-Änderung und keine Migration.

## Begriffe
- **Workflow-Actor**: Die Identität, die einen Documents-Workflow-Schritt fachlich ausführt, z. B. Rollenvergabe, Start, Editing-Abschluss, Review, Approval, Abbruch, Archivierung oder Gültigkeitsverlängerung.
- **AuditActor**: Die im Audit-/Nachweiskontext protokollierte handelnde Instanz einer auditrelevanten Aktion nach AP-006. Der AuditActor kann aus dem Workflow-Actor entstehen, wenn dessen Quelle belastbar klassifiziert ist.
- **Owner**: Fachlich verantwortliche Person oder objektbezogene Beziehung am Dokument. Owner erklärt Verantwortung, Berechtigung oder Zielbezug, ist aber nicht automatisch ausführender User.
- **Zieluser**: Der User, der von einer Aktion betroffen ist oder in einem Zielobjekt steht, z. B. Reviewer, Approver, Read-Receipt-User oder Kommentaradressat. Zieluser ist nicht automatisch Actor.
- **System Actor**: Explizit benannter nicht-menschlicher Actor für tatsächlich systeminitiierte technische Vorgänge, Jobs, Lifecycle-Events oder zulässige Service-Folgeprozesse.
- **Optionaler Actor**: Ein Actor-Parameter, der fehlen darf oder als freier String ohne zentrale Quellenvalidierung übergeben wird. Er ist nur nach Quellklassifikation auditfähig.
- **Fallback**: Ersatzquelle, die verwendet wird, wenn kein expliziter Actor übergeben wurde, z. B. `actor_user_id or owner_user_id or "system"`.
- **Correlation/Causation**: Technische Verkettung von Requests, Commands, Events und Folgeprozessen. Sie erklärt Zusammenhang und Auslöser, ersetzt aber keinen Actor.

## Entscheidung
Empfohlene Ziel-Policy für Documents-Workflow-Fallbacks:

Owner-Fallbacks sind nicht als belastbarer AuditActor zulässig. Ein Owner darf nur dann AuditActor eines Workflow-Ereignisses sein, wenn er unabhängig von der Owner-Eigenschaft als ausdrücklich ausführender User bestimmt wurde, z. B. über später freigegebenen UserContext/RequestContext an der Service-Grenze. Die reine Ableitung `actor_user_id or owner_user_id` ist für MVP-Audit-Exports `legacy` bzw. nicht belastbar.

`system` ist in Documents-Workflow-Events nur für echte systeminitiierte oder klar technische Folgeprozesse zulässig. `system` darf keinen fehlenden UserContext bei interaktiven Workflow-Aktionen ersetzen. Bei technischen Folgeprozessen nach einer interaktiven Handlung, z. B. DOCX->PDF- oder Release-PDF-Erzeugung, ist `system` höchstens eingeschränkt belastbar, solange keine explizite Causation zum auslösenden menschlichen Workflow-Event ausgewiesen wird.

Optionale Actor-Parameter sind ohne belastbare Quelle nicht ausreichend für MVP-Audit-Exports. Ein optionaler Actor-String kann nur dann `belastbar` werden, wenn ein später freigegebenes Paket seine Quelle, Validierung und Service-Grenze als expliziten ausführenden User oder zulässigen System/Service Actor nachweist. Bis dahin sind solche Felder `eingeschränkt`; Fallback-Ketten auf Owner/`system` bleiben `legacy`, wenn sie interaktive Aktionen ersetzen.

Workflow-Actor, Read-Receipt-Actor, Signatur-Actor, Kommentar-/DOCX-Autor und AuditActor werden getrennt bewertet. Keine dieser Identitäten darf automatisch als AuditActor einer anderen fachlichen Handlung übernommen werden.

Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Exportformat und keine Implementierung.

## Fallback-Matrix

| Fallback-Quelle | zulässig: ja/nein/eingeschränkt | Nachweisstatus | Bedingung | Risiko | spätere Behandlung |
| --- | --- | --- | --- | --- | --- |
| Expliziter Workflow-Actor aus freigegebenem UserContext/RequestContext | ja | belastbar | Interaktiver ausführender User wird an der Service-Grenze explizit bestimmt und service-seitig autorisiert. | Rollen-/Actor-Semantik könnte vermischt werden. | Zielquelle für spätere Workflow-Actor-Implementierungsvorbereitung. |
| Expliziter Service-Parameter `actor_user_id` aus heutiger CLI/PyQt-Quelle | eingeschränkt | eingeschränkt | Aktueller Bestand übergibt Actor explizit, aber Quelle ist lokale Session/Adapterzustand. | Wirkt belastbarer als der Desktop-/Legacy-Kontext erlaubt. | Für Exporte mit Quellenstatus markieren; später UserContext/RequestContext anbinden. |
| Freier Actor-String ohne zentrale Validierung | eingeschränkt/nein | eingeschränkt/legacy | Nur einordnen, wenn Herkunft, Actor-Typ und Use Case nachvollziehbar sind. | Inkonsistente oder erfundene Actor. | Später Quellenkatalog und Validierungsgrenze entscheiden. |
| Owner als Verantwortlichkeitsmetadatum | ja, aber nicht als Actor | nicht anwendbar als AuditActor | Owner bleibt Dokumentbeziehung, Ziel-/Verantwortlichkeitsinfo oder Berechtigungsfaktor. | Owner kann fälschlich als handelnde Person gelesen werden. | In Exporten getrennt von Actor ausweisen. |
| Owner-Fallback bei fehlendem Actor | nein | legacy/nicht belastbar | Keine Bedingung für belastbaren AuditActor; nur als Altbestand/Gap markierbar. | Ersetzt ausführenden User und verschleiert, wer gehandelt hat. | Später gezielt entfernen oder als legacy ausweisen, nur nach separater Freigabe. |
| Zieluser, Reviewer, Approver oder Verantwortlicher als reine Objektableitung | nein | legacy/nicht belastbar | Nur als Target/Subject/Assignment zulässig, nicht als Actor-Ersatz. | Vermischt Betroffenheit mit Handlung. | Actor/Target im Nachweispaket trennen. |
| `system` bei echter systeminitiierter Aktion | ja | belastbar/eingeschränkt | Eindeutig nicht-menschlicher Vorgang, benannter System/Service Actor, kein verdeckter Userkontext. | Unklare Governance kann Verantwortung verschleiern. | System-/Service-Actor-Namensschema später konkretisieren. |
| `system` als technischer Folgeprozess nach interaktiver Aktion | eingeschränkt | eingeschränkt | Nur wenn fachlicher Auslöser separat nachweisbar ist; Causation empfohlen bzw. später zu entscheiden. | Folgeprozess wirkt unabhängig oder verdeckt menschlichen Auslöser. | Event-Correlation/Causation-ADR oder Matrix. |
| `system` als Ersatz für fehlenden UserContext | nein | legacy/nicht belastbar | Keine zulässige Bedingung für interaktive Workflow-Aktionen. | Verwischt Admin/QMB/User-Verantwortung. | Als AP-011-Gap markieren; nicht automatisch reparieren. |
| `unknown` | nein | legacy/nicht belastbar | Höchstens Import-/Fremdmetadatum oder Altbestand. | Kein identifizierbarer Actor. | Sichtbar als legacy markieren; keine stille Aufwertung. |
| DOCX-/Import-/Kommentar-Autor | nein als AuditActor | legacy/metadaten | Externer Autor oder Importmetadatum darf als Herkunft sichtbar bleiben. | Fremdautor kann als QM-User missverstanden werden. | Kommentar-/DOCX-Sync-Exportdarstellung separat planen. |
| Signatur-Actor / `signer_user` | eingeschränkt | eingeschränkt bis abgegrenzt | Nur für Signaturvorgang selbst; darf Workflow-AuditActor nicht automatisch ersetzen. | Elektronische Signatur, UI-Current-User und Workflow-Actor werden vermischt. | Separate Signatur-vs-AuditActor-Abgrenzung in späterem Paket. |

## Owner-Fallback
- Zielregel:
  - Owner ist ein fachliches Verantwortlichkeits- oder Berechtigungsmetadatum am Dokument.
  - Owner darf nicht allein deshalb AuditActor sein, weil ein expliziter Actor fehlt.
  - Wenn Owner und ausführender User identisch sind, muss diese Identität aus einer belastbaren Actor-Quelle kommen; die Owner-Eigenschaft ist dafür nicht ausreichend.
- Zulässige Fälle:
  - Owner als Dokumentmetadatum.
  - Owner als Target/Subject, Verantwortlicher oder Berechtigungsfaktor in service-seitigen Regeln.
  - Owner als ausführender User nur, wenn derselbe User explizit und belastbar an der Service-Grenze bestimmt wurde.
- Unzulässige Fälle:
  - `actor_user_id or owner_user_id` als belastbarer AuditActor.
  - Owner als Ersatz für fehlenden UserContext bei Rollenvergabe, Workflow-Start, Editing-Abschluss oder Workflow-Abbruch.
  - Owner als Nachweis dafür, dass eine interaktive Handlung tatsächlich vom Owner ausgeführt wurde.
  - Owner oder Verantwortlicher als Kommentar-, DOCX-Sync-, Archivierungs- oder Artefakt-Actor ohne separate ausführende Quelle.
- Offene Punkte:
  - Welche Owner-basierten Berechtigungen je Workflow-Schritt im Zielmodell bestehen bleiben.
  - Wie Exporte Owner, Actor, Target und Verantwortlichkeit konkret darstellen.
  - Welche bestehenden Tests/Fälle bewusst Legacy-Fallbacks abdecken und später nicht blind bereinigt werden dürfen.

## System-Fallback
- Zielregel:
  - `system` ist zulässig für echte systeminitiierte Vorgänge, nicht als allgemeiner Ersatz für fehlende Actor-Parameter.
  - Technische Folgeprozesse nach menschlicher Aktion brauchen eine erkennbare Verbindung zum auslösenden fachlichen Event.
  - System Actor ist kein Rollenstatus und keine QMB-/Admin-Befugnis.
- Zulässige echte Systemvorgänge:
  - Modul-/Runtime-Lifecycle-Events ohne fachliche Userhandlung.
  - Geplante technische Jobs oder Wartungsvorgänge mit bewusst benanntem System/Service Actor.
  - Automatische technische Artefakterzeugung nur eingeschränkt, wenn sie nicht selbst eine menschliche Workflow-Entscheidung behauptet und später mit Causation an den Auslöser gekoppelt werden kann.
  - Import-/Legacy-Prozesse nur mit sichtbarer Kennzeichnung als System/Service/Legacy-Quelle.
- Unzulässiger Ersatz für fehlenden UserContext:
  - Rollenvergabe, Workflow-Start, Editing-Abschluss, Workflow-Abbruch oder fachliche Archivierung, wenn eine menschliche Aktion vorliegt oder erwartet wird.
  - GUI-/CLI-/Backend-Aufrufe, bei denen der Userkontext nur nicht bis zur Service-Grenze gelangt.
  - Signatur- oder Read-Receipt-Flows, bei denen `system` eine fehlende interaktive Bestätigung verdecken würde.
- Offene Punkte:
  - Ob Documents-Archivierung im Zielmodell jemals als echte Systemaktion erlaubt ist oder immer menschlichen QMB/Admin-Actor braucht.
  - Welcher System-/Service-Actor-Name für technische Dokumentenjobs zulässig ist.
  - Ab wann Causation für technische Folgeevents verpflichtend wird.

## Optionale Actor-Parameter
- Zielregel:
  - Optionale Actor-Parameter dürfen für auditrelevante interaktive Workflow-Aktionen im Zielmodell nicht die finale Actor-Pflicht ersetzen.
  - Ein optionaler Actor kann nur `belastbar` sein, wenn seine Quelle explizit freigegeben und validiert ist.
  - Eine Fallback-Kette `Actor -> Owner -> system` ist für MVP-Audit-Exports nicht belastbar.
- Risiken:
  - Fehlender Actor wird durch Owner oder `system` kaschiert.
  - Freie Strings werden wie validierte User-Identitäten gelesen.
  - EventEnvelope-Actor und AuditLogger-Actor können unterschiedliche Qualität haben.
  - Tests können unabsichtlich die Produktivsemantik von optionalen Actor-Feldern normalisieren.
- Spätere Behandlung:
  - Je Workflow-Use-Case entscheiden, ob Actor-Pflicht, System Actor oder Legacy-Markierung gilt.
  - Exportstatus `belastbar/eingeschränkt/legacy` je Eventfamilie sichtbar machen.
  - Quellenvalidierung und UserContext/RequestContext nur in separat freigegebenen Implementierungsvorbereitungspaketen planen.
- Offene Punkte:
  - Welche Bestandspfade wegen Test-/Legacy-Kompatibilität optional bleiben dürfen.
  - Ob bestehende optionale Parameter als Übergangsschnitt oder nur als Legacy-Fund bewertet werden.

## Abgrenzung
- Zu Read-Receipt:
  - Read-Receipt-Actor ist der ausführende User der Kenntnisnahme nach AP-010.
  - Workflow-Owner oder Workflow-Actor darf nicht automatisch Read-Receipt-Actor sein.
  - Receipt-User ist Ziel-/Subject-Information und nur bei belegter Selbst-Kenntnisnahme zugleich Actor.
- Zu Signatur:
  - Signatur-Actor oder `signer_user` ist die Identität des Signaturvorgangs.
  - Signatur-Actor ist nicht automatisch Documents-AuditActor eines Workflow-Übergangs.
  - Wenn Signatur und Workflow-Handlung zusammenfallen, muss später entschieden werden, ob beide Identitäten gleich sein müssen und welches Nachweisniveau gilt.
- Zu Kommentar/DOCX-Sync:
  - PDF-Kommentar-Actor, Kommentarstatus-Bearbeiter, DOCX-Autor und Sync-Actor sind getrennte Konzepte.
  - DOCX-Autor oder `unknown` ist Import-/Quellmetadatum, kein AuditActor.
  - Kommentar-/Sync-Events ohne belastbaren Envelope-Actor bleiben eingeschränkt oder legacy.
- Zu UserContext:
  - UserContext liefert die Identitätsbasis für ausführende User, entscheidet aber nicht selbst den AuditActor.
  - Lokaler Current User, GUI-/CLI-Zustand und Adapterrollen sind keine belastbare Zielquelle für backend-migrierte Use Cases.
  - Services bleiben Ort der fachlichen Actor-/Autorisierungsbewertung.
- Zu Audit-Export / Nachweispaket:
  - Export/Nachweispaket muss Actor, Actor-Quelle, Actor-Typ, Nachweisstatus, Owner, Target/Subject und technische Folgekontexte getrennt darstellen.
  - Fallback-Actor dürfen nicht als voll belastbare menschliche Handlung erscheinen.
  - Correlation/Causation kann Nachweisketten erklären, ersetzt aber keinen Actor.

## Umgang mit aktuellem Zustand

| AP-011-Fundtyp | aktueller Zustand | Zielrichtung | spätere Behandlung | benötigte Vorentscheidung |
| --- | --- | --- | --- | --- |
| Optionale Workflow-Actor mit Owner/`system`-Fallbacks | `assign_workflow_roles`, `start_workflow`, `complete_editing` und `abort_workflow` nutzen optionalen Actor und Audit-Fallbacks auf Owner/`system`. | Interaktive Workflow-Aktionen brauchen belastbaren ausführenden Actor; Owner/`system`-Fallbacks nicht als belastbar exportieren. | Documents-Workflow-Actor-Implementierungsvorbereitung. | Welche Workflow-Schritte zwingend Actor-Pflicht bekommen und welche Legacy bleiben. |
| Archivierung mit `actor_user_id or "system"` | `archive_approved` verlangt QMB/Admin-Rolle, kann auditseitig aber `system` verwenden, wenn Actor fehlt. | Fachliche Archivierung soll nicht still System Actor werden; System nur bei ausdrücklich systeminitiierter Archivierung. | Workflow-Actor-Implementierungsvorbereitung oder System-Actor-Policy. | Archivierung immer menschlicher QMB/Admin oder zulässiger Systemjob? |
| DOCX->PDF-Erzeugung vor Signatur | `_ensure_source_pdf_artifact_for_signing` erzeugt SOURCE_PDF mit optionalem Actor und Audit-Fallback auf Owner/`system`. | Technische Artefakterzeugung als Folgeprozess einordnen, nicht als eigenständige menschliche Workflow-Handlung. | Documents-Event-Correlation/Causation-ADR oder Matrix. | Muss der Folgeprozess den ursprünglichen Workflow-Actor oder einen System Actor tragen? |
| Release-PDF-Erzeugung | `_ensure_release_pdf_artifact` erzeugt RELEASED_PDF ohne eigenes Event/Audit im gelesenen Ausschnitt. | Fachliche Freigabe und technische Artefakterzeugung getrennt, aber kausal nachvollziehbar ausweisen. | Correlation/Causation-Matrix oder Audit-Export-Readiness-Matrix. | Ob Release-PDF ein eigenes Nachweisereignis braucht. |
| Kommentar-/DOCX-Sync-Events ohne belastbaren Envelope-Actor | Kommentar- und Sync-Services führen Actor teils im Record/Payload, nicht im Envelope; DOCX-Autor bleibt Fremdmetadatum. | Kommentar-/Sync-Actor und DOCX-/Import-Autor trennen; fehlender Envelope-Actor nicht still aus Metadaten ableiten. | Documents-Audit-Export-Readiness-Matrix. | Welche Kommentar-/Sync-Ereignisse für MVP belastbaren Event-Actor brauchen. |
| Documents-nahe Signatur-Events | Signaturmodul nutzt `signer_user`; PyQt baut SignRequests aus lokalem Current User. | Signatur-Actor nicht automatisch als Workflow-AuditActor übernehmen. | Signatur-vs-AuditActor später als Teil der Workflow-Vorbereitung oder eigener Analyseblock. | Ob Workflow-Actor und Signatur-Actor zwingend identisch sein müssen. |
| Fehlende explizite Correlation/Causation | Documents-Events erzeugen bzw. tragen keine explizit durchgereichte Use-Case-/Request-Kette. | Nachweisketten für technische Folgeprozesse und Signatur/Workflow-Verknüpfung sichtbar machen. | Documents-Event-Correlation/Causation-ADR oder Matrix. | Pflichtgrad für MVP-Documents-Events. |
| Tests mit fehlenden Actor-Parametern oder Fake-Actors | Tests rufen Workflow-Schritte teils ohne Actor oder mit `owner-1`, `qmb-1`, `admin` auf. | Tests nur einordnen, nicht bereinigen; Produktivnähe je Test später prüfen. | Workflow-Actor-Implementierungsvorbereitung mit gezielter Testklassifikation. | Welche Tests Legacy-Verhalten sichern und welche Zielsemantik prüfen sollen. |

## Nicht-Ziele
- Keine Documents-Implementierung.
- Keine Workflow-Implementierung.
- Keine Audit-Implementierung.
- Keine UserContext-, Auth-, Rollen- oder RequestContext-Implementierung.
- Keine API-Änderung, kein DTO, kein Contract, kein Re-Export und keine Wrapper-API.
- Keine Event-Schema-Änderung.
- Keine Backend-Feature-Route.
- Keine Migration.
- Keine Dependency-Änderung.
- Keine Bereinigung bestehender AP-002- bis AP-011-Findings.
- Keine Änderung an Produktions-, Test-, Runtime-, GUI-, CLI- oder Backend-Code.
- Keine Entscheidung über elektronische Signatur, Re-Auth oder rechtliches Signaturniveau.
- Keine vollständige Audit-Export-Spezifikation.
- Keine automatische Reparatur von Owner-/`system`-/`unknown`-/Current-User-Funden.

## Konsequenzen
- Für Documents-Service-Grenzen:
  - Auditnahe Workflow-Use-Cases brauchen langfristig explizite Actor-/Target-/System-Actor-Semantik an der Service-Grenze.
  - Services bleiben fachliche Grenze für Autorisierung, Workflow-Regeln und Actor-Bewertung.
  - Owner-basierte Berechtigung darf nicht mit Actor-Bestimmung verwechselt werden.
- Für Events:
  - EventEnvelope-Actor kann nur so belastbar sein wie seine Quelle.
  - Events ohne Actor oder mit Fallback-Actor müssen im Nachweispaket als eingeschränkt/legacy sichtbar bleiben.
  - Correlation/Causation wird für technische Folgeprozesse und Signatur-/Workflow-Ketten wichtiger, aber durch diese ADR nicht implementiert.
- Für Audit-Export / Nachweispaket:
  - Fallbacks auf Owner, `system` ohne echte Systemaktion, freie Strings und Adapterzustand dürfen nicht als `belastbar` erscheinen.
  - Exporte müssen Actor, Owner, Zieluser/Target, Signatur-Actor, Import-/DOCX-Autor und System Actor getrennt darstellen.
  - Technische Folgeprozesse müssen als Folgeprozesse oder Systemvorgänge mit Nachweisstatus erkennbar sein.
- Für GUI/CLI:
  - GUI/CLI dürfen Workflowaktionen auslösen, Kontext transportieren und Auditinformationen anzeigen.
  - GUI-/CLI-Zustand und lokaler Current User bleiben als finale Actor-Quelle eingeschränkt/legacy.
  - GUI-Fehler-Audit mit `system` ist kein fachlicher Documents-Service-AuditActor.
- Für Backend:
  - Backend darf Owner, `system` oder Transportzustand nicht als fachlichen Actor-Ersatz einsetzen.
  - Backend-migrierte Workflow-Use-Cases brauchen später expliziten Request-/UserContext zur Service-Grenze.
- Für Tests:
  - Keine Tests werden in AP-012 geändert.
  - Spätere Tests müssen Zielsemantik und Legacy-Fälle getrennt prüfen.
  - Test-Fake-Actors werden nicht als Produktivquelle gewertet.
- Für spätere Implementierungspakete:
  - Folgepakete müssen klein bleiben und vor Implementierung jeweils separat freigegeben werden.
  - Vor jeder Reparatur der AP-011-Gaps ist festzulegen, ob Actor-Pflicht, System Actor oder Legacy-Markierung gilt.

## Risiken
- Technische Risiken:
  - Bestehende Event- und Auditpfade nutzen unterschiedliche Actor-Felder und freie Strings.
  - Optionale Actor-Parameter erlauben weiterhin uneinheitliche Aufruferqualität.
  - Correlation/Causation ist vorhanden, aber nicht als Use-Case-Kette verbindlich durchgereicht.
  - Release-/SOURCE-PDF-Folgeprozesse können ohne klare Eventkette schwer exportierbar bleiben.
- Fachliche Risiken:
  - Owner-Fallback kann Verantwortlichkeit mit Handlung verwechseln.
  - `system` kann menschliche QMB/Admin/User-Verantwortung verschleiern.
  - Signatur-Actor kann fälschlich als Workflow-AuditActor gelesen werden.
  - DOCX-/Kommentar-Autoren können als interne QM-User missverstanden werden.
- Migrationsrisiken:
  - Bestehende Desktop-/CLI-/PyQt-Flows liefern Actor aus lokaler Session und Adapterzustand.
  - Backend-Migration darf keine halb lokalen Workflow-Actor-Quellen behalten.
  - Altbestände und Tests mit optionalen Actor-Feldern brauchen klare Legacy-Kennzeichnung.
- Audit-/Nachweisrisiken:
  - MVP-Audit-Exports könnten Fallback-Actor zu belastbar darstellen.
  - Fehlende Actor-/Target-/Owner-Trennung erschwert Nachweispakete.
  - Technische Folgeevents ohne Causation wirken isoliert oder verantwortungslos.
  - `system` ohne belegte Systemquelle kann Auditfragen auslösen.

## Offene Supervisor-Entscheidungen
- Muss Documents-Archivierung im Zielmodell immer einen menschlichen QMB/Admin-Actor haben, oder darf es einen echten System-Archivierungsjob geben?
- Welches System-/Service-Actor-Namensschema gilt für technische Documents-Folgeprozesse?
- Ab wann sind `correlation_id` und `causation_id` für Workflow-/Signatur-/Artefakt-Nachweisketten Pflicht?
- Müssen Workflow-Actor und Signatur-Actor in signaturpflichtigen Übergängen identisch sein, oder reicht eine kausale Trennung?
- Welche bestehenden Tests sichern bewusst Legacy-Fallbackverhalten und welche sollen später Zielsemantik prüfen?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`
  - `docs/AP-004_USER_CONTEXT_ADR.md`
  - `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md`
  - `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md`
  - `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`
  - `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md`
  - `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `modules/documents/workflow_use_cases.py`
  - `modules/documents/service.py`
  - `interfaces/cli/commands/documents_commands.py`
  - `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py`
  - `interfaces/pyqt/presenters/documents_signature_ops.py`
  - `modules/signature/signature_execute_ops.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md`.
  - `rg` in `modules/documents` nach `actor_user_id or updated.owner_user_id or "system"`, `actor_user_id or state.owner_user_id or "system"`, `actor_user_id or "system"`, `actor=str(`, `_emit_audit`, `domain.documents`, `_publish`, `ensure_source_pdf_for_signing`, `_ensure_release_pdf_artifact`, `last_actor_user_id`, `signer_user` und `sign_request`.
  - `rg` in `modules/signature` nach `signer_user`, `sign_request`, `actor_user_id`, `domain.signature`, `audit_logger.emit`, `actor=request.signer_user` und `"system"`.
  - `rg` in `interfaces/pyqt` nach Documents-Actor-, Signatur-, Current-User- und System-Fallback-Kontexten.
  - `rg` in `interfaces/cli/commands/documents_commands.py` nach Workflow-/Actor-/Signatur-Weitergaben.
  - `rg` in `tests` nach Documents-Workflow-, Actor-, Owner-, `system`- und Signatur-Funden.
- Keine Testsuite ausgeführt, weil AP-012 ein ADR-/Dokumentationspaket ist und die Vorgabe Tests ausdrücklich ausschließt.
- Keine Linter oder Typechecker ausgeführt, weil AP-012 ein ADR-/Dokumentationspaket ist und keine erfundenen Tools ausgeführt werden sollen.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Event-Schema-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll als nächstes ein reines Analyse-/Vorbereitungspaket `Documents-Event-Correlation-Causation-Matrix` freigeben oder zurückstellen; keine Implementierung automatisch starten.
