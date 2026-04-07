from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


CANTICLES_TEXT = (
    "At the start of your Command phase, select one of the abilities in the Canticles of the Omnissiah section. "
    "Until the start of your next Command phase, this model has that ability."
)
INVOCATION_TEXT = (
    "At the start of your Command phase, select one unit from your opponent's army. Until the start of your next "
    "Command phase, that enemy unit is your Machine Vengeance target. Each time a model in a friendly Adeptus "
    "Mechanicus unit makes an attack that targets your Machine Vengeance target, you can re-roll the Hit roll."
)
MANTRA_TEXT = (
    "This model has the BATTLELINE keyword and has the following ability: Binharic Courage (Aura): While a friendly "
    "ADEPTUS MECHANICUS unit is within 6\" of this model, add 1 to the Objective Control characteristic of models in "
    "that unit and each time you take a Battle-shock or Leadership test for that unit, add 1 to that test."
)
SHROUDPSALM_TEXT = (
    "While a friendly ADEPTUS MECHANICUS unit is within 6\" of this model, that unit has the Stealth ability."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "6",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
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
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Other")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, admech_army, enemy_army, p1, p2


def _find_quarry_request(game: Game, ability_key: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "")) == str(ability_key)
        ),
        None,
    )


def _cawl_abilities():
    return [
        {"name": "Canticles of the Omnissiah", "description": CANTICLES_TEXT, "type": "Datasheet", "parameter": ""},
        {
            "name": "Invocation of Machine Vengeance",
            "description": INVOCATION_TEXT,
            "type": "Datasheet",
            "parameter": "",
        },
        {"name": "Mantra of Discipline", "description": MANTRA_TEXT, "type": "Datasheet", "parameter": ""},
        {"name": "Shroudpsalm (Aura)", "description": SHROUDPSALM_TEXT, "type": "Datasheet", "parameter": ""},
    ]


def test_canticles_mantra_selection_grants_battleline_and_mantra_effects():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    cawl = _make_unit(
        "Belisarius Cawl",
        abilities=_cawl_abilities(),
        keywords=["INFANTRY", "CHARACTER", "BELISARIUS CAWL"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    ally = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(cawl)
    admech_army.add_unit(ally)
    enemy_army.add_unit(enemy)
    game.map.units = [cawl, ally, enemy]
    game.rebuild_entity_registry()

    cawl.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    ally.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(18.0, 0.0, 0.0, 0.0)

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    request = _find_quarry_request(game, "canticles_of_the_omnissiah")
    assert request is not None
    assert request.decision_type == DECISION_CHOOSE_QUARRY

    mantra_option = next(
        (
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("canticles_mode", "")) == "mantra_of_discipline"
        ),
        None,
    )
    assert mantra_option is not None

    result = resolve_decision_command(game, request, mantra_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    assert cawl.has_any_keyword("BATTLELINE")
    assert int(ally.models[0].objective_control) == 2

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=7):
        ally.pass_leadership_check()
    assert int(getattr(ally, "_last_leadership_test_roll", -1)) == 7
    assert int(getattr(ally, "_last_leadership_test_modified_roll", -1)) == 8


def test_canticles_invocation_marks_target_and_grants_hit_rerolls():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    cawl = _make_unit(
        "Belisarius Cawl",
        abilities=_cawl_abilities(),
        keywords=["INFANTRY", "CHARACTER", "BELISARIUS CAWL"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    ally = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cawl)
    admech_army.add_unit(ally)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    game.map.units = [cawl, ally, enemy_a, enemy_b]
    game.rebuild_entity_registry()

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    mode_request = _find_quarry_request(game, "canticles_of_the_omnissiah")
    assert mode_request is not None
    invocation_option = next(
        (
            opt
            for opt in list(mode_request.options or [])
            if str((opt.payload or {}).get("canticles_mode", "")) == "invocation_of_machine_vengeance"
        ),
        None,
    )
    assert invocation_option is not None
    result = resolve_decision_command(game, mode_request, invocation_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    target_request = _find_quarry_request(game, "canticles_machine_vengeance_target")
    assert target_request is not None
    enemy_a_id = str(get_entity_id(enemy_a) or "")
    target_option = next(
        (
            opt
            for opt in list(target_request.options or [])
            if str((opt.payload or {}).get("target_unit_id", "")) == enemy_a_id
        ),
        None,
    )
    assert target_option is not None
    result = resolve_decision_command(game, target_request, target_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    enemy_a_sr = enemy_a.special_rules
    assert bool(enemy_a_sr.get("canticles_machine_vengeance_active")) is True
    assert str(enemy_a_sr.get("canticles_machine_vengeance_owner", "")) == str(p1.id)

    mods_vs_a = ally.get_unit_hit_reroll_modifiers("ranged", target=enemy_a, attacker_model=ally.models[0])
    mods_vs_b = ally.get_unit_hit_reroll_modifiers("ranged", target=enemy_b, attacker_model=ally.models[0])
    assert bool(mods_vs_a.get("reroll_hit_full")) is True
    assert bool(mods_vs_b.get("reroll_hit_full")) is False


def test_canticles_shroudpsalm_grants_stealth_to_friendly_aura_units():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    cawl = _make_unit(
        "Belisarius Cawl",
        abilities=_cawl_abilities(),
        keywords=["INFANTRY", "CHARACTER", "BELISARIUS CAWL"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    near_ally = _make_unit(
        "Near Ally",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    far_ally = _make_unit(
        "Far Ally",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cawl)
    admech_army.add_unit(near_ally)
    admech_army.add_unit(far_ally)
    enemy_army.add_unit(enemy)
    game.map.units = [cawl, near_ally, far_ally, enemy]
    game.rebuild_entity_registry()

    cawl.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    near_ally.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    far_ally.models[0].set_location(10.0, 0.0, 0.0, 0.0)

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    request = _find_quarry_request(game, "canticles_of_the_omnissiah")
    assert request is not None
    shroud_option = next(
        (
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("canticles_mode", "")) == "shroudpsalm"
        ),
        None,
    )
    assert shroud_option is not None
    result = resolve_decision_command(game, request, shroud_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    assert near_ally.has_stealth() is True
    assert far_ally.has_stealth() is False


def test_canticles_expire_and_machine_vengeance_marker_clears_next_command_phase():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    cawl = _make_unit(
        "Belisarius Cawl",
        abilities=_cawl_abilities(),
        keywords=["INFANTRY", "CHARACTER", "BELISARIUS CAWL"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cawl)
    enemy_army.add_unit(enemy)
    game.map.units = [cawl, enemy]
    game.rebuild_entity_registry()

    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    mode_request = _find_quarry_request(game, "canticles_of_the_omnissiah")
    invocation_option = next(
        (
            opt
            for opt in list(mode_request.options or [])
            if str((opt.payload or {}).get("canticles_mode", "")) == "invocation_of_machine_vengeance"
        ),
        None,
    )
    assert invocation_option is not None
    result = resolve_decision_command(game, mode_request, invocation_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    target_request = _find_quarry_request(game, "canticles_machine_vengeance_target")
    assert target_request is not None
    only_target = list(target_request.options or [])[0]
    result = resolve_decision_command(game, target_request, only_target.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True
    assert bool(enemy.special_rules.get("canticles_machine_vengeance_active")) is True

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_optional_abilities(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)

    assert str(cawl.special_rules.get("canticles_of_the_omnissiah_selected_mode", "") or "") == ""
    assert bool(enemy.special_rules.get("canticles_machine_vengeance_active", False)) is False
