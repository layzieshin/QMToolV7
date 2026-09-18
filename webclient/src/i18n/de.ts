export default {
  app: {
    title: "QMTool",
  },
  shell: {
    homeTitle: "Start",
    homeHint: "Die Produktnavigation wird in den nächsten Checkpoints ergänzt.",
    homeAuthenticatedHint: "Sie sind angemeldet. Weitere Funktionen folgen in WEB01-B+.",
    logout: "Abmelden",
    loading: "Laden…",
    connection: {
      online: "Verbunden",
      offline: "Getrennt",
      unknown: "Unbekannt",
    },
    auth: {
      anonymous: "Nicht angemeldet",
      authenticated: "Angemeldet als {username}",
      passwordChangeRequired: "Passwortänderung erforderlich",
    },
  },
  login: {
    title: "Anmeldung",
    username: "Benutzername",
    password: "Passwort",
    submit: "Anmelden",
    failed: "Anmeldung fehlgeschlagen",
  },
  changePassword: {
    title: "Passwort ändern",
    hint: "Bitte setzen Sie ein neues Passwort, um fortzufahren.",
    newPassword: "Neues Passwort",
    submit: "Passwort speichern",
    failed: "Passwortänderung fehlgeschlagen",
    weakPassword: "Das Passwort ist zu schwach.",
  },
  api: {
    errors: {
      unauthorized: "Sitzung abgelaufen oder nicht angemeldet.",
      forbidden: "Diese Aktion ist nicht erlaubt.",
      notFound: "Die angeforderte Ressource wurde nicht gefunden.",
      conflict: "Der Datensatz wurde zwischenzeitlich geändert.",
      preconditionRequired: "Ein erforderlicher Vorbedingungs-Header fehlt.",
      transport: "Die Anfrage konnte nicht ausgeführt werden.",
    },
  },
};
