from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


HYPNOTIC_GAZE_RULE = (
    "At the start of the Fight phase, select one enemy unit within Engagement Range of this model. "
    "Until the end of the phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        faction_name: str = "Tyranids",
        base_size: str = "25mm",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "5",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
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


def _make_unit(
    name: str,
    *,
    model_count: int = 1,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    base_size: str = "25mm",
):
    return Unit(
        _MockDatasheet(
            name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            base_size=base_size,
        ),
        quantity=int(model_count),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 1
    game.current_player_index = 0

    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _find_hypnotic_gaze_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "fight_phase_select_enemy_melee_hit_penalty":
            continue
        return req
    return None


def _build_melee_profile():
    melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=melee_parent,
    )


def test_hypnotic_gaze_queues_selection_and_applies_melee_hit_penalty():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    broodlord = _make_unit(
        "Broodlord",
        model_count=1,
        abilities=[{"name": "Hypnotic Gaze (Psychic)", "description": HYPNOTIC_GAZE_RULE, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        base_size="25mm",
    )
    enemy = _make_unit(
        "Enemy Infantry",
        model_count=1,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        base_size="25mm",
    )
    broodlord.deployed = True
    enemy.deployed = True
    broodlord.reserve_status = "deployed"
    enemy.reserve_status = "deployed"
    broodlord.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    enemy.models[0].set_location(21.8, 20.0, 0.0, 0.0)

    tyr_army.add_unit(broodlord)
    enemy_army.add_unit(enemy)
    assert game.map.place_unit(broodlord)
    assert game.map.place_unit(enemy)
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=tyr_player, phase=game.phase)
    request = _find_hypnotic_gaze_request(game)
    assert request is not None

    choose_enemy = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("target_unit_id", "")) == str(get_entity_id(enemy) or "")
    )
    resolved = resolve_decision_command(
        game,
        request,
        choose_enemy.option_id,
        result_payload={},
        player_id=tyr_player.id,
    )
    assert bool(getattr(resolved, "ok", False))

    target_sr = dict(getattr(enemy, "special_rules", {}) or {})
    assert bool(target_sr.get("fight_selected_enemy_melee_hit_penalty_active"))
    assert int(target_sr.get("fight_selected_enemy_melee_hit_penalty_value", 0) or 0) == 1
    assert any("hypnotic gaze" in str(source).lower() for source in list(target_sr.get("fight_selected_enemy_melee_hit_penalty_sources", []) or []))

    profile = _build_melee_profile()
    aura_stub = SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )
    attack_instance = {"_aura_attack_mods": aura_stub}
    hit_res = profile._hit_target_with_tracking(
        broodlord,
        enemy.models[0],
        attack_instance,
        roll_value=4,
        log_roll=False,
    )
    assert any("hypnotic gaze" in str(mod).lower() for mod in list(hit_res.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    cleared_sr = dict(getattr(enemy, "special_rules", {}) or {})
    assert "fight_selected_enemy_melee_hit_penalty_active" not in cleared_sr
