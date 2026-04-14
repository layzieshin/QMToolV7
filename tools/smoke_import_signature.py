# tools/smoke_import_signature.py
import importlib

def must_import(path: str):
    mod_path, _, cls_name = path.rpartition(".")
    print(f"Trying import: {path}")
    m = importlib.import_module(mod_path)
    cls = getattr(m, cls_name)
    print(f"  OK: {cls}")

if __name__ == "__main__":
    must_import("modules.signature.service.SignatureServiceV2")
    must_import("modules.signature.pdf_signer.PdfSigner")
    must_import("modules.signature.visual_models.SignaturePlacement")
    print("All good.")
