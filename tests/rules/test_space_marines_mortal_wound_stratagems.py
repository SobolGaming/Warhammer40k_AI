from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game(detachment_type: str):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.turn = 1
    sm_player.command_points = 10
    enemy_player.command_points = 10
    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def test_space_marines_mortal_wound_stratagem_descriptors_registered():
    expected = {
        "000008375002": "Angelic Grace",
        "000009844002": "Fuelled by Faith",
    }
    for stratagem_id, expected_name in expected.items():
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name)
        assert descriptor is not None
        assert descriptor.name == expected_name
        assert descriptor.timing == "any_phase_after_mortal_wound_allocated"
        assert descriptor.target == "adeptus_astartes_unit_allocated_mortal_wound"
        assert descriptor.effect == "feel_no_pain_vs_mortals"
        assert int(descriptor.cp_cost or 0) == 1
        assert int((descriptor.effect_params or {}).get("feel_no_pain_value", 0) or 0) == 5
        assert "mortal" in str((descriptor.effect_params or {}).get("condition", "") or "").lower()


@pytest.mark.parametrize(
    "detachment_type,stratagem_name",
    [
        ("Liberator Assault Group", "ANGELIC GRACE"),
        ("Wrathful Procession", "FUELLED BY FAITH"),
    ],
)
def test_space_marines_mortal_wound_stratagems_queue_on_mortal_wound_and_apply_fnp(
    detachment_type: str,
    stratagem_name: str,
):
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game(detachment_type)
    target = _make_unit(
        "Target Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "mortal_wound_allocated",
        attacker_unit=attacker,
        target_unit=target,
        target_model=target.models[0],
        phase_name="Shooting phase",
    )

    pending = _pending_by_name(sm_player.stratagems, stratagem_name)
    assert pending is not None
    assert str(pending.get("event", "") or "").lower() == "mortal_wound_allocated"

    starting_cp = int(sm_player.command_points or 0)
    ok = sm_player.stratagems.use(stratagem_name, phase_name="Shooting phase", dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == starting_cp - 1

    fnp_entries = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert any(int(value) == 5 and "mortal" in str(condition or "").lower() for value, condition in fnp_entries)

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    fnp_after = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert not any(int(value) == 5 and "mortal" in str(condition or "").lower() for value, condition in fnp_after)
