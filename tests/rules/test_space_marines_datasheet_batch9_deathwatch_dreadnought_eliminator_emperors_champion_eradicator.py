from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        move: int = 6,
        toughness: int = 4,
        wounds: int = 2,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


class _ChargeMap:
    def __init__(self, *, enemies=None, engaged=None):
        self._enemies = list(enemies or [])
        self._engaged = set(engaged or [])

    def get_enemy_units(self, _unit):
        return list(self._enemies)

    def is_within_engagement_range(self, _unit, enemy):
        return enemy in self._engaged


class _AuraMap:
    def __init__(self, *, friendly_units=None, enemy_units=None):
        self._friendly_units = list(friendly_units or [])
        self._enemy_units = list(enemy_units or [])

    def get_friendly_units(self, _unit):
        return list(self._friendly_units)

    def get_enemy_units(self, _unit):
        return list(self._enemy_units)


class _WeaponProfile:
    def __init__(self, *, melee: bool = False, ranged: bool = False):
        self._melee = bool(melee)
        self._ranged = bool(ranged)

    def is_melee(self) -> bool:
        return self._melee

    def is_ranged(self) -> bool:
        return self._ranged


class _RangedWargear:
    name = "Test Gun"

    def is_ranged(self):
        return True

    def is_melee(self):
        return False


def _actual_unit(name: str, *, datasheet_id: str, faction_id: str = "SM") -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id=faction_id))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _first_yes_option_id(request) -> str:
    for option in list(getattr(request, "options", []) or []):
        if bool((option.payload or {}).get("choice", False)):
            return option.option_id
    raise AssertionError("No yes option found.")


def test_deathwatch_terminatus_assault_applies_battleshock_modifier_only_to_non_imperium_or_chaos():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    game.turn = 2
    terminators = _actual_unit("Deathwatch Terminator Squad", datasheet_id="000003873")
    xeno_enemy = _mock_unit("Xenos", keywords=["INFANTRY"], faction_keywords=["XENO"])
    imperium_enemy = _mock_unit("Imperium", keywords=["INFANTRY"], faction_keywords=["IMPERIUM"])

    sm_army.add_unit(terminators)
    enemy_army.add_unit(xeno_enemy)
    enemy_army.add_unit(imperium_enemy)
    game.map = _ChargeMap(enemies=[xeno_enemy, imperium_enemy], engaged=[xeno_enemy, imperium_enemy])

    xeno_modifiers: list[int] = []
    imperium_modifiers: list[int] = []
    xeno_enemy.take_battle_shock_test = lambda turn=1: xeno_modifiers.append(
        int(getattr(xeno_enemy, "special_rules", {}).get("battle_shock_test_modifier", 0) or 0)
    )
    imperium_enemy.take_battle_shock_test = lambda turn=1: imperium_modifiers.append(
        int(getattr(imperium_enemy, "special_rules", {}).get("battle_shock_test_modifier", 0) or 0)
    )

    specs = terminators.unit_charge_end_engagement_battleshock_specs()
    assert len(specs) == 1
    assert int(specs[0].get("test_modifier_if_missing_keywords", 0) or 0) == -1
    assert set(specs[0].get("test_modifier_missing_keywords_any", [])) == {"IMPERIUM", "CHAOS"}

    game._on_unit_move_ended_charge_battleshock(unit=terminators, action="charge")

    assert xeno_modifiers == [-1]
    assert imperium_modifiers == [0]


def test_dreadnought_wisdom_of_the_ancients_aura_grants_hit_reroll_ones():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    dreadnought = _actual_unit("Dreadnought", datasheet_id="000000117")
    infantry = _mock_unit(
        "Space Marines Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _mock_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    aura_map = _AuraMap(friendly_units=[dreadnought, infantry], enemy_units=[enemy])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(infantry, enemy, _WeaponProfile(ranged=True), game_map=aura_map)

    assert mods.reroll_hit_ones is True


def test_eliminator_reposition_under_covering_fire_requires_instigator_bolt_carbine():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    eliminators = _actual_unit("Eliminator Squad", datasheet_id="000001668")
    enemy = _mock_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(eliminators)
    enemy_army.add_unit(enemy)
    game.map = _ChargeMap(enemies=[enemy], engaged=[])
    _register_units(game, eliminators, enemy)

    specs = eliminators.unit_post_shoot_reactive_move_no_charge_specs()
    assert len(specs) == 1
    assert str(specs[0].get("required_model_name", "")).lower() == "eliminator sergeant"
    assert str(specs[0].get("required_wargear_name", "")).lower() == "instigator bolt carbine"

    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=eliminators)
    assert list(game.decision_queue.list() or []) == []

    sergeant = eliminators._find_model_named("Eliminator Sergeant")
    assert sergeant is not None
    sergeant.optional_wargear = ["Instigator bolt carbine"]

    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=eliminators)
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    assert str((pending[0].context or {}).get("reactive_move_kind", "")) == "post_shoot_no_charge"
    assert sm_player is not None


def test_emperors_champion_armour_of_faith_sets_damage_to_zero_once_per_phase():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    champion = _actual_unit("Emperor's Champion", datasheet_id="000002795")
    attacker = _mock_unit("Attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(champion)
    enemy_army.add_unit(attacker)
    _register_units(game, champion, attacker)

    profile = WargearProfile(
        "Test Gun",
        {"range": "24", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "2", "description": ""},
        parent_wargear=_RangedWargear(),
    )
    target_model = champion.models[0]

    attack_instance = {}
    sm_player.set_next_optional_decision("FIRST_FAILED_SAVE_DAMAGE_ZERO", True)
    save_result = profile._save_with_tracking(
        target_model,
        attack_instance,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert save_result["saved"] is False
    assert attack_instance.get("force_damage_zero") is True

    attack_instance_2 = {}
    save_result_2 = profile._save_with_tracking(
        target_model,
        attack_instance_2,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert save_result_2["saved"] is False
    assert attack_instance_2.get("force_damage_zero") is not True

    game.phase = BattleRoundPhases.FIGHT_PHASE
    attack_instance_3 = {}
    sm_player.set_next_optional_decision("FIRST_FAILED_SAVE_DAMAGE_ZERO", True)
    save_result_3 = profile._save_with_tracking(
        target_model,
        attack_instance_3,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert save_result_3["saved"] is False
    assert attack_instance_3.get("force_damage_zero") is True


def test_emperors_champion_sigismunds_heir_adds_charge_bonus_vs_character_targets():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    champion = _actual_unit("Emperor's Champion", datasheet_id="000002795")
    character_target = _mock_unit("Character Target", keywords=["CHARACTER", "INFANTRY"], faction_keywords=["ENEMY"])
    infantry_target = _mock_unit("Infantry Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(champion)
    enemy_army.add_unit(character_target)
    enemy_army.add_unit(infantry_target)
    _register_units(game, champion, character_target, infantry_target)

    character_mods = list(game.get_charge_roll_modifiers(champion, target_unit=[character_target]) or [])
    infantry_mods = list(game.get_charge_roll_modifiers(champion, target_unit=[infantry_target]) or [])

    assert any(int(val) == 2 and "sigismund" in str(source).lower() for val, source in character_mods)
    assert not any(int(val) == 2 and "sigismund" in str(source).lower() for val, source in infantry_mods)


def test_emperors_champion_sigismunds_heir_queues_and_applies_devastating_wounds():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    champion = _actual_unit("Emperor's Champion", datasheet_id="000002795")
    enemy_character = _mock_unit("Enemy Character", keywords=["CHARACTER", "INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(champion)
    enemy_army.add_unit(enemy_character)
    game.map = _ChargeMap(enemies=[enemy_character], engaged=[enemy_character])
    _register_units(game, champion, enemy_character)

    game._on_fight_unit_selected_target_keyword_melee_weapon_keyword(unit=champion, selecting_player=sm_player)
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    assert str((request.context or {}).get("ability", "")) == "fight_selected_target_keyword_melee_weapon_keyword"

    resolve_decision_command(game, request, _first_yes_option_id(request), player_id=sm_player.id)

    model = champion.models[0]
    melee_weapon_name = next(
        str(wargear.name)
        for wargear in list(getattr(model, "wargear", []) or [])
        if bool(getattr(wargear, "is_melee", lambda: False)())
    )
    bonuses = list(model.get_temporary_weapon_keyword_bonuses(melee_weapon_name) or [])
    assert any(str(entry.get("keyword", "")).upper() == "DEVASTATING WOUNDS" for entry in bonuses)


def test_eradicator_total_obliteration_parses_monster_vehicle_rerolls():
    eradicators = _actual_unit("Eradicator Squad", datasheet_id="000000103")
    rule = eradicators.get_monster_vehicle_reroll_rule(eradicators.models[0])

    assert isinstance(rule, dict)
    assert rule.get("reroll_hit") is True
    assert rule.get("reroll_wound") is True
    assert rule.get("reroll_damage") is True
