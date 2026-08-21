from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


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


def _content_fingerprint(root: Path, paths: set[str]) -> tuple[str, list[dict[str, object]]]:
    digest = hashlib.sha256()
    records: list[dict[str, object]] = []
    for relative in sorted(paths):
        path = root / Path(relative)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if not path.exists():
            digest.update(b"<deleted>")
            records.append({"path": relative, "state": "deleted", "sha256": None, "size": 0})
            continue
        if not path.is_file():
            digest.update(b"<non-file>")
            records.append({"path": relative, "state": "non-file", "sha256": None, "size": 0})
            continue
        content = path.read_bytes()
        file_hash = hashlib.sha256(content).hexdigest()
        digest.update(content)
        records.append(
            {"path": relative, "state": "present", "sha256": file_hash, "size": len(content)}
        )
    return digest.hexdigest(), records


def build_snapshot(
    *,
    root: Path,
    checkpoint: str,
    phase: str,
    allowlist: tuple[str, ...],
    foreign: tuple[str, ...],
    base_ref: str,
) -> dict[str, object]:
    root = root.resolve()
    actual_root = Path(_git(root, "rev-parse", "--show-toplevel") or "").resolve()
    if actual_root != root:
        raise RuntimeError(f"root must be repository root: expected {actual_root}, got {root}")

    staged = _paths(root, "diff", "--cached", "--name-only")
    unstaged = _paths(root, "diff", "--name-only")
    untracked = _paths(root, "ls-files", "--others", "--exclude-standard")
    changed = staged | unstaged | untracked
    permitted = {path for path in changed if _matches(path, allowlist)}
    declared_foreign = {path for path in changed if _matches(path, foreign)}
    out_of_scope = changed - permitted - declared_foreign
    fingerprint, files = _content_fingerprint(root, changed)

    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "checkpoint": checkpoint,
        "phase": phase,
        "repository_root": str(root),
        "branch": _git(root, "branch", "--show-current") or "DETACHED",
        "head": _git(root, "rev-parse", "HEAD"),
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture an AP-029 checkpoint Git-state snapshot.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow", action="append", default=[])
    parser.add_argument("--foreign", action="append", default=[])
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--fail-on-out-of-scope", action="store_true")
    args = parser.parse_args()

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


if __name__ == "__main__":
    raise SystemExit(main())
