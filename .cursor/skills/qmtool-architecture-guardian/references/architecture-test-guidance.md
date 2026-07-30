# Leitfaden für Architekturtests

## Importtests

AST-basierte Tests sollen:

- Pfade relativ zum Modul-Root bestimmen,
- `ast.Import` und `ast.ImportFrom` behandeln,
- relative Imports über `node.level` berücksichtigen,
- Treffer sammeln und gemeinsam verständlich ausgeben,
- explizite Ausnahmen zentral dokumentieren,
- nicht pauschal jede fremde `ports.py` oder `capabilities.py` als öffentlich erlauben.

Die erlaubten Cross-Module-Flächen müssen aus der QMTool-Architektur stammen, nicht aus einem generischen Beispiel.

## Weitere mögliche Tests

- Fachmodule importieren keine GUI oder Hosts.
- Plattform importiert keine Fachmodule.
- öffentliche Contracts referenzieren keine ORM-Typen.
- alle `required_ports` sind registrierbar.
- keine unerlaubten Modulzyklen.
- Backend-Host verwendet nur freigegebene öffentliche Flächen.
- GUI greift nicht direkt auf interne Repositorys zu.

## Testdesign

- Eine Regel pro Test oder klarer Testgruppe.
- Aussagekräftige Fehlermeldung mit Datei und Import/Symbol.
- Positivbeispiel und mindestens ein Negativ-Fixpoint, soweit praktikabel.
- Bestehende Verletzungen nicht durch willkürliche breite Ausnahmen verstecken.
- Bei Altlasten kann ein Baseline-Modus sinnvoll sein, der neue Verstöße verhindert und alte einzeln abbaut.

## Korrekturbudget

Nach Implementierung eines Architekturtests:

1. Test einmal ausführen.
2. Fehler als echte Verletzung, Testfehler oder dokumentierte Ausnahme klassifizieren.
3. Höchstens zwei gezielte Korrekturrunden.
4. Danach Bericht und separaten Bereinigungsumfang erstellen.
