from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.documents.api import DocumentWorkflowError, SystemRole
from modules.signature.api import SignatureError
from modules.usermanagement.role_policies import is_effective_qmb
from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def cmd_training(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    usermanagement = container.get_port("usermanagement_service")
    training_api = container.get_port("training_api")
    training_admin_api = container.get_port("training_admin_api")
    documents_read_api = container.get_port("documents_read_api")
    current_user = usermanagement.get_current_user()
    if current_user is None:
        print("BLOCKED: login required for training commands")
        return 6
    role_map = {"Admin": SystemRole.ADMIN, "QMB": SystemRole.QMB, "User": SystemRole.USER}
    current_role = role_map.get(current_user.role)
    if current_role == SystemRole.USER and is_effective_qmb(current_user):
        current_role = SystemRole.QMB
    if current_role is None:
        print("BLOCKED: login required for training commands")
        return 6

    try:
        if args.training_command == "list-required":
            rows = training_api.list_training_inbox_for_user(current_user.user_id, open_only=True)
            print(
                json.dumps(
                    [
                        {
                            "document_id": r.document_id,
                            "version": r.version,
                            "title": r.title,
                            "status": r.status,
                            "source": r.source.value,
                            "read_confirmed": r.read_confirmed,
                            "quiz_available": r.quiz_available,
                            "quiz_passed": r.quiz_passed,
                            "last_score": r.last_score,
                        }
                        for r in rows
                    ],
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "confirm-read":
            # Legacy command alias. Read confirmation is owned by documents_read_api.
            row = documents_read_api.confirm_released_document_read(
                user_id=current_user.user_id,
                document_id=args.document_id,
                version=args.version,
                source="cli-training-confirm-read",
            )
            print(
                json.dumps(
                    {
                        "receipt_id": row.receipt_id,
                        "user_id": row.user_id,
                        "document_id": row.document_id,
                        "version": row.version,
                        "confirmed_at": row.confirmed_at.isoformat(),
                        "source": row.source,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "quiz-start":
            session, questions = training_api.start_quiz(current_user.user_id, args.document_id, args.version)
            print(
                json.dumps(
                    {
                        "session_id": session.session_id,
                        "document_id": session.document_id,
                        "version": session.version,
                        "questions": [
                            {"question_id": q.question_id, "text": q.question_text, "options": list(q.options)}
                            for q in questions
                        ],
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "quiz-answer":
            answers = json.loads(args.answers_json)
            if not isinstance(answers, list):
                print("BLOCKED: --answers-json must be a JSON array")
                return 6
            result = training_api.submit_quiz_answers(args.session_id, [int(v) for v in answers])
            print(
                json.dumps(
                    {
                        "session_id": result.session_id,
                        "score": result.score,
                        "total": result.total,
                        "passed": result.passed,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "comment-add":
            row = training_api.add_comment(current_user.user_id, args.document_id, args.version, args.comment)
            print(json.dumps({"comment_id": row.comment_id}, ensure_ascii=True))
            return 0
        if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
            print("BLOCKED: only QMB or ADMIN may execute training admin commands")
            return 6
        if args.training_command == "admin-list-approved":
            rows = training_admin_api.list_assignable_documents()
            print(
                json.dumps(
                    [
                        {
                            "document_id": r.document_id,
                            "version": r.version,
                            "title": r.title,
                            "owner_user_id": r.owner_user_id,
                            "released_at": r.released_at.isoformat() if r.released_at else None,
                        }
                        for r in rows
                    ],
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "admin-category-create":
            category = training_admin_api.create_category(args.category_id, args.name, description=args.description)
            print(json.dumps({"category_id": category.category_id, "name": category.name}, ensure_ascii=True))
            return 0
        if args.training_command == "admin-category-assign-document":
            training_admin_api.assign_document_to_category(args.category_id, args.document_id)
            print("OK")
            return 0
        if args.training_command == "admin-category-assign-user":
            training_admin_api.assign_user_to_category(args.category_id, args.user_id)
            print("OK")
            return 0
        if args.training_command == "admin-sync":
            count = training_admin_api.rebuild_assignment_snapshots()
            print(json.dumps({"rebuilt_snapshots": count}, ensure_ascii=True))
            return 0
        if args.training_command == "admin-quiz-import":
            result = training_admin_api.import_quiz_json(Path(args.input).read_bytes())
            binding = training_admin_api.bind_quiz_to_document(
                result.import_id,
                args.document_id,
                args.version,
            )
            print(
                json.dumps(
                    {
                        "import_id": result.import_id,
                        "questions": result.question_count,
                        "sha256": result.source_hash_sha256,
                        "binding_id": binding.binding_id,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "admin-matrix":
            result = training_admin_api.export_training_matrix()
            print(
                json.dumps(
                    {
                        "rows": result.row_count,
                        "csv_bytes": len(result.csv_bytes),
                    },
                    ensure_ascii=True,
                )
            )
            return 0
    except (ValueError, KeyError, json.JSONDecodeError, DocumentWorkflowError, SignatureError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1

