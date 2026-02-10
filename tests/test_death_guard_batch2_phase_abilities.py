from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        leadership: str = "7",
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": str(leadership),
                "OC": "1",
                "base_size": "32mm",
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


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str,
    faction_keywords,
    keywords=None,
    abilities=None,
    leadership: str = "7",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            leadership=leadership,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    dg_army = Army("Death Guard", "Plague Company")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.REMOTE, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    return game, dg_army, enemy_army, dg_player, enemy_player


def _deploy(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def test_blinding_spray_requires_activation_and_apply_sets_fights_first():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    blinding_spray = {
        "name": "Blinding Spray",
        "description": (
            "In the Fight phase, you can select one model from your army with this ability to use this ability. "
            "If you do, until the end of the phase, that model's unit has the Fights First ability. "
            "Each model can only be selected for this ability once per battle."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Death Guard Source",
        "dg-src",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
        abilities=[blinding_spray],
    )
    enemy = _make_unit(
        "Enemy Target",
        "en-1",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy(source, enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    assert source.has_fight_first() is False

    game._on_phase_start_blinding_spray(player=dg_player, phase=game.phase)
    requests = [
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "")) == DECISION_CHOOSE_QUARRY
        and str((getattr(r, "context", {}) or {}).get("ability", "")) == "blinding_spray"
    ]
    assert len(requests) == 1
    request = requests[0]
    assert any(str((o.payload or {}).get("action", "")) == "skip" for o in list(request.options or []))

    source_model_id = str(source.models[0]._id)
    select_option = next(
        o for o in list(request.options or []) if str((o.payload or {}).get("model_id", "")) == source_model_id
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=dg_player.id,
        option_id=select_option.option_id,
    )
    _apply_choose_quarry(game, request, result)

    assert source.has_fight_first() is True
    assert source.models[0].has_used_once_per_battle(f"blinding_spray:{source_model_id}")


def test_blinding_spray_invalid_choice_does_not_activate():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Death Guard Source",
        "dg-src",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
    )
    enemy = _make_unit(
        "Enemy Target",
        "en-1",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy(source, enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    enemy_model_id = str(enemy.models[0]._id)
    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Blinding Spray",
        player_id=dg_player.id,
        options=[
            DecisionOption.create(
                "Invalid enemy model",
                payload={
                    "model_id": enemy_model_id,
                    "source_unit_id": source._id,
                    "ability_name": "Blinding Spray",
                },
            )
        ],
        context={
            "ability": "blinding_spray",
            "ability_name": "Blinding Spray",
            "source_unit_id": source._id,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=dg_player.id,
        option_id=request.options[0].option_id,
    )
    _apply_choose_quarry(game, request, result)

    assert bool(source.special_rules.get("blinding_spray_fight_first_active", False)) is False
    assert source.has_fight_first() is False


def test_tocsin_of_misery_forces_battleshock_and_applies_psyker_penalty():
    game, dg_army, enemy_army, _dg_player, enemy_player = _build_game()
    tocsin = {
        "name": "Tocsin of Misery (Aura)",
        "description": (
            "In the Battle-shock step of your opponent's Command phase, if an enemy unit that is below its Starting Strength "
            "is within 9\" of this model, that enemy unit must take a Battle-shock test, subtracting 1 from that test if it "
            "is a PSYKER unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Noxious Blightbringer",
        "dg-src",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
        abilities=[tocsin],
    )
    psyker_target = _make_unit(
        "Psyker Target",
        "en-psy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY", "PSYKER"],
        leadership="6",
    )
    non_psyker_target = _make_unit(
        "Non-Psyker Target",
        "en-non",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
        leadership="6",
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(psyker_target)
    enemy_army.add_unit(non_psyker_target)
    _deploy(source, psyker_target, non_psyker_target)
    game.map.units = [source, psyker_target, non_psyker_target]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    psyker_target.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    non_psyker_target.models[0].set_location(5.0, 0.0, 0.0, 0.0)

    source._model_within_range_of_unit = lambda _m, _u, _r: True
    psyker_target.is_below_starting_strength = lambda: True
    non_psyker_target.is_below_starting_strength = lambda: True

    psyker_calls = []
    non_psyker_calls = []

    def _psyker_take(current_turn=1):
        psyker_calls.append(
            (
                int(current_turn),
                int(psyker_target.special_rules.get("battle_shock_test_modifier", 0) or 0),
            )
        )

    def _non_psyker_take(current_turn=1):
        non_psyker_calls.append(
            (
                int(current_turn),
                int(non_psyker_target.special_rules.get("battle_shock_test_modifier", 0) or 0),
            )
        )

    psyker_target.take_battle_shock_test = _psyker_take
    non_psyker_target.take_battle_shock_test = _non_psyker_take

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 1
    game._on_phase_start_tocsin_of_misery(player=enemy_player, phase=game.phase)

    assert psyker_calls == [(2, -1)]
    assert non_psyker_calls == [(2, 0)]


def test_pestilent_fallout_parses_enfeebled_post_shoot_spec():
    pestilent_fallout = {
        "name": "Pestilent Fallout (Psychic)",
        "description": (
            "In your Shooting phase, after this model has shot, select one enemy INFANTRY unit hit by one or more of those "
            "attacks made with its Plague Wind. Until the end of your opponent's next turn, that unit is enfeebled. While a "
            "unit is enfeebled, subtract 2\" from the Move characteristic of models in that unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Rotigus",
        "dg-src",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["MONSTER", "PSYKER"],
        abilities=[pestilent_fallout],
    )

    specs = source.model_post_shoot_wracking_agonies_specs(source.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("weapon_key", "")) == "plague wind"
    assert int(spec.get("move_penalty", 0) or 0) == -2
    assert int(spec.get("charge_penalty", 0) or 0) == 0


def test_silent_bodyguard_grants_fnp_to_attached_character():
    silent_bodyguard = {
        "name": "Silent Bodyguard",
        "description": (
            "While a CHARACTER model is leading this unit, that CHARACTER model has the Feel No Pain 4+ ability."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    bodyguard = _make_unit(
        "Deathshroud Terminators",
        "dg-bg",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
        abilities=[silent_bodyguard],
    )
    leader = _make_unit(
        "Death Guard Character",
        "dg-ldr",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["CHARACTER", "INFANTRY"],
    )
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]

    bodyguard._refresh_bearer_unit_common_modifiers()

    fnp_vals = list(leader.has_feel_no_pain(target_model=leader.models[0]) or [])
    assert any(int(v[0]) == 4 for v in fnp_vals)


def test_sickening_vitality_parses_that_unit_movement_bonus_and_rerolls():
    sickening_vitality = {
        "name": "Sickening Vitality",
        "description": (
            "While this model is leading a unit, add 1\" to the Move characteristic of that unit and you can re-roll "
            "Advance and Charge rolls made for that unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    bodyguard = _make_unit(
        "Plague Marines",
        "dg-bg",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
    )
    leader = _make_unit(
        "Death Guard Character",
        "dg-ldr",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[sickening_vitality],
    )
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]

    bodyguard._refresh_bearer_unit_common_modifiers()
    movement = bodyguard.get_effective_model_characteristic(bodyguard.models[0], "movement")

    assert int(movement) == 7
    assert bodyguard.can_reroll_advance_roll() is True
    assert bodyguard.can_reroll_charge_roll() is True


def test_sevenfold_chant_command_phase_cp_roll_resolves_gain():
    game, dg_army, _enemy_army, dg_player, _enemy_player = _build_game()
    sevenfold_chant = {
        "name": "Sevenfold Chant",
        "description": "In your Command phase, if this model is on the battlefield, roll 2D6. On a 7+, you gain 1CP.",
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Tallyman",
        "dg-src",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY", "CHARACTER"],
        abilities=[sevenfold_chant],
    )
    dg_army.add_unit(source)
    _deploy(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    specs = list(source.special_rules.get("command_phase_bonus_cp_roll_specs", []) or [])
    assert len(specs) == 1
    assert int(specs[0].get("dice_count", 0) or 0) == 2
    assert int(specs[0].get("threshold", 0) or 0) == 7
    assert int(specs[0].get("cp", 0) or 0) == 1

    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    before_cp = int(dg_player.command_points or 0)
    with patch("warhammer40k_ai.engine.game_mixins.phase_handlers_mixin.get_roll", return_value=8):
        game._on_phase_start_command_phase_cp_rolls(player=dg_player, phase=game.phase)
    after_cp = int(dg_player.command_points or 0)

    assert after_cp == before_cp + 1
