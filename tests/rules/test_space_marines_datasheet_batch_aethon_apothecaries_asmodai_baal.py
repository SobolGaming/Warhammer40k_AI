from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.charge import _validate_declare_charge
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    model_count: int = 1,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            model_count=model_count,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    return game, sm_army, enemy_army, sm_player, enemy_player


def _find_quarry_request(game: Game, *, ability: str) -> object | None:
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str((req.context or {}).get("ability", "") or "") == ability:
            return req
    return None


def test_master_of_shadows_marks_target_and_enforces_charge_inclusion():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE

    aethon = _make_unit(
        "Aethon Shaan",
        "000004148",
        abilities=[
            _ability(
                "Master of Shadows",
                (
                    "In your Command phase, you can select one unit from your opponent's army. Until the start "
                    "of your next Command phase, each time an ADEPTUS ASTARTES unit from your army declares a "
                    'charge while it is within 12" of that enemy unit, you can re-roll the Charge roll, but it '
                    "must declare that enemy unit as a target of that charge (if possible)."
                ),
            ),
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    charger = _make_unit(
        "Assault Squad",
        "sm_charger",
        abilities=[],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    marked_enemy = _make_unit("Marked Enemy", "enemy_marked", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    other_enemy = _make_unit("Other Enemy", "enemy_other", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(aethon)
    sm_army.add_unit(charger)
    enemy_army.add_unit(marked_enemy)
    enemy_army.add_unit(other_enemy)

    aethon.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    charger.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    marked_enemy.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    other_enemy.models[0].set_location(8.0, 3.0, 0.0, 0.0)

    game.map.units = [aethon, charger, marked_enemy, other_enemy]
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=sm_player, phase=BattleRoundPhases.COMMAND_PHASE)
    request = _find_quarry_request(game, ability="master_of_shadows")
    assert request is not None

    marked_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(marked_enemy) or "")
    )
    result = resolve_decision_command(game, request, marked_option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False))

    assert bool(charger.can_reroll_charge_roll(target_unit=marked_enemy, game=game, game_map=game.map)) is True
    assert bool(charger.can_reroll_charge_roll(target_unit=other_enemy, game=game, game_map=game.map)) is False

    game.phase = BattleRoundPhases.CHARGE_PHASE
    request_invalid = DecisionRequest.create(
        "DECLARE_CHARGE",
        "Declare charge",
        player_id=sm_player.id,
        options=[
            DecisionOption.create(
                "Other Enemy",
                payload={"unit_id": str(get_entity_id(charger) or ""), "target_unit_id": str(get_entity_id(other_enemy) or "")},
            ),
            DecisionOption.create(
                "Marked Enemy",
                payload={"unit_id": str(get_entity_id(charger) or ""), "target_unit_id": str(get_entity_id(marked_enemy) or "")},
            ),
        ],
        context={},
    )
    invalid_result = DecisionResult(
        decision_id=request_invalid.decision_id,
        player_id=sm_player.id,
        option_id=request_invalid.options[0].option_id,
        payload={"target_unit_ids": [str(get_entity_id(other_enemy) or "")]},
    )
    errors = list(_validate_declare_charge(game, request_invalid, invalid_result))
    assert any("Master of Shadows" in err for err in errors)

    valid_result = DecisionResult(
        decision_id=request_invalid.decision_id,
        player_id=sm_player.id,
        option_id=request_invalid.options[0].option_id,
        payload={
            "target_unit_ids": [
                str(get_entity_id(other_enemy) or ""),
                str(get_entity_id(marked_enemy) or ""),
            ]
        },
    )
    assert list(_validate_declare_charge(game, request_invalid, valid_result)) == []


def test_blackwing_mantle_grants_free_rapid_ingress_and_heroic_intervention_repeat_bypass():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    aethon = _make_unit(
        "Aethon Shaan",
        "000004148",
        abilities=[
            _ability(
                "Blackwing Mantle",
                (
                    "You can target this model's unit with the Rapid Ingress and Heroic Intervention "
                    "Stratagems for 0CP, even if you have already used that Stratagem on a different unit this phase."
                ),
            ),
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other = _make_unit("Other Unit", "sm_other", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy", "enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(aethon)
    sm_army.add_unit(other)
    enemy_army.add_unit(enemy)
    game.map.units = [aethon, other, enemy]
    game.rebuild_entity_registry()

    rapid_ingress = SimpleNamespace(name="RAPID INGRESS", cp_cost=1)
    heroic = SimpleNamespace(name="HEROIC INTERVENTION", cp_cost=1)

    aethon.set_reserve_status("strategic_reserves")
    preview = sm_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=aethon)
    assert int(preview.get("cost", 0) or 0) == 0
    assert any("Blackwing Mantle" in str(reason or "") for reason in list(preview.get("reasons", []) or []))

    sm_player.set_next_optional_decision("BLACKWING_MANTLE_STRATAGEM_DISCOUNT", True)
    applied = sm_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=aethon)
    assert int(applied.get("cost", 0) or 0) == 0

    manager = StratagemManager(sm_player)
    manager._used_stratagems_this_phase.add("RAPID INGRESS")
    manager._record_rapid_ingress_use(other)
    assert bool(manager._rapid_ingress_repeat_allowed(target_unit=aethon)) is True

    aethon.set_reserve_status("deployed")
    preview_heroic = sm_player.preview_stratagem_cp_cost(heroic, target_unit=aethon)
    assert int(preview_heroic.get("cost", 0) or 0) == 0

    manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
    manager._record_heroic_intervention_use(other)
    assert bool(manager._heroic_intervention_repeat_allowed(target_unit=aethon)) is True


def test_apothecary_gene_seed_recovery_triggers_when_bodyguard_unit_is_destroyed():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Apothecary",
        "000000063",
        abilities=[
            _ability(
                "Narthecium",
                "While this model is leading a unit, in your Command phase, you can return 1 destroyed model (excluding Character models) to that unit.",
            ),
            _ability(
                "Gene-seed Recovery",
                "When this model's Bodyguard unit is destroyed, roll one D6: on a 2+, you gain 1CP.",
            ),
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        attached_to=["bodyguard_ds"],
    )
    bodyguard = _make_unit(
        "Bodyguard",
        "bodyguard_ds",
        model_count=2,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(bodyguard)
    sm_army.add_unit(leader)
    game.map.units = [bodyguard]
    game.rebuild_entity_registry()

    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attach_to_unit(bodyguard)
    bodyguard.models = []
    bodyguard._pending_leader_separation = True

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        bodyguard.resolve_pending_leader_separation(game_map=game.map)

    assert int(sm_player.command_points or 0) == 1
    assert leader.attached_to is None


def test_apothecary_biologis_vivispectrum_sets_only_the_leader_model_objective_control():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    biologis = _make_unit(
        "Apothecary Biologis",
        "000000060",
        abilities=[
            _ability(
                "Vivispectrum",
                (
                    "If this model's unit destroys an enemy unit as the result of a melee attack, until the end of "
                    "the battle, this model has an Objective Control characteristic of 9."
                ),
            ),
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        attached_to=["bodyguard_ds"],
    )
    bodyguard = _make_unit(
        "Aggressors",
        "bodyguard_ds",
        model_count=2,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit("Enemy Unit", "enemy_ds", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(bodyguard)
    sm_army.add_unit(biologis)
    enemy_army.add_unit(enemy)
    bodyguard.can_be_attached_to = []
    biologis.can_be_attached_to = [bodyguard.get_datasheet_id()]
    biologis.attach_to_unit(bodyguard)
    game.map.units = [bodyguard, enemy]
    game.rebuild_entity_registry()

    melee_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True))
    game._on_unit_destroyed_rules(
        unit=enemy,
        destroyed_by_unit=bodyguard,
        destroyed_by_model=bodyguard.models[0],
        destroyed_by_weapon_profile=melee_profile,
    )

    leader_model = biologis.models[0]
    bodyguard_model = bodyguard.models[0]
    assert int(bodyguard.get_effective_model_characteristic(leader_model, "objective_control") or 0) == 9
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0) == 1


def test_asmodai_feared_interrogator_applies_fight_phase_battleshock_penalty():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.turn = 3
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE

    asmodai = _make_unit(
        "Asmodai",
        "000000225",
        abilities=[
            _ability(
                "Feared Interrogator",
                (
                    'At the start of the Fight phase, each enemy CHARACTER unit within 6" of this model must take a '
                    "Battle-shock test, subtracting 1 from that test when they do. In addition, each time this "
                    "model destroys an enemy CHARACTER model with a melee attack, you gain 1CP."
                ),
            ),
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Character",
        "enemy_character",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(asmodai)
    enemy_army.add_unit(enemy)

    asmodai.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(5.0, 0.0, 0.0, 0.0)

    recorded_modifiers: list[int] = []

    def _record_battleshock(_turn=0):
        sr = dict(getattr(enemy, "special_rules", {}) or {})
        recorded_modifiers.append(int(sr.get("battle_shock_test_modifier", 0) or 0))

    enemy.take_battle_shock_test = _record_battleshock

    game.map.units = [asmodai, enemy]
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)

    assert recorded_modifiers == [-1]


def test_baal_predator_overcharged_engines_allows_advance_reroll():
    baal = _make_unit(
        "Baal Predator",
        "000000168",
        abilities=[_ability("Overcharged Engines", "You can re-roll Advance rolls made for this model.")],
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    assert bool(baal.can_reroll_advance_roll()) is True
