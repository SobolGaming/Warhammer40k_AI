from __future__ import annotations

from warhammer40k_ai.units.unit_mixins.state_attachment_mixin import StateAttachmentMixin


class _AttachmentUnit(StateAttachmentMixin):
    def __init__(self, *, can_attach=None):
        self.can_be_attached_to = list(can_attach or [])
        self.attached_to = None
        self.support_joined_to = None

    def has_joined_support_ability(self) -> bool:
        return self.support_joined_to is not None


def test_self_attached_leader_resolves_to_self_without_recursion() -> None:
    unit = _AttachmentUnit(can_attach=["bodyguard-datasheet"])
    unit.attached_to = unit

    assert unit.is_leader is True
    assert unit.get_attachment_target() is None
    assert unit.get_attached_unit_root() is unit


def test_joined_support_self_link_resolves_to_self_without_recursion() -> None:
    unit = _AttachmentUnit()
    unit.support_joined_to = unit

    assert unit.get_attachment_target() is None
    assert unit.get_attached_unit_root() is unit
