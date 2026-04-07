from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.utility.calcs import measure_path_distance


_ADVANCE_NO_ROLL_TEXT = (
    'Each time this unit Advances, do not make an Advance roll. Instead, until the end of the '
    'phase, add 6" to the Move characteristic of models in this unit.'
)
_ADVANCE_NO_ROLL_PHASE_MOVE_TEXT = (
    "Each time this model's unit Advances, do not make an Advance roll for it. Instead, until the end of the phase, "
    'add 6" to the Move characteristic of models in that unit. In addition, each time a model in that unit makes a '
    "Normal, Advance or Fall Back move, until that move is finished, it can move horizontally through models and "
    "terrain features (it cannot finish a move on top of another model or its base)."
)
_LEADING_ADVANCE_VERTICAL_TEXT = (
    'While this model is leading a unit, each time that unit Advances, do not make an Advance roll. '
    'Instead, until the end of the phase, add 6" to the Move characteristic of models in that unit '
    'and each time a model in that unit makes an Advance move, ignore any vertical distance when '
    'determining the total distance that model can be moved during that move.'
)


class _DummyPlayer:
    def __init__(self, name: str = "P1") -> None:
        self.name = name
        self.game = None


class _MockDatasheet:
    def __init__(
        self,
        ability_text: str,
        *,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
    ) -> None:
        self.id = "advance-no-roll"
        self.name = "Swift Unit"
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or ["INFANTRY"])
        self.faction_keywords = list(faction_keywords or ["TEST"])
        self.attached_to = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": "Fixed Advance",
                "description": ability_text,
                "type": "",
                "parameter": "",
            }
        ]
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    ability_text: str = _ADVANCE_NO_ROLL_TEXT,
    *,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            ability_text,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


class _LeaderDatasheet(_MockDatasheet):
    def __init__(self) -> None:
        super().__init__(_LEADING_ADVANCE_VERTICAL_TEXT)
        self.id = "leader-advance"
        self.name = "Leader"
        self.attached_to = ["bodyguard-advance"]


class _BodyguardDatasheet:
    def __init__(self) -> None:
        self.id = "bodyguard-advance"
        self.name = "Bodyguard"
        self.faction_data = {"name": "Test"}
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["TEST"]
        self.attached_to = []
        self.attached_to_names = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def test_advance_no_roll_is_parsed_and_skips_roll():
    unit = _make_unit()
    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6

    with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
        advance = unit.prepare_advance()

    assert int(advance or 0) == 6
    roll_mock.assert_not_called()


def test_advance_no_roll_ignores_advance_roll_modifiers():
    unit = _make_unit()
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["advance_roll_modifier"] = 3
    unit.special_rules = sr

    assert unit._apply_advance_roll_modifiers(1) == 6


def test_advance_no_roll_with_phase_move_through_models_and_terrain():
    from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules

    unit = _make_unit(_ADVANCE_NO_ROLL_PHASE_MOVE_TEXT)
    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6

    with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
        advance = unit.prepare_advance()
    assert int(advance or 0) == 6
    roll_mock.assert_not_called()

    sr = dict(getattr(unit, "special_rules", {}) or {})
    assert set(sr.get("bearer_unit_phase_move_types", []) or []) >= {"move", "advance", "fall_back"}

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
    assert bool(move_rules.get("can_move_through_enemy_models"))
    assert bool(move_rules.get("can_move_through_terrain"))
    assert bool(move_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range"))

    advance_rules = get_validation_rules(MovementType.ADVANCE, moving_unit=unit)
    assert bool(advance_rules.get("can_move_through_enemy_models"))
    assert bool(advance_rules.get("can_move_through_terrain"))
    assert bool(advance_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(advance_rules.get("cannot_end_in_engagement_range"))


def test_hammer_of_the_emperor_iron_tread_squadron_advance_support():
    from warhammer40k_ai.rules.astra_militarum_detachments import AstraMilitarumDetachmentManager
    from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules

    squadron = _make_unit(
        ability_text="",
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    non_squadron = _make_unit(
        ability_text="",
        keywords=["INFANTRY", "REGIMENT"],
        faction_keywords=["ASTRA MILITARUM"],
    )

    army = Army.with_detachment(faction="Astra Militarum", detachment_type="Hammer of the Emperor", points_limit=2000)
    army.faction_id = "AM"
    army.player = _DummyPlayer()
    army.units = [squadron, non_squadron]
    for unit in army.units:
        unit.parent_army = army
    army.astra_militarum_detachments = AstraMilitarumDetachmentManager(army)

    effect = squadron._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6
    assert "Iron Tread" in str(effect.get("source", "") or "")

    with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
        prepared = squadron.prepare_advance()
    assert int(prepared or 0) == 6
    roll_mock.assert_not_called()

    no_effect = non_squadron._get_advance_no_roll_effect()
    assert no_effect is None

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=squadron)
    assert bool(move_rules.get("cannot_move_within_engagement_range", False))

    advance_rules = get_validation_rules(MovementType.ADVANCE, moving_unit=squadron)
    assert bool(advance_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(advance_rules.get("cannot_end_in_engagement_range"))


def test_leading_advance_ignore_vertical_distance():
    leader = Unit(_LeaderDatasheet())
    bodyguard = Unit(_BodyguardDatasheet())

    army = Army.with_detachment(faction="Test", detachment_type="Test", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = [leader, bodyguard]
    for u in army.units:
        u.parent_army = army

    assert bodyguard._get_advance_no_roll_effect() is None
    assert not bodyguard.advance_ignores_vertical_distance()

    leader.attach_to_unit(bodyguard)
    effect = bodyguard._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6
    assert bodyguard.advance_ignores_vertical_distance()

    path = [(0.0, 0.0, 0.0), (0.0, 6.0, 5.0)]
    advance_dist = measure_path_distance(path, bodyguard, movement_type="advance")
    assert abs(advance_dist - 6.0) < 1e-6
    move_dist = measure_path_distance(path, bodyguard, movement_type="move")
    assert move_dist > 6.0
