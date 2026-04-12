from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DARK_PACT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


_DARK_PACTS_ABILITY = {
    "name": "Dark Pacts",
    "description": (
        "If your Army Faction is HERETIC ASTARTES, each time a unit with this ability is selected to shoot or "
        "fight, it can make a Dark Pact. If it does, it must first take a Leadership test before any effects of "
        "that Dark Pact are resolved; if that test is failed, that unit suffers D3 mortal wounds. Then, select "
        "one of the following abilities for that unit's weapons to gain until the end of the phase: [LETHAL HITS]; "
        "[SUSTAINED HITS 1]."
    ),
    "type": "Faction",
    "parameter": "",
}
_DAEMONFORGE_ABILITY = {
    "name": "Daemonforge",
    "description": (
        "Each time this unit makes a Dark Pact, until the end of the phase, each time this model makes an attack, "
        "re-roll a Wound roll of 1. In addition, once per battle, when this unit makes a Dark Pact, before making "
        "the resulting Leadership test, you can declare it will overcharge its daemonforge. If it does: If the "
        "resulting Leadership test is failed, this model suffers 3 mortal wounds instead of D3 mortal wounds. "
        "Until the end of the phase, each time this model makes an attack, you can re-roll the Wound roll."
    ),
    "type": "Datasheet",
    "parameter": "",
}


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "11",
                "Sv": "3",
                "W": "18",
                "Ld": "6",
                "OC": "5",
                "base_size": "120mm x 92mm",
                "inv_sv": "5",
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
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Other")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.FIGHT_PHASE
    return game, csm_player, csm_army, enemy_player, enemy_army


def _daemonforge_unit() -> Unit:
    return _make_unit(
        "Defiler",
        abilities=[_DARK_PACTS_ABILITY, _DAEMONFORGE_ABILITY],
        keywords=["VEHICLE", "DAEMON", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )


def _find_dark_pact_request(game: Game, unit: Unit):
    unit_id = str(get_entity_id(unit) or "")
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_DARK_PACT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("unit_id", "") or "") == unit_id:
            return request
    return None


def _find_dark_pact_option(request, *, choice: str, daemonforge_overcharge: bool):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice", "") or "").strip().upper() != str(choice).strip().upper():
            continue
        if bool(payload.get("daemonforge_overcharge", False)) != bool(daemonforge_overcharge):
            continue
        return option
    return None


def test_daemonforge_dark_pact_request_includes_combined_overcharge_options():
    game, _csm_player, csm_army, _enemy_player, _enemy_army = _build_game()
    defiler = _daemonforge_unit()
    csm_army.add_unit(defiler)
    game.map.units = [defiler]
    game.rebuild_entity_registry()

    defiler.maybe_trigger_dark_pacts(game, phase_name="FIGHT_PHASE", trigger="fight")

    request = _find_dark_pact_request(game, defiler)
    assert request is not None

    assert _find_dark_pact_option(request, choice="LETHAL HITS", daemonforge_overcharge=False) is not None
    assert _find_dark_pact_option(request, choice="LETHAL HITS", daemonforge_overcharge=True) is not None
    assert _find_dark_pact_option(request, choice="SUSTAINED HITS 1", daemonforge_overcharge=False) is not None
    assert _find_dark_pact_option(request, choice="SUSTAINED HITS 1", daemonforge_overcharge=True) is not None


def test_daemonforge_dark_pact_grants_wound_reroll_ones_for_the_phase():
    game, csm_player, csm_army, _enemy_player, _enemy_army = _build_game()
    defiler = _daemonforge_unit()
    defiler.pass_leadership_check = lambda *args, **kwargs: True
    csm_army.add_unit(defiler)
    game.map.units = [defiler]
    game.rebuild_entity_registry()

    defiler.maybe_trigger_dark_pacts(game, phase_name="FIGHT_PHASE", trigger="fight")
    request = _find_dark_pact_request(game, defiler)
    assert request is not None

    option = _find_dark_pact_option(request, choice="LETHAL HITS", daemonforge_overcharge=False)
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    special_rules = dict(getattr(defiler, "special_rules", {}) or {})
    assert bool(special_rules.get("daemonforge_active", False)) is True
    assert bool(special_rules.get("daemonforge_overcharge_active", False)) is False
    assert defiler.has_used_unit_once_per_battle("daemonforge_overcharge") is False

    mods = defiler.get_unit_wound_reroll_modifiers("melee")
    assert mods.get("reroll_wound_values", ()) == (1,)
    assert bool(mods.get("reroll_wound_full", False)) is False
    assert any("Daemonforge" in str(reason or "") for reason in list(mods.get("reroll_wound_reasons", ()) or ()))


def test_daemonforge_overcharge_grants_full_wound_rerolls_and_marks_once_per_battle():
    game, csm_player, csm_army, _enemy_player, _enemy_army = _build_game()
    defiler = _daemonforge_unit()
    defiler.pass_leadership_check = lambda *args, **kwargs: True
    csm_army.add_unit(defiler)
    game.map.units = [defiler]
    game.rebuild_entity_registry()

    defiler.maybe_trigger_dark_pacts(game, phase_name="FIGHT_PHASE", trigger="fight")
    request = _find_dark_pact_request(game, defiler)
    assert request is not None

    option = _find_dark_pact_option(request, choice="SUSTAINED HITS 1", daemonforge_overcharge=True)
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    special_rules = dict(getattr(defiler, "special_rules", {}) or {})
    assert bool(special_rules.get("daemonforge_active", False)) is True
    assert bool(special_rules.get("daemonforge_overcharge_active", False)) is True
    assert defiler.has_used_unit_once_per_battle("daemonforge_overcharge") is True

    mods = defiler.get_unit_wound_reroll_modifiers("melee")
    assert mods.get("reroll_wound_values", ()) == (1,)
    assert bool(mods.get("reroll_wound_full", False)) is True
    assert any("Daemonforge" in str(reason or "") for reason in list(mods.get("reroll_wound_full_reasons", ()) or ()))


def test_daemonforge_overcharge_failed_dark_pact_inflicts_three_mortal_wounds():
    game, _csm_player, csm_army, _enemy_player, _enemy_army = _build_game()
    defiler = _daemonforge_unit()
    mortal_wounds = []

    defiler.pass_leadership_check = lambda *args, **kwargs: False
    defiler._apply_mortal_wounds_to_unit = lambda _unit, amount, game_map=None: mortal_wounds.append(int(amount))
    csm_army.add_unit(defiler)
    game.map.units = [defiler]
    game.rebuild_entity_registry()

    applied = defiler.apply_dark_pacts_choice(
        game,
        choice="LETHAL HITS",
        phase_name="FIGHT_PHASE",
        trigger="fight",
        daemonforge_overcharge=True,
    )
    assert applied is True
    assert mortal_wounds == [3]
    assert defiler.has_used_unit_once_per_battle("daemonforge_overcharge") is True
