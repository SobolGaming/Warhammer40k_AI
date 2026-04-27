from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, VoiceOfCommandManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


OMNISSIAHS_BLESSING_TEXT = (
    "In your Command phase, select one friendly Astra Militarum Vehicle model within 3\" of this model. "
    "That VEHICLE model regains up to D3 lost wounds. Each model can only be selected for this ability once per turn."
)


class _Datasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wounds: int = 6,
        transport: str = "",
    ):
        self.id = f"ds-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "11",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": "5",
                "base_size": "170mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": getattr(ability, "name", ""),
                "description": getattr(ability, "description", ""),
                "type": "Datasheet",
                "parameter": "",
            }
            for ability in list(abilities or [])
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str = ""):
    return SimpleNamespace(name=name, description=description or name)


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    wounds: int = 6,
    transport: str = "",
) -> Unit:
    unit = Unit(
        _Datasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            wounds=wounds,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(detachment_type: str = "Steel Hammer"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    am_army = Army.with_detachment("Astra Militarum", detachment_type=detachment_type)
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "ENEMY"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, am_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _battalion_commander() -> Enhancement:
    return Enhancement(
        id="000010787002",
        name="Battalion Commander",
        faction_id="AM",
        detachment="Steel Hammer",
        points=20,
        description=(
            "Astra Militarum Titanic Character model only. The bearer has the Voice of Command ability "
            "and the Officer keyword, and can issue up to 2 Orders to Astra Militarum Titanic and Squadron units."
        ),
    )


def _titan_killer() -> Enhancement:
    return Enhancement(
        id="000010787003",
        name="Titan Killer",
        faction_id="AM",
        detachment="Steel Hammer",
        points=25,
        description=(
            "Astra Militarum Titanic Character model only. Each time the bearer makes a ranged attack, "
            "you can re-roll the Damage roll."
        ),
    )


def _engine_speaker() -> Enhancement:
    return Enhancement(
        id="000010787004",
        name="Engine Speaker",
        faction_id="AM",
        detachment="Steel Hammer",
        points=10,
        description=(
            "Astra Militarum Tech-Priest Enginseer model only. Each time the bearer uses its Omnissiah's Blessing "
            "ability, until the start of your next Command phase, add 3\" to the Move characteristic of the selected "
            "VEHICLE model."
        ),
    )


def _assault_hatches() -> Enhancement:
    return Enhancement(
        id="000010787005",
        name="Assault Hatches",
        faction_id="AM",
        detachment="Steel Hammer",
        points=15,
        description=(
            "Astra Militarum Titanic Character Transport model only. Each time a unit disembarks from the bearer after "
            "it has made a Normal move, that unit is still eligible to declare a charge this turn."
        ),
    )


def _find_request(game: Game, decision_type: str, *, ability: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != decision_type:
            continue
        if ability is None:
            return req
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == ability:
            return req
    return None


def _option_for_model(request, model):
    model_id = str(get_entity_id(model) or "")
    return next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("target_model_id", "") or "") == model_id
    )


def _damage_profile(*, weapon_type: str = "Ranged"):
    return Wargear(
        {
            "name": "Test Cannon",
            "type": weapon_type,
            "range": "36" if weapon_type == "Ranged" else "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "12",
            "AP": "-3",
            "D": "D3",
            "description": "",
        }
    ).profiles["default"]


def test_steel_hammer_enhancement_descriptors_exist():
    battalion = get_enhancement_tool_descriptor(enhancement_id="000010787002")
    titan_killer = get_enhancement_tool_descriptor(enhancement_id="000010787003")
    engine_speaker = get_enhancement_tool_descriptor(enhancement_id="000010787004")
    assault_hatches = get_enhancement_tool_descriptor(enhancement_id="000010787005")

    assert battalion is not None
    assert battalion.name == "Battalion Commander"
    assert battalion.effect == "grant_voice_of_command_and_officer"
    assert battalion.effect_params["order_count"] == 2
    assert titan_killer is not None
    assert titan_killer.name == "Titan Killer"
    assert titan_killer.effect == "bearer_ranged_damage_reroll"
    assert engine_speaker is not None
    assert engine_speaker.name == "Engine Speaker"
    assert engine_speaker.effect == "omnissiahs_blessing_vehicle_move_bonus"
    assert engine_speaker.effect_params["move_bonus"] == 3
    assert assault_hatches is not None
    assert assault_hatches.name == "Assault Hatches"
    assert assault_hatches.effect == "allow_charge_after_normal_move_disembark"


def test_battalion_commander_grants_voice_and_two_titanic_or_squadron_orders():
    game, army, _enemy_army = _build_game()
    commander = _make_unit("Baneblade Commander", keywords=["VEHICLE", "TITANIC", "CHARACTER"], wounds=24)
    titanic_target = _make_unit("Stormsword", keywords=["VEHICLE", "TITANIC"], wounds=24)
    squadron_target = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    regiment_target = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    non_am_squadron = _make_unit(
        "Allied Speeder",
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=7,
    )

    for unit in (commander, titanic_target, squadron_target, regiment_target, non_am_squadron):
        army.add_unit(unit)
    _battalion_commander().apply_to_unit(commander)

    _place_unit(game, commander, 10.0, 10.0)
    _place_unit(game, titanic_target, 14.0, 10.0)
    _place_unit(game, squadron_target, 15.0, 10.0)
    _place_unit(game, regiment_target, 12.0, 10.0)
    _place_unit(game, non_am_squadron, 13.0, 10.0)
    game.rebuild_entity_registry()

    manager = VoiceOfCommandManager(army)
    manager._army_has_voice = lambda: True
    army.voice_of_command = manager

    assert commander.has_any_keyword("OFFICER")
    assert commander in manager.get_eligible_officers(game=game, player=army.player)

    targets = manager.get_eligible_targets(commander, game=game, order_key=ORDER_MOVE.key)
    assert titanic_target in targets
    assert squadron_target in targets
    assert regiment_target not in targets
    assert non_am_squadron not in targets

    assert manager.issue_order(game, commander, titanic_target, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
    assert manager.issue_order(game, commander, squadron_target, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
    assert manager.orders_remaining(commander, 1) == 0
    assert not manager.issue_order(game, commander, regiment_target, ORDER_MOVE.key, phase_name="COMMAND_PHASE")


def test_battalion_commander_is_detachment_and_character_gated():
    game, army, _enemy_army = _build_game(detachment_type="Combined Arms")
    commander = _make_unit("Baneblade Commander", keywords=["VEHICLE", "TITANIC", "CHARACTER"], wounds=24)
    army.add_unit(commander)
    _battalion_commander().apply_to_unit(commander)
    _place_unit(game, commander, 10.0, 10.0)
    game.rebuild_entity_registry()

    manager = VoiceOfCommandManager(army)
    manager._army_has_voice = lambda: True
    army.voice_of_command = manager

    assert not commander.has_any_keyword("OFFICER")
    assert commander not in manager.get_eligible_officers(game=game, player=army.player)

    steel_game, steel_army, _ = _build_game(detachment_type="Steel Hammer")
    non_character = _make_unit("Baneblade", keywords=["VEHICLE", "TITANIC"], wounds=24)
    steel_army.add_unit(non_character)
    _battalion_commander().apply_to_unit(non_character)
    _place_unit(steel_game, non_character, 10.0, 10.0)
    steel_game.rebuild_entity_registry()

    steel_manager = VoiceOfCommandManager(steel_army)
    steel_manager._army_has_voice = lambda: True
    steel_army.voice_of_command = steel_manager

    assert non_character.has_any_keyword("OFFICER")
    assert non_character not in steel_manager.get_eligible_officers(game=steel_game, player=steel_army.player)


def test_titan_killer_rerolls_bearer_ranged_damage_roll(monkeypatch):
    from warhammer40k_ai.utility import dice as dice_mod

    game, army, enemy_army = _build_game()
    commander = _make_unit("Baneblade Commander", keywords=["VEHICLE", "TITANIC", "CHARACTER"], wounds=24)
    target = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds=12)
    army.add_unit(commander)
    enemy_army.add_unit(target)
    _titan_killer().apply_to_unit(commander)
    _place_unit(game, commander, 10.0, 10.0)
    _place_unit(game, target, 14.0, 10.0)
    game.rebuild_entity_registry()

    profile = _damage_profile()
    calls = []
    game.install_decision_providers(roll_reroll_provider=lambda **kwargs: calls.append(kwargs) or True)
    rolls = iter([1, 3])
    monkeypatch.setattr(dice_mod, "get_dice_roll", lambda _size=6: next(rolls))

    damage = profile._damage_target_with_tracking(target.models[0], commander.models[0], {}, game.map)

    assert int(damage.get("damage_rolled", 0) or 0) == 3
    assert damage.get("reroll") == 3
    assert any("Titan Killer" in str(effect) for effect in damage.get("special_effects", []))
    assert any(call.get("roll_type") == "damage" and call.get("reason") == "Titan Killer" for call in calls)


def test_titan_killer_is_ranged_and_character_gated(monkeypatch):
    from warhammer40k_ai.utility import dice as dice_mod

    game, army, enemy_army = _build_game()
    commander = _make_unit("Baneblade Commander", keywords=["VEHICLE", "TITANIC", "CHARACTER"], wounds=24)
    non_character = _make_unit("Baneblade", keywords=["VEHICLE", "TITANIC"], wounds=24)
    target = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds=12)
    for unit in (commander, non_character):
        army.add_unit(unit)
    enemy_army.add_unit(target)
    _titan_killer().apply_to_unit(commander)
    _titan_killer().apply_to_unit(non_character)
    _place_unit(game, commander, 10.0, 10.0)
    _place_unit(game, non_character, 11.0, 10.0)
    _place_unit(game, target, 14.0, 10.0)
    game.rebuild_entity_registry()

    ranged = _damage_profile()
    melee = _damage_profile(weapon_type="Melee")
    calls = []
    game.install_decision_providers(roll_reroll_provider=lambda **kwargs: calls.append(kwargs) or True)

    rolls = iter([1, 3, 1, 3])
    monkeypatch.setattr(dice_mod, "get_dice_roll", lambda _size=6: next(rolls))

    melee_damage = melee._damage_target_with_tracking(target.models[0], commander.models[0], {}, game.map)
    non_character_damage = ranged._damage_target_with_tracking(target.models[0], non_character.models[0], {}, game.map)

    assert int(melee_damage.get("damage_rolled", 0) or 0) == 1
    assert "reroll" not in melee_damage
    assert int(non_character_damage.get("damage_rolled", 0) or 0) == 3
    assert "reroll" not in non_character_damage
    assert calls == []


def test_engine_speaker_adds_move_to_selected_omnissiahs_blessing_vehicle_until_next_command_phase():
    game, army, _enemy_army = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    enginseer = _make_unit(
        "Tech-Priest Enginseer",
        keywords=["INFANTRY", "CHARACTER", "ASTRA MILITARUM"],
        abilities=[_ability("Omnissiah's Blessing", OMNISSIAHS_BLESSING_TEXT)],
    )
    tank = _make_unit("Leman Russ", keywords=["VEHICLE", "ASTRA MILITARUM"], wounds=13)
    army.add_unit(enginseer)
    army.add_unit(tank)
    _engine_speaker().apply_to_unit(enginseer)
    _place_unit(game, enginseer, 10.0, 10.0)
    _place_unit(game, tank, 12.0, 10.0)
    game.rebuild_entity_registry()

    tank_model = tank.models[0]
    base_move = int(tank.movement)

    game._on_phase_start_master_of_mechanisms(player=army.player, phase=game.phase)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="master_of_mechanisms")

    assert request is not None
    assert int((request.context or {}).get("move_bonus", 0) or 0) == 3
    option = _option_for_model(request, tank_model)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
        result = resolve_decision_command(game, request, option.option_id, player_id=army.player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert int(tank.movement) == base_move + 3
    sr = dict(getattr(tank, "special_rules", {}) or {})
    assert bool(sr.get("master_of_mechanisms_move_bonus_active", False)) is True
    assert int(sr.get("master_of_mechanisms_move_bonus", 0) or 0) == 3
    assert str(sr.get("master_of_mechanisms_move_bonus_model_id", "") or "") == str(get_entity_id(tank_model) or "")

    game.turn = 2
    game._on_phase_start_master_of_mechanisms_cleanup(player=army.player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert int(tank.movement) == base_move
    sr_after = dict(getattr(tank, "special_rules", {}) or {})
    assert bool(sr_after.get("master_of_mechanisms_move_bonus_active", False)) is False


def test_engine_speaker_is_detachment_gated_for_omnissiahs_blessing_move_bonus():
    game, army, _enemy_army = _build_game(detachment_type="Combined Arms")
    game.phase = BattleRoundPhases.COMMAND_PHASE
    enginseer = _make_unit(
        "Tech-Priest Enginseer",
        keywords=["INFANTRY", "CHARACTER", "ASTRA MILITARUM"],
        abilities=[_ability("Omnissiah's Blessing", OMNISSIAHS_BLESSING_TEXT)],
    )
    tank = _make_unit("Leman Russ", keywords=["VEHICLE", "ASTRA MILITARUM"], wounds=13)
    army.add_unit(enginseer)
    army.add_unit(tank)
    _engine_speaker().apply_to_unit(enginseer)
    _place_unit(game, enginseer, 10.0, 10.0)
    _place_unit(game, tank, 12.0, 10.0)
    game.rebuild_entity_registry()

    base_move = int(tank.movement)

    game._on_phase_start_master_of_mechanisms(player=army.player, phase=game.phase)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="master_of_mechanisms")

    assert request is not None
    assert int((request.context or {}).get("move_bonus", 0) or 0) == 0
    option = _option_for_model(request, tank.models[0])
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
        result = resolve_decision_command(game, request, option.option_id, player_id=army.player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert int(tank.movement) == base_move
    assert not bool((getattr(tank, "special_rules", {}) or {}).get("master_of_mechanisms_move_bonus_active", False))


def test_assault_hatches_allows_passengers_to_charge_after_bearer_normal_move():
    game, army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    transport = _make_unit(
        "Stormlord Commander",
        keywords=["VEHICLE", "TITANIC", "CHARACTER", "TRANSPORT", "ASTRA MILITARUM"],
        wounds=24,
        transport="Transport Capacity 40",
    )
    passenger = _make_unit("Kasrkin", keywords=["INFANTRY", "ASTRA MILITARUM"])
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(transport)
    army.add_unit(passenger)
    enemy_army.add_unit(enemy)
    _assault_hatches().apply_to_unit(transport)
    _place_unit(game, transport, 10.0, 10.0)
    _place_unit(game, enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.round_state.moved_this_round = True
    transport.round_state.remained_stationary_this_round = False

    with patch.object(
        passenger,
        "_find_disembark_positions",
        return_value=[(12.0, 10.0, 0.0, 0.0)],
    ), patch.object(game.map, "place_unit", return_value=True):
        disembarked = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)

    assert disembarked is True
    if passenger not in game.map.units:
        game.map.units.append(passenger)
    assert bool(passenger.round_state.disembarked_from_moved_transport) is True
    assert bool(passenger.round_state.disembarked_cannot_charge) is False
    assert passenger.can_declare_charge_against(enemy, game) is True


def test_assault_hatches_is_detachment_and_bearer_keyword_gated():
    game, army, enemy_army = _build_game(detachment_type="Combined Arms")
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    transport = _make_unit(
        "Stormlord Commander",
        keywords=["VEHICLE", "TITANIC", "CHARACTER", "TRANSPORT", "ASTRA MILITARUM"],
        wounds=24,
        transport="Transport Capacity 40",
    )
    passenger = _make_unit("Kasrkin", keywords=["INFANTRY", "ASTRA MILITARUM"])
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(transport)
    army.add_unit(passenger)
    enemy_army.add_unit(enemy)
    _assault_hatches().apply_to_unit(transport)
    _place_unit(game, transport, 10.0, 10.0)
    _place_unit(game, enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.round_state.moved_this_round = True
    transport.round_state.remained_stationary_this_round = False

    with patch.object(
        passenger,
        "_find_disembark_positions",
        return_value=[(12.0, 10.0, 0.0, 0.0)],
    ), patch.object(game.map, "place_unit", return_value=True):
        disembarked = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)

    assert disembarked is True
    if passenger not in game.map.units:
        game.map.units.append(passenger)
    assert bool(passenger.round_state.disembarked_cannot_charge) is True
    assert passenger.can_declare_charge_against(enemy, game) is False

    steel_game, steel_army, steel_enemy_army = _build_game(detachment_type="Steel Hammer")
    steel_game.phase = BattleRoundPhases.MOVEMENT_PHASE
    non_titanic_transport = _make_unit(
        "Chimera Commander",
        keywords=["VEHICLE", "CHARACTER", "TRANSPORT", "ASTRA MILITARUM"],
        transport="Transport Capacity 12",
    )
    second_passenger = _make_unit("Cadians", keywords=["INFANTRY", "ASTRA MILITARUM"])
    second_enemy = _make_unit("Second Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    steel_army.add_unit(non_titanic_transport)
    steel_army.add_unit(second_passenger)
    steel_enemy_army.add_unit(second_enemy)
    _assault_hatches().apply_to_unit(non_titanic_transport)
    _place_unit(steel_game, non_titanic_transport, 10.0, 10.0)
    _place_unit(steel_game, second_enemy, 30.0, 10.0)
    steel_game.rebuild_entity_registry()

    non_titanic_transport.transport_passengers = [second_passenger]
    second_passenger.embarked_in = non_titanic_transport
    second_passenger.reserve_status = "embarked"
    non_titanic_transport.round_state.moved_this_round = True
    non_titanic_transport.round_state.remained_stationary_this_round = False

    with patch.object(
        second_passenger,
        "_find_disembark_positions",
        return_value=[(12.0, 10.0, 0.0, 0.0)],
    ), patch.object(steel_game.map, "place_unit", return_value=True):
        second_disembarked = second_passenger.disembark(
            game_map=steel_game.map,
            transport_unit=non_titanic_transport,
            current_turn=steel_game.turn,
        )

    assert second_disembarked is True
    if second_passenger not in steel_game.map.units:
        steel_game.map.units.append(second_passenger)
    assert bool(second_passenger.round_state.disembarked_cannot_charge) is True
    assert second_passenger.can_declare_charge_against(second_enemy, steel_game) is False
