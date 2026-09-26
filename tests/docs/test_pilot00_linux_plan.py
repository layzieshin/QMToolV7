from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
PREP = DOCS / "AP-029_PILOT00_LINUX_PREPARATION.md"
ADR = DOCS / "AP-029_PILOT_PROFILE_ADR.md"
PLAN = DOCS / "AP-029_WEB_POSTGRES_TRANSITION_PLAN.md"
ROADMAP = DOCS / "MASTER_ORCHESTRATION_ROADMAP.md"

DECISIONS = {"DECIDED", "RECOMMENDED", "OPEN", "SUPERSEDED", "N/A", "DEFERRED"}
EVIDENCE = {"NOT RUN", "PARTIAL", "IMPLEMENTED_VERIFIED"}
EXPECTED_COUNTS = {
    "Q01": 14,
    "Q02": 15,
    "Q03": 29,
    "Q04": 19,
    "Q05": 14,
    "Q06": 28,
    "Q07": 19,
    "Q08": 23,
    "Q09": 16,
    "Q10": 22,
    "Q11": 31,
    "Q12": 12,
    "Q13": 19,
    "Q14": 28,
    "Q15": 19,
    "Q16": 16,
    "Q17": 12,
    "Q18": 21,
    "Q19": 14,
    "Q20": 16,
    "Q21": 24,
    "Q22": 17,
    "Q23": 16,
    "Q24": 17,
    "Q25": 23,
    "Q26": 13,
    "Q27": 19,
    "Q28": 23,
    "Q29": 10,
    "Q30": 18,
    "Q31": 14,
    "Q32": 11,
}
EMPTY_OPEN = {"", "—", "-", "–"}


class PlanContractError(AssertionError):
    pass


def parse_control(text: str) -> dict[str, str]:
    start = text.count("<!-- PILOT00_LINUX_CONTROL_START -->")
    end = text.count("<!-- PILOT00_LINUX_CONTROL_END -->")
    if start != 1 or end != 1:
        raise PlanContractError("control block must appear exactly once")
    body = text.split("<!-- PILOT00_LINUX_CONTROL_START -->", 1)[1].split(
        "<!-- PILOT00_LINUX_CONTROL_END -->", 1
    )[0]
    fields: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in fields:
            raise PlanContractError(f"duplicate control field {key}")
        fields[key] = value.strip()
    return fields


def parse_subpoints(text: str) -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = {}
    current: str | None = None
    seen: set[str] = set()
    for line in text.splitlines():
        header = re.match(r"^### (Q\d{2}) ", line)
        if header:
            qid = header.group(1)
            if qid in sections:
                raise PlanContractError(f"duplicate section {qid}")
            sections[qid] = []
            current = qid
            continue
        if current is None or not line.startswith("| Q"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            raise PlanContractError(f"row does not have 7 cells: {line}")
        sp, topic, decision, evidence, owner, open_value, gate = cells
        if not re.fullmatch(rf"{current}-\d{{2}}", sp):
            raise PlanContractError(f"{sp} is outside section {current}")
        if sp in seen:
            raise PlanContractError(f"duplicate subpoint {sp}")
        seen.add(sp)
        if decision not in DECISIONS:
            raise PlanContractError(f"{sp} has unknown decision {decision}")
        if evidence not in EVIDENCE:
            raise PlanContractError(f"{sp} has unknown evidence {evidence}")
        if not owner or not gate or not topic:
            raise PlanContractError(f"{sp} is missing topic, owner, or gate")
        if decision == "OPEN" and open_value in EMPTY_OPEN:
            raise PlanContractError(f"{sp} is OPEN without an open value")
        if decision in {"N/A", "SUPERSEDED", "RECOMMENDED"} and open_value in EMPTY_OPEN:
            raise PlanContractError(f"{sp} {decision} has no explanation")
        sections[current].append(
            {
                "sp": sp,
                "topic": topic,
                "decision": decision,
                "evidence": evidence,
                "owner": owner,
                "open_value": open_value,
                "gate": gate,
            }
        )
    return sections


def assert_preparation_contract(text: str) -> None:
    control = parse_control(text)
    required = {
        "active_preparation": "PILOT00-LINUX-PLAN",
        "preparation_status": "PLAN_DOCS_LOCAL",
        "deployment_status": "NOT RUN",
        "formal_pilot_status": "NOT RUN",
        "current_checkpoint": "PILOT00",
        "current_checkpoint_count": "1",
        "windows_scm_status": "NOT RUN",
        "linux_profile_status": "PROPOSED",
        "linux_profile_decision": "HUMAN_DECISION_REQUIRED",
        "slot2_lab_bypass": "forbidden",
        "automatic_pilot01": "forbidden",
        "settings_pg_blocks_pilot": "true",
        "signature_recovery_blocks_pilot": "true",
        "target_recovery_blocks_pilot": "true",
        "dual_write": "forbidden",
        "runtime_ddl": "forbidden",
        "sqlite_product_fallback": "forbidden",
        "ux_d37": "accepted-limited",
        "accessibility_smoke": "included",
        "accessibility_evidence": "NOT RUN",
        "greenfield": "required",
        "synthetic_data": "required",
        "first_password_change": "required",
        "signature_identity": "own-authentication",
        "recommendations_are_approvals": "false",
        "rootless_setup_is_deployment": "false",
        "closeout_evidence": "NOT RUN",
        "human_recovery_required": "true",
        "git_approval": "separate",
        "remote_approval": "separate",
        "phase_approval": "separate",
        "plan_challenge_status": "UNAVAILABLE",
        "roadmap_architect_status": "UNAVAILABLE",
        "native_role_pass": "not-claimed",
        "control_plane_pinned": "false",
        "runtime_attested": "false",
        "codex_plan_review": "HUMAN_AUTHORIZED_INDEPENDENT_CODEX_PLAN_REVIEW",
    }
    for key, value in required.items():
        if control.get(key) != value:
            raise PlanContractError(f"{key}={control.get(key)!r} expected {value!r}")
    if "C before D" not in control.get("package_order", ""):
        raise PlanContractError("package order must keep C before D")
    if "A-D before E" not in control.get("package_order", ""):
        raise PlanContractError("package order must keep A-D before E")
    if "modules/<name>/api.py" not in control.get("external_module_calls", ""):
        raise PlanContractError("external module calls must stay on api.py")
    for verdict in (
        "TECHNICAL_PASS",
        "SECURITY_REVIEW_PASS",
        "ARCHITECTURE_REVIEW_PASS",
        "HUMAN_ACCEPTANCE_PASS",
    ):
        if verdict not in control.get("closeout_verdicts", ""):
            raise PlanContractError(f"missing closeout verdict {verdict}")
    if control["formal_pilot_status"] == "PASS" or control["deployment_status"] == "PASS":
        raise PlanContractError("preparation must not be recorded as deployment or formal PASS")
    sections = parse_subpoints(text)
    if list(sections) != list(EXPECTED_COUNTS):
        raise PlanContractError("Q01-Q32 sections are missing, extra, or out of order")
    for qid, count in EXPECTED_COUNTS.items():
        rows = sections[qid]
        if len(rows) != count:
            raise PlanContractError(f"{qid} has {len(rows)} rows, expected {count}")
        ids = [row["sp"] for row in rows]
        expected_ids = [f"{qid}-{index:02d}" for index in range(1, count + 1)]
        if ids != expected_ids:
            raise PlanContractError(f"{qid} ids are not contiguous: {ids[:3]}...")
    assert_decision_evidence_split(text, sections)


def _row(sections: dict[str, list[dict[str, str]]], sp: str) -> dict[str, str]:
    qid = sp.split("-", 1)[0]
    found = next(row for row in sections[qid] if row["sp"] == sp)
    return found


def _require_decided_not_run(row: dict[str, str], reason: str) -> None:
    if row["decision"] != "DECIDED" or row["evidence"] != "NOT RUN":
        raise PlanContractError(
            f"{row['sp']} {reason} must stay DECIDED / NOT RUN, "
            f"got {row['decision']} / {row['evidence']}"
        )


def assert_decision_evidence_split(
    text: str,
    sections: dict[str, list[dict[str, str]]],
) -> None:
    for row in sections["Q25"]:
        _require_decided_not_run(row, "fachlicher Human-Smoke")
    for row in sections["Q28"]:
        _require_decided_not_run(row, "security review scope")
    _require_decided_not_run(_row(sections, "Q28-23"), "HIGH/CRITICAL gate")
    for sp in (
        "Q13-10",
        "Q14-07",
        "Q14-11",
        "Q15-02",
        "Q15-03",
        "Q15-15",
        "Q16-08",
        "Q17-06",
        "Q17-11",
        "Q18-04",
        "Q18-05",
        "Q18-16",
        "Q19-07",
        "Q19-08",
        "Q19-14",
        "Q20-16",
    ):
        _require_decided_not_run(_row(sections, sp), "mandatory Q13-Q20 scope")
    for row in sections["Q30"]:
        _require_decided_not_run(row, "evidence field")
    for sp in (
        "Q11-25",
        "Q12-10",
        "Q13-11",
        "Q13-12",
        "Q13-13",
        "Q13-14",
        "Q13-15",
        "Q13-16",
        "Q14-19",
        "Q14-20",
        "Q14-21",
        "Q14-22",
        "Q14-23",
        "Q14-24",
        "Q14-25",
        "Q14-26",
    ):
        _require_decided_not_run(_row(sections, sp), "mandatory recovery or identity scope")
    for sp in (
        "Q13-19",
        "Q14-12",
        "Q14-16",
        "Q15-16",
        "Q15-17",
        "Q17-10",
    ):
        _require_decided_not_run(_row(sections, sp), "mandatory drill, measurement, runbook, or doctor evidence")
    for sp in ("Q19-10", "Q19-13", "Q29-04", "Q29-05", "Q29-06"):
        row = _row(sections, sp)
        if row["decision"] != "OPEN" or row["evidence"] != "NOT RUN":
            raise PlanContractError(
                f"{sp} must stay OPEN / NOT RUN, got {row['decision']} / {row['evidence']}"
            )
    if _row(sections, "Q02-14")["decision"] == "DECIDED":
        raise PlanContractError("Q02-14 must not invent a fachlicher Abnehmer")
    if "keine belegte Person" not in _row(sections, "Q02-14")["open_value"]:
        raise PlanContractError("Q02-14 must keep the missing-person marker")
    if "kein Passwortmanager unterstellt" not in _row(sections, "Q16-06")["open_value"]:
        raise PlanContractError("Q16-06 must not assume a password manager")
    ux = next(row for row in sections["Q26"] if "UX-D37" in row["topic"] and "akzeptiert" in row["topic"])
    _require_decided_not_run(ux, "limited UX-D37 acceptance")
    _require_decided_not_run(_row(sections, "Q27-01"), "accessibility smoke")
    if _row(sections, "Q27-02")["decision"] != "OPEN":
        raise PlanContractError("screenreader tool stays OPEN")
    package_a = text.split("### A. PILOT00-SETTINGS-PG", 1)[1].split(
        "### B. PILOT00-SERVICE-RELEASE", 1
    )[0]
    if "wire_backend_documents" not in package_a:
        raise PlanContractError("package A must name both settings bootstrap paths")
    if "Exact allowlist" not in package_a:
        raise PlanContractError("package A allowlist must be exact")
    if "Provisional allowlist" in package_a or "provisional allowlist" in package_a:
        raise PlanContractError("package A allowlist must not stay provisional")
    headings = (
        "## Entscheidungsblock 1 — Profil/Ausführung",
        "## Entscheidungsblock 2 — Zielbetrieb",
        "## Entscheidungsblock 3 — Mensch/Test/Betriebsziele",
    )
    positions = []
    for heading in headings:
        count = text.count(heading)
        if count != 1:
            raise PlanContractError(f"{heading} must appear exactly once")
        positions.append(text.index(heading))
    if positions != sorted(positions):
        raise PlanContractError("decision blocks are out of order")
    follow = text.split(headings[2], 1)[1]
    if "Status dieses Auftrags: `NICHT AUTORISIERT`." not in follow:
        raise PlanContractError("A-E follow-up must stay unauthorized")
    for heading in headings:
        block = text.split(heading, 1)[1].split("## ", 1)[0]
        if "Profilfreigabe" not in block or "Ausführungsfreigabe" not in block:
            raise PlanContractError(f"{heading} must separate profile and execution approval")
        if "<leer>" not in block:
            raise PlanContractError(f"{heading} answer field must stay unanswered")
    block_2 = text.split(headings[1], 1)[1].split(headings[2], 1)[0]
    if "Lizenz-Policy-Konflikt" not in block_2 or "LICENSE_SPEC" not in block_2:
        raise PlanContractError("license policy conflict must stay visible in block 2")
    if "SCOPE_CORRECTION_REQUIRED" not in follow or "wire_backend_documents" not in follow:
        raise PlanContractError("follow-up must freeze package A and fail closed on scope expansion")


def test_pilot00_linux_plan_contract_is_explicit() -> None:
    text = PREP.read_text(encoding="utf-8")
    assert_preparation_contract(text)
    sections = parse_subpoints(text)
    q02 = sections["Q02"]
    assert all(row["decision"] in {"OPEN", "N/A"} for row in q02)
    assert all(row["decision"] != "DECIDED" for row in q02)
    assert q02[2]["decision"] == "N/A"
    assert "keine belegte Person" in q02[0]["open_value"]
    q26 = sections["Q26"]
    ux = next(row for row in q26 if "UX-D37" in row["topic"])
    assert ux["decision"] == "DECIDED"
    assert "akzeptiert" in ux["topic"]
    assert sections["Q27"][0]["decision"] == "DECIDED"
    assert sections["Q27"][0]["evidence"] == "NOT RUN"
    assert sections["Q27"][1]["decision"] == "OPEN"
    assert any("GREENFIELD" in row["topic"].upper() or "Greenfield" in row["topic"] for row in sections["Q23"])
    assert sections["Q23"][0]["decision"] == "DECIDED"
    assert sections["Q21"][18]["decision"] == "DECIDED"
    assert "must_change_password" in sections["Q21"][18]["topic"]
    assert "kein Passwortmanager unterstellt" in sections["Q16"][5]["open_value"]
    assert sections["Q13"][4]["decision"] == "OPEN"
    assert "keine Nutzerfreigabe" in sections["Q13"][4]["open_value"]
    assert sections["Q29"][0]["decision"] == "OPEN"
    assert "keine Nutzerfreigabe" in sections["Q29"][0]["open_value"]
    assert "PILOT00-SETTINGS-PG" in text
    assert "PILOT00-SIGNATURE-RECOVERY" in text
    assert "PILOT00-TARGET-RECOVERY-ADAPTER" in text
    assert "blocks D" in text or "This package blocks D." in text
    assert "SqliteSettingsRepository" in text
    assert "kein Runtime-DDL" in text or "runtime_ddl: forbidden" in text
    assert "Slot-2" in text
    assert "host-wide" in text or "Host-Ausnahme" in text or "host-wide exception" in text


def test_profile_adr_is_proposed_not_a_windows_pass() -> None:
    adr = ADR.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    assert "PROPOSED / HUMAN_DECISION_REQUIRED" in adr
    assert "linux-rootless-synthetic" in adr
    assert "Windows Server remains" in adr
    assert "not a Windows readiness PASS" in adr
    assert plan.count("Current checkpoint: PILOT00") == 1
    assert "PILOT00-LINUX-PLAN" in plan
    assert "not a qualification PASS" in plan
    assert "ausschliesslich PILOT00" in roadmap
    assert "PILOT00 bleibt TODO" in roadmap
    assert "PROPOSED / HUMAN_DECISION_REQUIRED" in roadmap
    assert "gegenseitiger PASS" in roadmap
    assert "C vor D" in roadmap
    assert "PILOT00-SIGNATURE-RECOVERY" in roadmap
    assert "build-only" in roadmap
    assert "C vor D" in plan
    assert "PILOT00-SETTINGS-PG" in plan
    operations = (DOCS / "OPERATIONS_CANONICAL.md").read_text(encoding="utf-8")
    database = (DOCS / "DATABASE_EVOLUTION_POLICY.md").read_text(encoding="utf-8")
    smoke = (DOCS / "TEST_SMOKE_GATES.md").read_text(encoding="utf-8")
    index = (DOCS / "DOCS_CANONICAL_INDEX.md").read_text(encoding="utf-8")
    assert "Windows Server first" in operations
    assert "PROPOSED / HUMAN_DECISION_REQUIRED" in operations
    assert "NOT RUN" in operations
    assert "PILOT00-SETTINGS-PG" in database
    assert "no dual-write" in database
    assert "test_pilot00_linux_plan.py" in smoke
    assert "host-wide exception" in smoke
    p0 = index.split("## P0 (canonical, decision-making)", 1)[1].split("## P1", 1)[0]
    p1 = index.split("## P1 (important, domain/process detail)", 1)[1].split("## P2", 1)[0]
    assert "AP-029_PILOT_PROFILE_ADR.md" not in p0
    assert "AP-029_PILOT00_LINUX_PREPARATION.md" not in p0
    assert "`docs/AP-029_PILOT_PROFILE_ADR.md`" in p1
    assert "`docs/AP-029_PILOT00_LINUX_PREPARATION.md`" in p1


def test_negative_contracts_reject_missing_and_duplicate_ids() -> None:
    good = PREP.read_text(encoding="utf-8")
    broken = good.replace("### Q32 ", "### Q31 ", 1)
    try:
        parse_subpoints(broken)
    except PlanContractError as exc:
        assert "duplicate section" in str(exc)
    else:
        raise AssertionError("duplicate section was accepted")

    missing = good.replace("### Q02 ", "### QXX ", 1)
    try:
        assert_preparation_contract(missing)
    except PlanContractError as exc:
        assert "out of order" in str(exc) or "missing" in str(exc) or "outside section" in str(exc)
    else:
        raise AssertionError("missing Q02 was accepted")

    open_without_value = (
        "| Q01-01 | topic | OPEN | NOT RUN | PLAN | — | later |\n"
    )
    try:
        parse_subpoints("### Q01 Beispiel (1)\n" + open_without_value)
    except PlanContractError as exc:
        assert "OPEN without an open value" in str(exc)
    else:
        raise AssertionError("empty OPEN value was accepted")

    duplicate_row = (
        "### Q01 Beispiel (2)\n"
        "| Q01-01 | topic | DECIDED | NOT RUN | PLAN | — | later |\n"
        "| Q01-01 | topic | DECIDED | NOT RUN | PLAN | — | later |\n"
    )
    try:
        parse_subpoints(duplicate_row)
    except PlanContractError as exc:
        assert "duplicate subpoint" in str(exc)
    else:
        raise AssertionError("duplicate subpoint was accepted")

    passed = good.replace("formal_pilot_status: NOT RUN", "formal_pilot_status: PASS", 1)
    try:
        assert_preparation_contract(passed)
    except PlanContractError as exc:
        assert "formal PASS" in str(exc) or "expected" in str(exc)
    else:
        raise AssertionError("formal PASS was accepted for the preparation package")


def _reject(text: str, needle: str) -> None:
    try:
        assert_preparation_contract(text)
    except PlanContractError as exc:
        assert needle in str(exc)
    else:
        raise AssertionError(f"regression was accepted, expected {needle}")


def test_decision_evidence_regressions_fail() -> None:
    good = PREP.read_text(encoding="utf-8")
    smoke = good.replace(
        "| Q25-01 | Login | DECIDED | NOT RUN |",
        "| Q25-01 | Login | OPEN | NOT RUN |",
        1,
    )
    _reject(smoke, "Q25-01")
    claimed = good.replace(
        "| Q25-01 | Login | DECIDED | NOT RUN |",
        "| Q25-01 | Login | DECIDED | IMPLEMENTED_VERIFIED |",
        1,
    )
    _reject(claimed, "Q25-01")
    security = good.replace(
        "| Q28-23 | offene HIGH-/CRITICAL-Findings blockieren den Pilot | DECIDED |",
        "| Q28-23 | offene HIGH-/CRITICAL-Findings blockieren den Pilot | OPEN |",
        1,
    )
    _reject(security, "Q28-23")
    review_scope = good.replace(
        "| Q28-01 | Authentifizierung | DECIDED |",
        "| Q28-01 | Authentifizierung | OPEN |",
        1,
    )
    _reject(review_scope, "Q28-01")
    integrity = good.replace(
        "| Q13-10 | Integritätsprüfung | DECIDED |",
        "| Q13-10 | Integritätsprüfung | OPEN |",
        1,
    )
    _reject(integrity, "Q13-10")
    readback = good.replace(
        "| Q14-07 | funktionaler Readback | DECIDED |",
        "| Q14-07 | funktionaler Readback | OPEN |",
        1,
    )
    _reject(readback, "Q14-07")
    alarm = good.replace(
        "| Q18-16 | nachgewiesene Alarmzustellung | DECIDED |",
        "| Q18-16 | nachgewiesene Alarmzustellung | OPEN |",
        1,
    )
    _reject(alarm, "Q18-16")
    redaction = good.replace(
        "| Q19-07 | Secret-Redaction | DECIDED |",
        "| Q19-07 | Secret-Redaction | OPEN |",
        1,
    )
    _reject(redaction, "Q19-07")
    blanket = good.replace(
        "| Q20-16 | keine pauschale Verzeichnisausnahme ohne Freigabe | DECIDED |",
        "| Q20-16 | keine pauschale Verzeichnisausnahme ohne Freigabe | OPEN |",
        1,
    )
    _reject(blanket, "Q20-16")
    evidence = good.replace(
        "| Q30-01 | Candidate-SHA | DECIDED | NOT RUN |",
        "| Q30-01 | Candidate-SHA | OPEN | NOT RUN |",
        1,
    )
    _reject(evidence, "Q30-01")
    sealed = good.replace(
        "| Q13-11 | versiegelte Backupsets | DECIDED |",
        "| Q13-11 | versiegelte Backupsets | OPEN |",
        1,
    )
    _reject(sealed, "Q13-11")
    recovery = good.replace(
        "| Q14-19 | öffentliches Operator-Kommando | DECIDED |",
        "| Q14-19 | öffentliches Operator-Kommando | OPEN |",
        1,
    )
    _reject(recovery, "Q14-19")
    invented = good.replace(
        "| Q02-14 | fachlicher Abnehmer | OPEN |",
        "| Q02-14 | fachlicher Abnehmer | DECIDED |",
        1,
    )
    _reject(invented, "Q02-14")
    password_manager = good.replace("kein Passwortmanager unterstellt", "Passwortmanager ist Pflicht", 1)
    _reject(password_manager, "password manager")
    reopened_ux = good.replace(
        "| Q26-03 | UX-D37 „Unbekannter Autor“ wird für den begrenzten Pilot akzeptiert. | DECIDED | NOT RUN | E/H-HUMAN | — |",
        "| Q26-03 | UX-D37 „Unbekannter Autor“ wird für den begrenzten Pilot akzeptiert. | OPEN | NOT RUN | E/H-HUMAN | erneut offen |",
        1,
    )
    _reject(reopened_ux, "UX-D37")
    reopened_access = good.replace(
        "| Q27-01 | repräsentativer Accessibility-/Screenreader-Smoke soll eingeschlossen werden. | DECIDED |",
        "| Q27-01 | repräsentativer Accessibility-/Screenreader-Smoke soll eingeschlossen werden. | OPEN |",
        1,
    )
    _reject(reopened_access, "Q27-01")
    backup_drill = good.replace(
        "| Q13-19 | manueller Backup-Drill | DECIDED |",
        "| Q13-19 | manueller Backup-Drill | OPEN |",
        1,
    )
    _reject(backup_drill, "Q13-19")
    restore_time = good.replace(
        "| Q14-12 | gemessene Restorezeit | DECIDED |",
        "| Q14-12 | gemessene Restorezeit | OPEN |",
        1,
    )
    _reject(restore_time, "Q14-12")
    runbook = good.replace(
        "| Q14-16 | Notfallhandbuch | DECIDED |",
        "| Q14-16 | Notfallhandbuch | OPEN |",
        1,
    )
    _reject(runbook, "Q14-16")
    update_time = good.replace(
        "| Q15-16 | Updatezeit | DECIDED |",
        "| Q15-16 | Updatezeit | OPEN |",
        1,
    )
    _reject(update_time, "Q15-16")
    rollback_time = good.replace(
        "| Q15-17 | Rollbackzeit | DECIDED |",
        "| Q15-17 | Rollbackzeit | OPEN |",
        1,
    )
    _reject(rollback_time, "Q15-17")
    doctor = good.replace(
        "| Q17-10 | `doctor --strict` erfolgreich | DECIDED |",
        "| Q17-10 | `doctor --strict` erfolgreich | OPEN |",
        1,
    )
    _reject(doctor, "Q17-10")
    dropped_block = good.replace("## Entscheidungsblock 2 — Zielbetrieb", "## Zielbetrieb ohne Block", 1)
    _reject(dropped_block, "Entscheidungsblock 2")
    authorized = good.replace(
        "Status dieses Auftrags: `NICHT AUTORISIERT`.",
        "Status dieses Auftrags: `AUTORISIERT`.",
        1,
    )
    _reject(authorized, "unauthorized")
