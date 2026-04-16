from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.documents.api import DocumentWorkflowError, SystemRole
from modules.signature.api import SignatureError
from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def cmd_training(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    usermanagement = container.get_port("usermanagement_service")
    training_api = container.get_port("training_api")
    training_admin_api = container.get_port("training_admin_api")
    current_user = usermanagement.get_current_user()
    if current_user is None:
        print("BLOCKED: login required for training commands")
        return 6
    role_map = {"Admin": SystemRole.ADMIN, "QMB": SystemRole.QMB, "User": SystemRole.USER}
    current_role = role_map.get(current_user.role)
    if current_role is None:
        print("BLOCKED: login required for training commands")
        return 6

    try:
        if args.training_command == "list-required":
            rows = training_api.list_required_for_user(current_user.user_id)
            print(
                json.dumps(
                    [
                        {
                            "assignment_id": r.assignment_id,
                            "document_id": r.document_id,
                            "version": r.version,
                            "status": r.status.value,
                            "active": r.active,
                            "last_score": r.last_score,
                        }
                        for r in rows
                    ],
                    ensure_ascii=True,
                )
            )
            return 0
        if args.training_command == "confirm-read":
            row = training_api.confirm_read(
                user_id=current_user.user_id,
                document_id=args.document_id,
                version=args.version,
                last_page_seen=args.last_page_seen,
                total_pages=args.total_pages,
                scrolled_to_end=args.scrolled_to_end,
            )
            print(
                json.dumps(
                    {
                        "assignment_id": row.assignment_id,
                        "document_id": row.document_id,
                        "version": row.version,
                        "status": row.status.value,
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
            rows = training_admin_api.list_approved_documents()
            print(
                json.dumps(
                    [{"document_id": r.document_id, "version": r.version, "owner_user_id": r.owner_user_id} for r in rows],
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
            count = training_admin_api.sync_required_assignments()
            print(json.dumps({"updated": count}, ensure_ascii=True))
            return 0
        if args.training_command == "admin-quiz-import":
            digest = training_admin_api.import_quiz_questions(
                args.document_id,
                args.version,
                Path(args.input).read_bytes(),
            )
            print(json.dumps({"sha256": digest}, ensure_ascii=True))
            return 0
        if args.training_command == "admin-matrix":
            rows = training_admin_api.list_matrix()
            print(
                json.dumps(
                    [
                        {
                            "user_id": r.user_id,
                            "document_id": r.document_id,
                            "version": r.version,
                            "category_id": r.category_id,
                            "status": r.status.value,
                            "active": r.active,
                        }
                        for r in rows
                    ],
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

