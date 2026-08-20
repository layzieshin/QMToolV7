# J04-M0 Pfadmatrix — vollstaendige Documents-Transportmigration

Stand: J04-M0 Meilenstein 0 Dokumentation geschlossen; M1/G1 Execute-Semantik technisch
remediated; G3 Interfaces-Wiring-Gate technisch abgeschlossen; M2 PyQt fail-closed +
OpenAPI/If-Match/428 technisch abgeschlossen; **M2R Header-/Kommentarstatus-CAS Consumer
technisch abgeschlossen** (2026-08-07); **formale Acceptance `Accepted`** (2026-08-20;
Produkt-Merge `e003b37`, Main-Basis `f7b867d`).
Zeilenstatus `implemented_unaccepted` / `gap` bezeichnen weiterhin Evidence-Tiefe einzelner
Pfade und ersetzen nicht den package-weiten Acceptance-Status in
`docs/J04_M0_ACCEPTANCE_REPORT.md`.
Kanonische Source of Truth fuer Status und Tests.
Same-Process-`TestClient`-Nachweise gelten nicht als Live-/Zwei-Client-Evidence.

## Statuswerte

| Status | Bedeutung |
| --- | --- |
| `existing_partial` | Route/Port vorhanden, aber ohne vollstaendige P0-Identitaet / UI-Consumer / Gesamtacceptance |
| `implemented_unaccepted` | Route, Modul und Port implementiert; Consumer-, Negativ- oder Live-Evidence für Abnahme fehlt noch |
| `gap` | Bewusst offen (z. B. Live-Gate, Word-COM-Smoke, unwired UI) |
| `available` | Route + Backend-Aufruf + HTTP-Port + UI-Consumer + Tests gemeinsam gruen; Same-Process allein reicht nicht, wenn angeführte Tests rot sind oder die UI lokal über Berechtigung entscheidet |
| `removed` | Bewusst entfernt / superseded (kein produktiver Pfad) |
| `superseded` | Frueheres Lab-/Interim-Ziel, zaehlt nicht als Abnahme |

Actor-Quelle nach P0: `backend_session` (Bearer → `UserContext`). CLI/Tests duerfen
`QMTOOL_SESSION_TOKEN` nutzen; PyQt nutzt Session-Port (`bind_pyqt_session_token_provider`).

## Paket-Legende

D0 Doku · P0 Session · P1 Ownership · P2 Reads/Capabilities · P3 Writes · P3A Artefakte ·
P3B Signatur · P3C Training-Read · P4 Comments · P5 Header/Metadata · P6 DOCX/Template ·
P7 Lifecycle · P8 Change Requests · P9 Profile-Admin · P10 Legacy-Entfernung

## ACTION_IDS ↔ Matrix (systematischer Abgleich)

Alle 16 Einträge aus `modules/documents/workflow_policy.ACTION_IDS`. Execute-Policy läuft
nach M1/G1 auf Lock-`current` inkl. Tokenfortschreibung / atomarem `new_version`. Client-
Sichtbarkeit ist nach M2 fail-closed backendgesteuert. Zeilen bleiben
`implemented_unaccepted`, weil Live-/Zwei-Prozess-Abnahme noch fehlt — **keine**
vorschnelle Hochstufung auf `available`.

| ACTION_ID | Matrixzeile(n) | Status |
| --- | --- | --- |
| `assign_roles` | B: Assign / Start / Transitions | `implemented_unaccepted` |
| `start` | B: Assign / Start / Transitions | `implemented_unaccepted` |
| `open_source` | D: Open/Edit/Default-Open | `implemented_unaccepted` |
| `complete_editing` | B: Assign / Start / Transitions; E: Signed workflow transitions | `implemented_unaccepted` |
| `review_accept` | B + E Signed workflow transitions | `implemented_unaccepted` |
| `review_reject` | B + E Signed workflow transitions | `implemented_unaccepted` |
| `approval_accept` | B + E Signed workflow transitions | `implemented_unaccepted` |
| `approval_reject` | B + E Signed workflow transitions | `implemented_unaccepted` |
| `abort` | B: Assign / Start / Transitions | `implemented_unaccepted` |
| `archive` | J: Archivieren | `implemented_unaccepted` |
| `extend_validity` | J: Verlaengern | `implemented_unaccepted` |
| `new_version` | J: Neue Version nach Archiv | `implemented_unaccepted` |
| `update_metadata` | H: Metadata speichern | `implemented_unaccepted` |
| `update_header` | H: Header speichern | `implemented_unaccepted` |
| `comments` | G: Comments read vs. Comments mutate | read `available` / mutate `implemented_unaccepted` |
| `change_requests` | K: CR list vs. CR create | list `available` / create `implemented_unaccepted` |

---

## A. Session / Identitaet (P0)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PyQt Login (`SessionCoordinator`) | `login_backend` | `POST /auth/login` | `backend_session_api.login` | session | `available` | `test_pyqt_session_coordinator.py`, `test_backend_session_client.py` | P0 |
| Forced password change | `change_own_password` | `POST /auth/change-password` | `backend_session_api.change_password` | session | `available` | `test_backend_session_client.py` | P0 |
| Session me | `resolve_session` | `GET /auth/me` | `backend_session_api.current_user` | session | `available` | `test_backend_session_client.py` | P0 |
| Logout | `logout_backend` | `POST /auth/logout` | `backend_session_api.logout` | session | `available` | `test_backend_session_client.py` | P0 |
| Documents Bearer (PyQt) | — | — | Session-Port (nicht Env) | session | `available` | `test_backend_session_client.py` (reject env), Arch-Gates | P0/P10 |
| Documents Bearer (CLI/Tests) | — | — | Env `QMTOOL_SESSION_TOKEN` | env_token | `available` | `test_documents_workflow_profile_cli.py`, CLI E2E | P0 |

## B. Core Workflow-/Pool-HTTP

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PyQt/CLI pool reload | `list_by_status` | `GET /documents/pool/by-status/{status}` | `HttpDocumentsPoolApi` | session | `available` | `test_documents_http_api.py` | P2/P3 |
| Version read + `available_actions` | `get_document_version_for_actor` | `GET /documents/versions/{id}/{ver}` | pool | session | `implemented_unaccepted` | Client fail-closed (M2); Blocker: CLI E2E/Live pending | P2/P3 |
| Create draft | actor-aware `create_document_version` | `POST /documents/versions/create` | workflow | session | `implemented_unaccepted` | Blocker: Negativ-/CLI-E2E-Evidence unvollständig | P3 |
| Assign / Start / Transitions | `assign_roles`, `start`, `complete_editing`, `review_*`, `approval_*`, `abort` | POST workflow/* | workflow | session | `implemented_unaccepted` | Execute: Policy-on-Lock-`current` (M1/G1); UI fail-closed (M2). Blocker: kein Zwei-Prozess-Live | P3 |
| PDF import | `import_existing_pdf` | POST import-pdf | workflow | session | `available` | `test_import_pdf_roundtrip`, artifacts | P3A |
| Profile definitions list | `list_workflow_profile_definitions` | GET definitions | workflow | session | `available` | profile CLI + HTTP | P2/P9 |
| User directory | `list_users_for_assignment` | `GET /users/directory` | UM HTTP | session | `available` | `test_user_directory_api.py` | P0/P2 |

## C. Reads + Capabilities (P2)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Details header | `get_header` | `GET /documents/headers/{id}` | pool | session | `available` | `test_header_read`, `test_documents_http_reads.py` | P2/P5 |
| Home tasks/reviews/recent | pool list APIs | GET `/documents/home/*` | pool | session | `available` | `test_documents_reads_http.py`, home widget | P2/P10 |
| Pool released list | `list_current_released_documents` | GET `/documents/released` | pool | session | `available` | `test_documents_reads_http.py` | P2 |
| Global capabilities | `GET /documents/capabilities` | capabilities | pool | session | `available` | `test_documents_reads_http.py` | P2 |
| Profile IDs by control class | `list_profile_ids_for_control_class` | via definitions | workflow | session | `available` | `test_documents_http_workflow_port_stubs.py` | P2 |

## D. Artefakte (P3A)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Open/Edit/Default-Open | artifacts API + download (`open_source`) | GET artifacts + content | `HttpDocumentsArtifactsApi` | session | `implemented_unaccepted` | UI-Key `edit`/`open_source` fail-closed (M2); Blocker: Live | P3A/P10 |
| Pool Lesen | `get_released_pdf_for_reading` | download | artifacts | session | `available` | artifacts + pool view | P3A/P10 |
| Sign prep | `ensure_source_pdf_for_signing` | POST `.../workflow/ensure-source-pdf` | workflow + download | session | `available` | `test_ensure_source_pdf_after_import_*` | P3A/P3B/P10 |
| Artifact metadata list | `list_artifacts` | GET metadata | artifacts | session | `available` | `test_documents_artifacts_http.py` | P3A |
| Fail-closed stubs | `_FailClosedArtifactsApi` | — | — | — | `removed` | `test_documents_http_gates.py` | P10 |

## E. Signatur (P3B)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Signature assets/templates | Signature HTTP | `/signature/*` | `signature_http` | session | `available` | `test_signature_http_api.py` | P3B |
| Signed workflow transitions | signed `complete_editing` / `review_*` / `approval_*` | signed transitions | workflow | session | `implemented_unaccepted` | Execute: Policy-on-Lock-`current` (M1/G1); Client fail-closed (M2). Blocker: Live-Gate | P3B |
| Standalone sign | Signature view | opaque upload | signature HTTP | session | `available` | `test_signature_http_api.py` | P3B |
| Word-COM DOCX→PDF Live-Smoke | converter host | import-docx / ensure-source-pdf | — | — | `gap` | **NOT RUN** (host-abhaengig) | P6/P3A |

## F. Training Documents-Read (P3C, follow-up only)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Training open/read/receipt | `DocumentsReadApi.*` | `/documents/reads/*` | `HttpDocumentsReadApi` | session | `available`, **not part of J04-M0 acceptance** | `test_documents_training_read_http.py` | P3C |

## G. Comments (P4)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Comments read / detail | list/get comment APIs | GET comments routes | `HttpDocumentsCommentsApi` | session | `available` | P4 HTTP read tests | P4/P10 |
| Comments mutate (sync/create/status) | comment write APIs (`comments`) | POST/PATCH comments | `HttpDocumentsCommentsApi` | session | `implemented_unaccepted` | Execute: Tokenfamilien (M1R3); Listen liefern `updated_at`; Resolve/Reactivate senden If-Match (**M2R**). Blocker: Live; Status-CAS prozesslokal | P4 |
| Fail-closed stubs | `_FailClosedCommentsApi` | — | — | — | `removed` | `test_documents_http_gates.py` | P10 |

## H. Header / Metadata Write (P5)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Metadata speichern | `update_version_metadata` | PATCH metadata | workflow | session | `implemented_unaccepted` | Execute: Policy-on-current + ETag (M1R1); UI an Backend-Action `update_metadata` (M2). Blocker: Live | P5 |
| Header speichern | `update_document_header` | PUT header | workflow | session | `implemented_unaccepted` | Execute: Header-`updated_at`-CAS; PyQt reicht geladenes Header-ETag als If-Match (**M2R**). Blocker: Live | P5 |

## I. DOCX / Template (P6)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Wizard DOCX | `import_existing_docx` | POST import-docx | workflow | session | `existing_partial` | Route+Port; Word-COM Live **NOT RUN** | P6 |
| Wizard Template | `create_from_template` | template upload | workflow | session | `existing_partial` | HTTP client wired; Live **NOT RUN** | P6 |

## J. Lifecycle (P7)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Archivieren | `archive_approved` (`archive`) | lifecycle/archive | workflow | session | `implemented_unaccepted` | Execute: Policy-on-Lock-`current` (M1/G1); UI fail-closed (M2). Blocker: Live | P7 |
| Verlaengern | `extend_annual_validity` (`extend_validity`) | lifecycle/extend-annual | workflow | session | `implemented_unaccepted` | Execute: Policy-on-Lock-`current` (M1/G1); UI-Key `extend_validity` (M2). Blocker: Live | P7/P3B |
| Neue Version nach Archiv | `create_new_version_after_archive` (`new_version`) | lifecycle route | workflow | session | `implemented_unaccepted` | Execute: CAS + QMB + Tokenverbrauch + `superseded_by_version` (M1R2); UI-Key `new_version` (M2). Blocker: Live | P7 |

## K. Change Requests (P8)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CR list | list change requests | GET CR routes | workflow | session | `available` | `test_change_request_list_and_create` (list) | P8 |
| CR create | create change request (`change_requests`) | POST CR routes | workflow | session | `implemented_unaccepted` | Execute: Policy-on-current + ETag (M1R1); UI an Backend-Action `change_requests` (M2). Blocker: Live | P8 |

## L. Profile Admin (P9)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Backend Profile Admin HTTP | profile create/version/activate/bind | POST/GET profiles | workflow | session | `implemented_unaccepted` | Backend-HTTP positiv (`test_profile_create_over_http_by_qmb`); Live-/Consumer-Abnahme offen | P9 |
| CLI Profile List | `list_workflow_profile_definitions` | GET definitions | workflow HTTP CLI | session env token | `available` | `test_profile_admin_cli_command_uses_session_token` | P9 |
| CLI Profile Mutations | `profile-create` / create-version / activate / deactivate / bind | — | reduced CLI | — | `legacy_not_in_m0` | Adapter-Eingang blockiert (`test_profile_admin_cli_create_is_blocked_under_reduced_m0_scope`; E2E `test_profile_create_is_blocked_under_reduced_m0_scope`) | P9 |
| PyQt Profile Manager | profile manager dialog | existing profile routes | workflow HTTP port | capability | `implemented_unaccepted` | Blocker: manual UI/live pending | P9 |

## M. Ownership / Env / Legacy (P10)

| Thema | Status | Test |
| --- | --- | --- |
| Product env local SQLite switch | `available` (ignored) | `test_product_env_var_does_not_enable_local_documents_sqlite` |
| Legacy Tk documents | `available` (fail-closed) | `test_gui_documents_fail_closed.py` |
| Soft-Degrade `DocumentsFeatureUnavailableError` (Artefakte/Kommentare/Header) | `removed` | selection/pool zeigen echte Fehler |
| `_FailClosed*Api` HTTP ports | `removed` | Soft-Degrade-Stubs entfernt; HTTP-Ports fail-closed ohne lokale SQLite |
| modules→interfaces wiring | `available` (G3) | `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` in `modules.documents.wiring`; Interfaces-Suite **174 passed** |
| Final Green Gate (2-Client-Live, Golive, Packaging) | `available` | MR10 Packaging/Golive/Human-Smoke PASS; formale Acceptance `Accepted` (2026-08-20). Word-COM-E2E und Produktionslizenz bleiben Folgepakete |
| PyQt `available_actions` fail-closed | `available` (Same-Process) | Presenter ohne `compute_available_actions`; Create nur Capability; Controls backendgesteuert (**M2**); Live/Packaging offen |

## N. Concurrency (P3)

| UI-Consumer | Moduloperation | HTTP | Client-Port | Actor | Status | Test | Paket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Mutating writes If-Match | optimistic lock | If-Match required / 409 / 428 | HTTP client | session | `implemented_unaccepted` | OpenAPI If-Match/428 + `current_state` (**M2**); Runtime Same-Process grün. Blocker: kein Zwei-Prozess-Live | P3 |

## J04-M0 Zielklassifikation

Der aktive PyQt-Client ist ein Kern-Uebergangsclient. Die vollstaendige
Backend-Funktionalitaet bleibt als HTTP-/OpenAPI-Vertrag erhalten, wird aber
nicht mehr als UI-Paritaet des bisherigen Clients abgenommen.

| Bereich | Zielklassifikation |
| --- | --- |
| Login, Logout, eigener Passwortwechsel | `transition_client_required` |
| Documents-Pool, Details, Aufgaben, freigegebene Artefakte | `transition_client_required` |
| Kernworkflow inkl. Signatur und ETag-Konflikten | `transition_client_required` |
| Documents-/Signature-/User-/Auth-HTTP-Vertrag | `backend_contract_required` |
| Profile, Kommentare, Header, Metadaten, Lifecycle, Change Requests, DOCX/Template | `backend_contract_required` |
| Settings- und Useradministration im PyQt-Client | `deferred_after_m0` |
| Eigenstaendiger Signature-Arbeitsbereich | `deferred_after_m0` |
| Incident, Training-Administration, Registry, Audit und Admin-Debug | `deferred_after_m0` |
| Legacy-Tk-Documents und lokale CLI-Fachpfade | `legacy_not_in_m0` |

Jede neue Matrixzeile muss genau eine dieser vier Zielklassifikationen tragen.
