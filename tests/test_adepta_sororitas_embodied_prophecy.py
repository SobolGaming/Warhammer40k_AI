from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_value


EMBODIED_PROPHECY_TEXT = (
    "Each time this unit is selected to fight, select one of the following abilities to apply to melee weapons "
    "equipped by models in this unit until the end of the phase: - [SUSTAINED HITS 1] - [LETHAL HITS] If this "
    "unit made a Charge move this turn, until the end of the phase, select both abilities above to apply to "
    "melee weapons equipped by models in this unit instead."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _ability(name: str, description: str) -> dict:
    return {"name": name, "description": description, "type": "Datasheet", "parameter": ""}


def _create_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _deploy(unit: Unit) -> None:
    unit.deployed = True
    set_reserve_status = getattr(unit, "set_reserve_status", None)
    if callable(set_reserve_status):
        set_reserve_status("deployed")
    else:
        unit.reserve_status = "deployed"


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sororitas = Army("Adepta Sororitas", "Detachment")
    sororitas.faction_id = "AS"
    enemy = Army("Enemy", "Detachment")
    enemy.faction_id = "EN"

    p1 = Player("Sororitas Player", control=PlayerControl.LOCAL, army=sororitas)
    p2 = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    return game, sororitas, enemy, p1, p2


def _find_embodied_prophecy_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "embodied_prophecy":
            continue
        return request
    return None


def _make_melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Melee Weapon", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Boltgun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_embodied_prophecy_queues_choice_and_applies_selected_melee_keyword_only():
    game, sororitas, enemy, p1, _p2 = _build_game()
    attacker = _create_unit(
        "Zephyrim Squad",
        abilities=[_ability("Embodied Prophecy", EMBODIED_PROPHECY_TEXT)],
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(attacker)
    enemy.add_unit(target)
    _deploy(attacker)
    _deploy(target)
    game.rebuild_entity_registry()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    game.event_system.publish("fight_unit_selected", unit=attacker, selecting_player=p1)
    request = _find_embodied_prophecy_request(game)
    assert request is not None
    labels = {str(getattr(opt, "label", "") or "") for opt in list(request.options or [])}
    assert labels == {"Lethal Hits", "Sustained Hits 1"}

    option = next(
        opt
        for opt in list(request.options or [])
        if str((getattr(opt, "payload", {}) or {}).get("choice", "") or "") == "LETHAL_HITS"
    )
    _value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=p1.id)
    assert bool(getattr(apply_result, "ok", False))

    melee_profile = _make_melee_profile()
    melee_attack = {}
    melee_hit = melee_profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        melee_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(melee_attack.get("lethal_hit", False))
    assert any("Lethal Hits" in str(effect or "") for effect in list(melee_hit.get("special_effects", []) or []))

    ranged_profile = _make_ranged_profile()
    ranged_attack = {}
    ranged_profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        ranged_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(ranged_attack.get("lethal_hit", False))


def test_embodied_prophecy_sustained_choice_grants_sustained_hits_one():
    game, sororitas, enemy, p1, _p2 = _build_game()
    attacker = _create_unit(
        "Zephyrim Squad",
        abilities=[_ability("Embodied Prophecy", EMBODIED_PROPHECY_TEXT)],
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(attacker)
    enemy.add_unit(target)
    _deploy(attacker)
    _deploy(target)
    game.rebuild_entity_registry()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    game.event_system.publish("fight_unit_selected", unit=attacker, selecting_player=p1)
    request = _find_embodied_prophecy_request(game)
    assert request is not None

    option = next(
        opt
        for opt in list(request.options or [])
        if str((getattr(opt, "payload", {}) or {}).get("choice", "") or "") == "SUSTAINED_HITS_1"
    )
    _value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=p1.id)
    assert bool(getattr(apply_result, "ok", False))

    melee_profile = _make_melee_profile()
    attack_instance = {}
    melee_profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1
    assert not bool(attack_instance.get("lethal_hit", False))


def test_embodied_prophecy_charge_auto_applies_both_without_choice_request():
    game, sororitas, enemy, p1, _p2 = _build_game()
    attacker = _create_unit(
        "Zephyrim Squad",
        abilities=[_ability("Embodied Prophecy", EMBODIED_PROPHECY_TEXT)],
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(attacker)
    enemy.add_unit(target)
    _deploy(attacker)
    _deploy(target)
    attacker.round_state.charged_this_round = True
    game.rebuild_entity_registry()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    game.event_system.publish("fight_unit_selected", unit=attacker, selecting_player=p1)
    assert _find_embodied_prophecy_request(game) is None

    sr = dict(getattr(attacker, "special_rules", {}) or {})
    assert bool(sr.get("embodied_prophecy_lethal_hits_active", False))
    assert int(sr.get("embodied_prophecy_sustained_hits_value", 0) or 0) == 1

    melee_profile = _make_melee_profile()
    attack_instance = {}
    melee_profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("lethal_hit", False))
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1
