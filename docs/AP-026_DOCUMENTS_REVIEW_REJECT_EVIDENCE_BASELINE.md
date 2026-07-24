# AP-026 Documents Review-ablehnen Evidence Baseline

## 1. Status
- Arbeitspaket: AP-026
- Typ: Evidence-Baseline / Test-Gate
- Status: erledigt
- Codeänderungen (Produkt): nein
- Teständerungen: ja (`tests/modules/test_documents_review_reject_evidence.py`)
- Refactoring: nein
- API-Änderung: nein
- DTO-Änderung: nein
- Event-Schema-Änderung: nein
- Auditlog-Schema-Änderung: nein
- Exportformat-Entscheidung: nein
- Migration: nein
- Backend-Feature-Route: nein
- Auth-/UserContext-/AuditActor-Implementierung: nein
- RequestContext-/CommandContext-/ExecutionContext-Implementierung: nein
- Command-ID-/Use-Case-ID-Implementierung: nein
- Cleanup: nein

## 2. Ziel
Service-seitige Nachweisentscheidung für **Documents Review ablehnen** regressionssicher absichern, ohne Produktverhalten, Schema oder Kettenkontext zu ändern.

Vorgänger:
- AP-023 priorisiert den Slice.
- AP-024 bereitet die Fundstellen vor (ohne Tests).

## 3. Nicht-Ziele
- Keine Änderung an `modules/documents/*` Produktivcode.
- Keine API-/DTO-/Event-/Auditlog-Schemaänderung.
- Keine UserContext-/RequestContext-/Command-ID-/Use-Case-ID-Implementierung.
- Keine CLI-/PyQt-Autorisierung.
- Keine Backend-Route.
- Keine Behauptung `kettenbelastbar`.

## 4. Abgesichertes Verhalten
Gate: `tests/modules/test_documents_review_reject_evidence.py`

- Review-Ablehnung nur in Status `IN_REVIEW`.
- Actor muss zugeordneter Reviewer sein.
- Domain-Event `domain.documents.review.rejected.v1` und Audit `documents.workflow.review.rejected` entstehen aus derselben Service-Entscheidung.
- Actor/Target/Reason und Statuswechsel nach `IN_PROGRESS` sind nachweisbar.
- Event `causation_id` bleibt leer; Audit trägt keine Correlation-/Causation-Felder.
- Default-`correlation_id` am Event wird nicht als belastbare Kette gewertet.

## 5. Nachweisbewertung nach Baseline
- Actor-Readiness im Service: `belastbar nach Quellklassifikation` (unverändert).
- Adapterherkunft: `eingeschränkt` (unverändert).
- Ketten-Readiness: `ketten-eingeschränkt` (unverändert; bewusst nicht aufgewertet).

## 6. Ausgeführte Prüfungen
- `.\.venv\Scripts\python.exe -m pytest tests/modules/test_documents_review_reject_evidence.py -q` → 3 passed
- `.\.venv\Scripts\python.exe -m pytest tests/modules/test_documents_service.py tests/modules/test_documents_event_contracts.py tests/modules/test_documents_variants_matrix.py tests/modules/test_documents_review_reject_evidence.py -q` → 31 passed
- `.\.venv\Scripts\python.exe -m pytest tests/docs/test_docs_consistency.py -q` → 4 passed

## 7. Maximal ein sinnvoller nächster Schritt
Separates Paket für Request-/Kettenkontext oder Event↔Audit-Kopplung freigeben oder zurückstellen; nicht still mit AP-026 vermengen.
