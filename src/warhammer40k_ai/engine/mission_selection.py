from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


def _text(value: object) -> str:
    return str(value or "").strip()


def _slug(value: object) -> str:
    text = _text(value).lower()
    return "_".join(part for part in text.replace("-", " ").split() if part)


def _layouts(values: object) -> tuple[int, ...]:
    unique = {int(value) for value in list(values or [])}
    return tuple(sorted(unique))


def _string_tuple(values: object) -> tuple[str, ...]:
    return tuple(_text(value) for value in list(values or []) if _text(value))


def _normalize_force_disposition(value: object) -> str | None:
    text = _text(value)
    return _slug(text) or None


def _pairing_slot_matches(expected: str, actual: str | None) -> bool:
    if expected == "*":
        return True
    return actual is not None and expected == actual


def force_disposition_pair_key(player_a_force_disposition: object, player_b_force_disposition: object) -> str:
    normalized_a = _normalize_force_disposition(player_a_force_disposition) or "any"
    normalized_b = _normalize_force_disposition(player_b_force_disposition) or "any"
    return f"{normalized_a}__{normalized_b}"


@dataclass(frozen=True)
class ForceDisposition:
    disposition_id: str
    display_name: str
    description: str = ""
    provisional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "disposition_id", _slug(self.disposition_id))
        object.__setattr__(self, "display_name", _text(self.display_name))
        object.__setattr__(self, "description", _text(self.description))
        object.__setattr__(self, "provisional", bool(self.provisional))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class DeploymentDefinition:
    deployment_definition_id: str
    deployment_name: str
    mission_name: str
    allowed_layouts: tuple[int, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "deployment_definition_id", _slug(self.deployment_definition_id))
        object.__setattr__(self, "deployment_name", _text(self.deployment_name))
        object.__setattr__(self, "mission_name", _text(self.mission_name) or _text(self.deployment_name))
        object.__setattr__(self, "allowed_layouts", _layouts(self.allowed_layouts))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class TwistDefinition:
    twist_definition_id: str
    display_name: str
    description: str = ""
    provisional: bool = False
    is_stubbed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "twist_definition_id", _slug(self.twist_definition_id))
        object.__setattr__(self, "display_name", _text(self.display_name))
        object.__setattr__(self, "description", _text(self.description))
        object.__setattr__(self, "provisional", bool(self.provisional))
        object.__setattr__(self, "is_stubbed", bool(self.is_stubbed))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class SecondaryRuleSet:
    secondary_rule_set_id: str
    display_name: str
    default_mode: str = "tactical"
    available_modes: tuple[str, ...] = ("tactical",)
    selection_stage: str = "pregame_stub"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "secondary_rule_set_id", _slug(self.secondary_rule_set_id))
        object.__setattr__(self, "display_name", _text(self.display_name))
        object.__setattr__(self, "default_mode", _slug(self.default_mode) or "tactical")
        object.__setattr__(self, "available_modes", _string_tuple(self.available_modes) or ("tactical",))
        object.__setattr__(self, "selection_stage", _slug(self.selection_stage) or "pregame_stub")
        object.__setattr__(self, "description", _text(self.description))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class MissionDefinition:
    mission_definition_id: str
    selection_id: str
    primary_mission_name: str
    deployment_definition_id: str
    allowed_layouts: tuple[int, ...]
    secondary_rule_set_id: str
    twist_definition_id: str
    provisional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission_definition_id", _slug(self.mission_definition_id))
        object.__setattr__(self, "selection_id", _text(self.selection_id))
        object.__setattr__(self, "primary_mission_name", _text(self.primary_mission_name))
        object.__setattr__(self, "deployment_definition_id", _slug(self.deployment_definition_id))
        object.__setattr__(self, "allowed_layouts", _layouts(self.allowed_layouts))
        object.__setattr__(self, "secondary_rule_set_id", _slug(self.secondary_rule_set_id))
        object.__setattr__(self, "twist_definition_id", _slug(self.twist_definition_id))
        object.__setattr__(self, "provisional", bool(self.provisional))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class MissionPairing:
    pairing_id: str
    player_a_force_disposition: str
    player_b_force_disposition: str
    mission_definition_ids: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pairing_id", _slug(self.pairing_id))
        object.__setattr__(
            self,
            "player_a_force_disposition",
            _normalize_force_disposition(self.player_a_force_disposition) or "*",
        )
        object.__setattr__(
            self,
            "player_b_force_disposition",
            _normalize_force_disposition(self.player_b_force_disposition) or "*",
        )
        object.__setattr__(self, "mission_definition_ids", _string_tuple(self.mission_definition_ids))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def matches(self, player_a_force_disposition: str | None, player_b_force_disposition: str | None) -> bool:
        actual_a = _normalize_force_disposition(player_a_force_disposition)
        actual_b = _normalize_force_disposition(player_b_force_disposition)
        return _pairing_slot_matches(self.player_a_force_disposition, actual_a) and _pairing_slot_matches(
            self.player_b_force_disposition,
            actual_b,
        )


@dataclass(frozen=True)
class MissionPack:
    pack_id: str
    display_name: str
    short_name: str
    description: str = ""
    provisional: bool = False
    selection_priority: int = 100
    random_selection_enabled: bool = False
    default_selection_id: str | None = None
    force_dispositions: tuple[ForceDisposition, ...] = ()
    deployment_definitions: tuple[DeploymentDefinition, ...] = ()
    twist_definitions: tuple[TwistDefinition, ...] = ()
    secondary_rule_sets: tuple[SecondaryRuleSet, ...] = ()
    mission_definitions: tuple[MissionDefinition, ...] = ()
    pairings: tuple[MissionPairing, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pack_id", _slug(self.pack_id))
        object.__setattr__(self, "display_name", _text(self.display_name))
        object.__setattr__(self, "short_name", _text(self.short_name))
        object.__setattr__(self, "description", _text(self.description))
        object.__setattr__(self, "provisional", bool(self.provisional))
        object.__setattr__(self, "selection_priority", int(self.selection_priority))
        object.__setattr__(self, "random_selection_enabled", bool(self.random_selection_enabled))
        object.__setattr__(self, "default_selection_id", _text(self.default_selection_id) or None)
        object.__setattr__(self, "force_dispositions", tuple(self.force_dispositions or ()))
        object.__setattr__(self, "deployment_definitions", tuple(self.deployment_definitions or ()))
        object.__setattr__(self, "twist_definitions", tuple(self.twist_definitions or ()))
        object.__setattr__(self, "secondary_rule_sets", tuple(self.secondary_rule_sets or ()))
        object.__setattr__(self, "mission_definitions", tuple(self.mission_definitions or ()))
        object.__setattr__(self, "pairings", tuple(self.pairings or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def deployment_by_id(self, deployment_definition_id: str) -> DeploymentDefinition:
        key = _slug(deployment_definition_id)
        for definition in self.deployment_definitions:
            if definition.deployment_definition_id == key:
                return definition
        raise KeyError(f"Unknown deployment definition '{deployment_definition_id}' in pack '{self.pack_id}'.")

    def mission_by_id(self, mission_definition_id: str) -> MissionDefinition:
        key = _slug(mission_definition_id)
        for definition in self.mission_definitions:
            if definition.mission_definition_id == key:
                return definition
        raise KeyError(f"Unknown mission definition '{mission_definition_id}' in pack '{self.pack_id}'.")

    def secondary_rule_set_by_id(self, secondary_rule_set_id: str) -> SecondaryRuleSet:
        key = _slug(secondary_rule_set_id)
        for definition in self.secondary_rule_sets:
            if definition.secondary_rule_set_id == key:
                return definition
        raise KeyError(f"Unknown secondary rule set '{secondary_rule_set_id}' in pack '{self.pack_id}'.")

    def twist_by_id(self, twist_definition_id: str) -> TwistDefinition:
        key = _slug(twist_definition_id)
        for definition in self.twist_definitions:
            if definition.twist_definition_id == key:
                return definition
        raise KeyError(f"Unknown twist definition '{twist_definition_id}' in pack '{self.pack_id}'.")

    def mission_selection_options(
        self,
        *,
        player_a_force_disposition: str | None,
        player_b_force_disposition: str | None,
    ) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        pair_key = force_disposition_pair_key(player_a_force_disposition, player_b_force_disposition)
        for pairing in self.pairings:
            if not pairing.matches(player_a_force_disposition, player_b_force_disposition):
                continue
            for mission_definition_id in pairing.mission_definition_ids:
                mission_definition = self.mission_by_id(mission_definition_id)
                deployment_definition = self.deployment_by_id(mission_definition.deployment_definition_id)
                secondary_rule_set = self.secondary_rule_set_by_id(mission_definition.secondary_rule_set_id)
                twist_definition = self.twist_by_id(mission_definition.twist_definition_id)
                options.append(
                    {
                        "id": mission_definition.selection_id,
                        "combination_id": mission_definition.selection_id,
                        "primary": mission_definition.primary_mission_name,
                        "mission_definition_id": mission_definition.mission_definition_id,
                        "deployment": deployment_definition.deployment_name,
                        "deployment_definition_id": deployment_definition.deployment_definition_id,
                        "layouts": list(mission_definition.allowed_layouts or deployment_definition.allowed_layouts),
                        "pack_id": self.pack_id,
                        "pack_display_name": self.display_name,
                        "pack_short_name": self.short_name,
                        "random_selection_enabled": bool(self.random_selection_enabled),
                        "pairing_id": pairing.pairing_id,
                        "force_disposition_pair": [player_a_force_disposition, player_b_force_disposition],
                        "force_disposition_pair_key": pair_key,
                        "secondary_rule_set_id": secondary_rule_set.secondary_rule_set_id,
                        "secondary_rule_set_name": secondary_rule_set.display_name,
                        "secondary_mission_mode": secondary_rule_set.default_mode,
                        "supported_secondary_modes": list(secondary_rule_set.available_modes),
                        "secondary_selection_stage": secondary_rule_set.selection_stage,
                        "twist_definition_id": twist_definition.twist_definition_id,
                        "twist_name": twist_definition.display_name,
                        "twist_is_stubbed": twist_definition.is_stubbed,
                        "provisional": bool(self.provisional or mission_definition.provisional or twist_definition.provisional),
                        "metadata": dict(mission_definition.metadata or {}),
                    }
                )
        return options

    def default_selection_option(self) -> dict[str, Any]:
        selection_id = _text(self.default_selection_id)
        if not selection_id:
            raise RuntimeError(f"Mission pack '{self.pack_id}' does not define a default selection.")
        for option in self.mission_selection_options(player_a_force_disposition=None, player_b_force_disposition=None):
            if _text(option.get("id")) == selection_id:
                return dict(option)
        raise RuntimeError(
            f"Default mission selection '{selection_id}' is not available in pack '{self.pack_id}'."
        )


_SHARED_DEPLOYMENTS: tuple[DeploymentDefinition, ...] = (
    DeploymentDefinition(
        deployment_definition_id="tipping_point",
        deployment_name="Tipping Point",
        mission_name="Tipping Point",
        allowed_layouts=(1, 2, 4, 6, 7, 8),
    ),
    DeploymentDefinition(
        deployment_definition_id="hammer_and_anvil",
        deployment_name="Hammer and Anvil",
        mission_name="Hammer and Anvil",
        allowed_layouts=(1, 7, 8),
    ),
    DeploymentDefinition(
        deployment_definition_id="search_and_destroy",
        deployment_name="Search and Destroy",
        mission_name="Search and Destroy",
        allowed_layouts=(1, 2, 3, 4, 6),
    ),
    DeploymentDefinition(
        deployment_definition_id="crucible_of_battle",
        deployment_name="Crucible of Battle",
        mission_name="Crucible of Battle",
        allowed_layouts=(1, 2, 3, 4, 6),
    ),
    DeploymentDefinition(
        deployment_definition_id="sweeping_engagement",
        deployment_name="Sweeping Engagement",
        mission_name="Sweeping Engagement",
        allowed_layouts=(3, 5),
    ),
    DeploymentDefinition(
        deployment_definition_id="dawn_of_war",
        deployment_name="Dawn of War",
        mission_name="Dawn of War",
        allowed_layouts=(5,),
    ),
)

_TWIST_NONE = TwistDefinition(
    twist_definition_id="none",
    display_name="No Twist",
    description="Current Chapter Approved matched play has no separate twist step.",
    provisional=False,
    is_stubbed=False,
)

_TWIST_PREVIEW_PLACEHOLDER = TwistDefinition(
    twist_definition_id="preview_twist_placeholder",
    display_name="Preview Twist Placeholder",
    description="Explicit placeholder until final 11th-edition twist rules are confirmed.",
    provisional=True,
    is_stubbed=True,
)

_CA_SECONDARY_RULES = SecondaryRuleSet(
    secondary_rule_set_id="chapter_approved_2025_2026",
    display_name="Chapter Approved 2025-26 Secondary Rules",
    default_mode="tactical",
    available_modes=("tactical", "fixed"),
    selection_stage="command_phase",
    description="Current competitive pack still used until 11th edition releases.",
)

_PREVIEW_SECONDARY_RULES = SecondaryRuleSet(
    secondary_rule_set_id="provisional_11e_preview",
    display_name="11E Preview Secondary Placeholder",
    default_mode="tactical",
    available_modes=("tactical",),
    selection_stage="pregame_stub",
    description="Preview-era placeholder only; not final release data.",
)


def _chapter_approved_missions() -> tuple[MissionDefinition, ...]:
    definitions: list[MissionDefinition] = []
    combos = (
        ("A", "Take and Hold", "tipping_point", (1, 2, 4, 6, 7, 8)),
        ("B", "Supply Drop", "tipping_point", (1, 2, 4, 6, 7, 8)),
        ("C", "Linchpin", "tipping_point", (1, 2, 4, 6, 7, 8)),
        ("D", "Scorched Earth", "tipping_point", (1, 2, 4, 6, 7, 8)),
        ("E", "Take and Hold", "hammer_and_anvil", (1, 7, 8)),
        ("F", "Hidden Supplies", "hammer_and_anvil", (1, 7, 8)),
        ("G", "Purge the Foe", "hammer_and_anvil", (1, 7, 8)),
        ("H", "Supply Drop", "hammer_and_anvil", (1, 7, 8)),
        ("I", "Hidden Supplies", "search_and_destroy", (1, 2, 3, 4, 6)),
        ("J", "Linchpin", "search_and_destroy", (1, 2, 3, 4, 6)),
        ("K", "Scorched Earth", "search_and_destroy", (1, 2, 3, 4, 6)),
        ("L", "Take and Hold", "search_and_destroy", (1, 2, 3, 4, 6)),
        ("M", "Purge the Foe", "crucible_of_battle", (1, 2, 3, 4, 6)),
        ("N", "Hidden Supplies", "crucible_of_battle", (1, 2, 3, 4, 6)),
        ("O", "Terraform", "crucible_of_battle", (1, 2, 3, 4, 6)),
        ("P", "Scorched Earth", "crucible_of_battle", (1, 2, 3, 4, 6)),
        ("Q", "Supply Drop", "sweeping_engagement", (3, 5)),
        ("R", "Terraform", "sweeping_engagement", (3, 5)),
        ("S", "Linchpin", "dawn_of_war", (5,)),
        ("T", "Purge the Foe", "dawn_of_war", (5,)),
    )
    for selection_id, primary, deployment_definition_id, layouts in combos:
        definitions.append(
            MissionDefinition(
                mission_definition_id=f"chapter_approved_{selection_id.lower()}",
                selection_id=selection_id,
                primary_mission_name=primary,
                deployment_definition_id=deployment_definition_id,
                allowed_layouts=layouts,
                secondary_rule_set_id=_CA_SECONDARY_RULES.secondary_rule_set_id,
                twist_definition_id=_TWIST_NONE.twist_definition_id,
                metadata={"legacy_combination_id": selection_id},
            )
        )
    return tuple(definitions)


def _provisional_preview_missions() -> tuple[MissionDefinition, ...]:
    return (
        MissionDefinition(
            mission_definition_id="preview_assault_assault",
            selection_id="P11-AA-1",
            primary_mission_name="Purge the Foe",
            deployment_definition_id="crucible_of_battle",
            allowed_layouts=(1, 2, 3, 4, 6),
            secondary_rule_set_id=_PREVIEW_SECONDARY_RULES.secondary_rule_set_id,
            twist_definition_id=_TWIST_PREVIEW_PLACEHOLDER.twist_definition_id,
            provisional=True,
            metadata={"preview_note": "Placeholder assault mirror pairing."},
        ),
        MissionDefinition(
            mission_definition_id="preview_assault_bulwark",
            selection_id="P11-AB-1",
            primary_mission_name="Take and Hold",
            deployment_definition_id="tipping_point",
            allowed_layouts=(1, 2, 4, 6, 7, 8),
            secondary_rule_set_id=_PREVIEW_SECONDARY_RULES.secondary_rule_set_id,
            twist_definition_id=_TWIST_PREVIEW_PLACEHOLDER.twist_definition_id,
            provisional=True,
            metadata={"preview_note": "Placeholder assault vs bulwark pairing."},
        ),
        MissionDefinition(
            mission_definition_id="preview_bulwark_bulwark",
            selection_id="P11-BB-1",
            primary_mission_name="Linchpin",
            deployment_definition_id="dawn_of_war",
            allowed_layouts=(5,),
            secondary_rule_set_id=_PREVIEW_SECONDARY_RULES.secondary_rule_set_id,
            twist_definition_id=_TWIST_PREVIEW_PLACEHOLDER.twist_definition_id,
            provisional=True,
            metadata={"preview_note": "Placeholder bulwark mirror pairing."},
        ),
        MissionDefinition(
            mission_definition_id="preview_siege_assault",
            selection_id="P11-SA-1",
            primary_mission_name="Scorched Earth",
            deployment_definition_id="hammer_and_anvil",
            allowed_layouts=(1, 7, 8),
            secondary_rule_set_id=_PREVIEW_SECONDARY_RULES.secondary_rule_set_id,
            twist_definition_id=_TWIST_PREVIEW_PLACEHOLDER.twist_definition_id,
            provisional=True,
            metadata={"preview_note": "Placeholder siege vs assault pairing."},
        ),
        MissionDefinition(
            mission_definition_id="preview_siege_bulwark",
            selection_id="P11-SB-1",
            primary_mission_name="Terraform",
            deployment_definition_id="sweeping_engagement",
            allowed_layouts=(3, 5),
            secondary_rule_set_id=_PREVIEW_SECONDARY_RULES.secondary_rule_set_id,
            twist_definition_id=_TWIST_PREVIEW_PLACEHOLDER.twist_definition_id,
            provisional=True,
            metadata={"preview_note": "Placeholder siege vs bulwark pairing."},
        ),
    )


_CHAPTER_APPROVED_MISSIONS = _chapter_approved_missions()
_PREVIEW_MISSIONS = _provisional_preview_missions()

_CHAPTER_APPROVED_PACK = MissionPack(
    pack_id="chapter_approved_2025_2026",
    display_name="Chapter Approved 2025-26",
    short_name="CA25-26",
    description="Current competitive mission pack used until 11th edition releases.",
    provisional=False,
    selection_priority=10,
    random_selection_enabled=True,
    default_selection_id="M",
    deployment_definitions=_SHARED_DEPLOYMENTS,
    twist_definitions=(_TWIST_NONE,),
    secondary_rule_sets=(_CA_SECONDARY_RULES,),
    mission_definitions=_CHAPTER_APPROVED_MISSIONS,
    pairings=(
        MissionPairing(
            pairing_id="chapter_approved_open_rotation",
            player_a_force_disposition="*",
            player_b_force_disposition="*",
            mission_definition_ids=tuple(
                definition.mission_definition_id for definition in _CHAPTER_APPROVED_MISSIONS
            ),
        ),
    ),
)

_PREVIEW_FORCE_DISPOSITIONS: tuple[ForceDisposition, ...] = (
    ForceDisposition("Assault", "Assault", description="Aggressive force posture.", provisional=True),
    ForceDisposition("Bulwark", "Bulwark", description="Defensive force posture.", provisional=True),
    ForceDisposition("Siege", "Siege", description="Attritional pressure posture.", provisional=True),
)

_PREVIEW_PACK = MissionPack(
    pack_id="provisional_11e_preview",
    display_name="11E Preview Matched Play",
    short_name="11E Preview",
    description="Preview-era mission-pack placeholder driven by force dispositions.",
    provisional=True,
    selection_priority=40,
    random_selection_enabled=False,
    deployment_definitions=_SHARED_DEPLOYMENTS,
    twist_definitions=(_TWIST_PREVIEW_PLACEHOLDER,),
    secondary_rule_sets=(_PREVIEW_SECONDARY_RULES,),
    force_dispositions=_PREVIEW_FORCE_DISPOSITIONS,
    mission_definitions=_PREVIEW_MISSIONS,
    pairings=(
        MissionPairing("preview_assault_assault", "assault", "assault", ("preview_assault_assault",)),
        MissionPairing("preview_assault_bulwark", "assault", "bulwark", ("preview_assault_bulwark",)),
        MissionPairing("preview_bulwark_assault", "bulwark", "assault", ("preview_assault_bulwark",)),
        MissionPairing("preview_bulwark_bulwark", "bulwark", "bulwark", ("preview_bulwark_bulwark",)),
        MissionPairing("preview_siege_assault", "siege", "assault", ("preview_siege_assault",)),
        MissionPairing("preview_assault_siege", "assault", "siege", ("preview_siege_assault",)),
        MissionPairing("preview_siege_bulwark", "siege", "bulwark", ("preview_siege_bulwark",)),
        MissionPairing("preview_bulwark_siege", "bulwark", "siege", ("preview_siege_bulwark",)),
        MissionPairing("preview_siege_siege", "siege", "siege", ("preview_siege_assault", "preview_siege_bulwark")),
    ),
)

MISSION_PACKS: tuple[MissionPack, ...] = (
    _CHAPTER_APPROVED_PACK,
    _PREVIEW_PACK,
)

_MISSION_PACKS_BY_ID = {pack.pack_id: pack for pack in MISSION_PACKS}
DEFAULT_MISSION_PACK_ID = _CHAPTER_APPROVED_PACK.pack_id


def iter_mission_packs() -> tuple[MissionPack, ...]:
    return MISSION_PACKS


def get_mission_pack(pack_id: str | None) -> MissionPack:
    key = _slug(pack_id or DEFAULT_MISSION_PACK_ID)
    if key not in _MISSION_PACKS_BY_ID:
        raise KeyError(f"Unknown mission pack '{pack_id}'.")
    return _MISSION_PACKS_BY_ID[key]


def get_default_mission_pack() -> MissionPack:
    return get_mission_pack(DEFAULT_MISSION_PACK_ID)


def _player_force_disposition(player: object | None) -> str | None:
    if player is None:
        return None
    direct = _normalize_force_disposition(getattr(player, "chosen_force_disposition", None))
    if direct:
        return direct
    army = getattr(player, "army", None)
    get_army = getattr(player, "get_army", None)
    if army is None and callable(get_army):
        army = get_army()
    army_force = _normalize_force_disposition(getattr(army, "force_disposition", None))
    if army_force:
        return army_force
    allowed = list(getattr(army, "allowed_force_dispositions", []) or [])
    if len(allowed) == 1:
        return _normalize_force_disposition(allowed[0])
    return None


def build_mission_selection_catalog(
    game: object | None = None,
    *,
    include_default_pack: bool = True,
    include_provisional_packs: bool = True,
    mission_pack_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    players = list(getattr(game, "players", []) or []) if game is not None else []
    player_a_force_disposition = _player_force_disposition(players[0]) if players else None
    player_b_force_disposition = _player_force_disposition(players[1]) if len(players) > 1 else None
    requested_pack_ids = {_slug(value) for value in list(mission_pack_ids or []) if _slug(value)}
    options: list[dict[str, Any]] = []
    for pack in sorted(MISSION_PACKS, key=lambda entry: (entry.selection_priority, entry.display_name.lower())):
        if requested_pack_ids and pack.pack_id not in requested_pack_ids:
            continue
        if not include_default_pack and pack.pack_id == DEFAULT_MISSION_PACK_ID:
            continue
        if not include_provisional_packs and pack.provisional:
            continue
        pack_options = pack.mission_selection_options(
            player_a_force_disposition=player_a_force_disposition,
            player_b_force_disposition=player_b_force_disposition,
        )
        if not pack_options:
            continue
        options.extend(dict(option) for option in pack_options)
    return options


def iter_mission_combinations(combos: Iterable[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if combos is not None:
        return [dict(entry) for entry in list(combos or [])]
    return [
        dict(entry)
        for entry in get_default_mission_pack().mission_selection_options(
            player_a_force_disposition=None,
            player_b_force_disposition=None,
        )
    ]


def iter_random_mission_options(game: object | None = None) -> list[dict[str, Any]]:
    del game
    pack = get_default_mission_pack()
    return pack.mission_selection_options(
        player_a_force_disposition=None,
        player_b_force_disposition=None,
    )


def default_mission_selection() -> tuple[dict[str, Any], int]:
    option = get_default_mission_pack().default_selection_option()
    layouts = list(option.get("layouts", []) or [])
    if not layouts:
        raise RuntimeError("Default mission selection has no terrain layouts.")
    return option, int(layouts[0])


def selected_mission_info_from_choice(
    choice: Mapping[str, Any],
    *,
    layout: object,
    existing_secondary_mode: str | None = None,
) -> dict[str, Any]:
    from .deployment_validation import normalize_layout_selection

    selection = dict(choice or {})
    selected_layout = normalize_layout_selection(
        layout,
        allowed_layouts=list(selection.get("layouts", []) or []),
    )
    secondary_mission_mode = _slug(existing_secondary_mode) or _slug(selection.get("secondary_mission_mode")) or "tactical"
    return {
        "combination_id": _text(selection.get("combination_id") or selection.get("id")),
        "primary": _text(selection.get("primary")),
        "deployment": _text(selection.get("deployment")),
        "layout": int(selected_layout),
        "layouts": [int(value) for value in list(selection.get("layouts", []) or [])],
        "mission_pack_id": _text(selection.get("pack_id")),
        "mission_pack_name": _text(selection.get("pack_display_name")),
        "mission_pack_short_name": _text(selection.get("pack_short_name")),
        "mission_definition_id": _text(selection.get("mission_definition_id")),
        "deployment_definition_id": _text(selection.get("deployment_definition_id")),
        "pairing_id": _text(selection.get("pairing_id")),
        "force_disposition_pair": list(selection.get("force_disposition_pair", []) or []),
        "force_disposition_pair_key": _text(selection.get("force_disposition_pair_key")),
        "secondary_rule_set_id": _text(selection.get("secondary_rule_set_id")),
        "secondary_rule_set_name": _text(selection.get("secondary_rule_set_name")),
        "secondary_mission_mode": secondary_mission_mode,
        "supported_secondary_modes": [
            _slug(value)
            for value in list(selection.get("supported_secondary_modes", []) or [])
            if _slug(value)
        ],
        "secondary_selection_stage": _text(selection.get("secondary_selection_stage")),
        "twist_definition_id": _text(selection.get("twist_definition_id")),
        "twist_name": _text(selection.get("twist_name")),
        "twist_is_stubbed": bool(selection.get("twist_is_stubbed", False)),
        "provisional": bool(selection.get("provisional", False)),
        "metadata": dict(selection.get("metadata", {}) or {}),
    }


def find_matching_option(
    options: Iterable[Mapping[str, Any]],
    *,
    pack_id: str | None,
    combination_id: str | None,
) -> dict[str, Any] | None:
    expected_pack_id = _text(pack_id)
    expected_combination_id = _text(combination_id)
    for option in list(options or []):
        if _text(option.get("pack_id")) != expected_pack_id:
            continue
        if _text(option.get("combination_id") or option.get("id")) != expected_combination_id:
            continue
        return dict(option)
    return None


__all__ = [
    "DEFAULT_MISSION_PACK_ID",
    "DeploymentDefinition",
    "ForceDisposition",
    "MissionDefinition",
    "MissionPack",
    "MissionPairing",
    "SecondaryRuleSet",
    "TwistDefinition",
    "build_mission_selection_catalog",
    "default_mission_selection",
    "find_matching_option",
    "force_disposition_pair_key",
    "get_default_mission_pack",
    "get_mission_pack",
    "iter_mission_combinations",
    "iter_mission_packs",
    "iter_random_mission_options",
    "selected_mission_info_from_choice",
]
