from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "9",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        for ability in list(abilities or []):
            if isinstance(ability, Ability):
                self.datasheets_abilities.append(
                    {
                        "name": ability.name,
                        "description": ability.description,
                        "type": ability.type,
                        "parameter": ability.parameter,
                    }
                )
            else:
                self.datasheets_abilities.append(ability)
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
):
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army("Chaos Space Marines", detachment_type="Other")
    csm_army.faction_id = "CSM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    p1 = Player("P1", PlayerControl.LOCAL, army=csm_army)
    p2 = Player("P2", PlayerControl.LOCAL, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, csm_army, enemy_army, p1, p2


def _resolve_yes(game: Game, player: Player):
    req = game.decision_queue.peek()
    assert req is not None
    option_id = None
    for opt in list(req.options or []):
        if bool((opt.payload or {}).get("choice", False)):
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=player.id)


def test_spirit_thief_queues_and_applies_wound_reroll_mark():
    ability = Ability(
        "Spirit Thief",
        "CSM",
        (
            "At the start of your Shooting phase, select one visible enemy VEHICLE unit. "
            "Until the end of the phase, each time a friendly HERETIC ASTARTES model makes an attack that targets that unit, "
            "re-roll a Wound roll of 1."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Lord Discordant", abilities=[ability], keywords=["HERETIC ASTARTES"])
    enemy = _make_unit("Enemy Tank", keywords=["VEHICLE"])

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    game._on_phase_start_spirit_thief(player=p1, phase=game.phase)
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert (req.context or {}).get("ability") == "spirit_thief"

    target_id = get_entity_id(enemy)
    option_id = None
    for opt in list(req.options or []):
        if str((opt.payload or {}).get("target_unit_id", "")) == str(target_id):
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=p1.id)

    assert bool(enemy.special_rules.get("spirit_thief_active"))
    mods = source.get_unit_wound_reroll_modifiers("ranged", target=enemy)
    assert bool(mods.get("reroll_wound_ones"))
    assert 1 in tuple(mods.get("reroll_wound_values") or ())


def test_corrupt_machine_spirits_queues_and_deals_mortal_wounds():
    ability = Ability(
        "Corrupt Machine Spirits",
        "CSM",
        (
            "At the start of your Shooting phase, select one visible enemy VEHICLE unit within 12\" of this model and roll one D6: "
            "on a 2-3, that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers 3 mortal wounds; "
            "on a 6, that enemy unit suffers D3+3 mortal wounds."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Lord Discordant", abilities=[ability])
    enemy = _make_unit("Enemy Tank", keywords=["VEHICLE"])

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(6.0, 0.0, 0.0, 0.0)
    source._apply_mortal_wounds_to_unit = Mock()

    game._on_phase_start_corrupt_machine_spirits(player=p1, phase=game.phase)
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert (req.context or {}).get("ability") == "corrupt_machine_spirits"

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        resolve_decision_command(game, req, req.options[0].option_id, player_id=p1.id)

    source._apply_mortal_wounds_to_unit.assert_called()
    call_args = source._apply_mortal_wounds_to_unit.call_args
    assert call_args.args[0] is enemy
    assert int(call_args.args[1]) == 3


def test_daemonic_ordnance_confirmation_sets_phase_effect():
    ability = Ability(
        "Daemonic Ordnance",
        "CSM",
        (
            "Each time this model is selected to shoot, it can use this ability. If it does, until the end of the phase, "
            "its ranged weapons have the [DEVASTATING WOUNDS] and [HAZARDOUS] abilities."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Forgefiend", abilities=[ability], keywords=["HERETIC ASTARTES"])
    enemy = _make_unit("Target")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_daemonic_ordnance(attacking_unit=source, target_units=[enemy])
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CONFIRM_YES_NO
    assert (req.context or {}).get("ability") == "daemonic_ordnance"

    _resolve_yes(game, p1)
    sr = source.special_rules
    assert bool(sr.get("daemonic_ordnance_active"))
    assert str(sr.get("daemonic_ordnance_expires_phase", "")).upper() == "SHOOTING_PHASE"


def test_warp_rift_firepower_confirmation_marks_once_per_battle():
    ability = Ability(
        "Warp Rift Firepower",
        "CSM",
        (
            "Once per battle, during the shooting phase, this unit can use this ability. If it does, until the end of the phase, "
            "ranged weapons equipped by models in this unit have the [INDIRECT FIRE] ability."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Obliterators", abilities=[ability], keywords=["HERETIC ASTARTES"])
    enemy = _make_unit("Target")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_warp_rift_firepower(attacking_unit=source, target_units=[enemy])
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CONFIRM_YES_NO
    assert (req.context or {}).get("ability") == "warp_rift_firepower"

    _resolve_yes(game, p1)
    assert source.has_used_unit_once_per_battle("warp_rift_firepower")
    assert bool(source.special_rules.get("warp_rift_firepower_active"))

    game._on_shooting_targets_selected_warp_rift_firepower(attacking_unit=source, target_units=[enemy])
    assert list(game.decision_queue.list() or []) == []


def test_daemonic_ordnance_and_warp_rift_effects_are_consumed_by_attack_resolution():
    source = _make_unit("Forgefiend", keywords=["HERETIC ASTARTES"])
    target = _make_unit("Target")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.special_rules["daemonic_ordnance_active"] = True
    source.special_rules["daemonic_ordnance_expires_phase"] = "SHOOTING_PHASE"
    source.special_rules["daemonic_ordnance_owner"] = p1.id
    source.special_rules["daemonic_ordnance_turn"] = int(getattr(game, "turn", 0) or 0)
    source.special_rules["warp_rift_firepower_active"] = True
    source.special_rules["warp_rift_firepower_expires_phase"] = "SHOOTING_PHASE"
    source.special_rules["warp_rift_firepower_owner"] = p1.id
    source.special_rules["warp_rift_firepower_turn"] = int(getattr(game, "turn", 0) or 0)

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Ectoplasma Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 2]):
        result = profile.attack(target, source.models[0], game_map=game.map)

    assert result is not None
    assert int(result.hazardous_roll or 0) == 2
    assert any("Daemonic Ordnance" in str(v) for v in list(result.attacks_special_modifiers or []))
    assert any("Warp Rift Firepower" in str(v) for v in list(result.attacks_special_modifiers or []))
    assert any(
        "Devastating Wounds" in str(effect)
        for wound in list(result.wound_results or [])
        for effect in list((wound or {}).get("special_effects", []) or [])
    )
