from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


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


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Explorator Maniple")
    admech_army.faction_id = "ADM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)

    obj_alpha = _make_objective("Alpha", 10.0, 10.0)
    obj_beta = _make_objective("Beta", 30.0, 10.0)
    game.objectives = [obj_alpha, obj_beta]
    game.map.objectives = [obj_alpha, obj_beta]
    return game, admech_army, enemy_army, admech_player, enemy_player, obj_alpha, obj_beta


def _find_acquisition_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "acquisition_at_any_cost"
    ]


def _choose_objective(game: Game, request, *, player_id: str, objective_id: str) -> None:
    wanted = str(objective_id or "").strip()
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("objective_id", "") or "").strip() == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def test_explorator_command_phase_queues_acquisition_objective_selection():
    game, admech_army, _enemy_army, admech_player, _enemy_player, obj_alpha, obj_beta = _build_game()
    game.turn = 1
    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    requests = _find_acquisition_requests(game)
    assert len(requests) == 1
    request = requests[0]
    assert request.player_id == admech_player.id
    objective_ids = {
        str((opt.payload or {}).get("objective_id", "") or "").strip()
        for opt in list(request.options or [])
    }
    assert objective_ids == {
        str(get_entity_id(obj_alpha) or ""),
        str(get_entity_id(obj_beta) or ""),
    }


def test_acquisition_at_any_cost_rerolls_wound_ones_when_attacker_within_selected_objective():
    game, admech_army, enemy_army, admech_player, _enemy_player, obj_alpha, _obj_beta = _build_game()
    attacker = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["SPACE MARINES"])
    admech_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    game.map.units = [attacker, enemy]
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(40.0, 10.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    request = _find_acquisition_requests(game)[0]
    _choose_objective(game, request, player_id=admech_player.id, objective_id=str(get_entity_id(obj_alpha) or ""))

    modifiers = attacker.get_model_wound_reroll_modifiers(attacker.models[0], target=enemy)
    assert 1 in set(modifiers.get("reroll_wound_values", ()) or ())
    assert any("Acquisition At Any Cost" in str(v) for v in list(modifiers.get("reroll_wound_reasons", ()) or ()))


def test_acquisition_at_any_cost_rerolls_wound_ones_when_target_within_selected_objective():
    game, admech_army, enemy_army, admech_player, _enemy_player, obj_alpha, _obj_beta = _build_game()
    attacker = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["SPACE MARINES"])
    admech_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    game.map.units = [attacker, enemy]
    attacker.models[0].set_location(40.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    request = _find_acquisition_requests(game)[0]
    _choose_objective(game, request, player_id=admech_player.id, objective_id=str(get_entity_id(obj_alpha) or ""))

    modifiers = attacker.get_model_wound_reroll_modifiers(attacker.models[0], target=enemy)
    assert 1 in set(modifiers.get("reroll_wound_values", ()) or ())


def test_acquisition_objective_expires_at_start_of_next_command_phase():
    game, admech_army, enemy_army, admech_player, _enemy_player, obj_alpha, _obj_beta = _build_game()
    attacker = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["SPACE MARINES"])
    admech_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    game.map.units = [attacker, enemy]
    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(40.0, 10.0, 0.0, 0.0)
    game.rebuild_entity_registry()

    mgr = admech_army.adeptus_mechanicus_detachments
    game.turn = 1
    mgr.on_command_phase_start(game=game, player=admech_player)
    request = _find_acquisition_requests(game)[0]
    _choose_objective(game, request, player_id=admech_player.id, objective_id=str(get_entity_id(obj_alpha) or ""))
    before = attacker.get_model_wound_reroll_modifiers(attacker.models[0], target=enemy)
    assert 1 in set(before.get("reroll_wound_values", ()) or ())

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=admech_player)
    after = attacker.get_model_wound_reroll_modifiers(attacker.models[0], target=enemy)
    assert 1 not in set(after.get("reroll_wound_values", ()) or ())
