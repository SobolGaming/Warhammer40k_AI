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


def make_melee_profile(*, ap: str = "0", strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(
        name="Guardian Spear",
        is_melee=lambda: True,
        is_ranged=lambda: False,
    )
    data = {
        "range": "Melee",
        "A": "1",
        "BS_WS": "3+",
        "S": str(strength),
        "AP": str(ap),
        "D": "1",
        "description": "",
    }
    return WargearProfile("Melee", wargear_data=data, parent_wargear=parent)


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
        crit_hit_threshold=None,
        crit_hit_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _make_game():
    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    custodes_army = Army("Adeptus Custodes", "Shield Host")
    custodes_army.faction_id = "AC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    return game, custodes_player, enemy_player


def test_martial_mastery_battle_round_request_and_selection_flow():
    game, player, enemy = _make_game()
    attacker = create_unit(
        "Custodian Guard",
        10.0,
        10.0,
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    attacker.attached_unit_has_martial_katah = lambda: True
    target = create_unit("Enemy", 20.0, 10.0, faction_keywords=["ENEMY"])
    player.army.add_unit(attacker)
    enemy.army.add_unit(target)
    game.map.units = [attacker, target]
    game.rebuild_entity_registry()

    game.turn = 1
    game._on_battle_round_started_adeptus_custodes(game=game, battle_round=1)

    pending = [
        req
        for req in game.decision_queue.list()
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "")) == "martial_mastery"
    ]
    assert len(pending) == 1
    request = pending[0]
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice_key", "")) == "AP_PLUS_1"
    )
    resolve_decision_command(game, request, option.option_id, player_id=player.id)

    mgr = player.army.adeptus_custodes_detachments
    assert mgr.get_martial_mastery_mode(game=game, battle_round=1) == "AP_PLUS_1"

    game.turn = 2
    game._on_battle_round_started_adeptus_custodes(game=game, battle_round=2)
    assert mgr.get_martial_mastery_mode(game=game, battle_round=2) == ""


def test_martial_mastery_critical_hits_on_5_plus_mode():
    game, player, enemy = _make_game()
    attacker = create_unit(
        "Custodian Guard",
        10.0,
        10.0,
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    attacker.attached_unit_has_martial_katah = lambda: True
    target = create_unit("Enemy", 20.0, 10.0, faction_keywords=["ENEMY"])
    player.army.add_unit(attacker)
    enemy.army.add_unit(target)
    game.map.units = [attacker, target]

    mgr = player.army.adeptus_custodes_detachments
    assert mgr.select_martial_mastery("CRIT_5_PLUS", battle_round=1)
    game.turn = 1

    profile = make_melee_profile(ap="0", strength="4")
    hit_result = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("crit_threshold", 6) or 6) == 5
    assert any("Critical hit (5+)" in effect for effect in hit_result.get("special_effects", []))


def test_martial_mastery_ap_mode_improves_melee_ap_by_one():
    game, player, enemy = _make_game()
    attacker = create_unit(
        "Custodian Guard",
        10.0,
        10.0,
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    attacker.attached_unit_has_martial_katah = lambda: True
    target = create_unit("Enemy", 20.0, 10.0, faction_keywords=["ENEMY"])
    player.army.add_unit(attacker)
    enemy.army.add_unit(target)
    game.map.units = [attacker, target]

    mgr = player.army.adeptus_custodes_detachments
    assert mgr.select_martial_mastery("AP_PLUS_1", battle_round=1)
    game.turn = 1

    profile = make_melee_profile(ap="0", strength="4")
    effective_ap = profile.get_effective_ap(attacker.models[0], target)
    assert effective_ap == -1
