from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_weapon_keyword_bonuses


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: int = 10,
    ):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "9",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "3",
                "base_size": "90mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


class _DummyRangedWargear:
    def is_ranged(self) -> bool:
        return True

    def is_melee(self) -> bool:
        return False


class _DummyMeleeWargear:
    def is_ranged(self) -> bool:
        return False

    def is_melee(self) -> bool:
        return True


class _DummyProfile:
    def __init__(self, parent_wargear):
        self.parent_wargear = parent_wargear

    def is_assault(self) -> bool:
        return False


def _unit(name: str, *, keywords=None, faction_keywords=None, wounds: int = 10) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    marine_army = Army.with_detachment("Space Marines", "Headhunter Task Force")
    marine_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    marine_player = Player("Marine Player", control=PlayerControl.REMOTE, army=marine_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(marine_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, marine_player, marine_army, enemy_army


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    unit.position = (float(x), float(y), 0.0)
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + index * 0.2, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Headhunter Task Force",
        points=0,
        description="",
    ).apply_to_unit(unit)


def test_headhunter_task_force_enhancement_descriptors_exist():
    expected = {
        "000010783002": ("Redoubtable Machine Spirit", "bearer_invulnerable_save_and_command_phase_heal"),
        "000010783003": ("Gunnery Honours", "bearer_once_per_phase_hit_wound_damage_rerolls"),
        "000010783004": ("Firestorm Coordinators", "bearer_ranged_weapons_gain_sustained_hits"),
        "000010783005": ("Astartes Tank Ace (Aura)", "friendly_vehicle_ranged_weapons_gain_assault_aura"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_redoubtable_machine_spirit_grants_bearer_invulnerable_save_and_command_heal():
    game, player, army, _enemy_army = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    predator = _unit("Predator Destructor", keywords=["VEHICLE"], wounds=10)
    army.add_unit(predator)
    game.map.units = [predator]
    game.rebuild_entity_registry()

    _apply_enhancement(
        predator,
        enhancement_id="000010783002",
        enhancement_name="Redoubtable Machine Spirit",
    )
    bearer = predator.models[0]
    invuln, source = predator.get_model_invulnerable_save_override(bearer)
    assert invuln == 5
    assert source == "Redoubtable Machine Spirit"

    bearer.take_damage(3, game_map=game.map)
    assert int(bearer.wounds) == 7
    healed = army.space_marines_detachments.heal_headhunter_redoubtable_machine_spirit_at_command_end(
        game=game,
        player=player,
    )
    assert healed == 1
    assert int(bearer.wounds) == 8


def test_gunnery_honours_tracks_one_hit_wound_and_damage_reroll_each_per_phase():
    game, _player, army, _enemy_army = _build_game()
    predator = _unit("Predator Destructor", keywords=["VEHICLE"], wounds=10)
    army.add_unit(predator)
    game.map.units = [predator]
    game.rebuild_entity_registry()

    _apply_enhancement(predator, enhancement_id="000010783003", enhancement_name="Gunnery Honours")
    bearer = predator.models[0]
    manager = army.space_marines_detachments

    assert manager.headhunter_gunnery_honours_reroll_is_available(bearer, "hit", game=game)
    assert manager.headhunter_gunnery_honours_reroll_is_available(bearer, "wound", game=game)
    assert manager.headhunter_gunnery_honours_reroll_is_available(bearer, "damage", game=game)

    assert manager.consume_headhunter_gunnery_honours_reroll(bearer, "hit", game=game)
    assert not manager.headhunter_gunnery_honours_reroll_is_available(bearer, "hit", game=game)
    assert manager.headhunter_gunnery_honours_reroll_is_available(bearer, "wound", game=game)
    assert manager.headhunter_gunnery_honours_reroll_is_available(bearer, "damage", game=game)

    game.phase = BattleRoundPhases.FIGHT_PHASE
    assert manager.headhunter_gunnery_honours_reroll_is_available(bearer, "hit", game=game)


def test_firestorm_coordinators_grants_sustained_hits_one_to_bearer_ranged_attacks_only():
    game, _player, army, enemy_army = _build_game()
    predator = _unit("Predator Destructor", keywords=["VEHICLE"], wounds=10)
    target = _unit("Enemy Rhino", keywords=["VEHICLE"], faction_keywords=["HERETIC ASTARTES"], wounds=10)
    army.add_unit(predator)
    enemy_army.add_unit(target)
    game.map.units = [predator, target]
    game.rebuild_entity_registry()

    _apply_enhancement(predator, enhancement_id="000010783004", enhancement_name="Firestorm Coordinators")
    ranged_profile = _DummyProfile(_DummyRangedWargear())
    melee_profile = _DummyProfile(_DummyMeleeWargear())

    ranged = predator.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=predator.models[0],
        weapon_profile=ranged_profile,
    )
    assert int(ranged.get("sustained_hits_value", 0) or 0) == 1

    melee = predator.get_attack_keyword_bonuses(
        target=target,
        attack_type="melee",
        model=predator.models[0],
        weapon_profile=melee_profile,
    )
    assert int(melee.get("sustained_hits_value", 0) or 0) == 0


def test_astartes_tank_ace_aura_grants_assault_to_nearby_friendly_astartes_vehicles_in_shooting_phase():
    game, _player, army, _enemy_army = _build_game()
    source = _unit("Predator Destructor", keywords=["VEHICLE"], wounds=10)
    nearby = _unit("Gladiator Lancer", keywords=["VEHICLE"], wounds=10)
    far = _unit("Repulsor", keywords=["VEHICLE"], wounds=12)
    infantry = _unit("Intercessor Squad", keywords=["INFANTRY"], wounds=2)
    for unit in (source, nearby, far, infantry):
        army.add_unit(unit)
    _set_model_location(source, 0.0, 0.0)
    _set_model_location(nearby, 5.0, 0.0)
    _set_model_location(far, 20.0, 0.0)
    _set_model_location(infantry, 5.0, 3.0)
    game.map.units = [source, nearby, far, infantry]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010783005", enhancement_name="Astartes Tank Ace (Aura)")
    ranged_profile = _DummyProfile(_DummyRangedWargear())

    assert nearby.can_shoot_after_advance(ranged_profile) is True
    assert far.can_shoot_after_advance(ranged_profile) is False
    assert infantry.can_shoot_after_advance(ranged_profile) is False

    aura_rules = get_aura_weapon_keyword_bonuses(
        nearby,
        ranged_profile,
        attacker_model=nearby.models[0],
        game_map=game.map,
    )
    assert any(rule.get("keyword") == "ASSAULT" for rule in aura_rules)

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    assert nearby.can_shoot_after_advance(ranged_profile) is False
