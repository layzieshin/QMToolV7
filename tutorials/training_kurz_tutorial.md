# Kurzes Tutorial: Schulungsmodul (Tags, Freigabedatum, Events)

## 1) Dokument-Tags setzen
- Öffne in der GUI den Bereich `Schulung`.
- Als `ADMIN` oder `QMB` in der oberen Leiste auf `Dokument-Tags` klicken.
- Dokument auswählen.
- Tags als CSV eintragen, z. B. `safety, quality, onboarding`.
- Speichern.

Hinweis:
- Tags werden über `training_admin_api.set_document_tags(...)` geschrieben.
- Es sind positive/additive Tags (keine negativen Tags).

## 2) Warum `Freigabe am` vorher leer war
- Ursache: `released_at` war im Trainings-Inbox-Pfad nicht befüllt.
- Jetzt verdrahtet über:
  - `modules/training/released_document_catalog_reader.py`
  - `modules/training/training_inbox_query_service.py`
- In der Tabelle wird das Datum nur gezeigt, wenn das Dokument im Dokumentenmodul tatsächlich ein `released_at` hat.

## 3) Wie Events erzeugt werden
- Events werden als `EventEnvelope` erstellt (`qm_platform/events/event_envelope.py`).
- Publishing läuft über `event_bus.publish(envelope)`.
- Beispiel Training-Events:
  - `domain.training.quiz.imported.v1`
  - `domain.training.quiz.binding.created.v1`
  - `domain.training.assignment.snapshot.rebuilt.v1`

## 4) Wie Events konsumiert werden
- Consumer registrieren Handler über `event_bus.subscribe(name, handler)`.
- Beispiel: Training konsumiert `domain.documents.read.confirmed.v1` in `modules/training/wiring.py`.
- Dort wird jetzt vor Fortschritts-Update ein Read-Receipt geprüft (`documents_read_api.get_read_receipt(...)`).

## 5) Kurz-Check per Tests
```powershell
cd I:\Projekte\QMToolV7
python -m pytest tests/training/test_training_events.py tests/training/test_training_read_event_receipt_verification.py -q
```

Optional (breiter Regression-Check):
```powershell
cd I:\Projekte\QMToolV7
python -m pytest tests/training/ tests/interfaces/test_training_login_gate.py tests/modules/test_documents_event_order.py -q
```

