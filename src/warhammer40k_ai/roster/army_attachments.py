"""Build-side attachment records for army mustering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if text:
        return text
    raise ValueError(f"{field_name} is required.")


@dataclass
class AttachmentBinding:
    """Build-time attachment choices selected during army construction."""

    binding_id: str
    bodyguard_entry_id: str
    leader_entry_id: str | None = None
    support_entry_id: str | None = None

    def __post_init__(self) -> None:
        self.binding_id = _required_text(self.binding_id, field_name="binding_id")
        self.bodyguard_entry_id = _required_text(
            self.bodyguard_entry_id,
            field_name="bodyguard_entry_id",
        )
        self.leader_entry_id = _optional_text(self.leader_entry_id)
        self.support_entry_id = _optional_text(self.support_entry_id)
        if self.leader_entry_id is None and self.support_entry_id is None:
            raise ValueError(
                "AttachmentBinding requires at least one of leader_entry_id or support_entry_id."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "bodyguard_entry_id": self.bodyguard_entry_id,
            "leader_entry_id": self.leader_entry_id,
            "support_entry_id": self.support_entry_id,
        }

    @classmethod
    def from_dict(
        cls,
        data: "AttachmentBinding | Mapping[str, Any]",
    ) -> "AttachmentBinding":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("AttachmentBinding data must be a mapping or AttachmentBinding.")
        return cls(
            binding_id=str(data.get("binding_id", "") or ""),
            bodyguard_entry_id=str(data.get("bodyguard_entry_id", "") or ""),
            leader_entry_id=data.get("leader_entry_id"),
            support_entry_id=data.get("support_entry_id"),
        )
