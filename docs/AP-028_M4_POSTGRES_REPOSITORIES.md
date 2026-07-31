# AP-028 M4 - PostgreSQL-Repositories und opaker Sessionpfad

## Ergebnis

M4 verbindet die bestehenden `UserRepository`- und `SessionRepository`-Ports
mit dem in M3/M3.1 abgesicherten PostgreSQL-Schema. Die fachliche
Sessionlogik bleibt in `UserManagementService` und `SessionOps`.

Der gewaehlte Authentifizierungspfad ist serverseitig und opak:

1. Der Dienst erzeugt ein Klartext-Token nur fuer die einmalige Ausgabe.
2. PostgreSQL speichert ausschliesslich den Token-Hash.
3. Ein Request wird ueber den Hash aufgeloest.
4. Benutzer, Aktivstatus und Rollen werden aus dem aktuellen User-Datensatz
   gelesen und nicht aus der Session uebernommen.

## Ausfuehrungspfad

```text
UserManagementService
  -> SessionOps
    -> PostgresSessionRepository
      -> runtime_connection
        -> PostgreSQL als konkrete LOGIN-Rolle unter qmtool_runtime
```

Der User-Pfad verwendet entsprechend `PostgresUserRepository`. Beide
Repositories eroeffnen pro Operation eine Verbindung und pruefen vor dem
ersten SQL-Zugriff:

- LOGIN-Rolle ist zugleich `current_user` und `session_user`.
- LOGIN-Rolle ist Mitglied von `qmtool_runtime` und darf dorthin wechseln.
- LOGIN-Rolle ist weder direkt noch transitiv Mitglied von
  `qmtool_migrator` und darf dorthin nicht wechseln.

Eine Migrator- oder Administrationsverbindung wird damit fail-closed
abgewiesen.

## Runtime-Komposition

`modules/usermanagement/module.py` verwendet den PostgreSQL-Pfad nur, wenn
der Composition Root den Port `usermanagement_postgres_dsn` ausdruecklich
registriert. Ohne diesen Port bleibt der bestehende Desktop-Pfad unveraendert:
SQLite-User-Repository und Legacy-Sessiondatei bleiben aktiv.

Der M4-Schritt fuehrt noch keine HTTP-Routen und keinen Produktiv-Cutover
ein. Die Backend-Komposition und die Auth-Endpunkte folgen in M5.

## Persistenz- und Konkurrenzregeln

- User-CRUD, Passwort-Hashing, Aktivstatus und Rollenfelder werden auf die
  M3-Tabelle `usermanagement.users` abgebildet.
- Session-IDs und User-IDs werden als UUID behandelt.
- Unique-, Foreign-Key- und Check-Verletzungen werden in Repository-Fehler
  beziehungsweise `KeyError`/`ValueError` uebersetzt.
- `touch` aktualisiert nur nicht widerrufene Sessions und monotonisiert
  `last_seen_at`.
- `revoke` und `revoke_all_for_user` setzen den Widerruf atomar.
- Ein paralleler Touch kann einen bereits gewonnenen Widerruf nicht
  zuruecksetzen.

## Verifikation

Die Live-Suite liegt in
`tests/modules/usermanagement/test_postgres_repositories_live.py` und prueft
CRUD-Mapping, Hashing, Constraints, Runtime-Rollen, den opaken Servicepfad,
die explizite Modulkomposition und den Touch-/Revoke-Konkurrenzfall.

Der PostgreSQL-CI-Job fuehrt diese Suite mit `QMTOOL_PG_REQUIRED=1` gegen
PostgreSQL 16 aus. M4 aendert weder das M3-Schema noch den Fingerprint und
fuehrt keinen neuen oeffentlichen API-Export ein.

## Uebergabe an M5

M5 kann den Backend-Host an den expliziten DSN-Port anschliessen und die
Auth-Endpunkte implementieren. Der Backend-Host greift dabei weiterhin nur
ueber die oeffentliche Modulgrenze zu; SQL und Repository-Internals bleiben
im Usermanagement-Modul.
