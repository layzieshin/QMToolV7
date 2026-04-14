from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


class TrainingCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._env = dict(os.environ)
        self._env["QMTOOL_HOME"] = str(Path(self._tmp.name) / "home")
        init = run_cli("init", "--non-interactive", "--admin-password", "admin", env=self._env)
        assert init.returncode == 0, init.stderr + init.stdout
        run_cli("logout", env=self._env)

    def tearDown(self) -> None:
        run_cli("logout", env=self._env)
        self._tmp.cleanup()

    def _login(self, username: str, password: str) -> None:
        result = run_cli("login", "--username", username, "--password", password, env=self._env)
        assert result.returncode == 0, result.stderr + result.stdout

    def test_training_flow_with_quiz_and_comments(self) -> None:
        doc_id = f"DOC-TR-{uuid.uuid4().hex[:8]}"
        self._login("admin", "admin")
        created = run_cli(
            "documents",
            "create-version",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--doc-type",
            "EXT",
            "--control-class",
            "EXTERNAL",
            "--workflow-profile-id",
            "external_control",
            env=self._env,
        )
        self.assertEqual(created.returncode, 0, msg=created.stderr + created.stdout)
        started = run_cli(
            "documents", "workflow-start", "--document-id", doc_id, "--version", "1", "--profile-id", "external_control", env=self._env
        )
        self.assertEqual(started.returncode, 0, msg=started.stderr + started.stdout)
        approved = run_cli("documents", "editing-complete", "--document-id", doc_id, "--version", "1", env=self._env)
        self.assertEqual(approved.returncode, 0, msg=approved.stderr + approved.stdout)

        self.assertEqual(
            run_cli("training", "admin-category-create", "--category-id", "cat-e2e", "--name", "E2E", env=self._env).returncode,
            0,
        )
        self.assertEqual(
            run_cli(
                "training",
                "admin-category-assign-document",
                "--category-id",
                "cat-e2e",
                "--document-id",
                doc_id,
                env=self._env,
            ).returncode,
            0,
        )
        self.assertEqual(
            run_cli("training", "admin-category-assign-user", "--category-id", "cat-e2e", "--user-id", "user", env=self._env).returncode,
            0,
        )
        sync = run_cli("training", "admin-sync", env=self._env)
        self.assertEqual(sync.returncode, 0, msg=sync.stderr + sync.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            quiz_file = Path(tmp) / "quiz.json"
            quiz_file.write_text(
                json.dumps(
                    {
                        "questions": [
                            {"id": "q1", "text": "Q1", "options": ["A", "B", "C"], "correct_index": 0},
                            {"id": "q2", "text": "Q2", "options": ["A", "B", "C"], "correct_index": 0},
                            {"id": "q3", "text": "Q3", "options": ["A", "B", "C"], "correct_index": 0},
                            {"id": "q4", "text": "Q4", "options": ["A", "B", "C"], "correct_index": 0},
                        ]
                    },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            imported = run_cli(
                "training",
                "admin-quiz-import",
                "--document-id",
                doc_id,
                "--version",
                "1",
                "--input",
                str(quiz_file),
                env=self._env,
            )
            self.assertEqual(imported.returncode, 0, msg=imported.stderr + imported.stdout)

        run_cli("logout", env=self._env)
        self._login("user", "user")
        required = run_cli("training", "list-required", env=self._env)
        self.assertEqual(required.returncode, 0, msg=required.stderr + required.stdout)
        rows = json.loads(required.stdout.strip() or "[]")
        self.assertTrue(any(r.get("document_id") == doc_id for r in rows))
        confirmed = run_cli(
            "training",
            "confirm-read",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--last-page-seen",
            "3",
            "--total-pages",
            "3",
            "--scrolled-to-end",
            env=self._env,
        )
        self.assertEqual(confirmed.returncode, 0, msg=confirmed.stderr + confirmed.stdout)
        quiz_start = run_cli("training", "quiz-start", "--document-id", doc_id, "--version", "1", env=self._env)
        self.assertEqual(quiz_start.returncode, 0, msg=quiz_start.stderr + quiz_start.stdout)
        session_payload = json.loads(quiz_start.stdout.strip() or "{}")
        session_id = session_payload.get("session_id")
        self.assertTrue(session_id)
        answered = run_cli("training", "quiz-answer", "--session-id", str(session_id), "--answers-json", "[0,0,0]", env=self._env)
        self.assertEqual(answered.returncode, 0, msg=answered.stderr + answered.stdout)
        answer_payload = json.loads(answered.stdout.strip() or "{}")
        self.assertTrue(answer_payload.get("passed"))
        comment = run_cli(
            "training",
            "comment-add",
            "--document-id",
            doc_id,
            "--version",
            "1",
            "--comment",
            "Bitte Kapitel 2 verbessern",
            env=self._env,
        )
        self.assertEqual(comment.returncode, 0, msg=comment.stderr + comment.stdout)
        self.assertIn("comment_id", comment.stdout)


if __name__ == "__main__":
    unittest.main()
