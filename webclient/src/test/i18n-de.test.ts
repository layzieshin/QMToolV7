import { describe, expect, it } from "vitest";

import de from "../i18n/de";
import { i18n } from "../i18n";

describe("german i18n", () => {
  it("exposes required shell and login keys", () => {
    expect(de.app.title).toBe("QMTool");
    expect(de.login.title).toBe("Anmeldung");
    expect(de.login.submit).toBe("Anmelden");
    expect(de.shell.auth.passwordChangeRequired).toBe("Passwortänderung erforderlich");
  });

  it("resolves interpolated auth label", () => {
    const message = i18n.global.t("shell.auth.authenticated", { username: "bob" });
    expect(message).toContain("bob");
  });
});
