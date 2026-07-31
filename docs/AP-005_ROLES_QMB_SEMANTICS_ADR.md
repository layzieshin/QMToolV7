# AP-005 Rollen-/QMB-Semantik ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Migration: nein
- Supervisor-Entscheidung Admin ≠ QMB: **angenommen** (2026-07-31, Option B; Bezug AP-028)
- Incident-Modul-Abweichung (Admin als QMB): bewusst noch nicht bereinigt; Cleanup außerhalb AP-028

## Kontext
- Bezug auf AP-003: `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md` dokumentiert uneinheitliche Rollen-/QMB-Verwendungen, unter anderem `modules/usermanagement/role_policies.py`, `modules/incident_management/authorization.py`, CLI-Rollenmapping in Documents/Settings und PyQt-`access_guards`.
- Bezug auf AP-004: `docs/AP-004_USER_CONTEXT_ADR.md` entscheidet, dass UserContext Identitätskontext liefert, aber Rollen/QMB nicht selbst fachlich entscheidet.
- Aktuelle Rollen-/QMB-Risiken:
  - `modules/usermanagement/role_policies.py` behandelt `QMB` oder `is_qmb=True` als effektiv QMB; `Admin` zählt dort nicht automatisch als QMB.
  - `modules/incident_management/authorization.py` behandelt `Admin` automatisch als QMB-berechtigt.
  - CLI und PyQt enthalten Rollenmapping und Zugriffsgates, die als UX/Sichtbarkeit eingeordnet werden müssen und keine fachliche Wahrheit sein dürfen.
  - Rollenanzeige, Navigationsfilter und fachliche Autorisierung sind im Bestand nicht immer eindeutig getrennt.
- Geltende Architekturregeln:
  - Rollen-/Rechteprüfungen gehören in Services.
  - GUI, CLI und Backend dürfen keine fachlichen Rollenentscheidungen treffen.
  - UserContext liefert Identitätskontext, entscheidet aber Rollen/QMB nicht selbst.
  - Audit-Actor bleibt getrennt und wird nicht durch Rollenlogik ersetzt.
  - Diese ADR ist ein Dokumentations-/Entscheidungspaket; keine Implementierung, keine API-Änderung, keine Migration.

## Begriffe
- **Admin**: Basisrolle für technische und organisatorische Administration, z. B. Benutzerverwaltung, Konfiguration und Systempflege. Ob Admin automatisch fachliche QMB-Rechte hat, ist die zentrale Supervisor-Entscheidung dieser ADR.
- **QMB**: Fachliche Qualitätsmanagement-Rolle für QM-relevante Freigaben, Bewertungen, Reviews oder Eskalationen. QMB ist fachlich, nicht bloß technisch-administrativ.
- **User**: Normale authentifizierte Benutzerrolle ohne pauschale Admin- oder QMB-Rechte.
- **`is_qmb`**: Zusatzflag, das einer Basisrolle zusätzliche QMB-Wirkung verleihen kann. Das Flag ist kein Ersatz für ein vollständiges Rollen-/Befugnissemantikmodell.
- **Modulrolle**: Fachmodulspezifische Rolle, z. B. `Leitung` im Incident-Modul. Modulrollen sind enger als Basisrollen und gehören zur Service-Autorisierung des jeweiligen Moduls.
- **Befugnis**: Konkrete Erlaubnis für einen fachlichen Vorgang, z. B. Freigeben, Bewerten, Signieren, Schulung bestätigen. Befugnisse können später aus Rolle, Modulrolle, Kompetenz, Tätigkeit oder Kontext abgeleitet werden.
- **Kompetenz**: Fachlicher Nachweis einer Fähigkeit oder Schulung. Kompetenz ist kein Login-Rollenersatz, kann aber später Voraussetzung für Befugnisse sein.
- **Owner/Verantwortlicher**: Fachliche Beziehung einer Person zu einem Objekt oder Prozess, z. B. Dokumenten-Owner, Incident-Reporter oder Aufgabenverantwortlicher. Owner-Rechte sind objektbezogen und nicht identisch mit Basisrollen.
- **Technischer Systemzugriff**: Zugriff eines Systems, Jobs oder Wartungsvorgangs. Er ist kein menschlicher Rollenstatus und darf nicht mit Admin/QMB verwechselt werden.

## Entscheidung
Empfohlene Zielentscheidung:

Basisrollen bleiben minimal und eindeutig: `Admin`, `QMB`, `User`. QMB-Fachrechte sollen primär durch die Basisrolle `QMB` oder durch ein ausdrücklich vergebenes QMB-Zusatzrecht `is_qmb=True` entstehen. `User` ohne `is_qmb` hat keine QMB-Fachrechte.

Admin soll nicht pauschal als QMB gelten. Admin erhält technische und organisatorische Administrationsrechte, aber fachliche QMB-Rechte nur dann, wenn die Basisrolle `QMB` vorliegt oder `is_qmb=True` ausdrücklich gesetzt ist. Diese Empfehlung trennt technische Administration von fachlicher Qualitätsverantwortung und reduziert Audit-/Nachweisrisiken. Weil der Bestand im Incident-Modul Admin aktuell als QMB-äquivalent behandelt, ist dafür eine explizite Supervisor-Entscheidung nötig, bevor Implementierung oder Cleanup geplant wird.

Modulrollen, Befugnisse und Kompetenzen ergänzen die Basisrollen, ersetzen sie aber nicht. Sie werden in den Services des jeweiligen Moduls ausgewertet. GUI, CLI und Backend dürfen Rolleninformationen anzeigen, UX-/Sichtbarkeitsgates anwenden und Kontext transportieren, aber keine fachliche Autorisierung abschließend treffen.

## Rollen- und QMB-Matrix

| Rolle/Konzept | Bedeutung | fachliche Wirkung | technische Wirkung | darf in UserContext stehen: ja/nein/offen | entscheidet welche Schicht | offene Punkte |
| --- | --- | --- | --- | --- | --- | --- |
| `Admin` | Technisch/organisatorische Administrationsrolle. | Nicht automatisch QMB; fachliche Rechte nur nach Service-Regel. | Benutzer-/Konfigurationsverwaltung, Adminbereiche, Diagnose. | offen, als Rollenreferenz/Claim möglich | Services für fachliche Wirkung; Plattform/Settings für technische Adminfunktionen | Supervisor-Entscheidung 2026-07-31: Admin ≠ QMB (Option B). |
| `QMB` | Basisrolle für Qualitätsmanagement-Verantwortung. | QMB-Fachrechte nach Modul-Service-Regeln. | Sichtbarkeit von QMB-Bereichen möglich. | offen, als Rollenreferenz/Claim möglich | Services | Detailrechte je Modul und Prozess offen. |
| `User` | Standardrolle für authentifizierte Benutzer. | Keine pauschalen QMB/Admin-Rechte. | Normale Nutzung, eigene Aufgaben/Objekte. | offen, als Rollenreferenz/Claim möglich | Services | Objektbezogene Owner-/Verantwortlichenrechte je Use Case. |
| `is_qmb` | Zusatzflag für QMB-Wirkung. | Verleiht QMB-Fachrechte nur nach bestätigter Service-Regel. | Kann UI-Sichtbarkeit beeinflussen. | offen, als Rollenreferenz/Claim möglich | Services | Governance: Wer darf Flag setzen, wie wird es auditiert? |
| Modulrolle | Modulinterne fachliche Rolle, z. B. Leitung. | Vorgangs-/modulspezifische Rechte. | Keine globale Admin/QMB-Wirkung. | offen, eher Referenz als vollständige Liste | jeweiliger Modul-Service | Einheitliches Modell für Modulrollen offen. |
| Befugnis | Konkrete Erlaubnis für einen Use Case. | Entscheidet, ob Aktion fachlich erlaubt ist. | Keine direkte technische Wirkung. | nein/offen, eher aus Rollen/Kompetenzen abzuleiten | Services | Spätere Befugnisse-/Kompetenzplanung nötig. |
| Kompetenz | Nachweis einer Fähigkeit/Schulung. | Kann Voraussetzung für Befugnis sein. | Keine Login-Rolle. | nein/offen | Services, später Schulungs-/Kompetenzmodul | Nachweisniveau und Aktualität offen. |
| Owner/Verantwortlicher | Objektbezogene Beziehung. | Erlaubt bestimmte objektbezogene Aktionen. | Keine globale Rolle. | nein, eher Use-Case-/Objektparameter | Services | Pro Modul definieren. |
| Technischer Systemzugriff | System-/Job-/Wartungskontext. | Keine menschlichen Fachrechte. | Technische Operationen nach separater Freigabe. | nein | Plattform/Services nach expliziter Policy | Audit-Actor-ADR muss System Actor regeln. |

## Admin-als-QMB-Frage
- Optionen:
  - Option A: Admin gilt automatisch als QMB-berechtigt.
  - Option B: Admin ist getrennte technische/administrative Rolle ohne automatische QMB-Fachrechte.
  - Option C: Admin gilt nur in ausgewählten Modulen oder Notfall-/Wartungspfaden als QMB-äquivalent.
- Empfehlung:
  - Option B als Zielsemantik wählen: Admin ist nicht automatisch QMB.
  - QMB-Fachrechte entstehen über Basisrolle `QMB`, `is_qmb=True` oder später freigegebene Modulrollen/Befugnisse.
- Begründung:
  - Trennt technische Administration von fachlicher QM-Verantwortung.
  - Reduziert Risiko, dass Admins fachliche Freigaben/Bewertungen ohne QMB-Beauftragung durchführen.
  - Passt zur AP-004-Abgrenzung: UserContext transportiert Identität/Rollenreferenzen, Services entscheiden fachliche Wirkung.
  - Macht Auditnachweise klarer, weil Admin-Handeln und QMB-Handeln unterscheidbar bleiben.
- Risiken:
  - Bestand im Incident-Modul behandelt Admin aktuell als QMB-äquivalent; spätere Änderung könnte Verhalten betreffen.
  - Kleine Teams könnten erwarten, dass Admin zugleich QMB-Aufgaben wahrnehmen darf.
  - Initiale Admin-/QMB-Bootstrap-Prozesse müssen später fachlich sauber definiert werden.
- Explizite Supervisor-Entscheidung nötig: ja.
- Supervisor-Entscheidung (2026-07-31): **Option B angenommen.** Admin ist nicht automatisch QMB. QMB-Fachrechte entstehen über Basisrolle `QMB` oder `is_qmb=True`. Die Abweichung in `modules/incident_management/authorization.py` bleibt bis zu einem separat freigegebenen Cleanup bestehen und ist nicht Teil von AP-028.

## Service-Autorisierung und Adapter-Gates
- Zielregel für Services:
  - Fachliche Autorisierung liegt ausschließlich in Services oder service-nahen Policy-/Validation-Komponenten des jeweiligen Moduls.
  - Services prüfen Basisrolle, QMB-Zusatzflag, Modulrollen, Owner/Verantwortlicher und spätere Befugnisse/Kompetenzen nach freigegebener Semantik.
  - Services dürfen sich nicht darauf verlassen, dass GUI/CLI/Backend bereits korrekt gefiltert haben.
- Zulässige GUI-Gates:
  - Navigation, Sichtbarkeit, Buttons, Hinweise und frühe UX-Blockmeldungen.
  - Anzeige von Rolle, QMB-Status oder Admin-Hinweisen.
  - Keine abschließende fachliche Entscheidung; Service muss die Aktion weiterhin prüfen.
- Zulässige CLI-Gates:
  - Frühe Login-/UX-Checks und lesbare Blockmeldungen.
  - Parameterprüfung und Anzeige von Rolleninformationen.
  - Kein Ersatz für Service-Autorisierung; CLI-Rollenmapping darf nicht die fachliche Wahrheit sein.
- Verbotene Backend-Entscheidungen:
  - Backend darf Rollen/QMB/Befugnisse nicht fachlich interpretieren.
  - Backend darf nicht entscheiden, ob ein User fachlich QMB-berechtigt ist.
  - Backend transportiert Auth-/UserContext und ruft öffentliche Modul-APIs bzw. freigegebene Use-Case-Grenzen auf.
- Repository-/Storage-Grenze:
  - Repositories/Storage dürfen Rollen-, Flag-, Modulrollen- oder Befugnisdaten speichern und laden.
  - Repositories/Storage treffen keine fachlichen Entscheidungen aus diesen Daten.

## Umgang mit aktuellem Zustand

| AP-003-Fundtyp | Zielrichtung | spätere Behandlung | benötigte Vorentscheidung |
| --- | --- | --- | --- |
| `modules/usermanagement/role_policies.py` | Als zentrale allgemeine Rollennormalisierung geeignet, aber Zielsemantik muss bestätigt werden. | Später nach Supervisor-Entscheidung prüfen, ob Admin nicht automatisch QMB bleibt. | Admin-als-QMB und `is_qmb`-Governance. |
| `modules/incident_management/authorization.py` | Service-nahe Autorisierung ist grundsätzlich richtig; Admin-als-QMB weicht von empfohlener Zielsemantik ab. | Kein Cleanup in AP-005; später gezielt mit Tests und Service-Matrix prüfen. | Supervisor-Entscheidung Admin-als-QMB. |
| CLI-Rollenmapping Documents/Settings | Als UX-/Parameterhilfe markieren, nicht als fachliche Wahrheit. | Später prüfen, ob Services alle fachlichen Gates vollständig besitzen. | Adapter-Gate-Policy und Service-Autorisierungsmatrix. |
| PyQt `access_guards` | Als UX-/Sichtbarkeitsgate markieren. | Später sicherstellen, dass Service-Gates maßgeblich bleiben. | Welche GUI-Gates zulässig bleiben. |
| QMB/Admin-Unschärfe | Ziel: technische Adminrechte und fachliche QMB-Rechte trennen. | Erst nach ADR-Freigabe implementierbar. | Explizite Supervisor-Entscheidung nötig. |
| Rollenanzeige vs. Rollenentscheidung | Anzeige ist unkritisch; Entscheidung muss service-seitig sein. | Später bei Inventar/Matrix getrennt ausweisen. | Kriterien für UX-Gate vs. Autorisierung. |
| Tests/Legacy-Funde | Nicht bereinigen; nur als Bestand markieren. | Testebenen und Legacy-Pfade separat nach AP-002A behandeln. | Test-/Legacy-Policy. |

## Abgrenzung
- Zu UserContext:
  - UserContext enthält Identität und eventuell Rollenreferenzen/Claims als Eingabe.
  - UserContext entscheidet nicht, ob `Admin`, `QMB`, `is_qmb` oder Modulrollen fachlich berechtigen.
- Zu Audit-Actor:
  - Audit-Actor ist nicht automatisch Rolle.
  - Actor-Nachweisniveau, System Actor, Unknown-Fallbacks, Zieluser-vs-ausführender-User und Correlation/Causation bleiben AP-006.
- Zu Session/Token/Auth:
  - Diese ADR entscheidet keine Authentifizierungsart, Session-ID, Token-Format oder externe Identität.
  - Rollen-/QMB-Semantik setzt erst nach erfolgreicher Auth/UserContext-Ermittlung an.
- Zu Befugnissen/Kompetenzen:
  - Diese ADR definiert nur die Abgrenzung.
  - Detaillierte Befugnisse, Kompetenznachweise, Schulungsvoraussetzungen und Tätigkeitsprofile brauchen spätere Planung.
- Zu Backend/Multiuser-Migration:
  - Backend transportiert Kontext.
  - Services bleiben Autorisierungsort.
  - Keine Migration, keine Backend-Route und keine API-Signatur wird durch diese ADR freigegeben.

## Nicht-Ziele
- Keine Implementierung eines Rollenmodells.
- Keine Änderung an `is_effective_qmb`, `authorization.py`, CLI-Gates oder PyQt-Gates.
- Keine API-Änderung, kein DTO, kein Export, kein Re-Export.
- Keine UserContext-Implementierung.
- Keine Auth-, Session- oder Token-Entscheidung.
- Keine Audit-Actor-Entscheidung.
- Keine elektronische Signatur oder Audit-Nachweisniveau-Entscheidung.
- Keine PostgreSQL- oder Datenmigration.
- Keine Test-, Legacy- oder Boundary-Cleanup-Arbeiten.

## Konsequenzen
- Für Audit-Actor-ADR:
  - Muss klarstellen, dass Actor nicht Rolle ist.
  - Muss klären, wie Rollen/QMB-Entscheidungen in Audit-Nachweisen sichtbar werden, ohne Actor-Semantik zu vermischen.
  - Muss Adminaktionen und QMB-Fachaktionen unterscheidbar machen.
- Für spätere Service-Autorisierung:
  - Eine Service-Autorisierungs-Matrix kann nötig werden, um je Use Case Service-Gates zu prüfen.
  - Zuerst sollten MVP-Module mit Dokumentenlenkung, Incident/CAPA und Training betrachtet werden.
- Für GUI/CLI:
  - Bestehende Gates sind als UX/Sichtbarkeit zu markieren, bis Service-Gates bestätigt sind.
  - Rollenanzeige bleibt zulässig.
  - CLI/PyQt dürfen keine fachliche Autorisierung als alleinige Barriere tragen.
- Für Tests:
  - Tests mit Rollenmatrizen bleiben wertvoll, müssen aber später nach Service-/Adapterebene getrennt werden.
  - Legacy-Tests nicht automatisch bereinigen.
- Für Backend/Multiuser-Migration:
  - Backend darf Rollen nicht fachlich interpretieren.
  - Use-Case-Migration muss sicherstellen, dass Services mit explizitem Kontext autorisieren.
  - Admin/QMB-Semantik muss vor fachlichen Backend-Use-Cases entschieden sein.

## Risiken
- Technische Risiken:
  - Bestehende Logik nutzt unterschiedliche QMB-Auslegungen; spätere Vereinheitlichung kann mehrere Module betreffen.
  - Adapter-Gates könnten weiterhin irrtümlich als Autorisierung gelten.
  - Rollenreferenzen im UserContext könnten zu breit werden und fachliche Semantik vorwegnehmen.
- Fachliche Risiken:
  - Trennung Admin/QMB kann organisatorisch unerwartet sein.
  - `is_qmb` als Zusatzflag braucht klare Vergabe- und Entzugsregeln.
  - Modulrollen, Befugnisse und Kompetenzen können ohne spätere Detailplanung uneinheitlich wachsen.
- Migrationsrisiken:
  - Wenn Admin bisher praktisch QMB war, können spätere Änderungen Workflows blockieren.
  - Übergangsphase zwischen Desktop-Gates und service-seitiger Autorisierung braucht kleine, testbare Pakete.
  - Tests müssen zwischen UX-Gate und Service-Autorisierung unterscheiden.
- Audit-/Nachweisrisiken:
  - Admin-Handeln als QMB-Handeln kann Nachweise verfälschen, wenn nicht explizit beauftragt.
  - Rollenänderungen und QMB-Flag-Änderungen brauchen später sauberen Actor und Nachweis.
  - Audit-Actor darf nicht aus Rollenlogik abgeleitet werden.

## Offene Supervisor-Entscheidungen
- ~~Soll Admin im Zielmodell ausdrücklich nicht automatisch QMB sein?~~ **Erledigt 2026-07-31: nein, Admin ist nicht automatisch QMB (Option B).**
- Soll `is_qmb` dauerhaft als Zusatzrecht bestehen oder später durch Befugnisse/Kompetenzen ersetzt werden?
- Wer darf `is_qmb` setzen oder entziehen, und welches Nachweisniveau gilt dafür?
- Welche MVP-Use Cases benötigen QMB-Rechte zwingend zuerst?
- Welche GUI-/CLI-Gates gelten als reine UX und welche müssen priorisiert durch Service-Gates abgesichert werden?
- Wie werden Modulrollen wie `Leitung` gegenüber QMB und Admin priorisiert?
- Wann wird eine Befugnisse-/Kompetenz-Detailplanung gestartet?
- Wann wird die Incident-Abweichung Admin=QMB bereinigt (separates Paket, nicht AP-028)?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`
  - `docs/AP-004_USER_CONTEXT_ADR.md`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `modules/usermanagement/role_policies.py`
  - `modules/incident_management/authorization.py`
  - `interfaces/pyqt/widgets/access_guards.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Prüfung, ob `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md` bereits existiert.
  - Keine zusätzlichen Code-Suchläufe nötig; AP-003/AP-004 und gezielte ReadFile-Hotspots waren ausreichend.
- Keine Testsuite ausgeführt, weil AP-005 ein ADR-/Dokumentationspaket ist.
- Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
AP-028 Milestone 0 (Ist-/Zielmatrix) bzw. danach Milestone 1 (öffentliche Identitäts- und Sessionverträge) starten; Incident-Admin=QMB-Cleanup nicht mitziehen.
