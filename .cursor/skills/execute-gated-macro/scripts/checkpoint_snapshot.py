from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


def _git(root: Path, *args: str, allow_missing_ref: bool = False) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode == 0:
        return completed.stdout.strip()
    if allow_missing_ref:
        return None
    message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
    raise RuntimeError(f"git {' '.join(args)}: {message}")


def _paths(root: Path, *args: str) -> set[str]:
    output = _git(root, *args) or ""
    return {PurePosixPath(line.strip()).as_posix() for line in output.splitlines() if line.strip()}


def _paths_strict(root: Path, *args: str) -> set[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise RuntimeError(f"git {' '.join(args)}: {message}")
    return {PurePosixPath(line.strip()).as_posix() for line in completed.stdout.splitlines() if line.strip()}


def _matches(path: str, rules: tuple[str, ...]) -> bool:
    normalized = PurePosixPath(path).as_posix()
    for raw in rules:
        rule = PurePosixPath(raw.rstrip("/")).as_posix()
        if normalized == rule or normalized.startswith(f"{rule}/"):
            return True
    return False


def _matches_exact(path: str, rules: tuple[str, ...]) -> bool:
    normalized = PurePosixPath(path).as_posix()
    rule_set = {PurePosixPath(raw.rstrip("/")).as_posix() for raw in rules}
    return normalized in rule_set


def _foreign_child_denials(changed: set[str], foreign: tuple[str, ...]) -> list[str]:
    reasons: list[str] = []
    for path in sorted(changed):
        normalized = PurePosixPath(path).as_posix()
        for raw in foreign:
            rule = PurePosixPath(raw.rstrip("/")).as_posix()
            if normalized != rule and normalized.startswith(f"{rule}/"):
                reasons.append(f"foreign_child_denied:{normalized}")
    return reasons


def _verify_base_commit(root: Path, base_ref: str) -> str | None:
    return _git(
        root,
        "rev-parse",
        "--verify",
        f"{base_ref}^{{commit}}",
        allow_missing_ref=True,
    )


def _resolve_base_sha(root: Path, base_ref: str) -> str:
    base_sha = _verify_base_commit(root, base_ref)
    if not base_sha:
        raise RuntimeError(f"missing base ref: {base_ref}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_sha, "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestor.returncode == 1:
        raise RuntimeError(f"base ref is not an ancestor of HEAD: {base_ref}")
    if ancestor.returncode != 0:
        raise RuntimeError(f"git merge-base failed for base ref: {base_ref}")
    return base_sha


def _committed_paths(root: Path, base_ref: str) -> set[str]:
    _resolve_base_sha(root, base_ref)
    output = _git(root, "diff", "--name-status", base_ref, "HEAD") or ""
    paths: set[str] = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0]
        if code.startswith("R") and len(parts) >= 3:
            paths.add(PurePosixPath(parts[1].strip()).as_posix())
            paths.add(PurePosixPath(parts[2].strip()).as_posix())
        elif len(parts) >= 2:
            paths.add(PurePosixPath(parts[1].strip()).as_posix())
    return paths


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _normalize_verification_command(command: str) -> str:
    return " ".join(command.strip().split())


def _content_fingerprint(
    root: Path,
    paths: set[str],
    *,
    staged: set[str],
    unstaged: set[str],
    untracked: set[str],
    head: str | None,
) -> tuple[str, list[dict[str, object]]]:
    digest = hashlib.sha256()
    digest.update((head or "<no-head>").encode("utf-8"))
    digest.update(b"\0")
    records: list[dict[str, object]] = []
    for relative in sorted(paths):
        path = root / Path(relative)
        index_entry = _git(root, "ls-files", "--stage", "--", relative) or None
        record: dict[str, object] = {
            "path": relative,
            "staged": relative in staged,
            "unstaged": relative in unstaged,
            "untracked": relative in untracked,
            "index_entry": index_entry,
        }
        if not path.exists():
            record.update({"state": "deleted", "sha256": None, "size": 0, "mode": None})
        elif not path.is_file():
            record.update({"state": "non-file", "sha256": None, "size": 0, "mode": None})
        else:
            content = path.read_bytes()
            record.update(
                {
                    "state": "present",
                    "sha256": _sha256_bytes(content),
                    "size": len(content),
                    "mode": path.stat().st_mode & 0o777,
                }
            )
        digest.update(json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\0")
        records.append(record)
    return digest.hexdigest(), records


def _resolve_repo_root(root: Path) -> Path:
    root = root.resolve()
    actual_root = Path(_git(root, "rev-parse", "--show-toplevel") or "").resolve()
    if actual_root != root:
        raise RuntimeError(f"root must be repository root: expected {actual_root}, got {root}")
    return root


def _output_path(root: Path, raw: str) -> Path:
    relative = PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("output must be a relative path below build/")
    if relative.parts[0] != "build":
        raise ValueError("output must be below build/")
    output = root.joinpath(*relative.parts).resolve()
    build_root = (root / "build").resolve()
    if build_root != output and build_root not in output.parents:
        raise ValueError("output escapes build/")
    return output


def _manifest_path(root: Path, raw: str) -> Path:
    return _output_path(root, raw)


def _owner_hashes(root: Path, allowlist: tuple[str, ...]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in sorted(allowlist):
        path = root / Path(relative)
        if not path.is_file():
            raise RuntimeError(f"allowlisted owner is missing or not a file: {relative}")
        hashes[PurePosixPath(relative).as_posix()] = _sha256_file(path)
    return hashes


def _load_profile(root: Path, profile_path: str) -> tuple[str, int, str]:
    relative = PurePosixPath(profile_path).as_posix()
    path = root / Path(relative)
    if not path.is_file():
        raise RuntimeError(f"profile path is missing: {relative}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    slug = str(payload.get("profile") or "")
    version = payload.get("version")
    if not slug or not isinstance(version, int):
        raise RuntimeError("profile JSON must contain profile slug and integer version")
    return slug, version, _sha256_file(path)


def _declared_foreign_binding_records(root: Path, profile_path: str) -> list[dict[str, object]]:
    relative = PurePosixPath(profile_path).as_posix()
    profile_file = root / Path(relative)
    payload = json.loads(profile_file.read_text(encoding="utf-8"))
    bindings = payload.get("external_codex_bound_review", {}).get("declared_foreign_bindings") or []
    records: list[dict[str, object]] = []
    for binding in bindings:
        foreign_path = PurePosixPath(str(binding["path"])).as_posix()
        disk_path = root / Path(foreign_path)
        index_entry = _git(root, "ls-files", "--stage", "--", foreign_path) or None
        if index_entry is not None and not index_entry.strip():
            index_entry = None
        index_state = "indexed" if index_entry else "untracked"
        if not disk_path.is_file():
            raise RuntimeError(f"foreign binding missing on disk: {foreign_path}")
        content = disk_path.read_bytes()
        size = len(content)
        sha256 = _sha256_bytes(content)
        configured_size = int(binding["size"])
        configured_sha256 = str(binding["sha256"]).lower()
        if size != configured_size:
            raise RuntimeError(f"foreign binding size mismatch: {foreign_path}")
        if sha256 != configured_sha256:
            raise RuntimeError(f"foreign binding hash mismatch: {foreign_path}")
        records.append(
            {
                "path": foreign_path,
                "size": size,
                "sha256": sha256,
                "index_state": index_state,
                "index_entry": index_entry,
            }
        )
    return sorted(records, key=lambda item: str(item["path"]))


def _manifest_includes_foreign_bindings(package_id: str, checkpoint_id: str) -> bool:
    return package_id == "AGENT-COST-01" and checkpoint_id == "FINAL_AUDIT"


def build_snapshot(
    *,
    root: Path,
    checkpoint: str,
    phase: str,
    allowlist: tuple[str, ...],
    foreign: tuple[str, ...],
    base_ref: str,
    scope_mode: str = "dirty",
) -> dict[str, object]:
    root = _resolve_repo_root(root)

    if scope_mode == "committed_final_audit":
        path_reader = _paths_strict
    else:
        path_reader = _paths

    staged = path_reader(root, "diff", "--cached", "--name-only")
    unstaged = path_reader(root, "diff", "--name-only")
    untracked = path_reader(root, "ls-files", "--others", "--exclude-standard")
    head = _git(root, "rev-parse", "HEAD")
    allow_paths = {PurePosixPath(path).as_posix() for path in allowlist}
    denial_reasons: list[str] = []
    committed: set[str] = set()
    base_sha: str | None

    if scope_mode == "committed_final_audit":
        try:
            base_sha = _resolve_base_sha(root, base_ref)
            committed = _committed_paths(root, base_ref)
        except RuntimeError as exc:
            verified_base_sha = _verify_base_commit(root, base_ref)
            error_text = str(exc)
            if verified_base_sha and "not an ancestor" in error_text:
                payload_base_sha: str | None = verified_base_sha
            else:
                payload_base_sha = verified_base_sha
            return {
                "schema_version": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "checkpoint": checkpoint,
                "phase": phase,
                "scope_mode": scope_mode,
                "repository_root": str(root),
                "branch": _git(root, "branch", "--show-current") or "DETACHED",
                "head": head,
                "base_ref": base_ref,
                "base_sha": payload_base_sha,
                "allowlist": sorted(allowlist),
                "declared_foreign_rules": sorted(foreign),
                "staged_paths": sorted(staged),
                "unstaged_paths": sorted(unstaged),
                "untracked_paths": sorted(untracked),
                "allowed_changed_paths": [],
                "declared_foreign_paths": [],
                "out_of_scope_paths": [],
                "denial_reasons": [f"base_failure:{exc}"],
                "repository_state_sha256": "",
                "files": [],
                "committed_paths": [],
                "dirty_tracked_or_index_paths": [],
            }
        dirty_tracked = sorted((staged | unstaged) & allow_paths)
        if dirty_tracked:
            denial_reasons.append(
                "dirty_tracked_or_index:" + ",".join(dirty_tracked)
            )
        changed = staged | unstaged | untracked | committed
    else:
        base_sha = _git(root, "rev-parse", base_ref, allow_missing_ref=True)
        changed = staged | unstaged | untracked

    declared_foreign = (
        {path for path in changed if _matches_exact(path, foreign)}
        if scope_mode == "committed_final_audit"
        else {path for path in changed if _matches(path, foreign)}
    )
    permitted = (
        {path for path in changed if _matches_exact(path, allowlist)}
        if scope_mode == "committed_final_audit"
        else {path for path in changed if _matches(path, allowlist)}
    )
    out_of_scope = changed - permitted - declared_foreign
    if scope_mode == "committed_final_audit":
        denial_reasons.extend(_foreign_child_denials(changed, foreign))
    fingerprint, files = _content_fingerprint(
        root,
        changed,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        head=head,
    )

    payload: dict[str, object] = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "checkpoint": checkpoint,
        "phase": phase,
        "scope_mode": scope_mode,
        "repository_root": str(root),
        "branch": _git(root, "branch", "--show-current") or "DETACHED",
        "head": head,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "allowlist": sorted(allowlist),
        "declared_foreign_rules": sorted(foreign),
        "staged_paths": sorted(staged),
        "unstaged_paths": sorted(unstaged),
        "untracked_paths": sorted(untracked),
        "allowed_changed_paths": sorted(permitted),
        "declared_foreign_paths": sorted(declared_foreign),
        "out_of_scope_paths": sorted(out_of_scope),
        "denial_reasons": denial_reasons,
        "repository_state_sha256": fingerprint,
        "files": files,
    }
    if scope_mode == "committed_final_audit":
        payload["committed_paths"] = sorted(committed)
        payload["dirty_tracked_or_index_paths"] = sorted((staged | unstaged) & allow_paths)
    return payload


def _repository_fingerprint_for_allowlist(
    root: Path,
    allowlist: tuple[str, ...],
    *,
    head: str | None,
) -> str:
    staged = _paths(root, "diff", "--cached", "--name-only")
    unstaged = _paths(root, "diff", "--name-only")
    untracked = _paths(root, "ls-files", "--others", "--exclude-standard")
    allow_paths = {PurePosixPath(path).as_posix() for path in allowlist}
    fingerprint, _ = _content_fingerprint(
        root,
        allow_paths,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        head=head,
    )
    return fingerprint


def build_context_manifest(
    *,
    root: Path,
    package_id: str,
    checkpoint_id: str,
    contract_path: str,
    profile_path: str,
    allowlist: tuple[str, ...],
    verification_commands: tuple[str, ...],
    evidence_paths: dict[str, str],
    base_ref: str,
    foreign: tuple[str, ...] = (),
) -> dict[str, object]:
    root = _resolve_repo_root(root)
    contract_relative = PurePosixPath(contract_path).as_posix()
    contract_file = _manifest_path(root, contract_relative)
    if not contract_file.is_file():
        raise RuntimeError(f"contract path is missing: {contract_relative}")

    profile_slug, profile_version, profile_sha256 = _load_profile(root, profile_path)
    include_foreign_bindings = _manifest_includes_foreign_bindings(package_id, checkpoint_id)
    declared_foreign_bindings: list[dict[str, object]] = []
    if include_foreign_bindings:
        declared_foreign_bindings = _declared_foreign_binding_records(root, profile_path)
    owner_hashes = _owner_hashes(root, allowlist)
    normalized_commands = sorted({_normalize_verification_command(cmd) for cmd in verification_commands if cmd.strip()})
    if not normalized_commands:
        raise RuntimeError("at least one verification command is required")

    relative_evidence: dict[str, str] = {}
    evidence_sha256: dict[str, str | None] = {}
    for key, raw in sorted(evidence_paths.items()):
        relative = PurePosixPath(raw).as_posix()
        _manifest_path(root, relative)
        relative_evidence[key] = relative
        evidence_file = root / Path(relative)
        if evidence_file.is_file():
            evidence_sha256[key] = _sha256_file(evidence_file)
        else:
            evidence_sha256[key] = None

    head = _git(root, "rev-parse", "HEAD")
    base_sha = _git(root, "rev-parse", base_ref, allow_missing_ref=True)
    branch = _git(root, "branch", "--show-current") or "DETACHED"
    repository_fingerprint = _repository_fingerprint_for_allowlist(root, allowlist, head=head)

    binding_payload = {
        "package_id": package_id,
        "checkpoint_id": checkpoint_id,
        "branch": branch,
        "head": head,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "contract_path": contract_relative,
        "contract_sha256": _sha256_file(contract_file),
        "profile_path": PurePosixPath(profile_path).as_posix(),
        "profile_slug": profile_slug,
        "profile_version": profile_version,
        "profile_sha256": profile_sha256,
        "allowlist": sorted(allowlist),
        "owner_hashes": owner_hashes,
        "verification_commands": normalized_commands,
        "evidence_paths": relative_evidence,
        "evidence_sha256": evidence_sha256,
        "repository_state_sha256": repository_fingerprint,
    }
    if include_foreign_bindings:
        binding_payload["declared_foreign_bindings"] = declared_foreign_bindings
    reuse_key_sha256 = _sha256_bytes(
        json.dumps(binding_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )

    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        **binding_payload,
        "reuse_key_sha256": reuse_key_sha256,
    }


def _manifest_binding(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "package_id",
        "checkpoint_id",
        "branch",
        "head",
        "base_ref",
        "base_sha",
        "contract_path",
        "contract_sha256",
        "profile_path",
        "profile_slug",
        "profile_version",
        "profile_sha256",
        "allowlist",
        "owner_hashes",
        "verification_commands",
        "evidence_paths",
        "evidence_sha256",
        "repository_state_sha256",
    )
    binding = {key: manifest[key] for key in keys}
    package_id = str(manifest.get("package_id", ""))
    checkpoint_id = str(manifest.get("checkpoint_id", ""))
    if _manifest_includes_foreign_bindings(package_id, checkpoint_id):
        binding["declared_foreign_bindings"] = manifest["declared_foreign_bindings"]
    return binding


def validate_context_manifest(
    *,
    root: Path,
    manifest_path: str,
    allow_reuse: bool = False,
    verification_commands: tuple[str, ...] | None = None,
) -> dict[str, object]:
    root = _resolve_repo_root(root)
    manifest_file = _manifest_path(root, manifest_path)
    if not manifest_file.is_file():
        return {
            "valid": False,
            "reuse_allowed": False,
            "reasons": ["manifest_missing"],
        }

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "valid": False,
            "reuse_allowed": False,
            "reasons": ["manifest_malformed"],
        }

    if not isinstance(manifest, dict):
        return {
            "valid": False,
            "reuse_allowed": False,
            "reasons": ["manifest_not_object"],
        }

    required = (
        "schema_version",
        "package_id",
        "checkpoint_id",
        "branch",
        "head",
        "base_ref",
        "base_sha",
        "contract_path",
        "contract_sha256",
        "profile_path",
        "profile_slug",
        "profile_version",
        "profile_sha256",
        "allowlist",
        "owner_hashes",
        "verification_commands",
        "evidence_paths",
        "evidence_sha256",
        "repository_state_sha256",
        "reuse_key_sha256",
    )
    reasons: list[str] = []
    for key in required:
        if key not in manifest:
            reasons.append(f"missing_field:{key}")
    package_id = str(manifest.get("package_id", ""))
    checkpoint_id = str(manifest.get("checkpoint_id", ""))
    if _manifest_includes_foreign_bindings(package_id, checkpoint_id):
        if "declared_foreign_bindings" not in manifest:
            reasons.append("missing_field:declared_foreign_bindings")

    if reasons:
        return {"valid": False, "reuse_allowed": False, "reasons": reasons}

    if allow_reuse and not verification_commands:
        return {
            "valid": False,
            "reuse_allowed": False,
            "reasons": ["reuse_requires_verification_commands"],
        }

    if verification_commands is not None:
        expected_commands = sorted(
            {_normalize_verification_command(cmd) for cmd in verification_commands if cmd.strip()}
        )
        observed_commands = sorted(str(cmd) for cmd in manifest["verification_commands"])
        if expected_commands != observed_commands:
            reasons.append("binding_mismatch:verification_commands")

    try:
        rebuilt = build_context_manifest(
            root=root,
            package_id=str(manifest["package_id"]),
            checkpoint_id=str(manifest["checkpoint_id"]),
            contract_path=str(manifest["contract_path"]),
            profile_path=str(manifest["profile_path"]),
            allowlist=tuple(str(path) for path in manifest["allowlist"]),
            verification_commands=tuple(str(cmd) for cmd in manifest["verification_commands"]),
            evidence_paths={str(k): str(v) for k, v in dict(manifest["evidence_paths"]).items()},
            base_ref=str(manifest["base_ref"]),
        )
    except (RuntimeError, ValueError, TypeError) as exc:
        return {
            "valid": False,
            "reuse_allowed": False,
            "reasons": [f"recompute_failed:{exc}"],
        }

    if str(manifest.get("reuse_key_sha256")) != str(rebuilt.get("reuse_key_sha256")):
        reasons.append("binding_mismatch:reuse_key_sha256")

    expected_binding = _manifest_binding(rebuilt)
    actual_binding = _manifest_binding(manifest)
    if expected_binding != actual_binding:
        for key in expected_binding:
            if expected_binding.get(key) != actual_binding.get(key):
                reasons.append(f"binding_mismatch:{key}")

    recorded_evidence_sha256 = dict(manifest["evidence_sha256"])
    for key, relative in dict(manifest["evidence_paths"]).items():
        rel = PurePosixPath(str(relative)).as_posix()
        try:
            evidence_file = _manifest_path(root, rel)
        except ValueError:
            reasons.append(f"evidence_traversal:{key}")
            continue
        if evidence_file.is_file():
            live_sha256 = _sha256_file(evidence_file)
        else:
            live_sha256 = None
        recorded_sha256 = recorded_evidence_sha256.get(key)
        if recorded_sha256 is None:
            reasons.append(f"evidence_not_bound_at_build:{key}")
        elif live_sha256 is None:
            reasons.append(f"evidence_missing:{key}")
        elif recorded_sha256 != live_sha256:
            reasons.append(f"evidence_changed:{key}")

    valid = not reasons
    evidence_complete = all(value is not None for value in recorded_evidence_sha256.values())
    reuse_allowed = valid and allow_reuse and evidence_complete
    return {
        "valid": valid,
        "reuse_allowed": reuse_allowed,
        "reasons": reasons,
        "expected_reuse_key_sha256": rebuilt["reuse_key_sha256"],
        "observed_reuse_key_sha256": manifest.get("reuse_key_sha256"),
    }


def _run_snapshot(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    snapshot = build_snapshot(
        root=root,
        checkpoint=args.checkpoint,
        phase=args.phase,
        allowlist=tuple(args.allow),
        foreign=tuple(args.foreign),
        base_ref=args.base_ref,
        scope_mode=args.scope_mode,
    )
    output = _output_path(root, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"snapshot={output}")
    print(f"repository_state_sha256={snapshot['repository_state_sha256']}")
    if snapshot.get("denial_reasons"):
        print("denial_reasons=" + ",".join(str(item) for item in snapshot["denial_reasons"]))
    out_of_scope = snapshot.get("out_of_scope_paths") or []
    if out_of_scope:
        print("out_of_scope=" + ",".join(out_of_scope))
        if args.fail_on_out_of_scope:
            return 2
    if args.fail_on_denial and snapshot.get("denial_reasons"):
        return 2
    return 0


def _run_manifest_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.foreign:
        profile_bindings = {
            PurePosixPath(str(item["path"])).as_posix()
            for item in json.loads((root / Path(args.profile_path)).read_text(encoding="utf-8"))
            .get("external_codex_bound_review", {})
            .get("declared_foreign_bindings", [])
        }
        cli_bindings = {PurePosixPath(path).as_posix() for path in args.foreign}
        if cli_bindings != profile_bindings:
            raise SystemExit("manifest-build --foreign cannot override profile declared_foreign_bindings")
    evidence_paths = {}
    for item in args.evidence or []:
        key, _, value = item.partition("=")
        if not key or not value:
            raise SystemExit("evidence entries must use key=relative/path form")
        evidence_paths[key] = value
    manifest = build_context_manifest(
        root=root,
        package_id=args.package_id,
        checkpoint_id=args.checkpoint_id,
        contract_path=args.contract_path,
        profile_path=args.profile_path,
        allowlist=tuple(args.allow),
        verification_commands=tuple(args.verify_command),
        evidence_paths=evidence_paths,
        base_ref=args.base_ref,
        foreign=tuple(args.foreign or []),
    )
    output = _manifest_path(root, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"context_manifest={output}")
    print(f"reuse_key_sha256={manifest['reuse_key_sha256']}")
    return 0


def _run_manifest_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.allow_reuse and not args.verify_command:
        result = {
            "valid": False,
            "reuse_allowed": False,
            "reasons": ["reuse_requires_verification_commands"],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    verify_commands = tuple(args.verify_command) if args.verify_command else None
    result = validate_context_manifest(
        root=root,
        manifest_path=args.manifest,
        allow_reuse=args.allow_reuse,
        verification_commands=verify_commands,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        return 2
    if args.allow_reuse and not result["reuse_allowed"]:
        return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture AP-029 checkpoint snapshots and context manifests.")
    subparsers = parser.add_subparsers(dest="command")

    snapshot = subparsers.add_parser("snapshot", help="Capture a checkpoint Git-state snapshot.")
    snapshot.add_argument("--root", default=".")
    snapshot.add_argument("--checkpoint", required=True)
    snapshot.add_argument("--phase", required=True)
    snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--allow", action="append", default=[])
    snapshot.add_argument("--foreign", action="append", default=[])
    snapshot.add_argument("--base-ref", default="origin/main")
    snapshot.add_argument("--scope-mode", default="dirty", choices=("dirty", "committed_final_audit"))
    snapshot.add_argument("--fail-on-out-of-scope", action="store_true")
    snapshot.add_argument("--fail-on-denial", action="store_true")
    snapshot.set_defaults(func=_run_snapshot)

    manifest_build = subparsers.add_parser("manifest-build", help="Build a deterministic context manifest.")
    manifest_build.add_argument("--root", default=".")
    manifest_build.add_argument("--package-id", required=True)
    manifest_build.add_argument("--checkpoint-id", required=True)
    manifest_build.add_argument("--contract-path", required=True)
    manifest_build.add_argument("--profile-path", default=".cursor/agent-system.json")
    manifest_build.add_argument("--output", required=True)
    manifest_build.add_argument("--allow", action="append", required=True)
    manifest_build.add_argument("--verify-command", action="append", required=True)
    manifest_build.add_argument("--evidence", action="append", default=[])
    manifest_build.add_argument("--foreign", action="append", default=[])
    manifest_build.add_argument("--base-ref", default="origin/main")
    manifest_build.set_defaults(func=_run_manifest_build)

    manifest_validate = subparsers.add_parser("manifest-validate", help="Validate a context manifest.")
    manifest_validate.add_argument("--root", default=".")
    manifest_validate.add_argument("--manifest", required=True)
    manifest_validate.add_argument("--allow-reuse", action="store_true")
    manifest_validate.add_argument("--verify-command", action="append", default=[])
    manifest_validate.set_defaults(func=_run_manifest_validate)

    # Backward-compatible legacy invocation without subcommand.
    parser.add_argument("--root", default=".", help=argparse.SUPPRESS)
    parser.add_argument("--checkpoint", help=argparse.SUPPRESS)
    parser.add_argument("--phase", help=argparse.SUPPRESS)
    parser.add_argument("--output", help=argparse.SUPPRESS)
    parser.add_argument("--allow", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--foreign", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--base-ref", default="origin/main", help=argparse.SUPPRESS)
    parser.add_argument("--scope-mode", default="dirty", help=argparse.SUPPRESS)
    parser.add_argument("--fail-on-out-of-scope", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fail-on-denial", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()
    if args.command:
        return int(args.func(args))

    if not args.checkpoint or not args.phase or not args.output:
        parser.error("legacy snapshot mode requires --checkpoint, --phase, and --output")
    return _run_snapshot(args)


if __name__ == "__main__":
    raise SystemExit(main())
