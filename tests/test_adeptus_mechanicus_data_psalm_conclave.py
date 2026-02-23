from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
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
                "T": "4",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Data-Psalm Conclave")
    admech_army.faction_id = "ADM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    return game, admech_army, enemy_army, admech_player, enemy_player


def _find_data_psalm_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "data_psalm_benediction"
    ]


def _choose_benediction(game: Game, request, *, player_id: str, choice_key: str) -> None:
    wanted = str(choice_key or "").strip().upper()
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


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


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Gamma Blaster", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Ranged",
        {
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Power Blades", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_data_psalm_round_one_queues_benediction_selection():
    game, admech_army, _enemy_army, admech_player, _enemy_player = _build_game()
    admech_army.on_battle_round_start(1)
    requests = _find_data_psalm_requests(game)
    assert len(requests) == 1
    request = requests[0]
    assert request.player_id == admech_player.id
    choices = {
        str((opt.payload or {}).get("choice_key", "") or "").strip().upper()
        for opt in list(request.options or [])
    }
    assert choices == {"PANEGYRIC_PROCESSION", "CITATION_IN_SAVAGERY"}


def test_panegyric_procession_improves_ap_at_half_range_for_cult_mechanicus_units():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    cult_unit = _make_unit(
        "Corpuscarii Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["SPACE MARINES"])
    admech_army.add_unit(cult_unit)
    enemy_army.add_unit(enemy)
    cult_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(18.0, 10.0, 0.0, 0.0)
    game.map.units = [cult_unit, enemy]

    admech_army.on_battle_round_start(1)
    request = _find_data_psalm_requests(game)[0]
    _choose_benediction(game, request, player_id=admech_player.id, choice_key="PANEGYRIC_PROCESSION")

    profile = _ranged_profile()
    attacker_model = cult_unit.models[0]
    assert profile.get_effective_ap(attacker_model, enemy) == -1

    enemy.models[0].set_location(30.0, 10.0, 0.0, 0.0)
    assert profile.get_effective_ap(attacker_model, enemy) == 0


def test_citation_in_savagery_grants_melee_strength_and_attacks_when_charged():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    cult_unit = _make_unit(
        "Fulgurite Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["SPACE MARINES"])
    admech_army.add_unit(cult_unit)
    enemy_army.add_unit(enemy)
    cult_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    game.map.units = [cult_unit, enemy]

    admech_army.on_battle_round_start(1)
    request = _find_data_psalm_requests(game)[0]
    _choose_benediction(game, request, player_id=admech_player.id, choice_key="CITATION_IN_SAVAGERY")

    profile = _melee_profile()
    attacker_model = cult_unit.models[0]
    cult_unit.round_state.charged_this_round = True

    attack_result = _attack_result_stub()
    attack_info = profile._resolve_attack_count(
        enemy,
        attacker_model,
        attack_result,
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(attack_info.num_attacks or 0) == 3
    assert any("Citation in Savagery" in str(v) for v in list(attack_result.attacks_special_modifiers or []))

    wound_result = profile._wound_target_with_tracking(
        enemy,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Citation in Savagery" in str(v) for v in list(wound_result.get("modifiers", []) or []))

    cult_unit.round_state.charged_this_round = False
    attack_result_no_charge = _attack_result_stub()
    attack_info_no_charge = profile._resolve_attack_count(
        enemy,
        attacker_model,
        attack_result_no_charge,
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(attack_info_no_charge.num_attacks or 0) == 2
