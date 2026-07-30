# Anforderungstreue und Herkunftsnachweis

## Ziel

Cursor darf technische Details selbstständig lösen, aber keine fachlichen Funktionen oder wesentlichen GUI-Entscheidungen frei erfinden. Vor jeder Implementierung muss er unterscheiden, ob eine Entscheidung wirklich vorgegeben ist oder lediglich plausibel erscheint.

## Vier Herkunftsklassen

### `EXPLIZIT_BESTAETIGT`

Die Funktion, Regel oder GUI-Entscheidung wurde vom Benutzer ausdrücklich bestätigt oder steht in einer fachlich freigegebenen Spezifikation.

Erforderlicher Nachweis:

- Entscheidungs-ID oder Anforderungs-ID,
- genaue Datei und Abschnitt,
- kurzer Inhalt der bestätigten Entscheidung.

Eine Vermutung aus bestehendem Code, üblichen Best Practices oder einem ähnlichen Modul ist kein expliziter Nachweis.

### `TECHNISCH_NOTWENDIG`

Die Entscheidung ist erforderlich, um eine bestätigte Anforderung technisch korrekt umzusetzen, verändert aber weder fachliche Bedeutung noch sichtbares Benutzerverhalten.

Beispiele:

- Mapping zwischen Domain und Persistenz,
- Wahl einer internen Fehlerklasse,
- Transaktionsgrenze zur Wahrung einer bestätigten Invariante,
- technische Validierung eines bereits bestätigten Pflichtfelds.

Keine Rückfrage erforderlich. Die Ableitung muss knapp begründet werden.

### `PROJEKTMUSTER`

Die Entscheidung folgt einem bereits etablierten QMTool-Muster und verändert keine Funktion, Datenbedeutung oder grundlegende Bedienweise.

Beispiele:

- bestehendes Presenter- oder ViewModel-Muster,
- übliche Dateiaufteilung,
- Standarddialog für technische Fehlermeldungen,
- bestehende Namens- und Testkonventionen,
- Abstände, Größen und Standard-Widgets innerhalb eines bestätigten GUI-Konzepts.

Keine Rückfrage erforderlich. Nenne das verwendete Muster oder eine Vergleichsstelle.

### `FACHLICHE_ODER_GUI_INTERPRETATION`

Die Entscheidung legt eine Funktion, eine fachliche Bedeutung oder eine wesentliche sichtbare Bedienweise fest, ohne dass dafür eine explizit bestätigte Quelle vorhanden ist.

Beispiele:

- zusätzliche oder weggelassene Funktion,
- automatische Aktion, Standardwert oder Statusänderung,
- neues Pflichtfeld oder veränderte Berechtigung,
- abweichende Reihenfolge eines Arbeitsablaufs,
- Dialog statt Workspace oder umgekehrt,
- Tabs statt Master-Detail-Ansicht,
- sichtbare beziehungsweise verborgene Informationen,
- Auswahl, welche Aktionen direkt oder nur über Unterdialoge erreichbar sind,
- automatische Speicherung statt ausdrücklichem Speichern.

Diese Klasse darf nicht implementiert werden. Frage den Benutzer konkret und dokumentiere seine Entscheidung.

## Verbindliche Prüfung vor Codeänderungen

1. Liste jede neue oder geänderte fachliche Funktion des Arbeitspakets auf.
2. Liste jede wesentliche GUI-Entscheidung auf, sofern GUI Bestandteil des Arbeitspakets ist.
3. Ordne jedem Punkt eine Herkunftsklasse zu.
4. Hinterlege bei `EXPLIZIT_BESTAETIGT` eine konkrete Quellenreferenz.
5. Kann eine Funktion oder wesentliche GUI-Entscheidung nur als `FACHLICHE_ODER_GUI_INTERPRETATION` eingeordnet werden, stoppe vor deren Implementierung und frage den Benutzer.
6. Aktualisiere `08_anforderungsnachweis.md` nach der Umsetzung mit der tatsächlichen Implementierung.

Cursor darf eine unklare Entscheidung nicht rückwirkend als `TECHNISCH_NOTWENDIG` oder `PROJEKTMUSTER` etikettieren, nur um eine Rückfrage zu vermeiden.

## Keine Übereskalation

Nicht jede Codezeile und nicht jedes Widgetdetail benötigt eine Benutzerentscheidung. Frage nicht bei Entscheidungen, die alle folgenden Kriterien erfüllen:

- Sie ändern keine fachliche Funktion.
- Sie ändern keine Datenbedeutung, Berechtigung oder Zustandslogik.
- Sie ändern keinen bestätigten Arbeitsablauf.
- Sie führen keine neue sichtbare Funktion oder automatische Aktion ein.
- Sie folgen einer bestehenden Projektkonvention oder sind rein intern.

Beispiele ohne Rückfrage:

- Aufteilung einer Serviceklasse,
- interne Methodennamen,
- Repository- und Mapperstruktur,
- Testparametrisierung,
- Standard-Buttonabstände innerhalb einer bestätigten Dialoggestaltung,
- Nutzung eines bereits im Projekt üblichen Tabellen-Widgets, wenn Tabellenansicht und Inhalte bestätigt sind.

## Konkrete Rückfrage

Nutze bei fehlendem Herkunftsnachweis:

```text
FACHLICHE ODER GUI-ENTSCHEIDUNG ERFORDERLICH
Arbeitspaket:
Nicht explizit geklärter Punkt:
Warum dies Funktion oder Bedienweise verändert:
Option A – Konsequenz:
Option B – Konsequenz:
Empfehlung:
```

Frage nicht abstrakt, sondern benenne genau die sichtbare oder fachliche Entscheidung.
