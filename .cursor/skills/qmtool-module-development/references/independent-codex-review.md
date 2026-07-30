# Unabhängige Codex-Prüfung

## Zweck

Codex prüft am Ende eines Arbeitspakets unabhängig den tatsächlichen Repository-Stand. Die Prüfung soll insbesondere erkennen, ob Cursor:

- den bestätigten Benutzerwunsch korrekt umgesetzt hat,
- eine Funktion weggelassen oder hinzugefügt hat,
- eine fachliche oder GUI-Entscheidung frei interpretiert hat,
- eine freie Interpretation fälschlich als technisches Detail oder Projektmuster deklariert hat.

Codex verändert keine Dateien.

## Voraussetzungen

Vor dem Review müssen aktuell sein:

- freigegebene Planungsdokumente,
- `06_entscheidungsprotokoll.md`,
- `08_anforderungsnachweis.md`,
- Abnahmekriterien und Traceability,
- `development_status.md`,
- Git-Diff des Arbeitspakets,
- dokumentierte Testergebnisse.

Fehlt der Herkunftsnachweis für eine neue oder geänderte fachliche Funktion oder eine wesentliche GUI-Entscheidung, darf Cursor den Review nicht als Ersatz für die notwendige Benutzerfrage verwenden. Die Rückfrage muss vor der Implementierung erfolgen.

## Modellwahl zur Kontingentschonung

### Economy: GPT-5.4 Mini, Medium

Verwende optional:

```powershell
.\.cursor\tools\codex_review_work_package.cmd -ReviewTier Economy
```

nur für rein technische, eng begrenzte Arbeitspakete ohne neue oder geänderte fachliche Funktion und ohne wesentliche GUI-Ausgestaltung, zum Beispiel Architekturtests, interne Refactorings oder Testergänzungen. Economy ist nicht der automatische Abnahmereviewer für fachlich relevante Iterationen.

### Standard: GPT-5.6 Luna, Medium

Verwende standardmäßig:

```powershell
.\.cursor\tools\codex_review_work_package.cmd -ReviewTier Standard
```

Geeignet für klar abgegrenzte, gut dokumentierte Arbeitspakete mit vollständigem Anforderungsnachweis. Luna ist für klare und wiederholbare Prüfaufgaben vorgesehen.

### Sensitiv: GPT-5.6 Terra, Medium

Verwende:

```powershell
.\.cursor\tools\codex_review_work_package.cmd -ReviewTier Sensitive
```

nur bei mindestens einem dieser Fälle:

- GUI-Iteration oder grundlegende sichtbare Bedienänderung,
- neue oder geänderte Rollen, Capabilities oder Berechtigungen,
- bedeutungsverändernde oder destruktive Migration,
- öffentliche modulübergreifende API- oder Contract-Änderung,
- fachlich besonders folgenreicher Zustands- oder Freigabeprozess,
- ungewöhnlich großer oder schwer abgrenzbarer Diff.

### Tiefenprüfung: GPT-5.6 Sol, High

`Deep` wird niemals automatisch gewählt. Verwende es nur nach ausdrücklicher Benutzerentscheidung für einen besonders schwierigen oder hochriskanten Review.

## Einmaliger Ablauf

1. Aktualisiere Anforderungsnachweis, Traceability und Entwicklungsstatus.
2. Wähle `Economy` nur für rein technische Arbeitspakete ohne fachliche oder wesentliche GUI-Auswirkung; ansonsten `Standard` oder bei den genannten Kriterien `Sensitive`.
3. Starte genau einen schreibgeschützten Review.
4. Lies `.cursor/reviews/qmtool-work-package-review.md` nicht um oder formuliere den Prüfauftrag nicht spontan neu.
5. Werte nur den erzeugten Bericht aus.
6. Bei `RUECKSPRACHE_ERFORDERLICH` frage den Benutzer. Triff die fehlende Funktions- oder GUI-Entscheidung nicht selbst.
7. Bei gezielter Nacharbeit behandle BLOCKER, HOCH und eindeutig arbeitspaketbezogene MITTEL-Funde.
8. Führe höchstens eine gezielte Nacharbeitsrunde aus und danach nur die betroffenen Tests einmal erneut.
9. Starte keinen zweiten vollständigen Codex-Review, außer der Benutzer verlangt ihn oder ein verbliebener Blocker kann anders nicht beurteilt werden.

## Gültige Abschlussurteile

- `ABNAHMEFAEHIG`
- `ABNAHMEFAEHIG_MIT_DOKUMENTATIONSKORREKTUR`
- `RUECKSPRACHE_ERFORDERLICH`
- `EINE_GEZIELTE_NACHARBEIT_ERFORDERLICH`
- `NICHT_ABNAHMEFAEHIG`

Ein technisches Implementierungsmuster ohne fachliche oder sichtbare Wirkung ist kein Grund für `RUECKSPRACHE_ERFORDERLICH`.
