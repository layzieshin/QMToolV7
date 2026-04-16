from __future__ import annotations
import argparse


def register_training_parsers(sub: argparse._SubParsersAction) -> None:
    training_parser = sub.add_parser("training", help="Training and document reading operations")
    training_sub = training_parser.add_subparsers(dest="training_command", required=True)
    training_sub.add_parser("list-required", help="List required training assignments for current user")

    tr_confirm = training_sub.add_parser("confirm-read", help="Confirm document was read to last page")
    tr_confirm.add_argument("--document-id", required=True)
    tr_confirm.add_argument("--version", type=int, required=True)
    tr_confirm.add_argument("--last-page-seen", type=int, required=True)
    tr_confirm.add_argument("--total-pages", type=int, required=True)
    tr_confirm.add_argument("--scrolled-to-end", action="store_true")

    tr_quiz_start = training_sub.add_parser("quiz-start", help="Start 3-question random quiz")
    tr_quiz_start.add_argument("--document-id", required=True)
    tr_quiz_start.add_argument("--version", type=int, required=True)

    tr_quiz_answer = training_sub.add_parser("quiz-answer", help="Submit answers for active quiz session")
    tr_quiz_answer.add_argument("--session-id", required=True)
    tr_quiz_answer.add_argument("--answers-json", required=True)

    tr_comment = training_sub.add_parser("comment-add", help="Add feedback comment for document version")
    tr_comment.add_argument("--document-id", required=True)
    tr_comment.add_argument("--version", type=int, required=True)
    tr_comment.add_argument("--comment", required=True)

    training_sub.add_parser("admin-list-approved", help="Admin: list approved documents")

    tr_cat_create = training_sub.add_parser("admin-category-create", help="Admin: create training category")
    tr_cat_create.add_argument("--category-id", required=True)
    tr_cat_create.add_argument("--name", required=True)
    tr_cat_create.add_argument("--description")

    tr_cat_doc = training_sub.add_parser("admin-category-assign-document", help="Admin: map document to category")
    tr_cat_doc.add_argument("--category-id", required=True)
    tr_cat_doc.add_argument("--document-id", required=True)

    tr_cat_user = training_sub.add_parser("admin-category-assign-user", help="Admin: map user to category")
    tr_cat_user.add_argument("--category-id", required=True)
    tr_cat_user.add_argument("--user-id", required=True)

    training_sub.add_parser("admin-sync", help="Admin: sync assignments from categories and approved documents")

    tr_quiz_import = training_sub.add_parser("admin-quiz-import", help="Admin: import quiz JSON for document version")
    tr_quiz_import.add_argument("--document-id", required=True)
    tr_quiz_import.add_argument("--version", type=int, required=True)
    tr_quiz_import.add_argument("--input", required=True)

    training_sub.add_parser("admin-matrix", help="Admin: list training matrix")

