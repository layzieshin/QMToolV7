# J04-M0 Allowed-Actions Analysis

Status: Meilenstein-0-Dokumentation geschlossen; **M1/G1, G3, M2 und M2R technisch remediated und verifiziert**
  (2026-08-07, Arbeitspaket bleibt `Rejected / follow-up required` bis Live/Packaging/Human)
Datum: 2026-08-07 (Ist-Stand nach M1R + G3 + M2 + M2R; historische M0-Analyse vom 2026-08-06)
Arbeitsbaum: `I:/Projekte/QMToolV7-j04-m0` (`feature/ap-j04-m0`)
Auftrag: Backend-gesteuerte erlaubte Aktionen; M1/G1 + G3 + M2 + M2R ohne Live/Packaging

Analyseumfang: **repo-weit** (Ist). Produktcodeänderungen dieses Reparaturlaufs betreffen nur den
backendmigrierten Documents-Pfad sowie die drei M0-Dokumente.

„M0 geschlossen“ bedeutet nur: der Dokumentationsmeilenstein ist abgeschlossen.
„M1/G1 technisch abgeschlossen“ bedeutet: Policy-on-Lock-`current`, ETag-Fortschreibung,
atomare `new_version`-Semantik und 16-ACTION-Coverage inkl. referenzierter Public-API-/HTTP-
Ausführungsnachweise sind hergestellt und verifiziert. Das ist **nicht** `Ready for acceptance`
und **nicht** `Accepted`.

---

## A. Kurzfazit

### Einstufung

| Scope | Stufe |
| --- | --- |
| **Gesamtprojekt (repo-weit)** | **2. Teilweise umgesetzt** |
| **Backendmigrierter Documents-/Signature-Pfad** | **3. Weitgehend umgesetzt** (Execute/G1 + Client/OpenAPI M2 grün; Live offen) |

**Gesamtprojekt Stufe 2:** Training-Administration, Incident Management und Legacy-CLI/Tk
besitzen keine serverseitige objektbezogene Aktionsliste für unabhängige Clients. Dort
entscheiden Clients bzw. lokale Modulhilfen weiterhin über Sichtbarkeit und/oder Rollen.
Eine repo-weite Stufe 3 wäre daher zu positiv.

**Documents-/Signature Stufe 3:** Für den migrierten Pfad berechnet das Backend
objektbezogene `available_actions` (`workflow_policy` / `capabilities`) und globale
Capabilities (`GET /documents/capabilities`). Actor kommt aus der Backend-Session
(`require_user_context*` → `UserContext`); mutierende Bodies akzeptieren keine
Client-`actor_user_id`. Optimistic Locking existiert (`If-Match` /
`mutate_version_if_current` / HTTP 409, Laufzeit-428).

**M1/G1 technisch remediated (2026-08-07):**

1. Gemeinsame Policy läuft für Policy-Mutationen auf dem unter Lock geladenen `current`
   (`DocumentsService.mutate_version_if_current` → `assert_workflow_action`).
2. `create_new_version_after_archive` verlangt Actor + Quell-ETag, prüft Policy `new_version`
   auf Lock-`current`, setzt `superseded_by_version`, stempelt Quelle und Nachfolger und
   verbraucht den Quelltoken.
3. Erfolgreiche Metadata-/CR-Mutationen übernehmen die Domain-Event-ID in den Zustand
   (`eventing.stamp_event_on_state`); der verwendete ETag ist danach nicht wiederverwendbar.
4. Alle 16 `ACTION_IDS` besitzen einen Coverage-Index plus referenzierte Ausführungs-/Negativtests
   in `tests/modules/test_documents_authorization_matrix.py` und ergänzende HTTP-Auth-Tests.
   Die Index-Tabelle (`test_sixteen_action_execution_coverage_table`) prüft nur die Zuordnung
   ACTION_ID → Testmethode; sie ist **kein** alleiniger Ausführungsnachweis.

Wesentliche **noch offene** Lücken verhindern Documents-/Signature-Stufe 4 und halten das
Gesamtprojekt bei Stufe 2:

1. ~~PyQt fällt bei fehlenden `available_actions` lokal auf `compute_available_actions` zurück~~ — **remediated (M2)**.
2. ~~OpenAPI weicht von der Laufzeit ab (`If-Match` optional, kein 428, `state` vs. `current_state`)~~ — **remediated (M2)**.
3. ~~Interfaces-Collection: fehlende exportierte Portkonstante in `wiring`~~ — **remediated (G3)**.
4. Echte Zwei-Prozess-/Zwei-Client-/Live-/Packaging-Nachweise fehlen.
5. Nicht migrierte Module/Clients ohne Backend-Aktionsliste (Training, Incident, Legacy).

---

## B. Ist-Ablauf

Beispiel: Version laden → Action-Bar → Workflow-Transition `complete_editing`
(bzw. `new_version` / `create_new_version_after_archive`).

```text
1. Login / Session
   PyQt SessionCoordinator
   → backend_session_api.login
   → POST /auth/login
   → modules.usermanagement.api.login_backend
   → opaque Bearer-Token

2. Dokumentversion laden
   PyQt selection_mixin / pool
   → HttpDocumentsPoolApi.get_document_version*
   → GET /documents/versions/{id}/{ver}
   → require_user_context_normal
   → DocumentsPoolApi / Workflow-Read
   → _state_payload / _state_response
      available_actions_for_actor(state, actor)
      → compute_available_actions
      → available_workflow_actions / evaluate_workflow_action
   Antwort: { state, available_actions, etag } (+ ETag-Header)

3. Button-Sichtbarkeit
   selection_mixin → DocumentsWorkflowPresenter.visible_actions_for_context
   - maps only known backend action names → UI keys
   - missing/invalid/empty available_actions → fail-closed (no mutation keys)
   - Create only via backend capability can_create_new_documents
   - no local compute_available_actions / role-policy fallback

4. Aktion ausführen (Normalfall complete_editing) — Ist-Reihenfolge nach M1/G1
   actions_mixin
   → HttpDocumentsWorkflowApi / documents_http
   → POST .../workflow/editing-complete + Header If-Match
   → _required_if_match (428 wenn fehlend)
   → DocumentsWorkflowApi.* mit actor
      mutate_version_if_current(state, expected_last_event_id, operation, action=…)
      → Write-Transaction + Lock
      → load current
      → compare last_event_id
      → assert_workflow_action(current, actor, action)   # Policy auf Lock-current
      → operation(current) → Domain-Event + stamp_event_on_state → persist
   → 403 / 409 / 400 / 404 je nach Fehler-Mapping

5. new_version after archive — Ist nach M1/G1
   POST .../lifecycle/new-version-after-archive
   → Session-Actor + If-Match
   → api.create_new_version_after_archive(state, next_version,
        expected_last_event_id=…, actor=…)
   → mutate_version_if_current(..., action="new_version")
   → Use-Case atomar: ARCHIVED / kein Nachfolger / create successor /
      source.superseded_by_version = next /
      Domain-Event / stamp source + new / persist beide
   → Response-ETag der neuen Version ist nicht leer / nicht "none"
```

Beteiligte Kernsymbole:

| Schritt | Datei | Symbol |
| --- | --- | --- |
| Capabilities/Actions | `modules/documents/capabilities.py` | `compute_available_actions`, `available_actions_for_actor`, `compute_global_capabilities` |
| Policy | `modules/documents/workflow_policy.py` | `evaluate_workflow_action`, `available_workflow_actions`, `ACTION_IDS` |
| Actor-Rolle | `modules/documents/actor_context.py` | `actor_user_and_role` (`is_effective_qmb` vor Admin) |
| HTTP Serialize | `src/backend/documents_routes.py` | `_state_payload`, `_state_response`, `_required_if_match`, `_mutate_version_state`, `_map_documents_error` |
| Optimistic Lock + Policy-on-current | `modules/documents/service.py` | `mutate_version_if_current` → `assert_workflow_action` |
| Event-Stamping | `modules/documents/eventing.py` | `stamp_event_on_state` |
| Metadata / CR Token advance | `modules/documents/service.py` | `update_version_metadata`, `add_change_request` |
| new_version Execute | `modules/documents/api.py` + `workflow_use_cases.py` | `create_new_version_after_archive` (CAS + atomare Persistenz) |
| HTTP Client | `interfaces/clients/documents_http.py` | fail-closed `_coerce_available_actions`; Konflikt `current_state` |
| PyQt Mapping | `interfaces/pyqt/presenters/documents_workflow_presenter.py` | Backend-Namen → UI-Keys; fail-closed (**M2**) |
| Action-Bar | `interfaces/pyqt/sections/action_bar.py` | `update_action_visibility` |

---

## C. Befundmatrix

| Bereich | Soll-Prinzip | Aktueller Stand | Fundstelle | Bewertung | Lücke |
| --- | --- | --- | --- | --- | --- |
| Globale Capabilities | Backend liefert Client-Fähigkeiten | Documents: `GET /documents/capabilities`; Training/Incident: keine vergleichbare Backend-Aktions-/Capability-Liste für UI | `capabilities.compute_global_capabilities`; Incident/Training Folgepakete | Documents weitgehend; Gesamt teilweise | Nicht-Documents ohne Vertrag |
| Objektaktionen | Backend liefert Aktionsliste | Documents: `available_actions` (Wire-Name verbindlich); Training/Incident/Legacy: fehlend | `_state_payload`; `DocumentVersionState.available_actions` | Documents weitgehend; Gesamt Stufe 2 | Response-Schemas required (**M2**) |
| Button-Sichtbarkeit | Client rendert nur Backend-Ergebnis | Documents: Backend-Liste fail-closed; andere Module: lokale Rollen | `documents_workflow_presenter.visible_actions_for_context` | Documents **M2 remediated** | Nicht-Documents lokal |
| Aktionsausführung | Backend prüft erneut auf aktuellem Zustand | Policy auf Lock-`current`; `new_version` über CAS + Policy; Metadata/CR stempeln Event-ID | `mutate_version_if_current`; `create_new_version_after_archive` | **M1/G1 remediated** | Live-/Zwei-Prozess-Evidence fehlt |
| Auth-Kontext | Benutzer serverseitig bestimmt | Documents/Signature Backend: Session/`UserContext`; Legacy: `get_current_user()` | `require_user_context*`; `actor_context.py` | ok für migrierten Pfad | Desktop-Identity für Nicht-Migrierte |
| Workflowzustand | Zustand erneut validiert | ETag unter Lock + Policy auf `current` + Tokenfortschreibung nach Mutation | `service.mutate_version_if_current`; `stamp_event_on_state` | **M1/G1 remediated** | Live-Gates offen |
| Fehlerbehandlung | unterscheidbare Fehler | 403/409/428 Laufzeit + OpenAPI | `_map_documents_error`, `_required_if_match`, `_customize_openapi` | **M2 remediated** | Live-Gates offen |
| Tests | Regeln clientunabhängig testbar | 16/16 Coverage-Index + Public-API-/HTTP-Ausführung; Interfaces/Backend Same-Process grün | Auth-Matrix; OpenAPI; Concurrency; `tests/interfaces` | Execute **grün (M1R + G3 + M2)** | Zwei-Prozess-Live |

---

## D. Konkrete Fundstellen

### D1. Serverseitige Aktionsberechnung (Documents)

- `modules/documents/workflow_policy.py` — `evaluate_workflow_action`, `available_workflow_actions`, `ACTION_IDS` inkl. `new_version` (QMB + `ARCHIVED`).
- `modules/documents/capabilities.py` — `compute_available_actions` delegiert an Policy; `available_actions_for_actor` nimmt `UserContext`.
- `src/backend/documents_routes.py` — `_state_payload` setzt `payload["available_actions"]` und Top-Level-Liste in `VersionStateResponse`.

### D2. PyQt fail-closed — **technisch remediated (M2)**

Historisch: lokaler `compute_available_actions`-Fallback und QMB-/Settings-Create.

**Ist (nach M2):**

- Presenter mappt nur bekannte Backend-Aktionsnamen → UI-Keys; fehlende Actions fail-closed.
- HTTP-Client coerce nur String-Listen; Konflikte lesen `current_state`.
- Create nur über Backend-Capability; Controls backendgesteuert; kein lokales Policy.

### D2b. Header-/Kommentarstatus-CAS Consumer — **technisch remediated (M2R)**

Historisch nach M2: Header-Speichern und Kommentarstatus ohne Consumer-ETag → produktive 428.

**Ist (nach M2R):**

- `_refresh_details` speichert geladenen `DocumentHeader` inkl. `updated_at` als `_current_header`.
- `_update_header` sendet `if_match=updated_at.isoformat()`; ohne Token kein Request;
  `doc_type`/`control_class` werden nicht erneut gesendet; HTTP-Port lehnt sie ab.
- `WorkflowCommentListItem.updated_at` + Listenpayload/`etag`; PyQt speichert Token an Zeile;
  Resolve/Reactivate verlangen `comments` + Token; Port/Client senden If-Match;
  stale → 409 ohne Statusmutation.

### D3. `new_version` after archive — **technisch remediated (M1/G1)**

Historisch (M0): API/Use-Case ohne Actor/Policy; HTTP ohne Execute-Bindung.

**Ist (nach M1R2):**

- `modules/documents/api.py` — `create_new_version_after_archive(..., expected_last_event_id, actor=…)`
  wrappt `mutate_version_if_current(..., action="new_version")`.
- `modules/documents/workflow_use_cases.py` — innerhalb der Mutation: ARCHIVED,
  kein bestehender Nachfolger, Successor erzeugen, `superseded_by_version` setzen,
  Domain-Event, `stamp_event_on_state` für Quelle und neue Version, atomare Persistenz.
- `src/backend/documents_routes.py` — Route ruft die öffentliche Modul-API direkt
  (kein äußerer Doppel-CAS-Wrapper).
- Fehlersemantik: Admin ohne QMB → 403; stale Quelltoken → 409; Replay mit altem Token → 409
  ohne zweiten Nachfolger; Response-ETag der neuen Version ist nicht `"none"`.

### D4. Policy-on-Lock-`current` + Tokenfortschreibung — **technisch remediated (M1/G1)**

Historisch (M0): gemeinsame Policy oft vor Lock auf Aufrufer-`state`; Metadata/CR publizierten
Events ohne `last_event_id` zu übernehmen.

**Ist (nach M1R1):**

- `modules/documents/service.py` — `mutate_version_if_current` lädt `current` unter Lock,
  vergleicht `last_event_id`, ruft bei gesetztem `action` `assert_workflow_action(current, …)`
  auf, danach `operation(current)`.
- `_NO_PRECONDITION` in der öffentlichen API wird auf `state.last_event_id` abgebildet und
  durchläuft denselben Lock-/CAS-/Policy-Pfad (Import-Sentinels unverändert).
- `update_version_metadata` / `add_change_request` publizieren Domain-Events und übernehmen
  Event-ID/Zeit/Actor über `eventing.stamp_event_on_state` in derselben Write-Transaction.
- Folge: erfolgreiche relevante Mutationen verbrauchen den verglichenen ETag; Wiederholung
  mit dem alten Token ergibt Conflict ohne zweite fachliche Mutation.

### D5. OpenAPI-/If-Match-/428-Vertrag — **technisch remediated (M2)**

Historisch: `If-Match` optional, kein 428, Drift `state` vs. `current_state`.

**Ist (nach M2):**

- `src/backend/api.py` — `_DOCUMENTS_IF_MATCH_REQUIRED` steuert OpenAPI `required: true` + 428/409;
  `create-from-template` optional mit konditionaler Beschreibung + 428; `ErrorDetail.current_state`;
  `available_actions` required in `VersionStateResponse` / `ExtendAnnualResponse` / `EnsureSourcePdfResponse`.
- Laufzeit: optionale FastAPI-Headerparameter bleiben; fehlendes If-Match → HTTP 428 via `_required_if_match`.
- `scripts/export_openapi.py` validiert If-Match-Menge, 428, create-from-template, `current_state`,
  required `available_actions`; Snapshot `docs/contracts/j04-m0-openapi.json` nur über Export.

### D6. Auth-Kontext Backend vs. Desktop

- Backend Documents/Signature: Session/`UserContext` (AP-028-Pfad).
- `modules/documents/actor_context.py` — `actor_user_and_role`: QMB über `is_effective_qmb`,
  sonst Admin, sonst USER; Admin allein ist kein QMB.
- Legacy Desktop/CLI nicht migrierte Use Cases: weiterhin `get_current_user()` —
  **Folgepaket**.

### D7. Repo-weite Nicht-Documents-Befunde (nur dokumentieren)

- `modules/incident_management/authorization.py` — lokale `is_qmb`/`is_admin`-Hilfen; kein Backend-`available_actions`-Vertrag. **Folgepaket.**
- Training-Administration: keine `available_actions`-Äquivalente; Documents-Read für Training ist HTTP-migriert, Fachadmin nicht. **Folgepaket.**
- Legacy Tk (`interfaces/gui`): fail-closed Documents, keine Backend-Action-Liste. **legacy_not_in_m0.**

### D8. TestClient ≠ Zwei-Prozess (bekannte Abweichung)

- Backend-HTTP-Tests nutzen Starlette `TestClient` im gleichen Prozess.
- Historischer M0-Lauf: `test_two_writers_with_same_if_match_have_one_winner` scheiterte an
  SQLite-Thread-Affinität — kein Zwei-Client-Prozessnachweis.
- Comment-Status-CAS bleibt unter dem Abnahmeziel **prozesslokal** (ein Backendprozess);
  keine neue DB-CAS-Infrastruktur in M1.

### D9. 16-ACTION-Coverage und Ausführungsnachweise — **technisch remediated (M1R3 + Evidence)**

- `tests/modules/test_documents_authorization_matrix.py::test_sixteen_action_execution_coverage_table`
  ist ein **Coverage-Index**: jede `ACTION_ID` mappt auf eine konkrete Testmethode (`callable`).
  Das belegt Vollständigkeit der Zuordnung, **nicht** allein die Ausführung.
- Positive Public-API-Ausführung u. a. für `review_reject` / `approval_reject`
  (`test_review_and_approval_reject_execute_on_public_api`) sowie `assign_roles` / `start` / `abort`
  (`test_assign_start_abort_execute_on_public_api`).
- `open_source` über öffentliche `DocumentsArtifactsApi` inkl. bestätigtem Actor
  (`test_open_source_reauthorization_on_artifact_read_path`); HTTP-Positiv/Negativ in
  `tests/backend/test_documents_authorization_http.py`.
- Tokenfamilien: Version-State-CAS, `new_version` Tokenverbrauch/Replay, Metadata/CR-Fortschritt,
  Header-`updated_at`, Comment-Status-`updated_at`, Read-Reauthorization ohne erfundene CAS.
- Maßgebliche Concurrency-Evidence nutzt keine privaten synthetischen `_store_state`-Bumps.

---

## E. Gefundene Risiken

1. ~~**Fachlogik im Client:** lokaler `compute_available_actions`-Fallback in PyQt~~ — **remediated (M2)**.
2. ~~Nur Client-Sichtbarkeit, schwache Execute-Bindung für `new_version`~~ — **remediated (M1/G1)**.
3. ~~Policy nicht atomar auf Lock-`current`~~ — **remediated (M1/G1)**.
4. ~~**Doppelte Berechtigungslogik:** Modul-Policy + optional Client-Fallback~~ — **remediated (M2)**.
5. ~~**Rollen- vs. Aktionsprüfung:** Create-/Metadaten-UI lokal QMB/Settings~~ — **remediated (M2)**.
6. ~~**OpenAPI drift:** `If-Match` optional, kein 428, `state` vs. `current_state`~~ — **remediated (M2)**.
7. ~~Actor×Status×Assignment×Action-Ausführungsmatrix unvollständig~~ —
   **Coverage-Index + Public-API-/HTTP-Ausführungsnachweise remediated (M1R3 + Evidence)**;
   Live-/Zwei-Prozess-Nachweise bleiben offen.
8. ~~**Interfaces-Collection-Bruch:** fehlende exportierte Portkonstante in `wiring`~~ — **remediated (G3)**.
9. **False Live-Confidence** durch Same-Process-Tests.
10. **Inkonsistente Aktionsnamen:** Backend vs. UI-Keys (Mapping muss deterministisch bleiben).
11. **Repo-weite Lücken** in Training/Incident/Legacy ohne Backend-Aktionsliste.

### Verbindliche Annahmen (keine offenen Fragen)

- Wire-Name bleibt **`available_actions`**. Keine Rename-Migration auf `allowed_actions` in J04.
- QMB wird aus dem bestätigten `UserContext` über **`is_effective_qmb`** bestimmt
  (`actor_context.actor_user_and_role`). **Admin allein ist kein QMB.**

---

## F. Zielbild

Minimal und an bestehende Grenzen angepasst (keine neue Berechtigungsabstraktion):

```text
Backend (modules/documents):
  available_actions_for_actor(state, actor)     # bereits vorhanden
  mutate_version_if_current(...):
    load current under lock
    compare ETag
    assert_workflow_action(current, actor, action)  # gemeinsame Policy auf current — IST
    apply mutation + stamp_event_on_state           # Tokenfortschreibung — IST

Backend HTTP:
  jede Version-State-Antwort: available_actions verpflichtend
  jede Mutation: If-Match required → 428; Policy-Fail → 403; stale → 409 (+ current_etag/current_state);
  missing/invisible → 404

Client (PyQt HTTP-Profil) — M2 IST:
  rendert nur bekannte Backend-Aktionsnamen
  fehlende/ungültige available_actions → fail-closed (keine Buttons, kein lokaler Policy-Fallback)
```

Wiederverwenden: `workflow_policy`, `capabilities`, `UserContext`, `actor_context`, bestehende Ports/`api.py`.
Nicht einführen: zweite Policy-Engine, generisches Command-Bus-Framework, repo-weite Rename-Migration.

---

## G. Empfohlene Umsetzungspakete

Hinweis: **M2 ist technisch abgeschlossen.** Live-/Packaging-/Human bleiben gesperrt.
Außerhalb Documents/Auth/Signature nur Folgepakete.

### Verbindliche Reihenfolge (nicht parallel)

```text
M1 / G1 technisch grün
  → G3 Wiring + Interfaces-Suite technisch grün
    → M2 / G2 technisch grün
      → M2R Header-/Kommentar-CAS technisch grün (dieser Stand)
        → PG-Live / Zwei-Client / Word-COM / Onedir / Human   [gesperrt]
```

- **G2 erst nach erfolgreichem M1-Gate und erfolgreichem G3-Interfaces-Gate.** — erfüllt.
- Keine parallele oder gleichzeitige Freigabe von G2 zusammen mit M1 zulässig.

### G1. Serverseitige Policy-on-current + `new_version` (→ J04-M0 Meilenstein 1)

- **Status:** **technisch umgesetzt und verifiziert** (M1R1–M1R3; serielle Gates M1R5).
- **Erreicht:**
  1. `create_new_version_after_archive` verlangt bestätigten Actor, Quell-ETag und Policy `new_version`.
  2. Policy auf Lock-`current` für Policy-Mutationen; Metadata/CR und `new_version` schreiben Tokens fort.
  3. Atomare Nachfolgerbeziehung (`superseded_by_version`) und gültige Tokens für Quelle und neue Version.
  4. 16-ACTION Coverage-Index plus referenzierte Public-API-/HTTP-Ausführungs-/Negativtests
     ohne synthetische Acceptance-Bumps.
- **Nächster Schritt nach G3:** ~~M2 (gesperrt)~~ → **M2 technisch abgeschlossen**.

### G3. Interfaces-Gate Wiring-Konstante

- **Status:** **technisch umgesetzt und verifiziert** (2026-08-07).
- **Erreicht:**
  1. `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT = "documents_allow_inprocess_sqlite"` in
     `modules.documents.wiring`; `_should_register_sqlite` verwendet ausschließlich die Konstante.
  2. Fehlender Opt-in bleibt fail-closed; Backend-Owner und expliziter Test-Opt-in unverändert.
  3. Vollständige Interfaces-Suite: **174 passed** (`-m "not postgres"`).
  4. P9-Scope: Backend-HTTP Profile Create positiv; mutierende Profile-CLI-Befehle bleiben
     `legacy_not_in_m0`; Interface-Test an denselben Vertrag angeglichen (kein CLI-Freischalten).
- **Nächster Schritt:** ~~M2 / G2~~ → **M2 technisch abgeschlossen**; danach externe Abnahmegates.

### G2. Client fail-closed + OpenAPI-Angleichung (→ J04-M0 Meilenstein 2)

- **Status:** **technisch umgesetzt und verifiziert** (2026-08-07).
- **Erreicht:**
  1. PyQt/HTTP-Client fail-closed ohne lokale Documents-Workflow-Policy.
  2. Create ausschließlich über Backend-Capability.
  3. OpenAPI: If-Match-required-Menge + 428; create-from-template konditional; `current_state`;
     required `available_actions`; Snapshot reproduzierbar via Exportskript.
  4. Interfaces **174**, Backend **97**, Auth-Matrix **19** (Same-Process).
- **Nächster gesperrter Schritt:** ~~G4 externe Abnahmegates~~ → nach M2R freigabefähig.

### G2R. Header-/Kommentarstatus-CAS Consumer (→ J04-M0 M2R)

- **Status:** **technisch umgesetzt und verifiziert** (2026-08-07).
- **Erreicht:** Header-If-Match aus geladenem Token; Kommentarlisten/`updated_at`;
  Resolve/Reactivate mit If-Match; stale 409; Action-Key-UI; Mengenassertionen hashstabil.
- **Nächster gesperrter Schritt:** G4 externe Abnahmegates.
### G4. Isolierte PG-Live-Infra / Zwei-Client / Word-COM / Onedir (→ Meilensteine 3–7)

Unverändert gemäß Bereinigungs- und Abnahmeplan; nicht Teil des kleinsten M1/M2-Fixes.

### G5. Incident / Training-Admin / Legacy-Desktop Actions (Folgepakete)

Repo-weite Lücken; **keine** Änderungen in J04-M0.

---

## Evidence-Bezug

- Historische M0-Evidence: `docs/J04_M0_ACCEPTANCE_REPORT.md` Abschnitt „Verification (Meilenstein 0)“
  — Zahlen dort **nicht** rückwirkend umgeschrieben.
- M1/G1-Evidence: derselbe Report, Abschnitt „Verification (M1/G1 Reparaturlauf)“.
- Same-Process-Ergebnisse sind **nicht** als Live-Evidence gewertet.
- Status bleibt `Rejected / follow-up required`.
