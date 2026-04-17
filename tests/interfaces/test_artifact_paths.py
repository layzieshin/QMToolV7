from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from pathlib import Path

from interfaces.pyqt.presenters.artifact_paths import resolve_openable_artifact_paths


@dataclass
class _Artifact:
    storage_key: str
    metadata: dict[str, object] = field(default_factory=dict)


class ArtifactPathResolverTest(unittest.TestCase):
    def test_resolves_storage_key_without_metadata_path(self) -> None:
        app_home = Path("I:/app")
        artifacts_root = app_home / "storage" / "documents" / "artifacts"
        artifact = _Artifact(
            storage_key="DOC-1/v1/released.pdf",
            metadata={},
        )
        paths = resolve_openable_artifact_paths(
            artifact=artifact,
            app_home=app_home,
            artifacts_root=artifacts_root,
        )
        self.assertEqual(paths, [artifacts_root / "DOC-1/v1/released.pdf"])


if __name__ == "__main__":
    unittest.main()
