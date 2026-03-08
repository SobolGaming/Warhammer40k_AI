from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


DISRUPTION_BOMBARDMENT_TEXT = (
    "In your Shooting phase, after this unit has shot, select one enemy INFANTRY unit "
    "hit by one or more of those attacks. Until the end of your opponent's next turn, that enemy unit is disrupted. "
    "While a unit is disrupted, subtract 2 from its Move characteristic and subtract 2 from Advance and Charge rolls made for it."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None, move: int = 6):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": "4",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "28mm",
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


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None, move: int = 6) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            move=move,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", detachment_type="Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=tyr_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, tyr_army, enemy_army, p1, p2


def _disruption_bombardment_ability():
    return {
        "name": "Disruption Bombardment",
        "description": DISRUPTION_BOMBARDMENT_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def _find_request(game: Game):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "")) == "post_shoot_shocked"
        ),
        None,
    )


def test_disruption_bombardment_filters_to_infantry_and_applies_penalties():
    game, tyr_army, enemy_army, p1, p2 = _build_game()
    attacker = _make_unit(
        "Barbgaunts",
        abilities=[_disruption_bombardment_ability()],
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_infantry = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        move=6,
    )
    enemy_vehicle = _make_unit(
        "Enemy Vehicle",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        move=10,
    )
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(enemy_infantry)
    enemy_army.add_unit(enemy_vehicle)
    game.map.units = [attacker, enemy_infantry, enemy_vehicle]
    game.rebuild_entity_registry()

    game._on_unit_shooting_resolved_post_shoot_shocked(
        attacker_unit=attacker,
        hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
    )

    request = _find_request(game)
    assert request is not None
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    option_target_ids = {
        str((getattr(opt, "payload", {}) or {}).get("target_unit_id", ""))
        for opt in list(request.options or [])
    }
    assert str(enemy_infantry._id) in option_target_ids
    assert str(enemy_vehicle._id) not in option_target_ids

    chosen = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == str(enemy_infantry._id)
    )
    result = resolve_decision_command(game, request, chosen.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False))

    sr = dict(getattr(enemy_infantry, "special_rules", {}) or {})
    assert bool(sr.get("shocked_active")) is True
    assert str(sr.get("shocked_owner", "")) == str(p1.id)
    assert int(sr.get("shocked_move_penalty", 0) or 0) == -2
    assert int(sr.get("shocked_advance_penalty", 0) or 0) == -2
    assert int(sr.get("shocked_charge_penalty", 0) or 0) == -2
    assert int(enemy_infantry.get_effective_model_characteristic(enemy_infantry.models[0], "movement")) == 4

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game._on_phase_end_shocked_cleanup(player=p1, phase=game.phase)
    assert bool(getattr(enemy_infantry, "special_rules", {}).get("shocked_active")) is True
    game._on_phase_end_shocked_cleanup(player=p2, phase=game.phase)
    assert bool(getattr(enemy_infantry, "special_rules", {}).get("shocked_active")) is False


def test_disruption_bombardment_does_not_queue_without_hit_infantry_targets():
    game, tyr_army, enemy_army, _p1, _p2 = _build_game()
    attacker = _make_unit(
        "Barbgaunts",
        abilities=[_disruption_bombardment_ability()],
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_vehicle = _make_unit(
        "Enemy Vehicle",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(enemy_vehicle)
    game.map.units = [attacker, enemy_vehicle]
    game.rebuild_entity_registry()

    game._on_unit_shooting_resolved_post_shoot_shocked(
        attacker_unit=attacker,
        hits_by_target={enemy_vehicle: 1},
    )

    assert _find_request(game) is None
