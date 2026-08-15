# Container-Modul — Requirements Traceability (M0)

Status: **module prototype passed** für GM-01 bis GM-25 und NI-01 bis NI-13;
der lokale Backend-/Swagger-Transport ist in M5 automatisiert und manuell
smoke-getestet. Produktive Mehrbenutzer-, PostgreSQL- und Kryptografie-E2E-
Nachweise bleiben ausdrücklich außerhalb dieses Prototyps.
Scope: GM-01 bis GM-25, Prototyp-Meilensteine M1–M5
Vertrag: `docs/container-module/ARCHITECTURE_CONTRACT.md`

Diese Matrix ist die verbindliche M0-Planung für die fachlichen Gerätemanage-
ment-Use-Cases. Sie benennt je GM ein beobachtbares Akzeptanzkriterium, den
geplanten Meilenstein und einen konkreten Testnamen samt Datei. M0 enthält
keine Code-, Test- oder Dependency-Änderung.

## 1. GM-Traceability (historische M0-Planung; durch §4 als aktueller Nachweis ersetzt)

| ID | Akzeptanzkriterium (kurz) | Meilenstein | Vorgesehener Test (Name / Datei) | Status |
| --- | --- | --- | --- | --- |
| GM-01 | QMB/Admin erzeugt aus veröffentlichtem `Gerät`-Template ein Object mit stabiler UID, gebundener Version, Pflicht-Children und AuditEvent. | M1 | `test_create_object_from_published_template` / `tests/modules/container/test_container_object_lifecycle.py` | planned |
| GM-02 | Stammdaten werden backendseitig anhand FieldDefinitions und Policies validiert, gespeichert und aktualisiert. | M1 | `test_validate_and_update_device_master_data` / `tests/modules/container/test_container_fields.py` | planned |
| GM-03 | Feste Children entstehen automatisch als normale Objects mit UID und können nicht verschoben/entfernt werden. | M1 | `test_create_fixed_children_and_reject_structural_change` / `tests/modules/container/test_container_tree.py` | planned |
| GM-04 | Unter `Wartungen` wird ein neues Object mit UID, Template-Version, Status und Audit angelegt. | M1 | `test_create_maintenance_object_under_device` / `tests/modules/container/test_container_object_lifecycle.py` | planned |
| GM-05 | Ein Wartungs-Artifact kann ohne Datei angelegt und gemäß ArtifactTemplate validiert werden. | M2 | `test_create_fileless_artifact_multiple_files_and_typed_values` / `tests/modules/container/test_container_m2_artifacts.py` | M2-Prototyp geprüft; Backend-E2E steht aus |
| GM-06 | Ein Artifact bündelt PDF, Foto und Messdaten als mehrere ArtifactFiles mit eigenen UIDs. | M2 | `test_create_fileless_artifact_multiple_files_and_typed_values` / `tests/modules/container/test_container_m2_artifacts.py` | M2-Prototyp geprüft; Backend-E2E steht aus |
| GM-07 | Finalisierung prüft Aktionen/Policies und erzeugt Snapshot, Hash sowie irreversible Immutability für Artifact und Dateien. | M2 | `test_finalization_snapshot_is_deterministic_and_blocks_mutation` / `tests/modules/container/test_container_m2_artifacts.py` | M2-Prototyp geprüft; Policy-/Backend-E2E steht aus |
| GM-08 | Signatur bezieht sich auf den exakten finalen Zustand; Mehrfachsignatur und vollständiges Audit bleiben nachvollziehbar. | M2 | `test_signature_and_correction_copy_files_without_changing_original` / `tests/modules/container/test_container_m2_artifacts.py` | M2-Prototyp geprüft; produktive Kryptografie nicht im Scope |
| GM-09 | Ein signierter Object-Zustand bleibt rekonstruierbar, während das Object gemäß Policy weiter bearbeitbar bleibt. | M3 | `test_external_reference_lifecycle_signature_archive_and_search` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft; keine produktive Kryptografie |
| GM-10 | Eine Wartung referenziert eine konkrete freigegebene SOP-Version über stabile externe IDs. | M3 | `test_external_reference_lifecycle_signature_archive_and_search` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft; Resolver-Port |
| GM-11 | Dynamische SOP-Referenz löst die aktuelle gültige Version auf und auditiert jede konkrete Auflösung. | M3 | `test_external_reference_lifecycle_signature_archive_and_search` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft; Stub/fehlender Resolver |
| GM-12 | Freier Querverweis verwendet Reference und LinkType; identisches Paar/LinkType wird nur einmal zugelassen. | M3 | `test_references_are_canonical_visible_and_physical_delete_is_decision_point` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft |
| GM-13 | Verschieben ändert die Object-UID nicht, erhält References und erzeugt ein Struktur-AuditEvent. | M3 | `test_move_object_preserves_uid_and_references` / `tests/modules/container/test_container_tree.py` | planned |
| GM-14 | Korrektur eines finalen Nachweises erzeugt neues Artifact plus `corrects`-Relation; Original bleibt immutable. | M2/M3 | `test_signature_and_correction_copy_files_without_changing_original` / `tests/modules/container/test_container_m2_artifacts.py` | M3-Prototyp geprüft; Relation sichtbar |
| GM-15 | Statuswechsel aktiv→außer Betrieb ist nur als erlaubter, rollen-/begründungs-/signaturkonformer Übergang möglich und wird auditiert. | M3 | `test_external_reference_lifecycle_signature_archive_and_search` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft |
| GM-16 | Archivierung macht Parent read-only, wendet Child-Regel an und erhält Links. | M3 | `test_external_reference_lifecycle_signature_archive_and_search` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft |
| GM-17 | Reaktivierung eines archivierten Geräts ist ein expliziter berechtigter, vollständig auditierter Vorgang. | M3 | `test_external_reference_lifecycle_signature_archive_and_search` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft |
| GM-18 | Seriennummernsuche liefert nur berechtigte Treffer, nutzt `searchable` und blendet Archiv standardmäßig aus. | M3 | `test_read_requires_confirmed_actor_and_search_is_permission_filtered` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft |
| GM-19 | Erweiterte Referenzsuche findet berechtigte Nachweise zu einem Gerät und filtert backendseitig. | M3 | `test_references_are_canonical_visible_and_physical_delete_is_decision_point` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft |
| GM-20 | Geräte-Teilbaum wird als fachlicher Export mit optionalen Artifacts, Printable-Ausgabe und UID/Hash-Manifest erzeugt. | M5 | `test_export_device_subtree_with_manifest` / `tests/modules/container/test_container_export.py` | planned |
| GM-21 | Stichtags-Export wird als eigenes Artifact abgelegt und kann finalisiert/signiert/referenziert werden. | M5 | `test_store_export_as_artifact` / `tests/modules/container/test_container_export.py` | planned |
| GM-22 | Physische Löschung prüft globale/Template-Policy, Backup/Vier-Augen, Begründung, Tombstone und Audit. | M5 | `test_physical_delete_requires_policy_backup_and_tombstone` / `tests/modules/container/test_container_deletion.py` | planned |
| GM-23 | Template V2 wird nach Konsistenzprüfung als immutable Version veröffentlicht; bestehende Geräte bleiben unverändert gebunden. | M5 | `test_publish_template_v2_without_mutating_existing_objects` / `tests/modules/container/test_container_templates.py` | planned |
| GM-24 | Template-Migration erfolgt nur explizit; Änderungen und Ergebnis werden auditierbar persistiert. | M5 | `test_explicit_template_migration_is_audited` / `tests/modules/container/test_container_templates.py` | planned |
| GM-25 | Detailabfrage liefert serverseitig `allowed_actions` sowie maschinenlesbare Codes/Parameter; Client leitet nichts selbst ab. | M3 | `test_archive_subtree_search_pagination_and_decisions` / `tests/modules/container/test_container_m3_policy_references.py` | M3-Prototyp geprüft; Backend-Transport folgt |

## 2. Negative Invarianten (historische M0-Planung; durch §4 als aktueller Nachweis ersetzt)

Diese Invarianten sind unabhängig von fachlicher Konfiguration technisch
verbindlich. Jeder Eintrag benötigt mindestens den genannten negativen Test;
alle sind im M0-Status `planned`.

| ID | Negative Invariante / erwartete Ablehnung | Geplanter Test / Datei | Status |
| --- | --- | --- | --- |
| NI-01 | Object ohne Parent oder mit gleichzeitigem WorkspaceRoot- und Object-Parent wird abgelehnt. | `test_object_has_exactly_one_structural_parent` / `tests/modules/container/test_container_tree.py` | planned |
| NI-02 | Baumtiefe über technischem `max_depth=32` wird abgelehnt; Admin-Settings dürfen die Grenze nicht erhöhen. | `test_reject_object_beyond_pseudo_hard_depth_limit` / `tests/modules/container/test_container_tree.py` | planned |
| NI-03 | Pfad, Anzeigename oder wechselnde `latest`-Auflösung wird nicht als persistente Identität akzeptiert. | `test_require_stable_uids_and_explicit_template_version` / `tests/modules/container/test_container_identity.py` | planned |
| NI-04 | Direkter Client-/Desktop-Zugriff auf Container-SQLite bzw. Desktop-Registrierung ist ausgeschlossen; nur Backend-Komposition öffnet DB. | `test_container_is_backend_only_and_desktop_does_not_open_db` / `tests/architecture/test_container_backend_boundary.py` | planned |
| NI-05 | Command ohne bestätigten UserContext oder mit unbestätigter Actor-Rolle wird abgelehnt. | `test_commands_require_confirmed_user_context` / `tests/modules/container/test_container_authorization.py` | planned |
| NI-06 | Veröffentlichung einer inkonsistenten Template-Version wird abgelehnt; veröffentlichte Version ist danach unveränderlich. | `test_reject_inconsistent_publish_and_edit_published_version` / `tests/modules/container/test_container_templates.py` | planned |
| NI-07 | Finalisiertes/immutables Artifact oder ArtifactFile darf über keinen normalen Schreibpfad editiert/überschrieben werden. | `test_reject_write_after_artifact_finalization` / `tests/modules/container/test_container_artifact_immutability.py` | planned |
| NI-08 | Korrektur überschreibt Original nicht, sondern verlangt neues Artifact und `corrects`-Relation. | `test_reject_in_place_correction_of_immutable_artifact` / `tests/modules/container/test_container_artifact_immutability.py` | planned |
| NI-09 | Referenz ohne stabile Ziel-UID oder Duplicate `(source,target,link_type)` wird abgelehnt; Verschieben darf Links nicht brechen. | `test_reject_broken_or_duplicate_reference` / `tests/modules/container/test_container_references.py` | planned |
| NI-10 | Erfolgs-Event vor Commit oder bei Rollback wird nicht veröffentlicht. | `test_publish_domain_event_only_after_successful_commit` / `tests/modules/container/test_container_event_contracts.py` | planned |
| NI-11 | Nicht autorisierte Suche und `allowed_actions` dürfen keine Daten bzw. Aktionen offenlegen. | `test_search_and_allowed_actions_do_not_leak_unauthorized_data` / `tests/modules/container/test_container_authorization.py` | planned |
| NI-12 | Automatische Template-/Schema-Migration bestehender Instanzen wird abgelehnt. | `test_new_template_version_does_not_auto_migrate_instances` / `tests/modules/container/test_container_templates.py` | planned |
| NI-13 | Physisches Löschen ohne privilegierte Policy, Begründung, erforderliches Backup/Vier-Augen oder Tombstone wird abgelehnt. | `test_reject_delete_without_policy_evidence_and_tombstone` / `tests/modules/container/test_container_deletion.py` | planned |

## 3. Acceptance-Checklist-Zuordnung

Die IDs referenzieren die Abschnitte von `spec/06_Acceptance_Checklist.md`.
Die Zuordnung macht sichtbar, in welchem M1–M5-Paket die Checklist abgedeckt
wird; jede Zeile bleibt bis zur Implementierung `planned`.

| Checklist-Bereich / Punkt | Zugeordnete Anforderungen | Meilenstein(e) | Geplanter Nachweis | Status |
| --- | --- | --- | --- | --- |
| Architecture: eigenständiges Backend-Modul; keine internen Cross-Module-Zugriffe | Contract §2; NI-04 | M1 | `tests/architecture/test_container_backend_boundary.py` | planned |
| Architecture: stabile IDs für persistierte References | Contract §3; GM-10–12; NI-03/NI-09 | M1/M3 | `tests/modules/container/test_container_identity.py`, `test_container_references.py` | planned |
| Architecture: genau ein Object-Parent | Contract §3; NI-01 | M1 | `test_object_has_exactly_one_structural_parent` | planned |
| Architecture: explizite Template-Version; veröffentlichte Version immutable | GM-01, GM-23/24; NI-03/NI-06/NI-12 | M1/M5 | `tests/modules/container/test_container_templates.py` | planned |
| Architecture: keine automatische Schema-Migration | Contract §5; NI-12 | M5 | `test_new_template_version_does_not_auto_migrate_instances` | planned |
| PoC: Geräte-Template veröffentlichen und Gerät mit Pflicht-Children erzeugen | GM-01, GM-03 | M1 | `tests/modules/container/test_container_object_lifecycle.py`, `test_container_tree.py` | planned |
| PoC: Stammdaten validieren/suchen und Wartungs-Object erzeugen | GM-02, GM-04, GM-18 | M1/M4 | `test_container_fields.py`, `test_container_search.py` | planned |
| PoC: fileless/multiple-file Artifact | GM-05, GM-06 | M2 | `tests/modules/container/test_container_artifacts.py` | planned |
| PoC: Finalisierung = Snapshot + Hash + Immutability | GM-07; NI-07/NI-08 | M2/M3 | `tests/modules/container/test_container_artifact_immutability.py` | planned |
| PoC: stabile References und Verschieben ohne Linkbruch | GM-10–13; NI-09 | M3 | `tests/modules/container/test_container_references.py`, `test_container_tree.py` | planned |
| PoC: Korrektur als neues Artifact + `corrects` | GM-14; NI-08 | M3 | `test_correct_final_artifact_creates_new_immutable_lineage` | planned |
| PoC: Object-/Artifact-Status, Archivierung/Reaktivierung nach Policy | GM-15–17 | M4 | `tests/modules/container/test_container_status.py`, `test_container_archive.py` | planned |
| PoC: Export mit Manifest; Export als Artifact | GM-20/21 | M5 | `tests/modules/container/test_container_export.py` | planned |
| PoC: backendseitige `allowed_actions` | GM-25; NI-05/NI-11 | M5 | `tests/modules/container/test_container_authorization.py` | planned |
| Tests: positive Tests für alle GM; negative Invarianten | GM-01–25; NI-01–13 | M1–M5 | Traceability-Matrix plus genannte Testdateien | planned |
| Tests: Suche leakt keine unberechtigten Treffer | GM-18/19; NI-11 | M4 | `tests/modules/container/test_container_search.py`, `test_container_authorization.py` | planned |
| Tests: Immutability, Template-Versionen, References, Linkduplikate | GM-07, GM-12, GM-14, GM-23/24; NI-06–09/NI-12 | M2/M3/M5 | Artefakt-, Referenz- und Template-Tests | planned |
| Tests: Audit für Struktur, Status, Links, Finalisierung | GM-01, GM-03, GM-07, GM-12–17, GM-22; NI-10 | M1–M5 | `tests/modules/container/test_container_audit.py`, `test_container_event_contracts.py` | planned |
| Nicht im Prototyp: keine Rule-Engine, Vererbung, gespeicherte Ansichten, vollständige Signaturintegration | Contract §9; Spec 04 B | M0 (Scope-Gate) | Architecture-Contract-Review; keine Implementierung in M0 | planned |

## 4. Aktueller automatisierter Modulnachweis (M5)

Alle folgenden Nachweise laufen im selben Modul-Testlauf. `module prototype
passed` bedeutet ausdrücklich keinen produktiven Mehrbenutzer-, PostgreSQL-
oder Kryptografie-E2E-Nachweis. Der lokale HTTP-Transport wird separat durch
`tests/backend/test_container_routes.py` und
`tests/backend/test_container_demo.py` nachgewiesen.

| ID | Exakter laufender Nachweis | Status |
| --- | --- | --- |
| GM-01 | `test_create_object_from_published_template_and_fixed_children` / `test_container_m1.py` | module prototype passed |
| GM-02 | `test_validate_fields_and_revision_conflict` / `test_container_m1.py` | module prototype passed |
| GM-03 | `test_create_object_from_published_template_and_fixed_children` / `test_container_m1.py` | module prototype passed |
| GM-04 | `test_create_object_from_published_template_and_fixed_children` / `test_container_m1.py` | module prototype passed |
| GM-05 | `test_create_fileless_artifact_multiple_files_and_typed_values` / `test_container_m2_artifacts.py` | module prototype passed |
| GM-06 | `test_create_fileless_artifact_multiple_files_and_typed_values` / `test_container_m2_artifacts.py` | module prototype passed |
| GM-07 | `test_finalization_snapshot_is_deterministic_and_blocks_mutation` / `test_container_m2_artifacts.py` | module prototype passed |
| GM-08 | `test_signature_and_correction_copy_files_without_changing_original` / `test_container_m2_artifacts.py` | module prototype passed |
| GM-09 | `test_lifecycle_negative_signatures_and_event_after_commit` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-10 | `test_external_reference_lifecycle_signature_archive_and_search` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-11 | `test_external_reference_lifecycle_signature_archive_and_search` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-12 | `test_references_are_canonical_visible_and_physical_delete_is_decision_point` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-13 | `test_reference_variants_move_and_correction_are_publicly_visible` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-14 | `test_reference_variants_move_and_correction_are_publicly_visible` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-15 | `test_lifecycle_negative_signatures_and_event_after_commit` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-16 | `test_archive_subtree_search_pagination_and_decisions` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-17 | `test_archive_subtree_search_pagination_and_decisions` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-18 | `test_read_requires_confirmed_actor_and_search_is_permission_filtered` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-19 | `test_references_are_canonical_visible_and_physical_delete_is_decision_point` / `test_container_m3_policy_references.py` | module prototype passed |
| GM-20 | `test_export_is_deterministic_permission_complete_and_printable` / `test_container_m4_export_delete_migration.py` | module prototype passed |
| GM-21 | `test_export_fails_closed_for_hidden_child_and_can_be_stored_finalized_signed` / `test_container_m4_export_delete_migration.py` | module prototype passed |
| GM-22 | `test_physical_delete_is_policy_evidence_and_approval_guarded` / `test_container_m4_export_delete_migration.py` | module prototype passed |
| GM-23 | `test_publish_is_immutable_and_new_version_does_not_migrate_instances` / `test_container_m1.py` | module prototype passed |
| GM-24 | `test_explicit_template_migration_keeps_v1_until_command_and_audits` / `test_container_m4_export_delete_migration.py` | module prototype passed |
| GM-25 | `test_archive_subtree_search_pagination_and_decisions` / `test_container_m3_policy_references.py` | module prototype passed |

| ID | Exakter negativer Nachweis | Status |
| --- | --- | --- |
| NI-01 | `test_reject_fixed_move_cycle_and_missing_parent` / `test_container_m1.py` | module prototype passed |
| NI-02 | `test_depth_limit_and_flexible_move_rebase` / `test_container_m1.py` | module prototype passed |
| NI-03 | `test_publish_is_immutable_and_new_version_does_not_migrate_instances` / `test_container_m1.py` | module prototype passed |
| NI-04 | `test_container_is_backend_only_and_exports_only_api_port` / `tests/architecture/test_container_backend_boundary.py` | module prototype passed |
| NI-05 | `test_read_requires_confirmed_actor_and_search_is_permission_filtered` / `test_container_m3_policy_references.py` | module prototype passed |
| NI-06 | `test_publish_is_immutable_and_new_version_does_not_migrate_instances` / `test_container_m1.py` | module prototype passed |
| NI-07 | `test_finalization_snapshot_is_deterministic_and_blocks_mutation` / `test_container_m2_artifacts.py` | module prototype passed |
| NI-08 | `test_signature_and_correction_copy_files_without_changing_original` / `test_container_m2_artifacts.py` | module prototype passed |
| NI-09 | `test_reference_variants_move_and_correction_are_publicly_visible` / `test_container_m3_policy_references.py` | module prototype passed |
| NI-10 | `test_delete_rejects_non_empty_leaf_and_failed_mutation_publishes_no_event` / `test_container_m4_export_delete_migration.py` | module prototype passed |
| NI-11 | `test_read_requires_confirmed_actor_and_search_is_permission_filtered` / `test_container_m3_policy_references.py` | module prototype passed |
| NI-12 | `test_explicit_template_migration_keeps_v1_until_command_and_audits` / `test_container_m4_export_delete_migration.py` | module prototype passed |
| NI-13 | `test_physical_delete_is_policy_evidence_and_approval_guarded` / `test_container_m4_export_delete_migration.py` | module prototype passed |

## 5. M0-Baseline und Verifikationsgrenze

Die M0-Baseline ist ausdrücklich keine Aussage, dass die Gesamtsuite grün
ist. Dokumentierter Ausgangsstand:

- unveränderte **Linux/Python-3.12-Umgebung**;
- die vollständige Suite kann in dieser Linux-Umgebung wegen fehlendem
  `libEGL.so.1` bereits bei zehn PyQt-/Interface-Testmodulen nicht sammeln;
- im separat sammelbaren `modules`-/`platform`-/`backend`-Umfang sind ein
  PyQt-Startpfad und drei Windows-DOCX/COM-Pfadtests umgebungsgebunden;
- **PostgreSQL-Live-Tests werden mangels DSN übersprungen**;
- daraus folgt ausdrücklich: **keine Behauptung, dass die Gesamtsuite grün
  ist**.

M0 selbst ändert ausschließlich Dokumentation. Die vorgesehenen Testnamen sind
Planungsziele für M1–M5 und wurden in M0 nicht als implementierte Tests
ausgegeben.

## 6. M2-Prototypentscheidung

M2 implementiert Artefakte inklusive fileless und 0..n Dateien, serverseitig
generierte Storage-Pfade, SHA-256/Größenprüfung, relationalem Snapshot,
irreversibler Finalisierung sowie einer bewusst vereinfachten,
snapshot-gebundenen Signatur. Die Signatur ist **keine** produktive
kryptografische Signaturintegration. Korrekturen kopieren geprüfte Dateien in
neue Artefakt-Datei-IDs und Pfade und halten die Herkunft relational fest.
Die fokussierten M2-Tests sind ein Modulnachweis; sie ersetzen weder die noch
später ergänzte Backend-Transportprüfung noch die M3-Referenz-Policy-Prüfung.

## 7. M5-Transport- und GUI-Nachweis

Der strikt authentifizierte Produktionsrouter und die explizit isolierte
lokale Demo verwenden denselben öffentlichen `ContainerApi`-Port. Die Demo
mountet weder Auth- noch User-Admin-Routen, markiert OpenAPI sichtbar als
`LOCAL DEMO – NO PRODUCTION AUTH` und hält Daten auch bei gesetzten
Produktions-Pfadvariablen unter dem gewählten `--app-home`. Der automatisierte
HTTP-Happy-Path umfasst Template → Object → Artifact → Upload/Download →
Finalisierung; negative Nachweise umfassen Auth, gefälschte Payload-Felder,
ungültige Nested-Commands, Base64, Dateinamen/Response-Header, Größenlimit und
Immutability. Die menschliche Prüfanleitung steht in `MANUAL_TEST.md`.
