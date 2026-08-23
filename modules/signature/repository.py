from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import SignatureAsset, UserSignatureTemplate


class SignatureRepository(ABC):
    @abstractmethod
    def add_asset(self, asset: SignatureAsset) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_asset(self, asset_id: str) -> SignatureAsset | None:
        raise NotImplementedError

    @abstractmethod
    def upsert_template(self, template: UserSignatureTemplate) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_templates(self, owner_user_id: str) -> list[UserSignatureTemplate]:
        raise NotImplementedError

    @abstractmethod
    def list_global_templates(self) -> list[UserSignatureTemplate]:
        raise NotImplementedError

    @abstractmethod
    def get_template(self, template_id: str) -> UserSignatureTemplate | None:
        raise NotImplementedError

    @abstractmethod
    def delete_template(self, template_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_active_signature_asset(self, owner_user_id: str, asset_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_active_signature_asset_id(self, owner_user_id: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def clear_active_signature_asset(self, owner_user_id: str) -> None:
        raise NotImplementedError
