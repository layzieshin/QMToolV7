from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

ROOT = Path(__file__).resolve().parents[1]

# --- Single executable allowlist (J00 inventory IDs) -----------------

# J01, J02, J03 — source-controlled domain JSON/JSONL under scan roots
ALLOWED_DOMAIN_JSON_FILES: frozenset[str] = frozenset(
    {
        "license/license.json",  # J01
        "qm_platform/persistence/migration_manifest.json",  # J02
        "modules/documents/workflow_profiles.json",  # J03
    }
)

# J20–J41 — table.column for inventoried *_json schema columns
ALLOWED_JSON_COLUMNS: frozenset[str] = frozenset(
    {
        "document_headers.distribution_roles_json",  # J20
        "document_headers.distribution_sites_json",  # J21
        "document_headers.distribution_departments_json",  # J22
        "document_versions.workflow_profile_json",  # J23
        "document_versions.editors_json",  # J24
        "document_versions.reviewers_json",  # J25
        "document_versions.approvers_json",  # J26
        "document_versions.reviewed_by_json",  # J27
        "document_versions.approved_by_json",  # J28
        "document_versions.custom_fields_json",  # J29–J31
        "document_artifacts.metadata_json",  # J32
        "document_workflow_comments.anchor_json",  # J33
        "workflow_profile_imports.report_json",  # J44 — J03 import evidence report
        "incidents.labels_json",  # J34
        "incident_timeline.details_json",  # J35
        "incident_artifacts.metadata_json",  # J36
        "training_quiz_attempts.selected_question_ids_json",  # J37
        "training_quiz_attempts.presented_questions_json",  # J38
        "training_quiz_attempts.answers_json",  # J39
        "training_comments.anchor_json",  # J40
        "training_audit_log.details_json",  # J41
        # J02 TARGET platform settings typed JSON cells (module_global only)
        "platform_settings.value_json",
        "platform_setting_revisions.old_value_json",
        "platform_setting_revisions.new_value_json",
        "audit_events.details_json",  # AP-029 PG00-C platform audit contract
    }
)

# Inventoried snapshot JSON columns without schema_version today
LEGACY_UNVERSIONED_SNAPSHOT_COLUMNS: frozenset[str] = frozenset(
    {
        "document_versions.workflow_profile_json",  # J23
    }
)

# Exact storage/*.json(l) path literals allowed in production sources (J04–J12)
ALLOWED_STORAGE_WRITE_PATHS: frozenset[str] = frozenset(
    {
        "storage/platform/session/current_user.json",  # J07
        "storage/platform/database-migration-journal.json",  # J08
        "storage/platform/backups/logs/_state.json",  # J10
    }
)

# Narrow file-scoped basename allows for inventory backup manifests (J09)
# Not a storage/** wildcard: only these production files may write this basename.
ALLOWED_STORAGE_BASENAME_WRITES_BY_FILE: dict[str, frozenset[str]] = {
    "qm_platform/persistence/database_evolution.py": frozenset({"manifest.json"}),
}

# Exact storage path literals allowed only in named cutover/import owners (read + archive).
ALLOWED_STORAGE_EXACT_PATHS_BY_FILE: dict[str, frozenset[str]] = {
    "qm_platform/settings/settings_cutover.py": frozenset(
        {
            "storage/platform/settings.json",
            "storage/platform/settings_cutover_journal.json",
        }
    ),
    "qm_platform/settings/residual_store.py": frozenset(
        {
            "storage/platform/settings_residual_archive/settings.json",
            "storage/platform/settings_residual_archive/settings.json.sha256",
        }
    ),
}

DOMAIN_SCAN_ROOTS = ("modules/", "qm_platform/", "license/")
SQL_SCAN_SUFFIXES = (".sql",)
JSON_SUFFIXES = (".json", ".jsonl")
PROD_PY_ROOTS = ("modules/", "qm_platform/", "interfaces/", "src/", "scripts/")


@dataclass
class Finding:
    kind: str
    path: str
    detail: str
    classification: str  # new_unregistered | unregistered_existing | gate_error

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "path": self.path,
            "detail": self.detail,
            "classification": self.classification,
        }


@dataclass
class _GateError(Exception):
    message: str


@dataclass
class _EvalState:
    findings: list[Finding] = field(default_factory=list)
    existing_allowed_files: list[str] = field(default_factory=list)
    existing_allowed_columns: list[str] = field(default_factory=list)
    new_unregistered: list[str] = field(default_factory=list)
    baseline_delta: list[str] = field(default_factory=list)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _is_under_roots(path: str, roots: tuple[str, ...]) -> bool:
    return any(_norm(path).startswith(root) for root in roots)


def _git_run(root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise _GateError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{(result.stderr or result.stdout).strip()}"
        )
    return result.stdout


def _git_lines(root: Path, args: list[str]) -> list[str]:
    return [line.strip() for line in _git_run(root, args).splitlines() if line.strip()]


def _list_current_paths(root: Path) -> set[str]:
    """Index + untracked only — never HEAD (staged deletions must disappear)."""
    paths: set[str] = set()
    paths.update(_norm(p) for p in _git_lines(root, ["ls-files", "--cached"]))
    paths.update(
        _norm(p) for p in _git_lines(root, ["ls-files", "--others", "--exclude-standard"])
    )
    return paths


def _list_baseline_paths(root: Path, *, base_ref: str) -> set[str]:
    return {_norm(p) for p in _git_lines(root, ["ls-tree", "-r", "--name-only", base_ref])}


def _read_current_text(root: Path, rel: str) -> str:
    """Read working tree or index blob — no HEAD fallback."""
    rel = _norm(rel)
    disk = root / rel
    if disk.is_file():
        return disk.read_text(encoding="utf-8")
    staged = subprocess.run(
        ["git", "show", f":{rel}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if staged.returncode == 0 and staged.stdout:
        return staged.stdout.decode("utf-8", errors="replace")
    raise _GateError(f"unable to read current index/worktree content for {rel}")


def _read_baseline_text(root: Path, base_ref: str, rel: str) -> str:
    """Read baseline exclusively via git show <base-ref>:<path>."""
    rel = _norm(rel)
    shown = subprocess.run(
        ["git", "show", f"{base_ref}:{rel}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if shown.returncode == 0:
        return shown.stdout.decode("utf-8", errors="replace")
    raise _GateError(f"unable to read baseline {base_ref}:{rel}")


def _is_staged_deletion(root: Path, rel: str) -> bool:
    """True when path exists in HEAD/base but is absent from the index."""
    rel = _norm(rel)
    cached = subprocess.run(
        ["git", "ls-files", "--cached", "--", rel],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if cached.returncode != 0:
        raise _GateError(f"git ls-files --cached failed for {rel}")
    if cached.stdout.strip():
        return False
    head = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{rel}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return head.returncode == 0


def _strip_sql_comments(sql: str) -> str:
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        if sql.startswith("--", i):
            while i < n and sql[i] != "\n":
                i += 1
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            if end < 0:
                raise _GateError("unclosed SQL block comment")
            i = end + 2
            continue
        ch = sql[i]
        if ch in "'\"":
            quote = ch
            out.append(ch)
            i += 1
            closed = False
            while i < n:
                if sql[i] == quote:
                    out.append(sql[i])
                    i += 1
                    if i < n and sql[i] == quote:
                        out.append(sql[i])
                        i += 1
                        continue
                    closed = True
                    break
                out.append(sql[i])
                i += 1
            if not closed:
                raise _GateError("unclosed SQL string literal")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_sql_statements(sql: str) -> list[str]:
    cleaned = _strip_sql_comments(sql)
    statements: list[str] = []
    buf: list[str] = []
    depth = 0
    in_quote: str | None = None
    i = 0
    while i < len(cleaned):
        ch = cleaned[i]
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                if i + 1 < len(cleaned) and cleaned[i + 1] == in_quote:
                    buf.append(cleaned[i + 1])
                    i += 2
                    continue
                in_quote = None
            i += 1
            continue
        if ch in "'\"":
            in_quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if ch == ";" and depth == 0:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _split_columns(body: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_quote: str | None = None
    for ch in body:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
            continue
        if ch in "'\"":
            in_quote = ch
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


_IDENT = r"(?:\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|\w+)"
_QUALIFIED_NAME = rf"(?:{_IDENT}\s*\.\s*)*{_IDENT}"

_CREATE_RE = re.compile(
    rf"create\s+table\s+(?:if\s+not\s+exists\s+)?(?P<name>{_QUALIFIED_NAME})",
    re.IGNORECASE,
)
_ALTER_ADD_RE = re.compile(
    rf"alter\s+table\s+(?P<name>{_QUALIFIED_NAME})\s+"
    rf"add(?:\s+column)?(?:\s+if\s+not\s+exists)?\s+(?P<col>{_IDENT})",
    re.IGNORECASE,
)


def _unquote_ident(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"`[]":
        return raw[1:-1]
    return raw


def _table_name_from_sql(raw: str) -> str:
    """Return unqualified table name (last component of schema.table)."""
    parts = re.split(r"\s*\.\s*", raw.strip())
    return _unquote_ident(parts[-1]).lower()


def _column_name_from_def(definition: str) -> str | None:
    token = definition.strip()
    if not token:
        return None
    upper = token.upper()
    if upper.startswith(("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN")):
        return None
    match = re.match(rf"^({_IDENT})", token)
    if not match:
        return None
    return _unquote_ident(match.group(1))


def apply_sql_to_table_state(sql: str, tables: dict[str, set[str]]) -> None:
    for statement in _split_sql_statements(sql):
        create = _CREATE_RE.match(statement)
        if create:
            start = statement.find("(")
            end = statement.rfind(")")
            if start < 0 or end <= start:
                raise _GateError(
                    f"unparseable CREATE TABLE statement: {statement[:120]}"
                )
            table = _table_name_from_sql(create.group("name"))
            body = statement[start + 1 : end]
            cols = {
                name.lower()
                for part in _split_columns(body)
                if (name := _column_name_from_def(part)) is not None
            }
            tables[table] = set(cols)
            continue
        if re.match(r"create\s+table\b", statement, re.IGNORECASE):
            raise _GateError(f"unparseable CREATE TABLE statement: {statement[:120]}")
        alter = _ALTER_ADD_RE.match(statement)
        if alter:
            table = _table_name_from_sql(alter.group("name"))
            col = _unquote_ident(alter.group("col")).lower()
            tables.setdefault(table, set()).add(col)
            continue
        if re.match(r"alter\s+table\b", statement, re.IGNORECASE) and re.search(
            r"\badd\b", statement, re.IGNORECASE
        ):
            raise _GateError(
                f"unparseable ALTER TABLE ADD statement: {statement[:120]}"
            )


def _is_snapshot_json_column(column: str) -> bool:
    lowered = column.lower()
    return lowered.endswith("_json") and "snapshot" in lowered


def _expected_schema_version_column(json_column: str) -> str:
    if json_column.lower().endswith("_json"):
        return json_column[: -len("_json")] + "_schema_version"
    return json_column + "_schema_version"


def _migration_groups(paths: set[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for path in sorted(paths):
        if not path.endswith(".sql"):
            continue
        if "/migrations/" not in path:
            continue
        if not (
            path.startswith("modules/")
            or path.startswith("qm_platform/")
        ):
            continue
        # group by directory containing the sql files
        group = path.rsplit("/", 1)[0]
        groups[group].append(path)
    for group, items in groups.items():
        items.sort()
    return dict(groups)


def _classify(path: str, baseline: set[str] | None) -> str:
    if baseline is None:
        return "new_unregistered"
    if path in baseline:
        return "unregistered_existing"
    return "new_unregistered"


def _check_domain_files(
    state: _EvalState,
    files: Mapping[str, str],
    *,
    baseline: set[str] | None,
) -> None:
    for path in sorted(files):
        if not _is_under_roots(path, DOMAIN_SCAN_ROOTS):
            continue
        if not path.lower().endswith(JSON_SUFFIXES):
            continue
        if path in ALLOWED_DOMAIN_JSON_FILES:
            state.existing_allowed_files.append(path)
            continue
        classification = _classify(path, baseline)
        state.findings.append(
            Finding(
                kind="unregistered_domain_json_file",
                path=path,
                detail="JSON/JSONL file not in ALLOWED_DOMAIN_JSON_FILES",
                classification=classification,
            )
        )
        if classification == "new_unregistered":
            state.new_unregistered.append(path)
            state.baseline_delta.append(f"file:{path}")


def _check_sql_columns(
    state: _EvalState,
    files: Mapping[str, str],
    *,
    baseline_columns: set[str] | None,
) -> None:
    sql_paths = {p for p in files if p.endswith(".sql") and "/migrations/" in p}
    groups = _migration_groups(sql_paths)
    for _group, ordered in groups.items():
        tables: dict[str, set[str]] = {}
        parse_failed = False
        for path in ordered:
            try:
                apply_sql_to_table_state(files[path], tables)
            except _GateError as exc:
                state.findings.append(
                    Finding(
                        kind="gate_error",
                        path=path,
                        detail=exc.message,
                        classification="gate_error",
                    )
                )
                parse_failed = True
                break
        if parse_failed:
            continue
        for table, columns in tables.items():
            for column in sorted(columns):
                if not column.endswith("_json"):
                    continue
                key = f"{table}.{column}"
                if key in ALLOWED_JSON_COLUMNS:
                    state.existing_allowed_columns.append(key)
                else:
                    classification = (
                        "unregistered_existing"
                        if baseline_columns is not None and key in baseline_columns
                        else "new_unregistered"
                    )
                    state.findings.append(
                        Finding(
                            kind="unregistered_json_column",
                            path=key,
                            detail=f"column from migrations group {_group}",
                            classification=classification,
                        )
                    )
                    if classification == "new_unregistered":
                        state.new_unregistered.append(key)
                        state.baseline_delta.append(f"column:{key}")
                if _is_snapshot_json_column(column) or key in LEGACY_UNVERSIONED_SNAPSHOT_COLUMNS:
                    if key in LEGACY_UNVERSIONED_SNAPSHOT_COLUMNS:
                        continue
                    expected = _expected_schema_version_column(column)
                    if expected not in columns and not any(
                        c.endswith("_schema_version") and c == expected for c in columns
                    ):
                        if expected not in columns:
                            state.findings.append(
                                Finding(
                                    kind="unversioned_snapshot_json_column",
                                    path=key,
                                    detail=(
                                        f"snapshot JSON column lacks companion "
                                        f"{expected} in accumulated table state"
                                    ),
                                    classification="new_unregistered",
                                )
                            )
                            state.new_unregistered.append(f"snapshot:{key}")


def _path_call_constant(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    is_path = (isinstance(func, ast.Name) and func.id == "Path") or (
        isinstance(func, ast.Attribute) and func.attr == "Path"
    )
    if not is_path or not node.args:
        return None
    arg0 = node.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return arg0.value.replace("\\", "/")
    return None


def _operand_storage_info(node: ast.AST) -> tuple[str | None, bool, bool]:
    """Return (constant_text_or_none, is_dynamic, looks_json_suffix)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value.replace("\\", "/")
        return text, False, text.endswith(JSON_SUFFIXES) or text.endswith((".json", ".jsonl"))
    path_const = _path_call_constant(node)
    if path_const is not None:
        return (
            path_const,
            False,
            path_const.endswith(JSON_SUFFIXES),
        )
    if isinstance(node, ast.JoinedStr):
        rendered: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                rendered.append(value.value)
            else:
                rendered.append("{}")
        text = "".join(rendered).replace("\\", "/")
        looks_json = ".json" in text or ".jsonl" in text
        return text, True, looks_json
    return None, True, False


def _flatten_div_operands(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _flatten_div_operands(node.left) + _flatten_div_operands(node.right)
    return [node]


def _extract_storage_writes(rel_path: str, source: str) -> list[tuple[str, str]]:
    """Return list of (path_or_marker, kind) where kind is exact|dynamic|basename."""
    results: list[tuple[str, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise _GateError(
            f"python syntax error while scanning {rel_path}: {exc.msg}"
        ) from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.replace("\\", "/")
            if "storage/" in value and value.endswith(JSON_SUFFIXES):
                results.append((value[value.find("storage/") :], "exact"))

    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            rendered: list[str] = []
            dynamic = False
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    rendered.append(value.value)
                else:
                    dynamic = True
                    rendered.append("{}")
            text_value = "".join(rendered).replace("\\", "/")
            if "storage/" in text_value and (".json" in text_value or ".jsonl" in text_value):
                results.append((text_value, "dynamic" if dynamic else "exact"))

    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        operands = _flatten_div_operands(node)
        infos = [_operand_storage_info(op) for op in operands]
        touches_storage = any(
            text is not None
            and (text == "storage" or text.startswith("storage/") or "storage/" in text)
            for text, _dyn, _json in infos
        )
        looks_json = any(is_json for _text, _dyn, is_json in infos)

        # Exact allowlisted path as a single constant segment: app_home / "storage/platform/x.json"
        for text, dyn, is_json in infos:
            if (
                not dyn
                and text is not None
                and text.startswith("storage/")
                and text.endswith(JSON_SUFFIXES)
            ):
                results.append((text, "exact"))
                touches_storage = True
                looks_json = True

        if not touches_storage:
            any_dynamic = any(dyn for _text, dyn, _json in infos)
            if (
                len(operands) >= 2
                and any_dynamic
                and isinstance(operands[-1], ast.Constant)
                and isinstance(operands[-1].value, str)
            ):
                basename = str(operands[-1].value).replace("\\", "/")
                if basename.endswith(JSON_SUFFIXES) and "/" not in basename:
                    allowed = ALLOWED_STORAGE_BASENAME_WRITES_BY_FILE.get(rel_path, frozenset())
                    if basename in allowed:
                        results.append((f"{rel_path}::{basename}", "basename"))
            continue

        if not looks_json:
            continue

        # Drop leading non-storage dynamic prefixes (e.g. app_home), then require the
        # storage-relative suffix to be fully constant for an exact path.
        start = 0
        while start < len(infos):
            text, dyn, _is_json = infos[start]
            if text is not None and (
                text == "storage" or text.startswith("storage/") or "storage/" in text
            ):
                break
            if dyn and (text is None or not text.startswith("storage")):
                start += 1
                continue
            break
        suffix = infos[start:]
        if not suffix:
            continue
        suffix_dynamic = any(dyn for _text, dyn, _json in suffix)
        const_parts = [text for text, dyn, _json in suffix if text is not None and not dyn]
        joined = "/".join(part.strip("/") for part in const_parts if part)
        storage_path = None
        if "storage/" in joined:
            storage_path = joined[joined.find("storage/") :]
        elif const_parts and const_parts[0] == "storage":
            storage_path = "storage/" + "/".join(p.strip("/") for p in const_parts[1:])

        if suffix_dynamic:
            results.append((storage_path or f"dynamic:{rel_path}", "dynamic"))
            continue

        if storage_path and storage_path.endswith(JSON_SUFFIXES):
            results.append((storage_path, "exact"))

    return results


def _check_storage_writes(
    state: _EvalState,
    files: Mapping[str, str],
) -> None:
    for path in sorted(files):
        if not path.endswith(".py"):
            continue
        if not _is_under_roots(path, PROD_PY_ROOTS):
            continue
        if path.startswith("scripts/") and path.endswith("json_persistence_gate.py"):
            continue
        try:
            writes = _extract_storage_writes(path, files[path])
        except _GateError as exc:
            state.findings.append(
                Finding(
                    kind="gate_error",
                    path=path,
                    detail=exc.message,
                    classification="gate_error",
                )
            )
            continue
        for target, kind in writes:
            if kind == "exact":
                if target in ALLOWED_STORAGE_WRITE_PATHS:
                    continue
                if target in ALLOWED_STORAGE_EXACT_PATHS_BY_FILE.get(path, frozenset()):
                    continue
                state.findings.append(
                    Finding(
                        kind="unregistered_storage_json_write",
                        path=path,
                        detail=f"exact storage path not catalogued: {target}",
                        classification="new_unregistered",
                    )
                )
                state.new_unregistered.append(target)
            elif kind == "basename":
                continue
            else:
                state.findings.append(
                    Finding(
                        kind="dynamic_storage_json_write",
                        path=path,
                        detail=f"dynamic storage JSON/JSONL path construction: {target}",
                        classification="new_unregistered",
                    )
                )
                state.new_unregistered.append(target)


def _baseline_column_keys(files: Mapping[str, str]) -> set[str]:
    keys: set[str] = set()
    for _group, ordered in _migration_groups(set(files)).items():
        tables: dict[str, set[str]] = {}
        for path in ordered:
            try:
                apply_sql_to_table_state(files[path], tables)
            except _GateError as exc:
                raise _GateError(f"{path}: {exc.message}") from exc
        for table, columns in tables.items():
            for column in columns:
                if column.endswith("_json"):
                    keys.add(f"{table}.{column}")
    return keys


def _load_scratch_files(source_files: Mapping[str, str | bytes]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_path, content in source_files.items():
        path = _norm(str(raw_path))
        if isinstance(content, bytes):
            out[path] = content.decode("utf-8", errors="replace")
        else:
            out[path] = str(content)
    return out


def _load_repo_files(root: Path, paths: set[str]) -> dict[str, str]:
    wanted = {
        p
        for p in paths
        if (
            (
                _is_under_roots(p, DOMAIN_SCAN_ROOTS)
                and p.lower().endswith(JSON_SUFFIXES)
            )
            or (p.endswith(".sql") and "/migrations/" in p)
            or (
                p.endswith(".py")
                and _is_under_roots(p, PROD_PY_ROOTS)
            )
        )
    }
    return {p: _read_current_text(root, p) for p in sorted(wanted)}


def evaluate_json_persistence_gate(
    root: Path | str = ROOT,
    *,
    mode: Literal["repo", "scratch"],
    base_ref: str | None = None,
    source_files: Mapping[str, str | bytes] | None = None,
) -> dict[str, object]:
    root_path = Path(root)
    state = _EvalState()
    diagnostics: dict[str, object] = {}

    try:
        if mode == "scratch":
            if source_files is None:
                raise _GateError("scratch mode requires source_files")
            files = _load_scratch_files(source_files)
            baseline_files: set[str] | None = None
            baseline_columns: set[str] | None = None
        elif mode == "repo":
            if source_files is not None:
                raise _GateError("repo mode must not receive source_files")
            ref = base_ref or "HEAD"
            current_paths = _list_current_paths(root_path)
            baseline_paths = _list_baseline_paths(root_path, base_ref=ref)
            files = _load_repo_files(root_path, current_paths)
            baseline_file_subset = {
                p
                for p in baseline_paths
                if _is_under_roots(p, DOMAIN_SCAN_ROOTS) and p.lower().endswith(JSON_SUFFIXES)
            }
            baseline_files = baseline_file_subset
            baseline_sql_contents: dict[str, str] = {}
            for p in sorted(baseline_paths):
                if not (p.endswith(".sql") and "/migrations/" in p):
                    continue
                baseline_sql_contents[p] = _read_baseline_text(root_path, ref, p)
            baseline_columns = _baseline_column_keys(baseline_sql_contents)
            diagnostics["base_ref"] = ref
            diagnostics["scanned_path_count"] = len(current_paths)
        else:
            raise _GateError(f"unknown mode: {mode}")

        _check_domain_files(state, files, baseline=baseline_files)
        _check_sql_columns(state, files, baseline_columns=baseline_columns)
        _check_storage_writes(state, files)

        if mode == "repo":
            # Allowlist liveness against current index/worktree only (no HEAD fallback).
            dead_files: list[str] = []
            staged_deletions: list[str] = []
            for allowed in sorted(ALLOWED_DOMAIN_JSON_FILES):
                if allowed in files:
                    continue
                if _is_staged_deletion(root_path, allowed):
                    staged_deletions.append(allowed)
                    state.findings.append(
                        Finding(
                            kind="staged_allowlist_deletion",
                            path=allowed,
                            detail="allowlist file staged for deletion (absent from index)",
                            classification="gate_error",
                        )
                    )
                else:
                    dead_files.append(allowed)
                    state.findings.append(
                        Finding(
                            kind="dead_allowlist_file",
                            path=allowed,
                            detail="allowlist file missing from current index/worktree",
                            classification="gate_error",
                        )
                    )
            diagnostics["staged_allowlist_deletions"] = staged_deletions
            diagnostics["dead_allowlist_files"] = dead_files

            found_columns = _baseline_column_keys(files)
            dead_columns = sorted(ALLOWED_JSON_COLUMNS - found_columns)
            for key in dead_columns:
                state.findings.append(
                    Finding(
                        kind="dead_allowlist_column",
                        path=key,
                        detail="allowlist column not present in current migration chain",
                        classification="gate_error",
                    )
                )

    except _GateError as exc:
        state.findings.append(
            Finding(
                kind="gate_error",
                path=str(root_path),
                detail=exc.message,
                classification="gate_error",
            )
        )

    ok = not state.findings
    diagnostics["new_unregistered"] = sorted(set(state.new_unregistered))
    diagnostics["existing_allowed_files"] = sorted(set(state.existing_allowed_files))
    diagnostics["existing_allowed_columns"] = sorted(set(state.existing_allowed_columns))
    diagnostics["baseline_delta"] = sorted(set(state.baseline_delta))
    diagnostics["findings"] = [f.as_dict() for f in state.findings]

    return {
        "ok": ok,
        "checks": {
            "no_unregistered_json_persistence": ok,
        },
        "findings": [f.as_dict() for f in state.findings],
        "diagnostics": diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JSON/JSONL persistence allowlist gate")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--mode", choices=("repo", "scratch"), default="repo")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.mode == "scratch":
        payload = {
            "ok": False,
            "checks": {"no_unregistered_json_persistence": False},
            "findings": [
                {
                    "kind": "gate_error",
                    "path": ".",
                    "detail": "CLI scratch mode requires programmatic source_files",
                    "classification": "gate_error",
                }
            ],
            "diagnostics": {},
        }
    else:
        payload = evaluate_json_persistence_gate(
            args.root, mode="repo", base_ref=args.base_ref
        )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if bool(payload["ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
