from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


THUNDERSHOCK_TEXT = (
    "In your Shooting phase, each time you select a target for this model's thundercoil harpoon, roll one D6 for the target "
    "unit and one D6 for each other enemy unit within 6\" of the target unit. On a 4+, the unit being rolled for is struck "
    "by arcing energies; after resolving all of this model's attacks against the target unit, each unit struck by arcing "
    "energies suffers D3 mortal wounds."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "12",
                "Sv": "3",
                "W": "20",
                "Ld": "6",
                "OC": "8",
                "base_size": "170x109mm",
                "inv_sv": "5",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str,
    faction_keywords,
    keywords=None,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army.with_detachment("Imperial Knights", "Noble Lance")
    ik_army.faction_id = "QI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ik_player = Player("IK", control=PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    return game, ik_army, enemy_army, ik_player, enemy_player


def _deploy(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def _make_ranged_profile(name: str) -> WargearProfile:
    profile = WargearProfile(
        "default",
        {
            "range": "18",
            "A": "1",
            "BS_WS": "2+",
            "S": "20",
            "AP": "-6",
            "D": "12",
            "description": "",
        },
    )
    profile.parent_wargear = SimpleNamespace(
        name=name,
        is_ranged=lambda: True,
        is_melee=lambda: False,
    )
    return profile


def _thundershock_ability():
    return {
        "name": "Thundershock",
        "description": THUNDERSHOCK_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def test_thundershock_spec_parsing():
    source = _make_unit(
        "Knight Valiant",
        "ik-valiant",
        faction_name="Imperial Knights",
        faction_keywords=["IMPERIAL KNIGHTS"],
        keywords=["VEHICLE", "TITANIC"],
        abilities=[_thundershock_ability()],
    )

    specs = source.unit_thundershock_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("range", 0) or 0) == 6
    assert int(spec.get("threshold", 0) or 0) == 4
    assert str(spec.get("mortal_wounds", "")).lower() == "d3"
    assert str(spec.get("weapon_key", "")).strip().lower() == "thundercoil harpoon"


def test_thundershock_marks_and_applies_mortals():
    game, ik_army, enemy_army, _ik_player, _enemy_player = _build_game()
    source = _make_unit(
        "Knight Valiant",
        "ik-valiant",
        faction_name="Imperial Knights",
        faction_keywords=["IMPERIAL KNIGHTS"],
        keywords=["VEHICLE", "TITANIC"],
        abilities=[_thundershock_ability()],
    )
    target = _make_unit(
        "Target",
        "en-target",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    nearby = _make_unit(
        "Nearby",
        "en-near",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    far = _make_unit(
        "Far",
        "en-far",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    ik_army.add_unit(source)
    enemy_army.add_unit(target)
    enemy_army.add_unit(nearby)
    enemy_army.add_unit(far)
    _deploy(source, target, nearby, far)
    game.map.units = [source, target, nearby, far]
    game.rebuild_entity_registry()

    target.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    nearby.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    far.models[0].set_location(20.0, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    declaration = {
        "weapon_profile": _make_ranged_profile("thundercoil harpoon"),
        "target_unit": target,
        "models": [source.models[0]],
    }

    applied = []
    source._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: applied.append((unit, int(amount)))

    rolls = iter([6, 4, 2, 3, 1])
    with patch("warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll", side_effect=lambda _spec: next(rolls)):
        game._on_shooting_targets_selected_thundershock(
            attacking_unit=source,
            target_units=[target],
            weapon_declarations=[declaration],
        )
        entries = list(getattr(source, "special_rules", {}).get("thundershock_pending_entries", []) or [])
        assert len(entries) == 1
        struck = set(entries[0].get("struck_ids", []) or [])
        assert struck == {str(get_entity_id(target)), str(get_entity_id(nearby))}
        game._on_unit_shooting_resolved_thundershock(attacker_unit=source)

    assert len(applied) == 2
    assert {u for u, _amt in applied} == {target, nearby}
    assert {amt for _u, amt in applied} == {2, 3}
    assert "thundershock_pending_entries" not in getattr(source, "special_rules", {})


def test_thundershock_ignores_non_harpoon_weapon_declarations():
    game, ik_army, enemy_army, _ik_player, _enemy_player = _build_game()
    source = _make_unit(
        "Knight Valiant",
        "ik-valiant",
        faction_name="Imperial Knights",
        faction_keywords=["IMPERIAL KNIGHTS"],
        keywords=["VEHICLE", "TITANIC"],
        abilities=[_thundershock_ability()],
    )
    target = _make_unit(
        "Target",
        "en-target",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    ik_army.add_unit(source)
    enemy_army.add_unit(target)
    _deploy(source, target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    declaration = {
        "weapon_profile": _make_ranged_profile("conflagration cannon"),
        "target_unit": target,
        "models": [source.models[0]],
    }
    game._on_shooting_targets_selected_thundershock(
        attacking_unit=source,
        target_units=[target],
        weapon_declarations=[declaration],
    )
    assert "thundershock_pending_entries" not in getattr(source, "special_rules", {})
