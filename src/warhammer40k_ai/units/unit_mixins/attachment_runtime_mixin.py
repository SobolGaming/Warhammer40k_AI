"""Attachment-runtime helpers kept separate from the core state attachment mixin."""

from __future__ import annotations

from ._common import *


class AttachmentRuntimeMixin:
    def initialize_attachment_runtime_state(self) -> None:
        self.build_entry_id = None
        self._leader_attachment_binding_id = None
        self._leader_attachment_binding_source = None
        self._support_attachment_binding_id = None
        self._support_attachment_binding_source = None
        self._leader_slot_binding_id = None
        self._leader_slot_binding_source = None
        self._support_slot_binding_id = None
        self._support_slot_binding_source = None

    @staticmethod
    def _normalize_attachment_runtime_text(value: object) -> str | None:
        text = str(value or "").strip()
        return text or None

    def set_build_entry_id(self, entry_id: object) -> None:
        self.build_entry_id = self._normalize_attachment_runtime_text(entry_id)

    def get_build_entry_id(self) -> str | None:
        return self._normalize_attachment_runtime_text(getattr(self, "build_entry_id", None))

    def leader_attachment_slot_limit(self) -> int:
        max_fn = getattr(self, "max_attached_leaders", None)
        if callable(max_fn):
            try:
                return max(0, int(max_fn() or 0))
            except (TypeError, ValueError):
                return 0
        return 1

    def support_attachment_slot_limit(self) -> int:
        return 1

    def support_attachment_requires_bodyguard(self) -> bool:
        return True

    def has_build_authored_leader_attachment(self) -> bool:
        return bool(
            self._normalize_attachment_runtime_text(getattr(self, "_leader_attachment_binding_id", None))
            and str(getattr(self, "_leader_attachment_binding_source", "") or "").strip().lower() == "build"
        )

    def has_build_authored_support_attachment(self) -> bool:
        return bool(
            self._normalize_attachment_runtime_text(getattr(self, "_support_attachment_binding_id", None))
            and str(getattr(self, "_support_attachment_binding_source", "") or "").strip().lower() == "build"
        )

    def _mark_leader_attachment_binding(
        self,
        bodyguard: "Unit" | None,
        *,
        binding_id: object,
        source: object,
    ) -> None:
        normalized_binding_id = self._normalize_attachment_runtime_text(binding_id)
        normalized_source = self._normalize_attachment_runtime_text(source)
        self._leader_attachment_binding_id = normalized_binding_id
        self._leader_attachment_binding_source = normalized_source
        if bodyguard is not None:
            bodyguard._leader_slot_binding_id = normalized_binding_id
            bodyguard._leader_slot_binding_source = normalized_source

    def _clear_leader_attachment_binding(self, bodyguard: "Unit" | None = None) -> None:
        self._mark_leader_attachment_binding(bodyguard, binding_id=None, source=None)

    def _mark_support_attachment_binding(
        self,
        bodyguard: "Unit" | None,
        *,
        binding_id: object,
        source: object,
    ) -> None:
        normalized_binding_id = self._normalize_attachment_runtime_text(binding_id)
        normalized_source = self._normalize_attachment_runtime_text(source)
        self._support_attachment_binding_id = normalized_binding_id
        self._support_attachment_binding_source = normalized_source
        if bodyguard is not None:
            bodyguard._support_slot_binding_id = normalized_binding_id
            bodyguard._support_slot_binding_source = normalized_source

    def _clear_support_attachment_binding(self, bodyguard: "Unit" | None = None) -> None:
        self._mark_support_attachment_binding(bodyguard, binding_id=None, source=None)
