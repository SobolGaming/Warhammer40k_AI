from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Companions of Vehemence")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for req in list(game.decision_queue.list() or []):
        if getattr(req, "decision_type", None) == decision_type:
            return req
    return None


def _melee_wargear(name: str = "Power Sword") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def test_companions_of_vehemence_stratagem_descriptors_registered():
    expected = {
        "000010393002": ("Devout Push", "extend_pile_in_and_consolidate_to_six"),
        "000010393007": ("Dread Crusaders", "force_battleshock_test_with_modifier"),
        "000010393004": ("For the Emperor's Honour!", "grant_precision_to_melee_weapons"),
        "000010393003": ("Hearts Hardened to Duty", "consolidate_ignore_closest_enemy_requirement"),
        "000010393006": ("Heresy Begets Retribution", "reactive_retribution_move_toward_closest_enemy"),
        "000010393005": ("Pious Enmity", "reroll_melee_hit_ones_and_conditional_wound_ones"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_devout_push_queues_extends_fight_moves_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    crusaders = _make_unit(
        "Primaris Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(crusaders)
    _deploy_unit(game, crusaders, 10.0, 10.0)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "DEVOUT PUSH")
    assert pending is not None

    ok = sm_player.stratagems.use("DEVOUT PUSH", unit=crusaders, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert float(crusaders.get_fight_phase_move_distance_override("pile_in") or 0.0) == 6.0
    assert float(crusaders.get_fight_phase_move_distance_override("consolidate") or 0.0) == 6.0

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert crusaders.get_fight_phase_move_distance_override("pile_in") is None
    assert crusaders.get_fight_phase_move_distance_override("consolidate") is None


def test_for_the_emperors_honour_grants_precision_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    brethren = _make_unit(
        "Sword Brethren",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    brethren.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(brethren)
    _deploy_unit(game, brethren, 10.0, 10.0)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "FOR THE EMPEROR'S HONOUR!")
    assert pending is not None

    ok = sm_player.stratagems.use("FOR THE EMPEROR'S HONOUR!", unit=brethren, dequeue=True)
    assert ok is True
    bonuses = brethren.models[0].get_temporary_weapon_keyword_bonuses("Power Sword")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "PRECISION"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(brethren.models[0].get_temporary_weapon_keyword_bonuses("Power Sword") or []) == []


def test_hearts_hardened_to_duty_queues_before_consolidate_and_updates_rules():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    crusaders = _make_unit(
        "Primaris Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(crusaders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, crusaders, 10.0, 10.0)
    _deploy_unit(game, enemy, 13.0, 10.0)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("fight_attacks_resolved", unit=crusaders, target_unit=enemy)
    pending = _pending_by_name(sm_player.stratagems, "HEARTS HARDENED TO DUTY")
    assert pending is not None

    ok = sm_player.stratagems.use("HEARTS HARDENED TO DUTY", unit=crusaders, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=crusaders)
    assert bool(rules.get("consolidate_ignore_closest_enemy_requirement", False)) is True

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=crusaders)
    assert bool(rules.get("consolidate_ignore_closest_enemy_requirement", False)) is False


def test_dread_crusaders_queues_on_charge_declared_and_forces_battleshock():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defenders = _make_unit(
        "Primaris Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    charger = _make_unit(
        "Enemy Charger",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    charger.force_battle_shock_test = Mock()
    sm_army.add_unit(defenders)
    enemy_army.add_unit(charger)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, charger, 16.0, 10.0)

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("charge_declared", unit=charger, target_units=[defenders])
    pending = _pending_by_name(sm_player.stratagems, "DREAD CRUSADERS")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "DREAD CRUSADERS",
        unit=defenders,
        charging_unit=charger,
        target_units=[defenders],
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    charger.force_battle_shock_test.assert_called_once_with(1, modifier=-1, source="DREAD CRUSADERS")


def test_heresy_begets_retribution_queues_reactive_move_request():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    chaplain = _make_unit(
        "Chaplain",
        keywords=["INFANTRY", "CHAPLAIN"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(chaplain)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, chaplain, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    pending = _pending_by_name(sm_player.stratagems, "HERESY BEGETS RETRIBUTION")
    assert pending is not None

    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=4):
        ok = sm_player.stratagems.use(
            "HERESY BEGETS RETRIBUTION",
            unit=chaplain,
            dequeue=True,
        )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    request = _first_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_kind", "") or "") == "heresy_begets_retribution"
    assert str(context.get("reactive_move_movement_type", "") or "") == "retribution_move"
    assert bool(context.get("reactive_move_allow_engagement_range", False)) is True
    assert int(context.get("max_distance", 0) or 0) == 4


def test_pious_enmity_queues_and_sets_melee_reroll_support():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    chaplain = _make_unit(
        "Chaplain",
        keywords=["INFANTRY", "CHAPLAIN"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    monster = _make_unit(
        "Enemy Monster",
        faction_name="Enemy",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
    )
    infantry = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    chaplain.models[0].wargear = [_melee_wargear("Crozius")]
    sm_army.add_unit(chaplain)
    enemy_army.add_unit(monster)
    enemy_army.add_unit(infantry)
    _deploy_unit(game, chaplain, 10.0, 10.0)
    _deploy_unit(game, monster, 12.0, 10.0)
    _deploy_unit(game, infantry, 18.0, 10.0)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "PIOUS ENMITY")
    assert pending is not None

    ok = sm_player.stratagems.use("PIOUS ENMITY", unit=chaplain, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    mgr = sm_army.space_marines_detachments
    reroll_hit_ones, hit_source = mgr.companions_of_vehemence_pious_enmity_reroll_hit_ones(
        chaplain.models[0],
        attack_type="melee",
        game=game,
    )
    reroll_wound_ones_vs_monster, wound_source = mgr.companions_of_vehemence_pious_enmity_reroll_wound_ones(
        chaplain.models[0],
        monster,
        attack_type="melee",
        game=game,
    )
    reroll_wound_ones_vs_infantry, _ = mgr.companions_of_vehemence_pious_enmity_reroll_wound_ones(
        chaplain.models[0],
        infantry,
        attack_type="melee",
        game=game,
    )
    reroll_hit_ones_ranged, _ = mgr.companions_of_vehemence_pious_enmity_reroll_hit_ones(
        chaplain.models[0],
        attack_type="ranged",
        game=game,
    )
    assert reroll_hit_ones is True
    assert hit_source == "PIOUS ENMITY"
    assert reroll_wound_ones_vs_monster is True
    assert wound_source == "PIOUS ENMITY"
    assert reroll_wound_ones_vs_infantry is False
    assert reroll_hit_ones_ranged is False

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    reroll_after_cleanup, _ = mgr.companions_of_vehemence_pious_enmity_reroll_hit_ones(
        chaplain.models[0],
        attack_type="melee",
        game=game,
    )
    assert reroll_after_cleanup is False
