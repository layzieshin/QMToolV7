# Codex-Reviews

`qmtool-work-package-review.md` ist der verbindliche Prüfauftrag für den unabhängigen Codex-Review am Ende eines Arbeitspakets.

Der Prompt wird vom Skript `.cursor/tools/codex_review_work_package.cmd` unverändert an `codex exec` übergeben. Cursor darf ihn nicht spontan vereinfachen oder durch einen selbst formulierten Review-Prompt ersetzen.

Der erzeugte Bericht liegt standardmäßig unter:

```text
docs/reviews/codex_latest_review.md
```

Das Skript legt dieses Zielverzeichnis bei Bedarf an.
