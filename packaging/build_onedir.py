"""Build a Windows onedir GUI bundle (PyInstaller) + production license + ZIP.

Run from repository root:
  python packaging/build_onedir.py
Output:
  packaging/dist_output/QM-Tool/   (folder)
  packaging/dist_output/QM-Tool.zip
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_PNG = ROOT / "packaging" / "icons" / "app_icon.png"
ICON_ICO = ROOT / "packaging" / "icons" / "app.ico"
ENTRY = ROOT / "interfaces" / "pyqt" / "main.py"
ISSUE_LICENSE = ROOT / "scripts" / "issue_production_license.py"

# PyInstaller does not ship *.sql / *.json next to packages by default; mirror repo paths under _internal.
_ADD_DATA_SEP = ";" if os.name == "nt" else ":"
_BUNDLE_DATA: list[tuple[str, str]] = [
    ("modules/usermanagement/schema.sql", "modules/usermanagement"),
    ("modules/documents/schema.sql", "modules/documents"),
    ("modules/documents/workflow_profiles.json", "modules/documents"),
    ("modules/registry/schema.sql", "modules/registry"),
    ("modules/signature/schema.sql", "modules/signature"),
    ("modules/training/schema.sql", "modules/training"),
    ("interfaces/pyqt/shell/styles.qss", "interfaces/pyqt/shell"),
]


def _png_to_ico() -> None:
    from PIL import Image

    if not ICON_PNG.is_file():
        raise FileNotFoundError(f"Icon PNG missing: {ICON_PNG}")
    img = Image.open(ICON_PNG).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    frames = [img.resize(s, Image.Resampling.LANCZOS) for s in sizes]
    frames[0].save(
        ICON_ICO,
        format="ICO",
        sizes=[(f.width, f.height) for f in frames],
        append_images=frames[1:],
    )


def main() -> int:
    os.chdir(ROOT)
    _png_to_ico()

    dist_out = ROOT / "packaging" / "dist_output"
    work = ROOT / "packaging" / "_pyi_build"
    bundle_dir = dist_out / "QM-Tool"
    if dist_out.is_dir():
        try:
            shutil.rmtree(dist_out)
        except PermissionError as exc:
            raise SystemExit(
                "Konnte packaging/dist_output nicht löschen (Datei gesperrt). "
                "Bitte alle QM-Tool.exe-Instanzen schließen und den Build erneut starten."
            ) from exc
    if work.is_dir():
        shutil.rmtree(work)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "QM-Tool",
        f"--icon={ICON_ICO}",
        f"--paths={ROOT}",
        f"--distpath={dist_out}",
        f"--workpath={work}",
        f"--specpath={ROOT / 'packaging'}",
    ]
    for rel, dest in _BUNDLE_DATA:
        src = ROOT / rel
        if not src.is_file():
            raise FileNotFoundError(f"Bundle data file missing: {src}")
        cmd.extend(["--add-data", f"{src.resolve()}{_ADD_DATA_SEP}{dest}"])
    cmd.append(str(ENTRY))
    print(" ", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    exe = bundle_dir / "QM-Tool.exe"
    if not exe.is_file():
        raise SystemExit(f"Expected output missing: {exe}")

    subprocess.check_call([sys.executable, str(ISSUE_LICENSE), "--output-dir", str(bundle_dir)], cwd=ROOT)

    for rel in (
        "storage/platform/logs",
        "storage/platform/session",
    ):
        (bundle_dir / rel).mkdir(parents=True, exist_ok=True)

    zip_base = dist_out / "QM-Tool"
    if zip_base.with_suffix(".zip").is_file():
        zip_base.with_suffix(".zip").unlink()
    shutil.make_archive(str(zip_base), "zip", root_dir=str(dist_out), base_dir="QM-Tool")
    zpath = zip_base.with_suffix(".zip")
    if not zpath.is_file():
        raise SystemExit(f"ZIP missing: {zpath}")
    print(f"OK: {exe}")
    print(f"OK: {zpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
