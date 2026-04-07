from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE, CHOICE_KEEP_ALL
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        movement: int = 8,
        toughness: int = 6,
        save: int = 4,
        wounds: int = 8,
        objective_control: int = 2,
        model_count: int = 1,
        keywords=None,
        faction_keywords=None,
        faction_name: str = "Chaos Daemons",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": str(objective_control),
                "base_size": "32mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


class _Wargear:
    def __init__(self, *, melee: bool = False, ranged: bool = False):
        self._melee = bool(melee)
        self._ranged = bool(ranged)

    def is_melee(self) -> bool:
        return self._melee

    def is_ranged(self) -> bool:
        return self._ranged


class _WeaponProfile:
    def __init__(self, *, melee: bool = False, ranged: bool = False):
        self.parent_wargear = _Wargear(melee=melee, ranged=ranged)


def _make_unit(
    name: str,
    army: Army,
    *,
    movement: int = 8,
    wounds: int = 8,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Chaos Daemons",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            movement=movement,
            wounds=wounds,
            keywords=keywords,
            faction_keywords=faction_keywords,
            faction_name=faction_name,
        )
    )
    unit.deployed = True
    army.add_unit(unit)
    return unit


def _build_game():
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))

    legion_army = Army.with_detachment("Chaos Daemons", detachment_type="Legion of Excess")
    legion_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
    enemy_army.faction_id = "SM"

    legion_player = Player("Legion", PlayerControl.REMOTE, legion_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, enemy_army)
    game.add_player(legion_player)
    game.add_player(enemy_player)

    return game, legion_player, enemy_player


def _apply_legion_enhancement(unit: Unit, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="CD",
        detachment="Legion of Excess",
    ).apply_to_unit(unit)


def test_legion_of_excess_enhancement_descriptors_registered():
    ids_to_names = {
        "000009806002": "False Majesty (Aura)",
        "000009806003": "Dreaming Crown (Aura)",
        "000009806004": "Avatar of Perfection",
        "000009806005": "Soul Glutton",
    }
    for enhancement_id, expected_name in ids_to_names.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == expected_name


def test_false_majesty_and_dreaming_crown_apply_melee_bonuses_with_keyword_restrictions():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    game, legion_player, enemy_player = _build_game()
    source_wound = _make_unit(
        "Source Wound Aura",
        legion_player.army,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    source_hit = _make_unit(
        "Source Hit Aura",
        legion_player.army,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    attacker = _make_unit(
        "Eligible Attacker",
        legion_player.army,
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    monster_attacker = _make_unit(
        "Monster Attacker",
        legion_player.army,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    target = _make_unit("Enemy", enemy_player.army, faction_name="Enemies")

    _apply_legion_enhancement(source_wound, "000009806002", "False Majesty (Aura)")
    _apply_legion_enhancement(source_hit, "000009806003", "Dreaming Crown (Aura)")

    source_wound.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    source_hit.models[0].set_location(0.0, 1.0, 0.0, 0.0)
    attacker.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    monster_attacker.models[0].set_location(1.0, 1.0, 0.0, 0.0)
    target.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    game.map.units = [source_wound, source_hit, attacker, monster_attacker, target]
    game.rebuild_entity_registry()

    melee_mods = get_aura_attack_modifiers(attacker, target, _WeaponProfile(melee=True), game_map=game.map)
    assert int(getattr(melee_mods, "hit", 0) or 0) == 1
    assert int(getattr(melee_mods, "wound", 0) or 0) == 1

    ranged_mods = get_aura_attack_modifiers(attacker, target, _WeaponProfile(ranged=True), game_map=game.map)
    assert int(getattr(ranged_mods, "hit", 0) or 0) == 0
    assert int(getattr(ranged_mods, "wound", 0) or 0) == 0

    monster_mods = get_aura_attack_modifiers(
        monster_attacker,
        target,
        _WeaponProfile(melee=True),
        game_map=game.map,
    )
    assert int(getattr(monster_mods, "hit", 0) or 0) == 0
    assert int(getattr(monster_mods, "wound", 0) or 0) == 0


def test_avatar_of_perfection_phase_start_activation_and_rerolls():
    game, legion_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Avatar Bearer",
        legion_player.army,
        movement=10,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    nearby = _make_unit(
        "Nearby Friendly",
        legion_player.army,
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )

    _apply_legion_enhancement(bearer, "000009806004", "Avatar of Perfection")

    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    nearby.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer, nearby]
    game.rebuild_entity_registry()

    game._on_phase_start_chaos_daemons_enhancements(player=legion_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    assert bool(bearer.special_rules.get("enhancement_avatar_of_perfection_active")) is True
    assert bool(bearer.can_reroll_advance_roll()) is True
    assert bool(bearer.can_reroll_charge_roll()) is True

    nearby.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    game._on_phase_start_chaos_daemons_enhancements(player=legion_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    assert bool(bearer.special_rules.get("enhancement_avatar_of_perfection_active")) is False
    assert bool(bearer.can_reroll_advance_roll()) is False
    assert bool(bearer.can_reroll_charge_roll()) is False


def test_avatar_of_perfection_updates_during_opponent_turn_phase_start():
    game, legion_player, enemy_player = _build_game()
    bearer = _make_unit(
        "Avatar Bearer",
        legion_player.army,
        movement=10,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )

    _apply_legion_enhancement(bearer, "000009806004", "Avatar of Perfection")
    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 1
    game.phase = BattleRoundPhases.CHARGE_PHASE

    game._on_phase_start_chaos_daemons_enhancements(player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)
    assert bool(bearer.special_rules.get("enhancement_avatar_of_perfection_active")) is True
    assert str(bearer.special_rules.get("enhancement_avatar_of_perfection_turn_owner", "") or "") == str(enemy_player.id)
    assert str(bearer.special_rules.get("enhancement_avatar_of_perfection_phase", "") or "") == "CHARGE_PHASE"
    assert bool(bearer.can_reroll_charge_roll()) is True


def test_avatar_of_perfection_modifier_choice_ignores_negative_modifiers():
    game, legion_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Avatar Bearer",
        legion_player.army,
        movement=10,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )

    _apply_legion_enhancement(bearer, "000009806004", "Avatar of Perfection")

    bearer.special_rules["enhancement_avatar_of_perfection_active"] = True
    bearer.special_rules["enhancement_avatar_of_perfection_turn_owner"] = str(legion_player.id)
    bearer.special_rules["enhancement_avatar_of_perfection_turn"] = 1
    bearer.special_rules["enhancement_avatar_of_perfection_phase"] = "MOVEMENT_PHASE"
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    bearer.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, -2, source="Slow"))
    bearer.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, 1, source="Fast"))
    model = bearer.models[0]

    bearer.round_state.move_modifier_choice = CHOICE_KEEP_ALL
    keep_all_move = int(bearer.get_effective_model_characteristic(model, "movement", game_map=game.map))

    bearer.round_state.move_modifier_choice = CHOICE_IGNORE_NEGATIVE
    ignore_negative_move = int(bearer.get_effective_model_characteristic(model, "movement", game_map=game.map))
    assert ignore_negative_move > keep_all_move

    mods = [(-2, "Debuff"), (1, "Buff")]
    bearer.round_state.advance_modifier_choice = CHOICE_IGNORE_NEGATIVE
    assert bearer._filter_avatar_of_perfection_roll_modifiers(mods, kind="advance") == [(1, "Buff")]
    bearer.round_state.charge_modifier_choice = CHOICE_IGNORE_NEGATIVE
    assert bearer._filter_avatar_of_perfection_roll_modifiers(mods, kind="charge") == [(1, "Buff")]


def test_soul_glutton_end_of_fight_queues_decision_and_heals_on_use():
    game, legion_player, enemy_player = _build_game()
    bearer = _make_unit(
        "Soul Glutton Bearer",
        legion_player.army,
        wounds=8,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    target = _make_unit("Enemy Target", enemy_player.army, wounds=4, faction_name="Enemies")

    _apply_legion_enhancement(bearer, "000009806005", "Soul Glutton")

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE

    bearer_model = bearer.models[0]
    bearer_model.wounds = 3
    base_wounds = int(getattr(bearer_model, "_base_wounds", 8) or 8)

    game._on_model_destroyed_rules(
        attacker_model=bearer_model,
        attacker_unit=bearer,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_WeaponProfile(melee=True),
    )
    assert int(bearer.special_rules.get("enhancement_soul_glutton_phase_kills", 0) or 0) == 1

    game._on_phase_end_chaos_daemons_enhancements(player=legion_player, phase=BattleRoundPhases.FIGHT_PHASE)
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "soul_glutton"
    ]
    assert len(requests) == 1
    request = requests[0]

    use_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("action", "") or "") == "use"
    )
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        result = resolve_decision_command(game, request, use_option.option_id, player_id=legion_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(bearer_model.wounds) == min(int(base_wounds), 6)


def test_soul_glutton_skip_option_does_not_heal():
    game, legion_player, enemy_player = _build_game()
    bearer = _make_unit(
        "Soul Glutton Bearer",
        legion_player.army,
        wounds=8,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    target = _make_unit("Enemy Target", enemy_player.army, wounds=4, faction_name="Enemies")

    _apply_legion_enhancement(bearer, "000009806005", "Soul Glutton")

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE

    bearer_model = bearer.models[0]
    bearer_model.wounds = 3

    game._on_model_destroyed_rules(
        attacker_model=bearer_model,
        attacker_unit=bearer,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_WeaponProfile(melee=True),
    )
    game._on_phase_end_chaos_daemons_enhancements(player=legion_player, phase=BattleRoundPhases.FIGHT_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "soul_glutton"
    )
    skip_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("action", "") or "") == "skip"
    )
    result = resolve_decision_command(game, request, skip_option.option_id, player_id=legion_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(bearer_model.wounds) == 3


def test_soul_glutton_queues_for_legion_player_during_opponent_turn_fight_phase():
    game, legion_player, enemy_player = _build_game()
    bearer = _make_unit(
        "Soul Glutton Bearer",
        legion_player.army,
        wounds=8,
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    target = _make_unit("Enemy Target", enemy_player.army, wounds=4, faction_name="Enemies")

    _apply_legion_enhancement(bearer, "000009806005", "Soul Glutton")

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 1
    game.phase = BattleRoundPhases.FIGHT_PHASE

    game._on_model_destroyed_rules(
        attacker_model=bearer.models[0],
        attacker_unit=bearer,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_WeaponProfile(melee=True),
    )
    game._on_phase_end_chaos_daemons_enhancements(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "soul_glutton"
    )
    assert str(getattr(request, "player_id", "") or "") == str(legion_player.id)
    assert str((request.context or {}).get("turn_owner", "") or "") == str(enemy_player.id)
