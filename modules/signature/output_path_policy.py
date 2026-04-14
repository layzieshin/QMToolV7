from __future__ import annotations

from pathlib import Path

from modules.signature.contracts import SignRequest


class OutputPathPolicy:
    """Determines output paths without mixing UI concerns into service flow."""

    @staticmethod
    def resolve(request: SignRequest) -> Path:
        if request.output_pdf:
            target = request.output_pdf
        else:
            stem = request.input_pdf.stem
            target = request.input_pdf.with_name(f"{stem}.signed.pdf")
        if request.overwrite_output or not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            return target

        base = target.with_suffix("")
        suffix = target.suffix
        for i in range(1, 1000):
            candidate = Path(f"{base}-{i}{suffix}")
            if not candidate.exists():
                return candidate
        raise RuntimeError("could not resolve deterministic output path")
