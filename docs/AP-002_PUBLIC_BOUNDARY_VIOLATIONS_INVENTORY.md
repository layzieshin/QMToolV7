# AP-002 Public-Boundary-Verstöße Inventar

## Status
- Arbeitspaket: AP-002
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Migration: nein

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` auf `docs/AP-002_PUBLIC_BOUNDARY_VIOLATIONS_INVENTORY.md` zur Existenzprüfung.
  - `ReadFile` für `docs/MASTER_ORCHESTRATION_ROADMAP.md`, `AGENTS.md` und `.cursor/rules/00-agent-workflow.mdc`.
  - `rg "^\\s*(from\\s+modules\\.[A-Za-z0-9_\\.]+\\s+import\\s+|import\\s+modules\\.[A-Za-z0-9_\\.]+)"` in `interfaces`, `tests`, `modules`, `src/backend`, `qm_platform`.
  - `rg "^\\s*(from\\s+src\\.backend\\.[A-Za-z0-9_\\.]+\\s+import\\s+|import\\s+src\\.backend\\.[A-Za-z0-9_\\.]+)"`.
  - `rg` auf Dokumentationshinweise zu `api.py`, `contracts.py`, Public Boundary, Re-Exports und Wrapper-APIs.
  - Kleine lokale Python-AST-Analyse mit `.\.venv\Scripts\python.exe -c ...`, nur lesend, zur vollständigen Import-Zählung und Kategorienvorbereitung.
- Geprüfte Bereiche:
  - `interfaces/*`
  - `tests/*`
  - `modules/*`
  - `src/backend/*`
  - `qm_platform/*`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
- Ausgeschlossene Bereiche:
  - Keine absichtlich ausgeschlossenen Bereiche innerhalb des freigegebenen Scopes.
  - Nicht-Python-Dateien wurden nur für die Regel-/Dokumentationsprüfung durchsucht, nicht als Code-Import-Funde gezählt.
- Datum der Analyse: 2026-06-26

## Zusammenfassung
- Import-Funde insgesamt in der AST-Analyse: 285
- Relevante Prüf-/Entscheidungsfunde ohne zulässige Kategorie C: 252
- Anzahl Kategorie A: 41
- Anzahl Kategorie B: 1
- Anzahl Kategorie C: 33
- Anzahl Kategorie D: 210
- Anzahl Kategorie E: 0

Hinweis: `src/backend/__main__.py` importiert `src.backend.api` und wurde als zulässiger Backend-API-Import gezählt, nicht als Kategorie-E-Grenzrisiko.

## Kategorie A — Echte Public-Boundary-Verstöße

| Datei | Zeile | Import | Zielmodul | Interne Zieldatei | Kurzbewertung | Risiko | Vorschlag für späteres Cleanup-Paket, falls eindeutig |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| `interfaces/pyqt/contributions/common.py` | 6 | `from modules.documents.contracts import SystemRole` | documents | contracts | PyQt-Adapter importiert DTO/Enum direkt aus internem Vertrag. | mittel | Adapter-DTO/Enum-Importe aus documents über `modules/documents/api.py` prüfen. |
| `interfaces/pyqt/contributions/documents_workflow_view.py` | 37 | `from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType` | documents | contracts | PyQt-View nutzt interne Dokumentenverträge direkt. | mittel | Documents-PyQt-Contract-Importe bündeln und API-Exportentscheidung separat freigeben. |
| `interfaces/pyqt/presenters/documents_signature_ops.py` | 27 | `from modules.documents.contracts import ArtifactType` | documents | contracts | Presenter importiert internen Dokumentenvertrag direkt. | mittel | Documents-Signature-Presenter-Boundary-Cleanup planen. |
| `interfaces/pyqt/presenters/documents_signature_ops.py` | 28 | `from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput` | signature | contracts | Presenter importiert Signaturverträge direkt. | mittel | Signature-DTO-API-Exportentscheidung vor Cleanup klären. |
| `interfaces/pyqt/presenters/documents_workflow_filter_presenter.py` | 5 | `from modules.documents.contracts import DocumentStatus` | documents | contracts | Presenter importiert internen Dokumentenstatus direkt. | mittel | In Documents-PyQt-Boundary-Cleanup aufnehmen. |
| `interfaces/pyqt/presenters/documents_workflow_presenter.py` | 3 | `from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole` | documents | contracts | Presenter importiert mehrere interne Dokumentenverträge direkt. | mittel | In Documents-PyQt-Boundary-Cleanup aufnehmen. |
| `interfaces/pyqt/presenters/incident_management_presenter.py` | 6 | `from modules.incident_management.contracts import (` | incident_management | contracts | Presenter importiert Incident-Verträge direkt. | mittel | Incident-PyQt-Boundary-Cleanup separat planen. |
| `interfaces/pyqt/presenters/training_presenter.py` | 5 | `from modules.training.contracts import TrainingInboxItem` | training | contracts | Presenter importiert Trainingsvertrag direkt. | mittel | Training-PyQt-Boundary-Cleanup separat planen. |
| `interfaces/pyqt/widgets/audit_log_helpers.py` | 6 | `from modules.documents.contracts import DocumentStatus` | documents | contracts | Shared Widget/Helper importiert Dokumentenstatus direkt. | mittel | Prüfen, ob UI-Hilfslogik DTOs über API beziehen darf. |
| `interfaces/pyqt/widgets/document_create_wizard.py` | 8 | `from modules.documents.contracts import DocumentType` | documents | contracts | PyQt-Wizard importiert Dokumententyp direkt. | mittel | Documents-Create-Wizard in API-Boundary-Cleanup aufnehmen. |
| `interfaces/pyqt/widgets/pdf_viewer_dialog.py` | 239 | `from modules.documents.contracts import WorkflowCommentContext` | documents | contracts | Widget importiert Workflow-Kommentar-Kontext direkt. | mittel | PDF-Viewer-Kommentarimports über Documents-API klären. |
| `interfaces/pyqt/widgets/pdf_viewer_dialog.py` | 243 | `from modules.documents.contracts import WorkflowCommentContext` | documents | contracts | Wiederholter lokaler Import im Widget. | mittel | Zusammen mit PDF-Viewer-Kommentarimports behandeln. |
| `interfaces/pyqt/widgets/pdf_viewer_dialog.py` | 305 | `from modules.documents.contracts import WorkflowCommentContext` | documents | contracts | Wiederholter lokaler Import im Widget. | mittel | Zusammen mit PDF-Viewer-Kommentarimports behandeln. |
| `interfaces/pyqt/widgets/pdf_viewer_dialog.py` | 309 | `from modules.documents.contracts import WorkflowCommentContext` | documents | contracts | Wiederholter lokaler Import im Widget. | mittel | Zusammen mit PDF-Viewer-Kommentarimports behandeln. |
| `interfaces/pyqt/widgets/reject_reason_dialog.py` | 5 | `from modules.documents.contracts import RejectionReason` | documents | contracts | Widget importiert Ablehnungsgrund direkt. | mittel | Documents-Workflow-Dialoge als Cleanup-Paket prüfen. |
| `interfaces/pyqt/widgets/signature_preview_panel.py` | 9 | `from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput` | signature | contracts | Widget importiert Signatur-DTOs direkt. | mittel | Signature-PyQt-DTO-Boundary-Cleanup prüfen. |
| `interfaces/pyqt/widgets/signature_request_form.py` | 7 | `from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput` | signature | contracts | Widget importiert Signatur-DTOs direkt. | mittel | Signature-PyQt-DTO-Boundary-Cleanup prüfen. |
| `interfaces/pyqt/widgets/signature_sign_wizard.py` | 27 | `from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput` | signature | contracts | Widget importiert Signatur-DTOs direkt. | mittel | Signature-PyQt-DTO-Boundary-Cleanup prüfen. |
| `interfaces/pyqt/widgets/validity_extension_dialog.py` | 22 | `from modules.documents.contracts import ValidityExtensionOutcome` | documents | contracts | Widget importiert Dokumentenvertrag direkt. | mittel | Documents-Workflow-Dialoge als Cleanup-Paket prüfen. |
| `interfaces/pyqt/widgets/workflow_profile_wizard.py` | 7 | `from modules.documents.contracts import ControlClass, DocumentStatus` | documents | contracts | Widget importiert interne Dokumentenverträge direkt. | mittel | Documents-Workflow-Dialoge als Cleanup-Paket prüfen. |
| `interfaces/pyqt/widgets/signature_placement/options_mixin.py` | 22 | `from modules.signature.contracts import LabelLayoutInput` | signature | contracts | Widget-Mixin importiert Signatur-DTO direkt. | mittel | Signature-Placement-Boundary-Cleanup prüfen. |
| `interfaces/pyqt/widgets/signature_placement/placement_dialog.py` | 38 | `from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput` | signature | contracts | Dialog importiert Signatur-DTOs direkt. | mittel | Signature-Placement-Boundary-Cleanup prüfen. |
| `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py` | 28 | `from modules.documents.contracts import ArtifactType, DocumentStatus, DocumentType, SystemRole, ValidityExtensionOutcome, control_class_for` | documents | contracts | PyQt-Workflow-Mixin importiert viele Dokumentenverträge direkt. | hoch | Documents-Workflow-PyQt-Imports als eigenes Cleanup-Paket. |
| `interfaces/pyqt/contributions/documents_workflow/core_mixin.py` | 17 | `from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, SystemRole, control_class_for` | documents | contracts | PyQt-Workflow-Core importiert viele Dokumentenverträge direkt. | hoch | Documents-Workflow-PyQt-Imports als eigenes Cleanup-Paket. |
| `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py` | 14 | `from modules.documents.contracts import ArtifactType, DocumentStatus, SystemRole, WorkflowCommentStatus` | documents | contracts | PyQt-Workflow-Selection importiert Dokumentenverträge direkt. | hoch | Documents-Workflow-PyQt-Imports als eigenes Cleanup-Paket. |
| `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py` | 144 | `from modules.documents.contracts import WorkflowCommentContext` | documents | contracts | Lokaler Import aus internem Vertrag. | mittel | Zusammen mit Selection-Mixin behandeln. |
| `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py` | 148 | `from modules.documents.contracts import WorkflowCommentContext` | documents | contracts | Lokaler Import aus internem Vertrag. | mittel | Zusammen mit Selection-Mixin behandeln. |
| `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py` | 152 | `from modules.documents.contracts import WorkflowCommentContext` | documents | contracts | Lokaler Import aus internem Vertrag. | mittel | Zusammen mit Selection-Mixin behandeln. |
| `interfaces/pyqt/contributions/incident_management_sections/actions_section.py` | 16 | `from modules.incident_management.contracts import ActionType` | incident_management | contracts | PyQt-Section importiert Incident-Vertrag direkt. | mittel | Incident-PyQt-Contracts-Cleanup prüfen. |
| `interfaces/pyqt/contributions/incident_management_sections/capa_section.py` | 17 | `from modules.incident_management.contracts import CapaStatus` | incident_management | contracts | PyQt-Section importiert Incident-Vertrag direkt. | mittel | Incident-PyQt-Contracts-Cleanup prüfen. |
| `interfaces/pyqt/contributions/incident_management_sections/qmb_review_section.py` | 18 | `from modules.incident_management.contracts import IncidentAssessmentInput, IncidentClassification` | incident_management | contracts | PyQt-Section importiert Incident-Verträge direkt. | mittel | Incident-PyQt-Contracts-Cleanup prüfen. |
| `interfaces/pyqt/contributions/incident_management_sections/register_section.py` | 7 | `from modules.incident_management.contracts import IncidentListFilter, IncidentStatus` | incident_management | contracts | PyQt-Section importiert Incident-Verträge direkt. | mittel | Incident-PyQt-Contracts-Cleanup prüfen. |
| `interfaces/pyqt/contributions/incident_management_sections/submit_section.py` | 22 | `from modules.incident_management.contracts import ArtifactType, IncidentSubmission` | incident_management | contracts | PyQt-Section importiert Incident-Verträge direkt. | mittel | Incident-PyQt-Contracts-Cleanup prüfen. |
| `interfaces/pyqt/contributions/settings_sections/signature_settings_section.py` | 36 | `from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput` | signature | contracts | Settings-UI importiert Signatur-DTOs direkt. | mittel | Signature-Settings-Boundary-Cleanup prüfen. |
| `interfaces/cli/commands/documents_commands.py` | 10 | `from modules.documents.contracts import (` | documents | contracts | CLI-Command importiert Dokumentenverträge direkt. | hoch | Documents-CLI-Boundary-Cleanup separat planen. |
| `interfaces/cli/commands/documents_commands.py` | 16 | `from modules.signature.contracts import SignRequest, SignaturePlacementInput, LabelLayoutInput` | signature | contracts | CLI-Command importiert Signaturverträge direkt. | hoch | Signature-CLI-Boundary-Cleanup separat planen. |
| `interfaces/cli/commands/incident_management_commands.py` | 9 | `from modules.incident_management.contracts import (` | incident_management | contracts | CLI-Command importiert Incident-Verträge direkt. | hoch | Incident-CLI-Boundary-Cleanup separat planen. |
| `interfaces/cli/commands/settings_commands.py` | 6 | `from modules.documents.contracts import SystemRole` | documents | contracts | CLI-Command importiert Dokumentenrolle direkt. | mittel | Settings-/Role-Importe über API klären. |
| `interfaces/cli/commands/signature_commands.py` | 8 | `from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput` | signature | contracts | CLI-Command importiert Signaturverträge direkt. | hoch | Signature-CLI-Boundary-Cleanup separat planen. |
| `interfaces/cli/commands/users_commands.py` | 6 | `from modules.documents.contracts import SystemRole` | documents | contracts | CLI-Command importiert Dokumentenrolle direkt. | mittel | Users-/Role-Importe über API klären. |
| `interfaces/cli/parsers/documents_parsers.py` | 4 | `from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, ValidityExtensionOutcome` | documents | contracts | CLI-Parser importiert Dokumentenverträge direkt. | hoch | Documents-Parser-Boundary-Cleanup separat planen. |

## Kategorie B — Cross-Module-Internal-Imports

| Datei | Zeile | Import | aufrufendes Modul | Zielmodul | Kurzbewertung | Risiko |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/training/released_document_catalog_reader.py` | 4 | `from modules.documents.contracts import DocumentStatus` | training | documents | Fachmodul `training` greift direkt auf internes `documents.contracts` zu statt auf `modules.documents.api`. | hoch |

## Kategorie C — Zulässige Imports
- Imports aus `modules.<name>.api` wurden als zulässig gezählt.
- Relative bzw. same-module absolute Imports innerhalb desselben Modulordners wurden als zulässig gezählt, z. B. `modules/documents/readmodel_use_cases.py` auf `modules.documents.contracts`.
- Cross-Module-Zugriffe über `api.py` wurden als zulässig gezählt, z. B. `modules/documents/signature_guard.py` auf `modules.signature.api`.
- `src/backend/__main__.py` importiert `src.backend.api` und wurde als zulässiger Backend-API-Import gezählt.
- Anzahl Kategorie C: 33.

Stichproben:
- `interfaces/pyqt/main.py:6` -> `from modules.documents.api import prepare_docx_conversion_runtime`
- `interfaces/cli/commands/training_commands.py:7` -> `from modules.documents.api import DocumentWorkflowError, SystemRole`
- `modules/training/api.py:7` -> `from modules.usermanagement.api import is_effective_qmb`
- `modules/documents/signature_guard.py:11` -> `from modules.signature.api import SignatureError`
- `src/backend/__main__.py:5` -> `from src.backend.api import create_app`

## Kategorie D — Supervisor-Entscheidung nötig

| Datei | Zeile | Import oder Fundstelle | Grund der Unklarheit | benötigte Entscheidung |
| --- | ---: | --- | --- | --- |
| `tests/*` | diverse | 200 interne Modulimporte in Tests | Tests sind nicht automatisch erlaubt; viele sind Whitebox-/Repository-/Service-Tests, andere Adapter-/Smoke-Tests. | Testimport-Policy je Testebene festlegen: Whitebox erlaubt, Adapter/E2E über `api.py`. |
| `interfaces/gui/main.py` | 19 | `from modules.documents.contracts import DocumentStatus, RejectionReason, SystemRole` | Legacy/Test-GUI; nicht ignorieren, aber nicht aktiver GUI-Pfad. | Entscheiden, ob Legacy-Funde nur dokumentiert oder später eingefroren bereinigt werden. |
| `interfaces/gui/main.py` | 20 | `from modules.documents.errors import DocumentWorkflowError` | Legacy/Test-GUI importiert interne Fehler direkt. | Legacy-GUI-Policy festlegen. |
| `interfaces/gui/main.py` | 21 | `from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput` | Legacy/Test-GUI importiert Signaturverträge direkt. | Legacy-GUI-Policy festlegen. |
| `interfaces/gui/main.py` | 22 | `from modules.signature.errors import SignatureError` | Legacy/Test-GUI importiert interne Fehler direkt. | Legacy-GUI-Policy festlegen. |
| `qm_platform/runtime/bootstrap.py` | 5 | `from modules.documents.module import create_documents_module_contract` | Runtime-Composition-Root importiert `module.py`; Architekturdocs nennen Bootstrap/Wiring als etablierten Sonderpfad, `module.py` ist zugleich intern. | Explizit entscheiden, ob Bootstrap-Imports aus `module.py` als zulässige Runtime-Ausnahme dokumentiert werden. |
| `qm_platform/runtime/bootstrap.py` | 6 | `from modules.incident_management.module import create_incident_management_module_contract` | Wie oben. | Runtime-Ausnahme bestätigen oder alternatives Registrierungsmodell planen. |
| `qm_platform/runtime/bootstrap.py` | 7 | `from modules.registry.module import create_registry_module_contract` | Wie oben. | Runtime-Ausnahme bestätigen oder alternatives Registrierungsmodell planen. |
| `qm_platform/runtime/bootstrap.py` | 8 | `from modules.signature.module import create_signature_module_contract` | Wie oben. | Runtime-Ausnahme bestätigen oder alternatives Registrierungsmodell planen. |
| `qm_platform/runtime/bootstrap.py` | 9 | `from modules.training.module import create_training_module_contract` | Wie oben. | Runtime-Ausnahme bestätigen oder alternatives Registrierungsmodell planen. |
| `qm_platform/runtime/bootstrap.py` | 10 | `from modules.usermanagement.module import create_usermanagement_module_contract` | Wie oben. | Runtime-Ausnahme bestätigen oder alternatives Registrierungsmodell planen. |
| `modules/usermanagement/api.py` | 4 | Docstring: external callers may import from `modules.usermanagement.contracts` | Widerspricht der geschärften P0-Regel, dass externe DTOs über `api.py` explizit verfügbar gemacht werden müssen. | Dokumentations-/Docstring-Konflikt separat klären; keine Codeänderung in AP-002. |

## Kategorie E — Backend-Grenze

| Datei | Zeile | Import oder Zugriff | Art des Grenzrisikos | Kurzbewertung |
| --- | ---: | --- | --- | --- |
| Keine Funde | - | - | - | In `src/backend/*` wurden keine direkten Imports aus `modules/<name>`-Internals und keine direkten Repository-/Storage-/SQL-Zugriffe gefunden. |

## Legacy/Test-Funde
- `interfaces/gui/*`:
  - 4 interne Modulimporte in `interfaces/gui/main.py`.
  - Klassifikation: Legacy/Test-Funde, Supervisor-Entscheidung nötig.
- `tests/*`:
  - 200 interne Modulimporte in Tests.
  - Häufige Muster: `contracts.py`, `service.py`, `sqlite_repository.py`, `storage.py`, `module.py`, `errors.py`, `secure_store.py`, `*_service.py`, `*_repository.py`, `*_use_cases.py`.
  - Klassifikation: nicht automatisch freigegeben; Testebene und Zweck müssen vor Cleanup entschieden werden.
- Historische oder compatibility-nahe Funde:
  - Legacy-GUI-Funde in `interfaces/gui/main.py`.
  - Runtime-Composition-Root-Funde in `qm_platform/runtime/bootstrap.py` als etablierter, aber boundary-relevanter Sonderfall.

## Dokumentationskonflikte

| Datei | Stelle | Konflikt zur aktuellen P0-Regel `api.py` | Empfehlung: markieren, nicht ändern |
| --- | --- | --- | --- |
| `modules/usermanagement/api.py` | Docstring Zeilen 4-5 | Der Docstring erlaubt externen Zugriff auf `modules.usermanagement.contracts`; aktuelle P0-Regel verlangt explizite Exporte über `api.py`. | Separates Dokumentations-/Boundary-Cleanup-Paket planen, falls freigegeben. |
| `docs/ARCHITECTURE_REFACTOR_CANONICAL.md` | Abschnitt Phase 8 / Folge-Track | Dokument benennt direkte externe `contracts.py`-Imports als bekannte Boundary-Schulden. Das ist kein Widerspruch, aber bestätigt den Cleanup-Bedarf. | Als P0-Kontext referenzieren; keine Änderung in AP-002. |
| `docs/MASTER_ORCHESTRATION_ROADMAP.md` | Abschnitt Bestehende Planungsartefakte / Konflikte | Roadmap markiert Hinweise auf direkte `contracts.py`-Nutzung bereits als Konflikt zur geschärften P0-Grenze. | Als Steuerungsreferenz verwenden; keine Änderung in AP-002. |

## Kritischste Funde
1. `modules/training/released_document_catalog_reader.py:4` importiert `modules.documents.contracts`; einziger produktiver Cross-Module-Internal-Import zwischen Fachmodulen.
2. `interfaces/cli/parsers/documents_parsers.py:4` importiert Dokumentenverträge direkt in einem CLI-Parser.
3. `interfaces/cli/commands/documents_commands.py:10` importiert Dokumentenverträge direkt in einem CLI-Command.
4. `interfaces/cli/commands/documents_commands.py:16` importiert Signaturverträge direkt in einem Dokumenten-CLI-Command.
5. `interfaces/cli/commands/incident_management_commands.py:9` importiert Incident-Verträge direkt in einem CLI-Command.
6. `interfaces/cli/commands/signature_commands.py:8` importiert Signaturverträge direkt in einem CLI-Command.
7. `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py:28` importiert zahlreiche Dokumentenverträge direkt in PyQt-Workflow-Code.
8. `interfaces/pyqt/contributions/documents_workflow/core_mixin.py:17` importiert zahlreiche Dokumentenverträge direkt in PyQt-Workflow-Code.
9. `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py:14` importiert zahlreiche Dokumentenverträge direkt in PyQt-Workflow-Code.
10. `qm_platform/runtime/bootstrap.py:5-10` importiert `modules/*/module.py`; wahrscheinlich etablierte Runtime-Ausnahme, aber supervisorpflichtig explizit zu entscheiden.

## Offene Supervisor-Entscheidungen
- Soll `qm_platform/runtime/bootstrap.py` dauerhaft als erlaubte Runtime-Composition-Root-Ausnahme für `modules/*/module.py` dokumentiert werden?
- Welche Testebenen dürfen weiterhin direkt auf Modul-Internals importieren?
- Sollen Adapter-/E2E-/Interface-Tests auf `api.py`-Imports umgestellt werden, während reine Modul-Whitebox-Tests intern bleiben dürfen?
- Wie sollen DTOs/Enums aus `contracts.py` öffentlich bereitgestellt werden: explizite `api.py`-Exporte, eigene API-DTOs oder anderer freigegebener Vertrag?
- Soll `interfaces/gui/*` als Legacy/Test-Pfad nur dokumentiert bleiben oder später trotz Freeze bereinigt werden?
- Soll der Docstring-Konflikt in `modules/usermanagement/api.py` separat korrigiert werden?
- Sollen Cleanup-Pakete nach Modul (`documents`, `signature`, `incident_management`, `training`) oder nach Adapter (`CLI`, `PyQt`, Tests) geschnitten werden?

## Ausgeführte Gates
- Such-/Analysekommandos:
  - `Glob` Existenzprüfung für `docs/AP-002_PUBLIC_BOUNDARY_VIOLATIONS_INVENTORY.md` -> Datei existierte nicht.
  - `ReadFile` der freigegebenen Regel-/Roadmap-Dateien -> erfolgreich.
  - Mehrere `rg`-Suchen nach `from modules.`, `import modules.`, `from src.backend.`, `import src.backend.` -> erfolgreich.
  - Lokale Python-AST-Analyse mit `.\.venv\Scripts\python.exe -c ...` -> erfolgreich, 285 Import-Funde klassifiziert.
  - Ein zusätzlicher Verdichtungsversuch per PowerShell/Python scheiterte an PowerShell-Quoting; es wurden keine Projektdateien geändert und die erfolgreiche AST-Analyse blieb maßgeblich.
- Ergebnis:
  - Inventar erstellt.
  - Keine Testsuite ausgeführt, weil AP-002 ein Analyse-/Inventar-Paket ist und nur eine Markdown-Inventardatei angelegt wurde.
  - Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-002_PUBLIC_BOUNDARY_VIOLATIONS_INVENTORY.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor-Entscheidung zur Test- und Runtime-Ausnahmen-Policy treffen, bevor irgendein Cleanup-Paket aus diesem Inventar abgeleitet wird.
