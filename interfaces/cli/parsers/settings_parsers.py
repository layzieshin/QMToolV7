from __future__ import annotations
import argparse


def register_settings_parsers(sub: argparse._SubParsersAction) -> None:
    settings_parser = sub.add_parser("settings", help="Settings operations")
    settings_sub = settings_parser.add_subparsers(dest="settings_command", required=True)
    settings_sub.add_parser("list-modules", help="List modules with settings contribution")
    settings_get = settings_sub.add_parser("get", help="Get module settings")
    settings_get.add_argument("--module", required=True)
    settings_set = settings_sub.add_parser("set", help="Set module settings from JSON object")
    settings_set.add_argument("--module", required=True)
    settings_set.add_argument("--values-json", required=True)
    settings_set.add_argument(
        "--acknowledge-governance-change",
        action="store_true",
        help="Required when changing governance_critical keys",
    )

