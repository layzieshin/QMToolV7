from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from modules.signature.contracts import LabelLayoutInput, SignRequest, SignaturePlacementInput
from modules.signature.api import SignatureError
from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def cmd_sign_visual(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    service = container.get_port("signature_service")
    date_text = args.date_text or datetime.now().strftime(args.date_format)
    name_text = args.name_text or args.signer_user
    request = SignRequest(
        input_pdf=Path(args.input),
        output_pdf=Path(args.output) if args.output else None,
        signature_png=Path(args.signature_png) if args.signature_png else None,
        placement=SignaturePlacementInput(
            page_index=args.page,
            x=args.x,
            y=args.y,
            target_width=args.width,
        ),
        layout=LabelLayoutInput(
            show_signature=args.show_signature,
            show_name=args.show_name,
            show_date=args.show_date,
            name_text=name_text if args.show_name else None,
            date_text=date_text if args.show_date else None,
            name_position=args.name_pos,
            date_position=args.date_pos,
            name_font_size=args.name_size,
            date_font_size=args.date_size,
            color_hex=args.color,
            name_above=args.name_above,
            name_below=args.name_below,
            date_above=args.date_above,
            date_below=args.date_below,
            x_offset=args.x_offset,
        ),
        overwrite_output=args.overwrite_output,
        dry_run=args.dry_run,
        sign_mode=args.mode,
        signer_user=args.signer_user,
        password=args.password,
        reason=args.reason,
    )
    try:
        result = service.sign_with_fixed_position(request)
    except SignatureError as exc:
        print(f"BLOCKED: {exc}")
        return 4
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 5
    status = "DRY-RUN" if result.dry_run else "OK"
    print(f"{status}: signed pdf -> {result.output_pdf}")
    if result.sha256:
        print(f"SHA256: {result.sha256}")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    api = container.get_port("signature_api")
    try:
        if args.sign_command == "visual":
            return cmd_sign_visual(args)
        if args.sign_command == "import-asset":
            asset = api.import_signature_asset(args.owner_user_id, Path(args.input))
            print(
                json.dumps(
                    {
                        "asset_id": asset.asset_id,
                        "owner_user_id": asset.owner_user_id,
                        "media_type": asset.media_type,
                        "size_bytes": asset.size_bytes,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "import-set-active":
            asset = api.import_signature_asset_and_set_active(
                args.owner_user_id,
                Path(args.input),
                password=args.password,
            )
            print(
                json.dumps(
                    {"asset_id": asset.asset_id, "owner_user_id": asset.owner_user_id, "active": True},
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "template-create":
            placement = SignaturePlacementInput(page_index=args.page, x=args.x, y=args.y, target_width=args.width)
            layout = LabelLayoutInput(
                show_signature=args.show_signature,
                show_name=args.show_name,
                show_date=args.show_date,
                name_text=args.name_text,
                date_text=args.date_text,
                name_position=args.name_pos,
                date_position=args.date_pos,
                name_font_size=args.name_size,
                date_font_size=args.date_size,
                color_hex=args.color,
                name_above=args.name_above,
                name_below=args.name_below,
                date_above=args.date_above,
                date_below=args.date_below,
                x_offset=args.x_offset,
            )
            template = api.create_user_signature_template(
                owner_user_id=args.owner_user_id,
                name=args.name,
                placement=placement,
                layout=layout,
                signature_asset_id=args.asset_id,
                scope=args.scope,
            )
            print(
                json.dumps(
                    {
                        "template_id": template.template_id,
                        "owner_user_id": template.owner_user_id,
                        "name": template.name,
                        "signature_asset_id": template.signature_asset_id,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "template-update":
            placement = None
            if args.page is not None and args.x is not None and args.y is not None and args.width is not None:
                placement = SignaturePlacementInput(page_index=args.page, x=args.x, y=args.y, target_width=args.width)
            layout = None
            if args.show_signature is not None or args.show_name is not None or args.show_date is not None:
                layout = LabelLayoutInput(
                    show_signature=True if args.show_signature is None else bool(args.show_signature),
                    show_name=True if args.show_name is None else bool(args.show_name),
                    show_date=True if args.show_date is None else bool(args.show_date),
                    name_text=args.name_text,
                    date_text=args.date_text,
                    name_position=args.name_pos,
                    date_position=args.date_pos,
                    name_font_size=args.name_size,
                    date_font_size=args.date_size,
                    color_hex=args.color,
                    name_above=args.name_above,
                    name_below=args.name_below,
                    date_above=args.date_above,
                    date_below=args.date_below,
                    x_offset=args.x_offset,
                )
            template = api.update_signature_template(
                template_id=args.template_id,
                owner_user_id=args.owner_user_id,
                name=args.name,
                placement=placement,
                layout=layout,
                signature_asset_id=args.asset_id,
            )
            print(
                json.dumps(
                    {
                        "template_id": template.template_id,
                        "owner_user_id": template.owner_user_id,
                        "name": template.name,
                        "signature_asset_id": template.signature_asset_id,
                        "scope": template.scope,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "template-delete":
            api.delete_signature_template(args.template_id)
            print(json.dumps({"deleted": True, "template_id": args.template_id}, ensure_ascii=True))
            return 0
        if args.sign_command == "template-list":
            if args.scope == "global":
                rows = api.list_global_signature_templates()
            else:
                if not str(args.owner_user_id).strip():
                    raise ValueError("--owner-user-id is required for --scope user")
                rows = api.list_user_signature_templates(args.owner_user_id)
            print(
                json.dumps(
                    [
                        {
                            "template_id": row.template_id,
                            "owner_user_id": row.owner_user_id,
                            "name": row.name,
                            "signature_asset_id": row.signature_asset_id,
                            "scope": row.scope,
                        }
                        for row in rows
                    ],
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "template-copy-global":
            template = api.copy_global_template_to_user(
                template_id=args.template_id,
                owner_user_id=args.owner_user_id,
                name=args.name,
            )
            print(
                json.dumps(
                    {
                        "template_id": template.template_id,
                        "owner_user_id": template.owner_user_id,
                        "name": template.name,
                        "scope": template.scope,
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if args.sign_command == "active-set":
            api.set_active_signature_asset(args.owner_user_id, args.asset_id, password=args.password)
            print(json.dumps({"active_set": True, "owner_user_id": args.owner_user_id, "asset_id": args.asset_id}, ensure_ascii=True))
            return 0
        if args.sign_command == "active-get":
            asset_id = api.get_active_signature_asset_id(args.owner_user_id)
            print(json.dumps({"owner_user_id": args.owner_user_id, "asset_id": asset_id}, ensure_ascii=True))
            return 0
        if args.sign_command == "active-clear":
            api.clear_active_signature(args.owner_user_id, password=args.password)
            print(json.dumps({"active_cleared": True, "owner_user_id": args.owner_user_id}, ensure_ascii=True))
            return 0
        if args.sign_command == "active-export":
            exported = api.export_active_signature(args.owner_user_id, Path(args.output))
            print(json.dumps({"owner_user_id": args.owner_user_id, "output": str(exported)}, ensure_ascii=True))
            return 0
        if args.sign_command == "template-sign":
            result = api.sign_with_template(
                template_id=args.template_id,
                input_pdf=Path(args.input),
                signer_user=args.signer_user,
                password=args.password,
                output_pdf=Path(args.output) if args.output else None,
                dry_run=args.dry_run,
                overwrite_output=args.overwrite_output,
                reason=args.reason,
            )
            status = "DRY-RUN" if result.dry_run else "OK"
            print(f"{status}: signed pdf -> {result.output_pdf}")
            if result.sha256:
                print(f"SHA256: {result.sha256}")
            return 0
    except SignatureError as exc:
        print(f"BLOCKED: {exc}")
        return 4
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 5
    return 1

