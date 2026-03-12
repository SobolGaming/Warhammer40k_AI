from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


_BREAK_THE_FOE_DESCRIPTION = (
    "Melee weapons equipped by models in this model's unit have the [SUSTAINED HITS 1] ability."
)
_RELENTLESS_AVALANCHE_DESCRIPTION = (
    "You can target this model's unit with the Heroic Intervention Stratagem for 0CP, and can do so even if "
    "you have already targeted a different unit with that Stratagem this phase."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    lov_army = Army("Leagues of Votann", "Detachment")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Detachment")
    enemy_army.faction_id = "EN"
    lov_player = Player("LOV", control=PlayerControl.LOCAL, army=lov_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(lov_player)
    game.add_player(enemy_player)
    return game, lov_player, enemy_player


def test_break_the_foe_applies_sustained_hits_to_melee_only():
    attacker = _make_unit(
        "Berehk Stornbrow",
        abilities=[
            {
                "name": "Break the Foe",
                "description": _BREAK_THE_FOE_DESCRIPTION,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    target = _make_unit("Enemy Unit")

    melee_parent = SimpleNamespace(name="Hammer", is_melee=lambda: True, is_ranged=lambda: False)
    ranged_parent = SimpleNamespace(name="Pistol", is_melee=lambda: False, is_ranged=lambda: True)

    melee_profile = WargearProfile(
        profile_name="Melee",
        wargear_data={"range": "Melee", "A": "1", "BS_WS": "3+", "S": "6", "AP": "-2", "D": "2", "description": ""},
        parent_wargear=melee_parent,
    )
    ranged_profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={"range": "12", "A": "1", "BS_WS": "3+", "S": "5", "AP": "0", "D": "1", "description": ""},
        parent_wargear=ranged_parent,
    )

    melee_attack = {"_aura_attack_mods": _aura_stub()}
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        melee_profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            melee_attack,
            allow_rerolls=False,
            log_roll=False,
        )
    assert int(melee_attack.get("sustained_hit", 0) or 0) == 1

    ranged_attack = {"_aura_attack_mods": _aura_stub()}
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        ranged_profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            ranged_attack,
            allow_rerolls=False,
            log_roll=False,
        )
    assert int(ranged_attack.get("sustained_hit", 0) or 0) == 0


def test_relentless_avalanche_allows_zero_cp_and_repeat_heroic_intervention():
    game, lov_player, _enemy_player = _build_game()
    berehk = _make_unit("Berehk Stornbrow", keywords=["INFANTRY"], faction_keywords=["LEAGUES OF VOTANN"])
    berehk.possible_abilities = [
        Ability("Relentless Avalanche", "LOV", _RELENTLESS_AVALANCHE_DESCRIPTION, "Datasheet", "")
    ]
    other_unit = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"], faction_keywords=["LEAGUES OF VOTANN"])

    lov_player.army.add_unit(berehk)
    lov_player.army.add_unit(other_unit)
    berehk.deployed = True
    berehk.reserve_status = "deployed"
    other_unit.deployed = True
    other_unit.reserve_status = "deployed"
    game.turn = 1

    rule = berehk.get_snarling_protector_heroic_intervention_rule()
    assert isinstance(rule, dict)

    lov_player.stratagems = SimpleNamespace(_used_this_turn={})
    strat = SimpleNamespace(name="Heroic Intervention", cp_cost=1)
    lov_player.set_next_optional_decision("SNARLING_PROTECTOR_HEROIC_INTERVENTION", True)
    applied = lov_player.apply_stratagem_cp_cost(strat, target_unit=berehk)
    assert int(applied.get("cost", -1)) == 0
    assert bool(applied.get("snarling_protector_heroic_intervention_use", False))

    manager = StratagemManager(lov_player)
    manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
    manager._record_heroic_intervention_use(other_unit)
    assert bool(manager._heroic_intervention_repeat_allowed(target_unit=berehk))
    assert not bool(manager._heroic_intervention_repeat_allowed(target_unit=other_unit))
