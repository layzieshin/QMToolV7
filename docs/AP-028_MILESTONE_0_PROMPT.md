# Prompt für die Umsetzungs-KI — AP-028 Milestone 0

Kopiere den Abschnitt **Auftrag** unten in eine neue Agent-Session. Bearbeite **nur Milestone 0**. Lies zuerst die genannten Dateien. Keine Code-Implementierung.

---

## Auftrag

Du setzt **ausschließlich Milestone 0** von AP-028 um.

### Verbindliche Quellen (in dieser Reihenfolge lesen)

1. `docs/AP-028_USERMANAGEMENT_BACKEND_SESSIONS_ROADMAP.md` — Abschnitt **Milestone 0** und Abschnitte A, D, E
2. `docs/MASTER_ORCHESTRATION_ROADMAP.md` — Status AP-028 / Freigaben
3. `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`
4. `docs/AP-004_USER_CONTEXT_ADR.md`
5. `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md` (Supervisor: Admin ≠ QMB angenommen)
6. `docs/AP-006_AUDIT_ACTOR_ADR.md` (nur Orientierung Actor/Target)
7. Kurz prüfen: `modules/usermanagement/api.py`, `session_store.py`, `auth_ops.py`, `contracts.py`, `role_policies.py`, `src/backend/api.py`

Workflow-Regeln: `.cursor/rules/00-agent-workflow.mdc`, `.cursor/rules/01-git-workflow.mdc`, `AGENTS.md`.

### Ziel von Milestone 0

Bestandsaufnahme und verbindliche Sollentscheidungen festhalten. **Keine Implementierung** von Sessions, UserContext-Code, PostgreSQL, Backend-Routen oder Dependency-Änderungen.

### Erwartetes Ergebnis

1. Eine knappe, widerspruchsfreie **Ist-Matrix** und **Ziel-Matrix** (entweder Nachtrag in der Roadmap unter Milestone 0 / Anhang oder neues schlankes `docs/AP-028_M0_STATE_MATRIX.md`).
2. Bestätigung der bereits entschiedenen Punkte (nicht neu verhandeln):
   - serverseitige opake Sessions (kein JWT als Erstmodell)
   - internes Login
   - bestätigter frozen UserContext
   - Admin ≠ QMB
   - PostgreSQL für Usermanagement-Scope
   - AP-028 vor Documents-Multiuser-MVP
3. Restoffenheiten nur laut Roadmap-Abschnitt E (Passwortwechsel-Sessions, user_id-Remapping, `must_change_password`-Enforcement, User-Admin-HTTP-Umfang, PG-Testinfrastruktur).
4. Explizit als **Out of Scope** markieren: Incident Admin=QMB-Abweichung, Documents-Fachautorisierung, PyQt-Vollumbau, andere Module auf PostgreSQL.

### Branch / Git

- Nicht auf `main` committen.
- Feature-Branch für Milestone 0, z. B. `feature/ap-028-m0-state-matrix` (von aktuellem `main` bzw. integriertem Planungsstand).
- Commit/Push/PR nur wenn der Nutzer das ausdrücklich verlangt.
- Pre-existing Dirty State anderer Dateien nicht anfassen.

### Scope-Grenzen (hart)

- **Erlaubt:** Dokumentation unter `docs/` für M0-Artefakte; minimale Statusklarstellungen in bestehenden AP-028/ADR-Docs falls nötig.
- **Verboten:** Änderungen unter `modules/`, `src/backend/`, `qm_platform/`, `interfaces/`, `tests/` (außer du findest einen Doc-only-Test — dann nicht anfassen, melden), `requirements.txt`, Schema/SQL.

### Selbstständig entscheiden (ohne Rückfrage)

- Dateiname der Matrix, Tabellenlayout, Formulierungen, kleine Doc-Struktur.
- Ob Matrix in Roadmap-Anhang oder eigene Datei liegt (eine Quelle der Wahrheit, keine Duplikat-Pflege).

### Eskalieren (Format laut Roadmap)

Stoppen und Nutzer fragen bei:

- Widerspruch ADR ↔ Code ↔ Roadmap, der Verhalten oder Architektur ändern würde
- Wunsch, Code oder Cleanup in anderen Modulen zu starten
- Änderung der öffentlichen Modulgrenze
- Datenmigrationsrisiko

Eskalationsformat:

```text
1. konkrete offene Entscheidung
2. betroffene Architektur oder Fachregel
3. verfügbare Optionen
4. Empfehlung
5. Auswirkung je Option
```

### Test-Gate vor Abschluss von M0

- Keine Produktcode-Änderung.
- Falls du die Suite anfasst: Baseline `.\.venv\Scripts\python.exe -m pytest tests/interfaces/test_architecture_gates.py -q` muss grün bleiben (Docs-only sollte das nicht berühren).
- Optional Baseline (nicht blockierend für Doc-only, aber melden falls rot):
  `.\.venv\Scripts\python.exe -m pytest tests/modules/test_usermanagement_persistence.py tests/modules/test_usermanagement_qmb_flag.py -q`

### Abnahme

Milestone 0 ist fertig, wenn:

- Ist- und Zielmatrix existieren und zur Roadmap passen
- Abschnitt-E-Offenheiten nicht „wegbeschlossen“ wurden
- Out-of-Scope-Abweichungen dokumentiert sind
- der Abschlussbericht enthält: geänderte Dateien, Verifikation, explizit „keine neuen öffentlichen Code-Surfaces / keine Parallelpfade“
- **Übergabe:** kurzer Hinweis, dass Milestone 1 als Nächstes dran ist (Contracts/UserContext) — aber Milestone 1 **nicht** in derselben Session beginnen

### Nicht tun

- Nicht Milestones 1–9 animplementieren
- Nicht `wiring.py` reaktivieren oder Parallel-Sessionstore bauen
- Nicht Master-Roadmap-Priorität rückgängig machen
- Nicht Admin=QMB in Incident „nebenbei“ fixen
