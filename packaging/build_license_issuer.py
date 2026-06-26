"""Build a Windows onedir internal License Issuer GUI (PyInstaller) + ZIP.

Run from repository root:
  python packaging/build_license_issuer.py
Output:
  packaging/dist_output/QM-Tool-LicenseIssuer/
  packaging/dist_output/QM-Tool-LicenseIssuer.zip
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
ENTRY = ROOT / "tools" / "license_issuer_gui" / "main.py"
VERIFY_ISSUER = ROOT / "packaging" / "verify_license_issuer_bundle.py"
PROD_PUBLIC_KEY = ROOT / "qm_platform" / "licensing" / "keys" / "prod_ed25519_public.pem"

_ADD_DATA_SEP = ";" if os.name == "nt" else ":"
_BUNDLE_DATA: list[tuple[str, str]] = [
    ("qm_platform/licensing/keys/prod_ed25519_public.pem", "qm_platform/licensing/keys"),
]

_HIDDEN_IMPORTS: list[str] = [
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
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
    if not PROD_PUBLIC_KEY.is_file():
        raise SystemExit(f"Missing production public key: {PROD_PUBLIC_KEY}")
    _png_to_ico()

    dist_out = ROOT / "packaging" / "dist_output"
    work = ROOT / "packaging" / "_pyi_build_license_issuer"
    bundle_dir = dist_out / "QM-Tool-LicenseIssuer"
    issuer_zip = dist_out / "QM-Tool-LicenseIssuer.zip"

    if bundle_dir.is_dir():
        try:
            shutil.rmtree(bundle_dir)
        except PermissionError as exc:
            raise SystemExit(
                "Konnte QM-Tool-LicenseIssuer nicht löschen (Datei gesperrt). "
                "Bitte alle Issuer-EXE-Instanzen schließen und den Build erneut starten."
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
        "QM-Tool-LicenseIssuer",
        f"--icon={ICON_ICO}",
        f"--paths={ROOT}",
        f"--distpath={dist_out}",
        f"--workpath={work}",
        f"--specpath={ROOT / 'packaging'}",
    ]
    for hidden in _HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hidden])
    for rel, dest in _BUNDLE_DATA:
        src = ROOT / rel
        if not src.is_file():
            raise FileNotFoundError(f"Bundle data file missing: {src}")
        cmd.extend(["--add-data", f"{src.resolve()}{_ADD_DATA_SEP}{dest}"])
    cmd.append(str(ENTRY))
    print(" ", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    exe = bundle_dir / "QM-Tool-LicenseIssuer.exe"
    if not exe.is_file():
        raise SystemExit(f"Expected output missing: {exe}")

    subprocess.check_call([sys.executable, str(VERIFY_ISSUER), str(bundle_dir)], cwd=ROOT)

    if issuer_zip.is_file():
        issuer_zip.unlink()
    shutil.make_archive(str(dist_out / "QM-Tool-LicenseIssuer"), "zip", root_dir=str(dist_out), base_dir="QM-Tool-LicenseIssuer")
    if not issuer_zip.is_file():
        raise SystemExit(f"ZIP missing: {issuer_zip}")
    print(f"OK: {exe}")
    print(f"OK: {issuer_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
