# Container Module: lokaler manueller Test

Die lokale Demo besitzt zwei Testoberflächen: die visuelle **Modulwerkstatt** zum
Zusammenstellen und Veröffentlichen kompletter Blueprints sowie Swagger für
einzelne API-Operationen. Beide sind ausdrücklich lokal und isoliert; die
Demo ersetzt Authentifizierung ausschließlich in dieser App.

```bash
python -m src.backend.container_demo --app-home /tmp/qmtool-container-demo --port 8765
```

Danach für den visuellen Builder `http://127.0.0.1:8765/container/admin`
öffnen. Die vollständige Klickanleitung steht in
`docs/container-module/MODULE_BUILDER_GUIDE.md`. Swagger bleibt unter
`http://127.0.0.1:8765/docs` erreichbar. Der Titel **LOCAL DEMO – NO
PRODUCTION AUTH** bestätigt den Demo-Modus. Die Daten liegen ausschließlich
unter dem mit `--app-home` gewählten Pfad; zum Zurücksetzen diesen konkreten
Demo-Pfad entfernen.

1. `GET /container/status` ausführen und `workspace_root_uid` kopieren.
2. `POST /container/templates/drafts` mit `{"kind":"OBJECT","name":"Demo Object","version_number":1,"create_roles":["ADMIN"],"fields":[{"key":"title","field_type":"string","required":true,"searchable":true}]}` ausführen.
3. Die zurückgegebene `uid` mit `POST /container/templates/{uid}/publish` veröffentlichen.
4. `POST /container/objects` mit der veröffentlichten `template_version_uid`, `parent_kind:"WORKSPACE_ROOT"`, der kopierten `parent_uid` und `values:{"title":"Erster Test"}` anlegen.
5. `GET /container/objects/{uid}` zeigt Field-Werte und die serverseitige `allowed_actions`-Map.
6. Ein zweites Template mit `kind:"ARTIFACT"` anlegen/veröffentlichen und anschließend `POST /container/artifacts` für die Objekt-UID aufrufen.
7. `POST /container/artifacts/{uid}/files` mit `{"original_name":"demo.txt","media_type":"text/plain","content_base64":"aGFsbG8=","expected_revision":1}` hochladen.
8. `GET /container/artifacts/{uid}` prüfen; die Revision ist nach dem Upload erhöht.
9. `POST /container/artifacts/{uid}/finalize` mit der aktuellen Revision aufrufen; danach `POST /container/artifacts/{uid}/sign` mit `{"meaning":"Demo-Freigabe"}`.
10. Den Download über `GET /container/artifacts/{artifact_uid}/files/{file_uid}/download` prüfen.

Negative Fälle: Ein falsches `expected_revision` liefert 409, eine Feldänderung nach Finalisierung
409 und Base64-Fehler bzw. Pfadnamen wie `../demo.txt` liefern eine stabile 422-Antwort. Im
produktiven Backend benötigen die Container-Routen stets Bearer-Authentifizierung; ohne Token
antworten sie 401.
