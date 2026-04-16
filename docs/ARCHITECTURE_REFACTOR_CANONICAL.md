# Architecture Refactor — Canonical Document

Status: **P0 — kanonisch, verbindlich**  
Ablösung von: `docs/SRP_REFACTOR_ROADMAP.md` und `docs/TRACK_B_SRP_PREP.md` (beide jetzt P2/History)

---

## Leitprinzipien (nicht verhandelbar)

1. **Öffentliche Modulgrenze**  
   Externe Imports gehen ausschließlich über `modules/<modul>/api.py` und `contracts.py`.  
   Verboten von außen: `service.py`, `sqlite_repository.py`, `password_crypto.py`, `errors.py`.

2. **Adapter bleiben Adapter**  
   `interfaces/cli/*` und `interfaces/pyqt/*` sammeln Eingaben, rufen Ports/APIs auf, rendern Ergebnisse.  
   Sie tragen keine Workflow-Regeln, greifen nicht auf Repositories zu und konvertieren keine Dateien fachlich.

3. **Godfile-Regel**  
   Eine Datei = eine technische Verantwortung.  
   Verbotene Mischungen: Parser+Dispatch+Rendering, Widget+Dateisystem+Workflow, Service+Eventing+Storage-Details.

4. **Fassade statt Monolith**  
   Große Services bleiben als öffentliche Fassade erhalten; die eigentliche Arbeit liegt in intern getrennten Bausteinen.

---

## document_id — Identity Rule (systemweit)

- `document_id` ist **immer** eine fachliche Kennung, die der Aufrufer bereitstellt (z. B. `"VA-2024-001"`).
- Das System generiert **niemals** automatisch eine UUID als `document_id`.
- Interne IDs (artifact_id, event_id, asset_id) dürfen UUIDs verwenden — diese sind opake Systembezeichner.
- Diese Regel gilt für alle Schichten: CLI, API, Service, Repository, Tests.

---

## Hotspot-Verantwortungsmatrix

| Datei | Aktuelle Vermischung | Ziel-Schnitt | Erlaubte Schnittstelle |
|---|---|---|---|
| `interfaces/cli/main.py` | Parsing + Bootstrap + Auth + Dispatch + Rendering + Fachlogik | Nur Entry-Point, delegiert an Handler | Nur über `api.py`-Ports |
| `interfaces/pyqt/contributions/documents_workflow_view.py` | Contribution + Widget + Tabelle + Dialoge + Artefaktpfade + Signaturen + Workflow-Actions | `contribution.py` + Teilwidgets + Dialoge + Presenter | Nur über Presenter/Ports |
| `interfaces/pyqt/contributions/settings_view.py` | Mehrere eigenständige Bereiche in einer Datei | Contribution + je Widget pro Bereich | Presenter je Bereich |
| `modules/documents/service.py` | Workflow + Artefakte + Dateinamen + Release-PDF + Signatur-Gates + Registry-Sync + Events + Validierung | Fassade + `workflow_ops.py`, `artifact_ops.py`, `query_ops.py`, `validation.py`, `signature_guard.py`, `eventing.py`, `registry_sync.py`, `naming.py` | Öffentlicher Vertrag stabil |
| `modules/signature/service.py` | Ausführung + Templates + Assets + Policy + Audit + PDF-Rendering | Fassade + `execute_ops.py`, `template_ops.py`, `asset_ops.py`, `policy.py`, `audit.py`, `pdf_rendering.py` | Öffentlicher Vertrag stabil |
| `modules/usermanagement/service.py` | Auth + Session-Persistenz + Nutzerverwaltung | `auth_ops.py`, `user_admin_ops.py`, `session_store.py` | Öffentlicher Vertrag stabil |
| `modules/*/module.py` | Contract + Wiring + Policy + Infrastruktur | Nur Contract + Entry; Wiring → `wiring.py` | Module-Entry stabil |

---

## Umsetzungsreihenfolge

### Phase 0 — Refactor verbindlich machen ✅
- [x] Kanonisches Dokument anlegen (dieses Dokument)
- [x] Hotspot-Verantwortungsmatrix schriftlich festlegen
- [x] Alte Roadmap-Dokumente auf P2/History gesetzt

### Phase 1 — Boundary Cleanup ✅
- [x] `interfaces/cli/main.py`: Direkt-Imports auf `usermanagement.sqlite_repository` und `usermanagement.password_crypto` entfernt
- [x] Explizite öffentliche Fläche in `usermanagement/api.py` schärfen
- [x] `modules/documents/api.py` re-exportiert `DocumentWorkflowError`; `modules/signature/api.py` re-exportiert `SignatureError`
- [x] CLI-Commands importieren `errors` nur noch über `api.py`
- [x] Admin-Seed-Bypass durch öffentlichen Bootstrap-Use-Case (`bootstrap_admin` in `usermanagement/api.py`) ersetzt
- **Abnahme**: Kein Import aus `interfaces/*` auf interne Moduldateien. ✅ (außer `interfaces/gui/` — Legacy-Pfad)

### Phase 2 — CLI zerlegen ✅
- [x] `interfaces/cli/bootstrap.py` extrahiert
- [x] `interfaces/cli/commands/documents_commands.py`, `users_commands.py`, `settings_commands.py`, `training_commands.py`, `signature_commands.py`, `session_commands.py`, `platform_commands.py`, `runtime_commands.py`
- [x] `main.py` enthält keine `cmd_*`-Implementierungen mehr — nur noch Parser + Dispatch
- [x] `interfaces/cli/parsers/` aufgeteilt: `documents_parsers.py`, `session_parsers.py`, `users_parsers.py`, `settings_parsers.py`, `signature_parsers.py`, `training_parsers.py`, `runtime_parsers.py`
- **Abnahme**: `main.py` enthält keine `cmd_*`-Implementierungen mehr. ✅

### Phase 3A — `documents_workflow_view.py` schneiden
- [x] `models/workflow_table_model.py` — `WorkflowTableModel` extrahiert
- [x] `documents_workflow_contribution.py` (nur Registrierung) — extrahiert aus View; Catalog umgestellt
- [x] Tote Klassen entfernt: `WizardPayload`, `DocumentWizard`, `TextReasonDialog`, `_WorkflowTableModel`
- [x] `presenters/documents_signature_ops.py` — Signatur-Aufbau, Template-Verwaltung, PDF-Suche, DOCX-Konvertierung, Artefakt-Öffnung extrahiert
- [x] `presenters/documents_detail_presenter.py` — Formatierung, Überblick-/Rollen-/Verlaufszeilen extrahiert
- [x] `sections/filter_bar.py`, `sections/action_bar.py`, `sections/detail_drawer.py` — UI-Komposition extrahiert
- [ ] `documents_workflow_widget.py` (UI-Komposition) — noch in `documents_workflow_view.py` (817 Zeilen, von 1544)
- [ ] Presenter für Tabelle/Filter, Sichtbarkeit/Aktionen, Formatierung
- **Abnahme**: Keine PDF-/Artefakt-/Signaturlogik im View. ✅ (via `DocumentsSignatureOps`)

### Phase 4A — `modules/documents/service.py` schneiden
- [x] `naming.py` — Dateinamen-Aufbau, Umlaut-Transliteration
- [x] `eventing.py` — Event-Publishing, Audit-Emission
- [x] `registry_sync.py` — Registry-Projektion-Synchronisation
- [x] `validation.py` — Custom-Field-Validierung, State-Invarianten, Berechtigungsprüfungen, Profil-Validierung
- [x] `signature_guard.py` — Signatur-Enforcement, Input-PDF-Resolution
- [x] `artifact_ops.py` — Artefakt-Erstellung, Pfad-Resolution, PDF-Konvertierung, Release-PDF
- **Abnahme**: `DocumentsService` delegiert, trägt keine Detailimplementierungen mehr. ✅

### Phase 3B — `settings_view.py` schneiden
- [ ] Contribution + Widgets je Bereich (Profile, Workflow-Profile, Module, Signatur, Lizenz)
- [ ] Presenter je Bereich

### Phase 4B/4C — `signature` und `usermanagement` schneiden
- [ ] Signature: `execute_ops.py`, `template_ops.py`, `asset_ops.py`, `policy.py`, `audit.py`, `pdf_rendering.py`
- [ ] Usermanagement: `auth_ops.py`, `user_admin_ops.py`, `session_store.py`

### Phase 5 — Composition Roots
- [ ] `module.py` → nur Contract + Entry-Adapter
- [ ] `wiring.py` je Modul für Port-Registrierung

### Phase 6 — Legacy GUI einfrieren ✅
- [x] `interfaces/gui/*` nur noch Smoke-Pfad, LEGACY FROZEN Header
- [x] Keine neue Fachlogik im Tk-Pfad

### Phase 7 — Architektur-Gates scharfstellen ✅
- [x] Boundary-Gate: `interfaces/*` darf keine internen Moduldateien importieren (`test_boundary_gate_cli_commands_no_internal_imports`)
- [x] CLI-Gate: `main.py` darf keine `cmd_*`-Implementierungen enthalten (`test_cli_main_is_thin_entry_point_only`)
- [x] GUI-Gate: Legacy GUI frozen (`test_legacy_gui_frozen_header`, `test_legacy_gui_boundary_violations_accepted`)
- [x] Hotspot-Gate: Signature-Ops extrahiert (`test_documents_signature_ops_extracted`), Sections extrahiert (`test_documents_sections_extracted`)
- [x] Service-Gate: Fassade delegiert an interne Module (`test_documents_service_delegates_to_internal_modules`)
- [x] Admin-Seed-Gate: Öffentliche API statt interner Bypass (`test_admin_seed_uses_public_api`)

---

## Arbeitspaket-Regeln

- Genau **eine** Hotspot-Datei oder **eine** Boundary-Regel pro Paket.
- Keine fachliche Verhaltensänderung durch Strukturschnitte.
- Vorher/Nachher-Tests pflicht.
- Erst Extraktion → dann Delegation intern → dann Aufräumen.

---

## Was ausdrücklich nicht getan wird

- Kein Big-Bang-Umbau aller Hotspots gleichzeitig.
- Keine Splits nur nach Zeilenanzahl.
- Keine Verlagerung von Business-Logik aus Services in Presenter oder Views.
- Keine neuen `*_helper.py`-Dateien ohne klaren Verantwortungsnamen.
- Keine Sonderwege in CLI/GUI „nur für Bootstrap/temporär".

