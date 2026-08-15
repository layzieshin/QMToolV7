# Container-Modul — Architecture Contract (Prototype)

Status: **P1 — verbindlicher fachlicher Vertrag für M0**
Gültig für: `container`-Prototyp, Backend-first
Quelle: Spezifikationspaket `spec/01` bis `spec/06` (Stand 2026-08-11)

Dieses Dokument ist der normative Vertrag für den generischen Container-Kern.
Gerätemanagement ist im Prototyp eine Template-/Policy-Konfiguration und keine
zweite, hart codierte Fachlogik. Bei Konflikten gelten technische Invarianten
vor Template-/Policy-Konfiguration und diese vor Client-Verhalten.

## 1. Zweck und Geltungsbereich

Das Modul bildet frei konfigurierbare fachliche Container als rekursive
Objektbäume ab. Derselbe technische Kern kann Geräte, Dossiers,
Ringversuche, Analytenverzeichnisse und weitere Nachweisgruppen tragen.

M0 legt die Grenze, das Domänenmodell und die nicht verhandelbaren Regeln fest.
Die späteren Meilensteine M1–M5 liefern die Use Cases GM-01 bis GM-25; die
vollständige Zuordnung steht in
`docs/container-module/REQUIREMENTS_TRACEABILITY.md`.

## 2. Modulgrenze und Komposition

- `container` ist ein eigenständiges **Backend-only-Fachmodul**. Fachliche
  Zustandsänderungen, Berechtigungsentscheidungen, Persistenz und
  Policy-Auswertung laufen im Backend-Prozess.
- Die einzige öffentliche Python-Grenze ist
  `modules/container/api.py`. Externe Aufrufer verwenden ausschließlich diese
  API bzw. ausdrücklich verdrahtete Ports, Capabilities und Events. Interna
  (`service.py`, Repositories, Storage, SQL, `module.py`, `wiring.py` und
  Helper) sind keine Importfläche.
- Die Registrierung erfolgt in der **Backend-Komposition**. Der Desktop-Core
  registriert das Modul nicht über `core_module_contracts()` und öffnet keine
  Container-Datenbank. `ModuleContract` und die öffentliche `api.py` bleiben
  trotzdem Pflicht; die alternative Komposition ist kein alternativer
  Modulvertrag.
- SQLite wird ausschließlich vom Backend-Prozess geöffnet. Kein Desktop-Client
  und kein anderer Client greift direkt auf dieselbe SQLite-Datei zu; ein
  Use Case läuft vollständig backendseitig.
- Jeder fachliche Command wird mit einem durch Usermanagement bestätigten
  `UserContext` ausgeführt. Identität wird nicht aus einem unbestätigten
  Client-Payload, einer lokalen `current_user`-Datei oder einer selbst
  gesetzten Rolle abgeleitet. Die Bestätigung erfolgt über die öffentliche
  Usermanagement-Grenze.
- `GET /docs` (Swagger/OpenAPI) ist ausschließlich eine Test-, Diagnose- und
  Inspektionsoberfläche. Es ist weder die Desktop-Integration noch ein
  separater fachlicher Vertrag.
- Die lokalen statischen Oberflächen `/container/admin` und `/container/app`
  sind ebenfalls ausschließlich Demo- und UX-Blaupausen. Sie werden nur durch
  `src.backend.container_demo` gemountet, greifen über den öffentlichen
  HTTP-Transport zu und gehören nicht zur Backend-only-Modulimplementierung.
  Ein produktiver Client rendert die actor-gefilterte Runtime-Projektion und
  `allowed_actions`; er erhält keine Rollenpolicy und leitet keine
  Berechtigung aus Clientzustand ab.
- Direkte Zugriffe auf Interna anderer QMTool-Module sind verboten. Externe
  Referenzen (z. B. Dokumente oder Benutzer) verwenden stabile externe IDs
  und die dafür vorgesehenen Ports/APIs.

## 3. Technischer WorkspaceRoot und Baumidentität

`WorkspaceRoot` ist ein technisches, nicht fachlich konfigurierbares
Wurzelobjekt mit stabiler UID. Ein Workspace besitzt genau einen Root. Er ist
die einzige zulässige Parent-Referenz für fachliche Top-Level-Objects.

Jedes fachliche `Object` besitzt genau einen strukturellen Parent:

```text
Object.parent = WorkspaceRoot XOR Object
```

Top-Level-Objects referenzieren den WorkspaceRoot; untergeordnete Objects
referenzieren ein Object. Eine Object-Zeile darf nicht zugleich beide Parent-
Arten oder keinen Parent haben. Zusätzliche Beziehungen (einschließlich
Querverweisen) werden ausschließlich als `Reference` persistiert und ändern
die Baumzugehörigkeit nicht. Object-UIDs bleiben bei Verschiebungen stabil.

Fachliche Kernentitäten:

- `Object`: rekursiver Container mit stabiler UID, expliziter Template-Version,
  Status, Revision und genau einem strukturellen Parent.
- `ObjectTemplate`: versionierte Bauanleitung; veröffentlichte Versionen sind
  immutable.
- `FieldDefinition` / `FieldValue`: Template-Felddefinition mit stabiler UID
  bzw. Wert ohne eigene UID; Identität eines Werts ergibt sich aus Object oder
  Artifact plus FieldDefinition.
- `Artifact`: eigenständiger fachlicher Nachweis, der ohne Datei existieren
  darf und 0..n `ArtifactFile`-Datensätze bündeln kann.
- `ArtifactTemplate`: versionierte Metadaten-, Status-, Policy- und
  Snapshot-Definition für Artifacts.
- `ArtifactFile`: physische Datei mit eigener stabiler UID.
- `Reference` / `LinkType`: stabile Quelle-Ziel-Beziehung bzw. zentrale
  Definition erlaubter Linktypen.
- `Signature`, `AuditEvent`, `BackupEvidence`, `Tombstone`: eigenständige
  Signatur-, unveränderliche Historien-, Sicherungs- bzw. Löschnachweis-
  Entitäten.

Persistierte Referenzen verwenden immer stabile UIDs, nie Anzeigenamen,
Baumpfade oder Dateipfade. Unterstützte kanonische Beziehungen sind
Object→Object, Object→Artifact und Artifact→Artifact. Eine nutzerinitiierte
Artifact→Object-Verknüpfung wird kanonisch als Object→Artifact gespeichert.

## 4. Templates, Felder und Policies

- Template-Versionen werden an jeder Instanz explizit gespeichert; `latest`
  darf nie die alleinige Bindung sein.
- Zustände sind mindestens `draft`, `published` und `disabled`. Vor der
  Veröffentlichung ist eine technische Konsistenzprüfung Pflicht;
  veröffentlichte Versionen sind immutable.
- Neue Instanzen verwenden standardmäßig die aktuellste aktive veröffentlichte
  Version. Bestehende Instanzen werden niemals automatisch migriert. Eine
  Migration ist ein expliziter, auditierter Vorgang.
- Template-Vererbung und eine Rule-Engine sind im Prototyp nicht enthalten.
  Zulässig sind statische Feldattribute und Zustands-/Policy-Definitionen.
- Initiale Feldtypen sind `string`, `multiline_text`, `integer`, `decimal`,
  `boolean`, `date`, `datetime`, `single_select`, `multi_select`,
  `user_reference`, `object_reference` und `artifact_reference`.
- Feld-Policies umfassen mindestens `required`, `searchable`, `linkable`,
  `printable`, `relevant_for_review`, `historized`, `editable` und `visible`.
  Validierung und `allowed_actions` werden backendseitig bestimmt.

## 5. Persistenz, Transaktionen und Audit

- Die Container-Fachdaten liegen in der konfigurierten SQLite-Datei
  `container_db_path`; sie wird nur vom Backend-Prozess geöffnet. Datenbank-
  Constraints (Foreign Keys, Unique-Constraint für
  `(source_uid, target_uid, link_type_uid)`) ergänzen die Domainvalidierung.
- Physische Artifact-Dateien liegen unter `artifact_files_root` und werden
  ausschließlich durch den Backend-Prozess aufgelöst und geschrieben. Der
  Client erhält keine fachliche Berechtigung, lokale Pfade als Referenzen zu
  persistieren.
- Schemaänderungen erfolgen nur über explizite, vorwärts gerichtete
  Migrationen. Es gibt keine implizite Änderung bestehender Instanzen oder
  Templates.
- Mutable Objects und Artifacts führen eine Revision bzw. einen
  Concurrency-Token. Mutationen prüfen `UserContext`, Berechtigung, Revision,
  Status und statische Policy in einer Transaktionsgrenze.
- Jede Mutation, Strukturänderung, Statusänderung, Referenzänderung,
  Finalisierung, Signatur, Archivierung und Löschung erzeugt ein
  unveränderliches `AuditEvent`. Audit- und Tombstone-Daten werden nicht über
  normale Löschpfade entfernt oder überschrieben.
- Fehler liefern stabile maschinenlesbare Codes; Meldungstexte sind nur
  Darstellung. Das Backend liefert `allowed_actions` samt Codes/Parametern;
  Clients leiten Aktionen nicht aus Rollen oder Status selbst ab.

## 6. Immutability, Finalisierung und Korrekturen

- Ein Artifact darf transient bzw. ohne Datei bestehen. Ab dem konfigurierten
  Finalisierungsstatus beginnt Immutability unwiderruflich.
- Bei der Finalisierung prüft das Backend alle `allowed_actions` und Policies,
  erzeugt einen Hash über den vollständigen Zustand und einen unveränderlichen
  Snapshot relevanter Object-/Ancestor-Felder sowie Referenzen. Artifact und
  zugehörige Dateien dürfen danach über keinen normalen Schreibpfad geändert
  oder überschrieben werden.
- Eine Korrektur eines finalen Nachweises erzeugt ein neues Artifact mit neuer
  UID und einer expliziten `corrects`-Relation. Das Original bleibt immutable;
  eine erneute Signatur folgt der geltenden Policy.
- Signaturen beziehen sich auf den exakten Zustand. Sie und ihre Auditdaten
  sind unveränderlich; ein Widerruf ist nur als zusätzlicher auditierter
  Vorgang zulässig.
- Archivierung ist der Regelfall für Entfernung. Archivierte Objects sind
  read-only; Links bleiben erhalten. Physische Löschung ist privilegiert,
  policygeschützt, begründungspflichtig und hinterlässt einen Tombstone mit
  UID, Typ, Löschdaten sowie erforderlicher Backup-Referenz.

## 7. Events und Commit-Reihenfolge

Domain-Events werden als kleine, versionierte `domain.container.*.v1`-Events
veröffentlicht. Ein Event wird **erst nach erfolgreichem Commit** der
zugehörigen Mutation publiziert; ein fehlgeschlagener oder zurückgerollter
Command publiziert kein Erfolgs-Event. Events sind Benachrichtigungen über
fachliche Änderungen und kein versteckter Request/Response-Mechanismus.

Der Prototyp sieht insbesondere Events für `ObjectCreated`, `ObjectArchived`,
`ArtifactCreated`, `ArtifactFinalized`, `ArtifactSigned` und
`ArtifactCorrected` vor (kanonische Namen z. B.
`domain.container.object.created.v1`). Auditdaten sind Teil des committed
Zustands und müssen die Mutation nachvollziehbar machen.

## 8. Rekursion und technische Schutzgrenze

Fachlich ist der Baum rekursiv. Für den Prototyp gilt eine technische
Pseudo-Hard-Limitierung von **32 Object-Ebenen** (WorkspaceRoot = Ebene 0,
Top-Level-Object = Ebene 1). Die Grenze ist Code-/Deployment-Konfiguration,
nicht über Admin-UI oder fachliche Settings erhöhbar. Überschreitung wird
serverseitig mit einem stabilen Fehlercode abgelehnt und auditiert.

Kardinalität, Pflicht-Children, automatische Anlage und strukturelle Fixierung
sind dagegen Template-/Policy-Konfiguration. Fixierte Children sind normale
Objects mit eigener UID und dürfen nicht verschoben oder entfernt werden.

## 9. Scope des Prototyps

**Im Scope:**

- generischer Object-/Artifact-Baum mit WorkspaceRoot, stabilen UIDs und
  Verschieben ohne Linkbruch;
- versionierte Templates und Field-Engine mit statischen Policies;
- atomare Module-Blueprints, die mehrere Templates über lokale Schlüssel
  gruppieren, ein Object-Root festlegen und erst nach serverseitiger
  Zyklus-/Konsistenzprüfung vollständig veröffentlichen;
- Artifacts ohne Datei bzw. mit mehreren Dateien, Finalisierung, Snapshot,
  Hash und irreversibler Immutability;
- interne und externe stabile References, LinkType-Eindeutigkeit,
  Auditierung, Archivierung, Tombstones und Export-Manifeste;
- backendseitige Berechtigungsprüfung, bestätigter UserContext,
  `allowed_actions`, maschinenlesbare Ablehnungscodes und post-commit Events;
- Gerätemanagement als konfiguriertes Proof-of-Concept gemäß GM-01 bis GM-25.

**Nicht im Scope:**

- Rule-Engine, Template-Vererbung oder gespeicherte Suchansichten;
- vollständige Admin-Konsole oder gerätespezifisch hart codierte Logik;
- automatische Migration bestehender Instanzen oder implizite Schemaänderung;
- produktive, vollständige Signaturintegration und die noch offenen Details
  von Signatur-/Widerrufsmodell, Löschpolicy, Audit-Retention,
  Langzeitarchivformat und Großbaum-Performance;
- externe Ressourcen-Einbettung als Standard (vorläufig referenz-only),
  produktiver Multi-Tenant-Betrieb oder PostgreSQL-Migration des Moduls.

## 10. Prototype-Settings und Governance

| Schlüssel | Governance | Vertrag |
| --- | --- | --- |
| `container_db_path` | `operational` | Backend-only SQLite-Pfad; Backup-/Migrationsplan erforderlich. |
| `artifact_files_root` | `operational` | Backend-only Dateiablage; keine Client-Pfadlogik. |
| `max_depth` | keine Admin-Setting | Technische Pseudo-Hard-Limitierung `32`; nur Code/Deployment-Konfiguration. |
| `license_tag` | — | `none`; keine Lizenzsperre im Prototyp. |

Fachliche Policies dürfen die technischen Invarianten (UIDs, Parent-Eindeutig-
keit, Audit, Immutability, Referenzintegrität, Backend-only und `max_depth`)
nicht deaktivieren oder abschwächen.

### Physische Löschung im Prototyp

Die V1-Prototypimplementierung unterstützt physische Löschung ausschließlich
für ein **archiviertes, leeres Leaf-Object**: keine Children, Artifacts,
References, Feldwerte, Snapshots/Signaturen oder Exporte dürfen mehr daran
hängen. Nicht-leere Teilbäume werden mit dem stabilen Code
`container.deletion.nonempty_leaf_unsupported` abgelehnt; sie bleiben
archiviert und auditierbar. Vor einer erfolgreichen Löschung erzwingt eine
explizit konfigurierte globale oder templatebezogene Policy passende Rolle,
Begründung sowie ggf. SHA-256-BackupEvidence und eine target-gebundene,
bestätigte Zweitfreigabe. Das ist eine technische Sicherheitsgrenze, keine
Festlegung einer künftigen Admin-/QMB-Produktrolle.

`BackupEvidence` ist im Prototyp ein auditierter Integritätsnachweis und noch
keine Anbindung an einen produktiven Backup-Provider. Ebenso bestätigt der
Prototyp die vom Usermanagement gelieferte Identität des abweichenden zweiten
Freigebers, begrenzt Evidence/Freigabe auf Admin-/QMB-Kontexte und bindet die
Freigabe an Antragsteller und Ziel; ein vollständiger
organisatorischer Freigabeworkflow mit eigener Produktrolle bleibt außerhalb
dieses Prototyps. Vor Produktionseinführung sind beide Integrationen zwingend
zu ergänzen.

## 11. Abnahmebezug

M0 dokumentiert den Vertrag und die Traceability; es ändert keinen Code,
keine Tests und keine Dependencies. Die Akzeptanzkriterien und die geplanten
Testnamen stehen in `docs/container-module/REQUIREMENTS_TRACEABILITY.md`.
Die kompakte Spezifikations-Checklist (`spec/06_Acceptance_Checklist.md`) ist
dort den Architektur-, Use-Case-, Test- und Nicht-Scope-Punkten zugeordnet.
