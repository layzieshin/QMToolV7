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


def _matches(path: str, rules: tuple[str, ...]) -> bool:
    normalized = PurePosixPath(path).as_posix()
    for raw in rules:
        rule = PurePosixPath(raw.rstrip("/")).as_posix()
        if normalized == rule or normalized.startswith(f"{rule}/"):
            return True
    return False


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


def build_snapshot(
    *,
    root: Path,
    checkpoint: str,
    phase: str,
    allowlist: tuple[str, ...],
    foreign: tuple[str, ...],
    base_ref: str,
) -> dict[str, object]:
    root = _resolve_repo_root(root)

    staged = _paths(root, "diff", "--cached", "--name-only")
    unstaged = _paths(root, "diff", "--name-only")
    untracked = _paths(root, "ls-files", "--others", "--exclude-standard")
    changed = staged | unstaged | untracked
    head = _git(root, "rev-parse", "HEAD")
    permitted = {path for path in changed if _matches(path, allowlist)}
    declared_foreign = {path for path in changed if _matches(path, foreign)}
    out_of_scope = changed - permitted - declared_foreign
    fingerprint, files = _content_fingerprint(
        root,
        changed,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        head=head,
    )

    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "checkpoint": checkpoint,
        "phase": phase,
        "repository_root": str(root),
        "branch": _git(root, "branch", "--show-current") or "DETACHED",
        "head": head,
        "base_ref": base_ref,
        "base_sha": _git(root, "rev-parse", base_ref, allow_missing_ref=True),
        "allowlist": sorted(allowlist),
        "declared_foreign_rules": sorted(foreign),
        "staged_paths": sorted(staged),
        "unstaged_paths": sorted(unstaged),
        "untracked_paths": sorted(untracked),
        "allowed_changed_paths": sorted(permitted),
        "declared_foreign_paths": sorted(declared_foreign),
        "out_of_scope_paths": sorted(out_of_scope),
        "repository_state_sha256": fingerprint,
        "files": files,
    }


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
    return {key: manifest[key] for key in keys}


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
    )
    output = _output_path(root, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"snapshot={output}")
    print(f"repository_state_sha256={snapshot['repository_state_sha256']}")
    if snapshot["out_of_scope_paths"]:
        print("out_of_scope=" + ",".join(snapshot["out_of_scope_paths"]))
        if args.fail_on_out_of_scope:
            return 2
    return 0


def _run_manifest_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
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
    snapshot.add_argument("--fail-on-out-of-scope", action="store_true")
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
    parser.add_argument("--fail-on-out-of-scope", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()
    if args.command:
        return int(args.func(args))

    if not args.checkpoint or not args.phase or not args.output:
        parser.error("legacy snapshot mode requires --checkpoint, --phase, and --output")
    return _run_snapshot(args)


if __name__ == "__main__":
    raise SystemExit(main())
