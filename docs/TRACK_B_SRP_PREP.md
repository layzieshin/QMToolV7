# Track B SRP Preparation

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md` and P0 docs

Dieses Dokument konkretisiert die SRP-Splits für den Backend/Runtime-Folge-Track.

## Scope

- `qm_platform/runtime/lifecycle.py`
- `modules/documents/service.py`
- `modules/signature/service.py`
- `modules/usermanagement/service.py`
- `modules/*/module.py` (Composition Roots)

## Ziel

- Verantwortlichkeiten aufteilen, ohne fachliche Regeln zu ändern.
- Öffentliche API-Verträge stabil halten, solange kein expliziter Contract-Change freigegeben ist.

## B1 Lifecycle Split

### Ist
- LifecycleManager bündelt Registry, Lizenzgates, Settings-Beiträge, Start/Stop-Orchestrierung und Port-Invariant-Checks.

### Vorbereitungsschnitt
- `lifecycle_policy.py`: Lizenz-/Capability-/Settings-Gating.
- `lifecycle_orchestrator.py`: Start-/Stop-Reihenfolge.
- `lifecycle_invariants.py`: Port-/Runtime-Invariant-Checks.

## B2 DocumentsService Split

### Ist
- Workflow-Orchestrierung, Artefakte, Readmodel-nahe Sammellogik und Eventing liegen in einem Service.

### Vorbereitungsschnitt
- `documents_workflow_ops.py`
- `documents_artifact_ops.py`
- `documents_query_ops.py`
- `documents_eventing.py`

## B3 UserManagementService Split

### Ist
- Auth, Session-Datei-Persistenz und Nutzerverwaltung sind eng gekoppelt.

### Vorbereitungsschnitt
- `session_store.py` (Interface + JSON-Implementierung)
- `auth_ops.py`
- `user_admin_ops.py`

## B4 SignatureService Split

### Ist
- Signaturausführung, Template-/Asset-Orchestrierung, Passwortpolicy und Ereigniswege in einem Service.

### Vorbereitungsschnitt
- `signature_execute_ops.py`
- `signature_template_ops.py`
- `signature_policy_ops.py`

## B5 Composition Roots Split

### Ist
- `modules/*/module.py` enthält Contract + Port-Wiring + teils Laufzeitpolicy.

### Vorbereitungsschnitt
- `modules/<module>/wiring.py` für Port-Registrierung
- `module.py` als schlanker Contract- und Entry-Adapter

## Qualitätsgates

- Vorher/Nachher `tests/modules/*` und `tests/platform/*`.
- Keine Änderung der öffentlichen API-Signaturen ohne separates Contract-Gate.
- Lifecycle-Regressionstest für Start/Stop und Lizenzpfade.
