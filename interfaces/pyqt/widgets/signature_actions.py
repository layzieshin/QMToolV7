from __future__ import annotations

import tempfile
from pathlib import Path
from dataclasses import replace


class SignatureActions:
    """Small orchestration helper to keep SignatureWorkspace focused on UI."""

    def __init__(self, signature_api) -> None:
        self._api = signature_api

    def list_template_names(self, user_id: str) -> list[str]:
        return [template.name for template in self._api.list_user_signature_templates(user_id)]

    def list_templates_for_select(self, user_id: str) -> list[tuple[str, str]]:
        return [(template.template_id, template.name) for template in self._api.list_user_signature_templates(user_id)]

    def get_template_by_name(self, user_id: str, template_name: str):
        templates = self._api.list_user_signature_templates(user_id)
        return next((template for template in templates if template.name == template_name), None)

    def get_template_by_id(self, user_id: str, template_id: str):
        templates = self._api.list_user_signature_templates(user_id)
        return next((template for template in templates if template.template_id == template_id), None)

    def sign_from_form(
        self,
        form,
        *,
        user_id: str,
        username: str,
        display_name: str | None = None,
        placement_override=None,
        layout_override=None,
    ) -> object:
        selected_profile = form.selected_profile()
        request = form.build_request(signer_user=username, reason="pyqt_signature_profile" if selected_profile else "pyqt_signature_adhoc")
        base_layout = layout_override or request.layout
        base_placement = placement_override or request.placement
        runtime_layout = replace(
            base_layout,
            name_text=(display_name or username) if request.layout.show_name else request.layout.name_text,
        )
        request = replace(request, placement=base_placement, layout=runtime_layout)
        if selected_profile:
            selected = self.get_template_by_id(user_id, selected_profile)
            if selected is None:
                raise RuntimeError(f"Signaturprofil '{selected_profile}' wurde nicht gefunden")
            return self._api.sign_with_template(
                template_id=selected.template_id,
                input_pdf=request.input_pdf,
                output_pdf=request.output_pdf,
                signer_user=username,
                password=form.password.text().strip() or None,
                dry_run=form.dry_run.isChecked(),
                overwrite_output=False,
                reason="pyqt_signature_profile",
                placement_override=base_placement,
                layout_override=runtime_layout,
            )
        if request.signature_png is None and request.layout.show_signature:
            active = self._api.get_active_signature_asset_id(user_id)
            if active:
                tmp_dir = Path(tempfile.mkdtemp(prefix="qmtool-active-signature-"))
                exported = self._api.export_active_signature(user_id, tmp_dir / "active-signature.png")
                request = replace(request, signature_png=exported)
        return self._api.sign_with_fixed_position(request)

    def build_profile_preview_payload(self, form, *, user_id: str) -> dict[str, object]:
        selected_name = form.selected_profile()
        if selected_name is None:
            return {
                "modus": "eigene_parameter",
                "hinweis": "Dropdown auf ein gespeichertes Signaturprofil stellen, um die Profilvorschau zu sehen.",
                "live_preview": form.preview.text(),
            }
        selected = self.get_template_by_id(user_id, selected_name)
        if selected is None:
            return {"error": f"Profil '{selected_name}' nicht gefunden"}
        return {"selected_profile": selected.name, "template": selected}
