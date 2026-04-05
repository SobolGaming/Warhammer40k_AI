from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        save: str = "2",
        toughness: str = "5",
    ):
        self.name = name
        self.faction_data = {"name": "Adeptus Custodes"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": str(save),
                "W": "3",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(
    name: str,
    x: float,
    y: float,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: str = "5",
) -> Unit:
    ds = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    unit = Unit(ds)
    for model in unit.models:
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True
    return unit


def make_profile(*, strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(
        name="Guardian Spear",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "4+",
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


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


def _make_game():
    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    custodes_army = Army("Adeptus Custodes", "Auric Champions")
    custodes_army.faction_id = "AC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    return game, custodes_player, enemy_player


def test_assemblage_of_might_command_phase_selection_request():
    game, player, enemy = _make_game()
    attacker = create_unit(
        "Shield-Captain",
        10.0,
        10.0,
        keywords=["CHARACTER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target_a = create_unit("Enemy A", 20.0, 10.0, faction_keywords=["ENEMY"], toughness="4")
    target_b = create_unit("Enemy B", 24.0, 10.0, faction_keywords=["ENEMY"], toughness="4")
    player.army.add_unit(attacker)
    enemy.army.add_unit(target_a)
    enemy.army.add_unit(target_b)
    game.map.units = [attacker, target_a, target_b]
    game.rebuild_entity_registry()

    mgr = player.army.adeptus_custodes_detachments
    mgr.on_command_phase_start(game=game, player=player)

    pending = [
        req
        for req in game.decision_queue.list()
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "")) == "assemblage_of_might"
    ]
    assert len(pending) == 1
    request = pending[0]
    option = request.options[0]
    resolve_decision_command(game, request, option.option_id, player_id=player.id)

    assert str(mgr.assemblage_of_might_target_unit_id) == str((option.payload or {}).get("target_unit_id", ""))
    assert bool(mgr.assemblage_of_might_target_name)


def test_assemblage_of_might_applies_only_to_character_unit_attacks():
    game, player, enemy = _make_game()
    character_unit = create_unit(
        "Shield-Captain",
        10.0,
        10.0,
        keywords=["CHARACTER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    guard_unit = create_unit(
        "Custodian Guard",
        12.0,
        10.0,
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit("Enemy", 20.0, 10.0, faction_keywords=["ENEMY"], toughness="4")
    player.army.add_unit(character_unit)
    player.army.add_unit(guard_unit)
    enemy.army.add_unit(target)
    game.map.units = [character_unit, guard_unit, target]

    mgr = player.army.adeptus_custodes_detachments
    assert mgr.set_assemblage_of_might_target(target)

    profile = make_profile(strength="4")
    char_result = profile._wound_target_with_tracking(
        target,
        character_unit.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert char_result["wound"] is True
    assert any("Assemblage of Might" in m for m in char_result.get("modifiers", []))

    non_char_result = profile._wound_target_with_tracking(
        target,
        guard_unit.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert non_char_result["wound"] is False
    assert not any("Assemblage of Might" in m for m in non_char_result.get("modifiers", []))


def test_assemblage_of_might_command_phase_clears_previous_target_and_avoids_duplicate_requests():
    game, player, enemy = _make_game()
    attacker = create_unit(
        "Shield-Captain",
        10.0,
        10.0,
        keywords=["CHARACTER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit("Enemy", 20.0, 10.0, faction_keywords=["ENEMY"], toughness="4")
    player.army.add_unit(attacker)
    enemy.army.add_unit(target)
    game.map.units = [attacker, target]
    game.rebuild_entity_registry()

    mgr = player.army.adeptus_custodes_detachments
    assert mgr.set_assemblage_of_might_target(target)
    assert bool(mgr.assemblage_of_might_target_unit_id)

    mgr.on_command_phase_start(game=game, player=player)
    assert mgr.assemblage_of_might_target_unit_id == ""

    mgr.on_command_phase_start(game=game, player=player)
    pending = [
        req
        for req in game.decision_queue.list()
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "")) == "assemblage_of_might"
    ]
    assert len(pending) == 1
