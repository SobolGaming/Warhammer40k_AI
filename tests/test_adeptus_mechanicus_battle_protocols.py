from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


BATTLE_PROTOCOLS_TEXT = (
    "At the start of the battle, if this model is leading a KASTELAN ROBOTS unit, that unit enters Aegis "
    "Protocols (see below). In your Command phase, if this model is leading a KASTELAN ROBOTS unit, you can "
    "select one protocol from those listed below for that unit to enter. Once a unit enters a protocol, it "
    "remains in that protocol until it enters a different one. "
    "- Protector Protocol: Add 2 to the Attacks characteristic of ranged weapons equipped by KASTELAN ROBOT "
    "models in that unit. "
    "- Conqueror Protocol: Add 2 to the Attacks characteristic of melee weapons equipped by KASTELAN ROBOT "
    "models in that unit. "
    "- Aegis Protocol: Add 1 to the Toughness characteristic of KASTELAN ROBOT models in that unit."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None, toughness: int = 4):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": "6",
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
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None, toughness: int = 4) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Other")
    admech_army.faction_id = "ADM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, admech_army, enemy_army, p1, p2


def _battle_protocols_ability():
    return {
        "name": "Battle Protocols",
        "description": BATTLE_PROTOCOLS_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _find_battle_protocols_request(game: Game):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "")) == "battle_protocols"
        ),
        None,
    )


def _attack_result_stub() -> AttackResult:
    return AttackResult(
        weapon_name="Test Weapon",
        attacker_name="Attacker",
        target_unit_name="Target",
        attacks_rolled=0,
        attacks_dice_expression="",
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _profile(*, is_ranged: bool, weapon_name: str) -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": weapon_name,
            "is_melee": (lambda self: not is_ranged),
            "is_ranged": (lambda self: is_ranged),
        },
    )()
    return WargearProfile(
        "Profile",
        {
            "range": "24" if is_ranged else "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "6",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_battle_protocols_start_of_battle_sets_aegis_on_led_kastelan_robots():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    robots = _make_unit(
        "Kastelan Robots",
        keywords=["VEHICLE", "KASTELAN ROBOT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        toughness=7,
    )
    datasmith = _make_unit(
        "Cybernetica Datasmith",
        abilities=[_battle_protocols_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        toughness=4,
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)

    _attach_leader(robots, datasmith)
    admech_army.add_unit(robots)
    admech_army.add_unit(datasmith)
    enemy_army.add_unit(enemy)
    game.map.units = [robots, datasmith, enemy]
    game.rebuild_entity_registry()

    game._on_phase_start_battle_protocols(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)

    assert str(robots.get_battle_protocols_selected_mode() or "") == "aegis_protocol"
    assert int(robots.get_effective_model_characteristic(robots.models[0], "toughness")) == 8
    assert int(datasmith.get_effective_model_characteristic(datasmith.models[0], "toughness")) == 4


def test_battle_protocols_command_phase_selection_switches_attack_modes():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    robots = _make_unit(
        "Kastelan Robots",
        keywords=["VEHICLE", "KASTELAN ROBOT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        toughness=7,
    )
    datasmith = _make_unit(
        "Cybernetica Datasmith",
        abilities=[_battle_protocols_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        toughness=4,
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)

    _attach_leader(robots, datasmith)
    admech_army.add_unit(robots)
    admech_army.add_unit(datasmith)
    enemy_army.add_unit(enemy)
    game.map.units = [robots, datasmith, enemy]
    game.rebuild_entity_registry()

    game._on_phase_start_battle_protocols(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    request = _find_battle_protocols_request(game)
    assert request is not None
    assert request.decision_type == DECISION_CHOOSE_QUARRY

    protector_option = next(
        (
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("battle_protocols_mode", "")) == "protector_protocol"
        ),
        None,
    )
    assert protector_option is not None
    result = resolve_decision_command(game, request, protector_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True
    assert str(robots.get_battle_protocols_selected_mode() or "") == "protector_protocol"

    ranged_profile = _profile(is_ranged=True, weapon_name="Kastelan phosphor blaster")
    melee_profile = _profile(is_ranged=False, weapon_name="Kastelan fist")
    ranged_attacks = ranged_profile._resolve_attack_count(
        enemy,
        robots.models[0],
        _attack_result_stub(),
        closest_dist=12.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(ranged_attacks.num_attacks or 0) == 4

    leader_ranged_attacks = ranged_profile._resolve_attack_count(
        enemy,
        datasmith.models[0],
        _attack_result_stub(),
        closest_dist=12.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(leader_ranged_attacks.num_attacks or 0) == 2

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_battle_protocols(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    request = _find_battle_protocols_request(game)
    assert request is not None
    conqueror_option = next(
        (
            opt
            for opt in list(request.options or [])
            if str((opt.payload or {}).get("battle_protocols_mode", "")) == "conqueror_protocol"
        ),
        None,
    )
    assert conqueror_option is not None
    result = resolve_decision_command(game, request, conqueror_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True
    assert str(robots.get_battle_protocols_selected_mode() or "") == "conqueror_protocol"

    melee_attacks = melee_profile._resolve_attack_count(
        enemy,
        robots.models[0],
        _attack_result_stub(),
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(melee_attacks.num_attacks or 0) == 4

    ranged_after_switch = ranged_profile._resolve_attack_count(
        enemy,
        robots.models[0],
        _attack_result_stub(),
        closest_dist=12.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(ranged_after_switch.num_attacks or 0) == 2


def test_battle_protocols_not_queued_when_datasmith_is_not_leading():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    robots = _make_unit(
        "Kastelan Robots",
        keywords=["VEHICLE", "KASTELAN ROBOT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        toughness=7,
    )
    datasmith = _make_unit(
        "Cybernetica Datasmith",
        abilities=[_battle_protocols_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        toughness=4,
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)

    admech_army.add_unit(robots)
    admech_army.add_unit(datasmith)
    enemy_army.add_unit(enemy)
    game.map.units = [robots, datasmith, enemy]
    game.rebuild_entity_registry()

    game._on_phase_start_battle_protocols(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)

    assert _find_battle_protocols_request(game) is None
    assert str(robots.get_battle_protocols_selected_mode() or "") == ""
