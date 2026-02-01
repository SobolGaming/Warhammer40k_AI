from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
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
        datasheet_id: str | None = None,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 2,
        inv_sv: str = "7",
        attached_to=None,
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": inv_sv,
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 2,
    inv_sv: str = "7",
    attached_to=None,
):
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
        wounds=wounds,
        inv_sv=inv_sv,
        attached_to=attached_to,
    )
    return Unit(datasheet)


def _build_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Army1", detachment_type="Detachment1")
    army1.faction_id = "AE"
    army2 = Army("Army2", detachment_type="Detachment2")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    return game, army1, army2, p1, p2


def test_whispering_web_marks_target_and_sets_crit_threshold():
    ability = Ability(
        "Whispering Web",
        "AE",
        (
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
            "Until the end of the turn, each time a friendly AELDARI model makes an attack that targets that unit, "
            "an unmodified Hit roll of 5+ scores a Critical Hit."
        ),
        "Datasheet",
        "",
    )
    attacker = _make_unit("Death Jester", abilities=[ability], faction_keywords=["AELDARI"])
    target = _make_unit("Target", faction_keywords=["ENEMY"])

    game, army1, army2, p1, _p2 = _build_game()
    army1.add_unit(attacker)
    army2.add_unit(target)
    game.map.units = [attacker, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    attacker_model = attacker.models[0]
    game._on_unit_shooting_resolved_post_shoot_crit_hit_threshold(
        attacker_unit=attacker,
        hits_by_target={target: 1},
        hit_models_by_target={target: {attacker_model}},
    )

    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY

    resolve_decision_command(game, req, req.options[0].option_id, player_id=p1.id)

    sr = getattr(target, "special_rules", {}) or {}
    assert sr.get("post_shoot_crit_hit_threshold_active") is True

    mods = attacker.get_unit_hit_reroll_modifiers("ranged", target=target)
    assert int(mods.get("crit_hit_threshold") or 0) == 5


def test_death_is_not_enough_applies_battleshock_modifier_on_kill():
    ability = Ability(
        "Death is Not Enough",
        "AE",
        (
            "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
            "hit by one or more of those attacks. That enemy unit must take a Battle-shock test. "
            "If one or more of those attacks destroyed a model in that enemy unit, subtract 1 from that test."
        ),
        "Datasheet",
        "",
    )
    attacker = _make_unit("Death Jester", abilities=[ability])
    target = _make_unit("Target")

    game, army1, army2, p1, _p2 = _build_game()
    army1.add_unit(attacker)
    army2.add_unit(target)
    game.map.units = [attacker, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    attacker_model = attacker.models[0]
    captured = {}

    def _fake_battleshock(_turn=1):
        captured["modifier"] = (target.special_rules or {}).get("battle_shock_test_modifier")

    target.take_battle_shock_test = _fake_battleshock

    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=attacker,
        hits_by_target={target: 1},
        hit_models_by_target={target: {attacker_model}},
        killing_models_by_target={target: {attacker_model}},
    )

    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    resolve_decision_command(game, req, req.options[0].option_id, player_id=p1.id)

    assert captured.get("modifier") == -1


def test_shadow_field_breaks_invulnerable_save():
    ability = Ability(
        "Shadow Field",
        "AE",
        (
            "You cannot re-roll invulnerable saving throws made for the bearer. "
            "The first time an invulnerable saving throw made for the bearer is failed, "
            "until the end of the battle the bearer has no invulnerable save."
        ),
        "Datasheet",
        "",
    )
    unit = _make_unit("Shadowseer", abilities=[ability], inv_sv="4")
    model = unit.models[0]
    model.set_location(0.0, 0.0, 0.0, 0.0)

    profile = WargearProfile(
        "Test Gun",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-3",
            "D": "1",
            "description": "",
        },
    )

    res1 = profile._save_with_tracking(
        model,
        {"weapon_profile": profile, "is_mortal": False},
        ap=-3,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert "Shadow Field broken" in res1.get("special_effects", [])
    assert unit.is_shadow_field_broken(model) is True

    res2 = profile._save_with_tracking(
        model,
        {"weapon_profile": profile, "is_mortal": False},
        ap=-3,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert res2.get("save_type") == "armor"
    assert int(res2.get("final_save") or 0) >= 6


def test_sonic_destruction_bonus_scales_with_other_attackers():
    ability = Ability("Sonic Destruction", "AE", "Sonic Destruction", "Datasheet", "")
    unit_a = _make_unit("Vibro A", abilities=[ability])
    unit_b = _make_unit("Vibro B", abilities=[ability])
    target = _make_unit("Target")

    game, army1, army2, p1, _p2 = _build_game()
    army1.add_unit(unit_a)
    army1.add_unit(unit_b)
    army2.add_unit(target)
    game.map.units = [unit_a, unit_b, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    profile = WargearProfile(
        "Vibro Cannon",
        {
            "range": "36",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Vibro Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    res1 = profile.attack(target, unit_a.models[0], game_map=game.map, attack_context={})
    assert not any("Sonic Destruction" in str(x) for x in res1.attacks_special_modifiers)

    res2 = profile.attack(target, unit_b.models[0], game_map=game.map, attack_context={})
    assert any("Sonic Destruction" in str(x) for x in res2.attacks_special_modifiers)


def test_spirit_mark_applies_sustained_hits_vs_marked_target():
    ability = Ability(
        "Spirit Mark (Psychic)",
        "AE",
        (
            "Once per turn, in your Movement phase, when this model starts or ends a move, select one friendly "
            "Wraith Construct unit within 6\" of this model (excluding TITANIC units) and one enemy unit visible to this model. "
            "Until the start of your next Movement phase, weapons equipped by models in that friendly unit have the "
            "[SUSTAINED HITS 1] ability while targeting that enemy unit."
        ),
        "Datasheet",
        "",
    )
    spiritseer = _make_unit("Spiritseer", abilities=[ability])
    friendly = _make_unit("Wraithguard", keywords=["WRAITH CONSTRUCT"])
    enemy = _make_unit("Enemy")

    game, army1, army2, p1, _p2 = _build_game()
    army1.add_unit(spiritseer)
    army1.add_unit(friendly)
    army2.add_unit(enemy)
    game.map.units = [spiritseer, friendly, enemy]
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    for unit in (spiritseer, friendly, enemy):
        unit.deployed = True
        unit.reserve_status = "deployed"

    spiritseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    game._on_unit_move_started_spirit_mark(unit=spiritseer, action="move")

    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    friendly_id = get_entity_id(friendly)
    option_id = None
    for opt in list(req.options or []):
        payload = opt.payload or {}
        if payload.get("target_unit_id") == friendly_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=p1.id)

    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    resolve_decision_command(game, req, req.options[0].option_id, player_id=p1.id)

    bonus = friendly.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=friendly.models[0],
        weapon_profile=None,
        weapon_name="Gun",
        target=enemy,
    )
    assert int(bonus.get("sustained_hits_value") or 0) == 1


def test_tears_of_isha_heals_when_no_destroyed_models(monkeypatch):
    ability = Ability(
        "Tears of Isha (Psychic)",
        "AE",
        (
            "In your Command phase, select one friendly Wraith Construct unit within 6\" of this model. "
            "If one or more models in that unit are destroyed, you can return one destroyed model to that unit. "
            "Otherwise, one model in that unit regains up to D3 lost wounds. Each unit can only be selected for this ability once per turn."
        ),
        "Datasheet",
        "",
    )
    spiritseer = _make_unit("Spiritseer", abilities=[ability])
    target = _make_unit("Wraithguard", keywords=["WRAITH CONSTRUCT"], wounds=4)

    game, army1, _army2, p1, _p2 = _build_game()
    army1.add_unit(spiritseer)
    army1.add_unit(target)
    game.map.units = [spiritseer, target]
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    for unit in (spiritseer, target):
        unit.deployed = True
        unit.reserve_status = "deployed"

    spiritseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    target.models[0].wounds = 2

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: 2)

    game._on_phase_start_tears_of_isha(player=p1, phase=game.phase)
    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    resolve_decision_command(game, req, req.options[0].option_id, player_id=p1.id)

    assert target.models[0].wounds == 4


def test_tears_of_isha_queues_bodyguard_return_when_destroyed():
    ability = Ability(
        "Tears of Isha (Psychic)",
        "AE",
        (
            "In your Command phase, select one friendly Wraith Construct unit within 6\" of this model. "
            "If one or more models in that unit are destroyed, you can return one destroyed model to that unit. "
            "Otherwise, one model in that unit regains up to D3 lost wounds. Each unit can only be selected for this ability once per turn."
        ),
        "Datasheet",
        "",
    )
    spiritseer = _make_unit("Spiritseer", abilities=[ability])
    target = _make_unit("Wraithguard", keywords=["WRAITH CONSTRUCT"], model_count=2)

    game, army1, _army2, p1, _p2 = _build_game()
    army1.add_unit(spiritseer)
    army1.add_unit(target)
    game.map.units = [spiritseer, target]
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    for unit in (spiritseer, target):
        unit.deployed = True
        unit.reserve_status = "deployed"

    lost = target.models[0]
    target.remove_model(lost)
    assert lost in target.models_lost

    spiritseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(3.0, 0.0, 0.0, 0.0)

    game._on_phase_start_tears_of_isha(player=p1, phase=game.phase)
    pending = list(game.decision_queue.list() or [])
    assert pending
    req = pending[0]
    resolve_decision_command(game, req, req.options[0].option_id, player_id=p1.id)

    pending = list(game.decision_queue.list() or [])
    assert any(r.decision_type == DECISION_ALLOCATE_DAMAGE for r in pending)


def test_tactical_acumen_sets_no_charge_after_reactive_move():
    ability = Ability(
        "Tactical Acumen",
        "AE",
        (
            "While this model is leading a unit, in your Shooting phase, after that unit has shot, it can make a Normal move "
            "of up to 6\". If it does, until the end of the turn, that unit is not eligible to declare a charge."
        ),
        "Datasheet",
        "",
    )
    bodyguard = _make_unit("Guardians", datasheet_id="bodyguard1", model_count=1)
    leader = _make_unit("Leader", datasheet_id="leader1", abilities=[ability], attached_to=["bodyguard1"])
    enemy = _make_unit("Enemy", model_count=1)

    game, army1, army2, p1, _p2 = _build_game()
    army1.add_unit(bodyguard)
    army1.add_unit(leader)
    army2.add_unit(enemy)
    leader.attach_to_unit(bodyguard)

    bodyguard.deployed = True
    bodyguard.reserve_status = "deployed"
    enemy.deployed = True
    enemy.reserve_status = "deployed"

    bodyguard.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    game.map.units = [bodyguard, leader, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game.event_system.publish("unit_shooting_resolved", attacker_unit=bodyguard, hits_by_target={enemy: 1})

    pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_MOVE_UNIT]
    assert pending
    move_request = pending[0]

    confirm_option = None
    for opt in list(move_request.options or []):
        if str((opt.payload or {}).get("action", "") or "") == "confirm":
            confirm_option = opt
            break
    assert confirm_option is not None

    model_positions = [
        {
            "model_id": get_entity_id(bodyguard.models[0]),
            "position": [0.0, 0.0, 0.0],
            "facing": 0.0,
        }
    ]
    resolve_decision_command(
        game,
        move_request,
        confirm_option.option_id,
        result_payload={"model_positions": model_positions},
        player_id=p1.id,
    )

    sr = getattr(bodyguard, "special_rules", {}) or {}
    assert sr.get("tactical_acumen_no_charge_turn_owner") == p1.id
    assert bodyguard.can_declare_charge_against(enemy, game) is False


def test_word_of_phoenix_queues_bodyguard_return(monkeypatch):
    ability = Ability(
        "Word of the Phoenix (Psychic)",
        "AE",
        (
            "While this model is leading a unit, in your Command phase, roll one D6: on a 2+, "
            "D3+1 destroyed bodyguard models (excluding Support Weapon models) are returned to that unit "
            "with their full wounds remaining."
        ),
        "Datasheet",
        "",
    )
    bodyguard = _make_unit("Guardians", datasheet_id="bodyguard2", model_count=2)
    leader = _make_unit("Leader", datasheet_id="leader2", abilities=[ability], attached_to=["bodyguard2"])

    game, army1, _army2, p1, _p2 = _build_game()
    army1.add_unit(bodyguard)
    army1.add_unit(leader)
    leader.attach_to_unit(bodyguard)

    bodyguard.deployed = True
    bodyguard.reserve_status = "deployed"
    leader.deployed = True
    leader.reserve_status = "deployed"

    lost = bodyguard.models[0]
    bodyguard.remove_model(lost)
    assert lost in bodyguard.models_lost

    game.map.units = [bodyguard, leader]
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    def _fake_roll(expr):
        key = str(expr).strip().upper()
        if key == "D6":
            return 2
        if key == "D3":
            return 2
        return 1

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_roll)
    monkeypatch.setattr("warhammer40k_ai.engine.game.get_roll", _fake_roll)

    game._on_phase_start_word_of_phoenix(player=p1, phase=game.phase)
    pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_ALLOCATE_DAMAGE]
    assert pending
    ctx = pending[0].context or {}
    assert ctx.get("selection_kind") == "bodyguard_return"
    assert int(ctx.get("remaining") or 0) == 3
