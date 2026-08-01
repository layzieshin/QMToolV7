# AP-028 M8 - Cutover-Vorbereitung (Prep-only)

## Zweck

M8 liefert Inventar, Validierung, Bericht und einen verpflichtenden
Backup-/Restore-Drill für den späteren Usermanagement-Cutover. M8 schaltet
**nicht** auf PostgreSQL um und importiert keine Benutzer.

Voraussetzung: Milestone 7 (`docs/AP-028_M7_AUDIT_EVIDENCE.md`) in `main`.

## Verbindliche Entscheidungen

- Prep-only: Statuswerte nur `invalid_source`, `blocked`, `ready_for_remapping`.
  Es gibt **kein** `cutover_ready`.
- Owner: `modules.usermanagement.api.prepare_postgres_cutover`.
- Optionales CLI: `scripts/prepare_postgres_cutover.py` - nur Argumente und
  API-Aufruf, keine zweite Import-/SQL-/Mapping-Logik.
- Kein Dual-Write, kein PG-Import, kein UUID-Remapping, keine Änderung an
  Documents / Training / Incident / Signature.
- Keine Schreiboperationen gegen die Runtime-DSN.
- Jede katalogisierte Quermodul-DB muss vorhanden und strukturell erwartbar sein.
- Jede nichtleere Quermodul-Userreferenz blockiert `ready_for_remapping`.
- Drill-Evidence entsteht ausschließlich innerhalb von `prepare_postgres_cutover`;
  handgeschriebenes Evidence-JSON reicht nicht.
- Der Restore läuft ohne `--clean` und nur in eine physisch getrennte, leere
  Datenbank mit Präfix `qmtool_um_restore_drill`.
- Späterer Cutover nur nach freigegebenem Quermodul-Migrationspaket
  (UUID-Mapping + Referenzmigration + Validierung + Umschaltung).

## Öffentliche API

```text
prepare_postgres_cutover(
  container,
  *,
  sqlite_users_path,
  cross_module_db_paths,   # module_id -> sqlite path
  postgres_migrator_dsn,   # read-only assessment and drill source
  report_dir,
  drill_restore_dsn,       # separate, empty restore target
  drill_work_dir=None,
) -> CutoverPrepResult
```

`CutoverPrepResult`: `status`, `report_path`, `blocker_codes`.

Der geprüfte `postgres_migrator_dsn` ist zugleich die Drill-Quelle. Eine zweite
Quell-DSN oder eine separat öffentliche Drill-Fassade existiert nicht.

## Bericht

Versioniertes JSON unter `report_dir` / `build/`:

- SQLite-Userzählungen, Integrität, Migrationschecksummen (ohne Passwort-Hashes)
- Quermodul-Referenzstatistik
- PostgreSQL-Readiness (read-only, Migrator-Rolle, Tip, Fingerprint, leere Zieltabellen)
- Drill-Status inkl. DB-Identitätsdigests, Exit-Codes, Dump-SHA256 und Fingerprints

Keine Klartext-Passwörter, Tokens, DSNs oder Passwort-Hashes.

## Backup-/Restore-Drill (verpflichtend)

Der Drill läuft ausschließlich über die Prep-API auf einer ausdrücklich separaten,
leeren Validierungsdatenbank. Manuelles Schreiben einer Evidence-Datei ist kein
Freigabenachweis.

### Ablauf

1. Quelle und Ziel über PostgreSQL-System-ID und Datenbank-OID identifizieren.
2. Gleiche physische Datenbanken auch bei abweichender DSN-Schreibweise ablehnen.
3. Zielname mit Präfix `qmtool_um_restore_drill` und vollständige Ziel-Leere prüfen.
4. `pg_dump` und `pg_restore` auf `PATH` verlangen.
5. `pg_dump --format=custom --schema=usermanagement` ausführen und SHA-256 bilden.
6. Ohne `--clean` in das weiterhin identische Restore-Ziel einspielen.
7. Migrationstip und Schema-Fingerprint von Quelle und Restore vergleichen.
8. Evidence-JSON kollisionsfrei unter `work_dir` schreiben.

Passwörter werden aus den Subprozessargumenten entfernt und nur in der kurzlebigen
libpq-Umgebung des jeweiligen Prozesses bereitgestellt. Evidenz und Berichte enthalten
keine DSNs oder Zugangsdaten.

Fehlt der Drill oder schlägt er fehl, bleibt der Prep-Status höchstens `blocked`
(nie `ready_for_remapping`).

## CLI

```text
python scripts/prepare_postgres_cutover.py ^
  --sqlite-users storage/platform/users.db ^
  --documents-db storage/documents/documents.db ^
  --training-db storage/training/training.db ^
  --incident-management-db storage/incident_management/incidents.db ^
  --signature-db storage/signature/templates.db ^
  --postgres-migrator-dsn "<migrator-dsn>" ^
  --drill-restore-dsn "<empty-restore-target-dsn>" ^
  --report-dir build ^
  --drill-work-dir build/drill
```

Exit-Code `0` bedeutet ausschließlich `ready_for_remapping`. `blocked` und
`invalid_source` liefern `1`, technische Ausführungsfehler `2`.

## Folgepaket (außerhalb M8)

Vor jedem produktiven Cutover muss ein separates Arbeitspaket festlegen und
umsetzen: UUID-Mapping, Migration aller Quermodulreferenzen, Datenvalidierung,
Rückfallverfahren und produktive Umschaltung.
