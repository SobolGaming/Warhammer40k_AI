from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        toughness: str = "5",
        wounds: str = "4",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": toughness,
                "Sv": "2",
                "W": wounds,
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Adeptus Custodes",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    toughness: str = "5",
    wounds: str = "4",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        faction_name=faction_name,
        model_count=model_count,
        keywords=keywords,
        faction_keywords=faction_keywords,
        attached_to=attached_to,
        toughness=toughness,
        wounds=wounds,
    )
    return Unit(datasheet)


def _make_game() -> tuple[Game, Player, Player]:
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    custodes_army = Army("Adeptus Custodes", "Lions of the Emperor")
    custodes_army.faction_id = "AC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("AC", control=PlayerControl.LOCAL, army=custodes_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    return game, custodes_player, enemy_player


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True


class _MeleeWargear:
    name = "Test Blade"

    @staticmethod
    def is_melee() -> bool:
        return True

    @staticmethod
    def is_ranged() -> bool:
        return False


def _melee_profile(
    *,
    strength: int = 4,
    attacks: int = 3,
    skill: int = 2,
    ap: int = -1,
    damage: int = 1,
) -> WargearProfile:
    return WargearProfile(
        "Test Blade",
        {
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=_MeleeWargear(),
    )


def _apply_enhancement(army: Army, unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    army.add_enhancement(enhancement, unit)


def _make_attack_result(profile: WargearProfile, attacker, target_unit: Unit) -> AttackResult:
    return AttackResult(
        weapon_name=profile.name,
        attacker_name=getattr(attacker, "name", "Attacker"),
        target_unit_name=getattr(target_unit, "name", "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def test_superior_creation_only_triggers_for_bearer():
    game, custodes_player, enemy_player = _make_game()
    bearer_unit = _make_unit(
        "Custodian",
        "ac-superior",
        model_count=2,
        keywords=["Character", "Infantry", "Adeptus Custodes"],
        faction_keywords=["ADEPTUS CUSTODES"],
        wounds="3",
    )
    enemy = _make_unit(
        "Enemy",
        "enemy-superior",
        faction_name="Enemy",
        keywords=["Infantry"],
        faction_keywords=["ENEMY"],
        wounds="10",
    )
    custodes_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(enemy, 50.0, 0.0)
    game.map.units = [bearer_unit, enemy]

    _apply_enhancement(custodes_player.army, bearer_unit, "Superior Creation")

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    non_bearer = bearer_unit.models[1]
    non_bearer.take_damage(int(non_bearer.wounds), game_map=game.map)
    assert not game._phoenix_gem_pending

    bearer_model = bearer_unit.models[0]
    bearer_model.take_damage(int(bearer_model.wounds), game_map=game.map)
    assert game._phoenix_gem_pending

    with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
        game._on_phase_end_cleanup(player=custodes_player, phase=game.phase)

    assert bearer_unit.is_alive()
    assert len(bearer_unit.models) == 1


def test_praesidius_grants_lone_operative_and_stealth_without_leaking():
    game, custodes_player, _enemy_player = _make_game()
    bodyguard = _make_unit(
        "Custodian Guard",
        "ac-bodyguard",
        keywords=["Infantry", "Adeptus Custodes"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    leader = _make_unit(
        "Shield-Captain",
        "ac-praesidius",
        keywords=["Character", "Infantry", "Adeptus Custodes", "Shield-Captain"],
        faction_keywords=["ADEPTUS CUSTODES"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    custodes_player.army.add_unit(bodyguard)
    custodes_player.army.add_unit(leader)
    _deploy_unit(bodyguard, 0.0, 0.0)
    _deploy_unit(leader, 0.0, 0.0)
    game.map.units = [bodyguard, leader]

    _apply_enhancement(custodes_player.army, leader, "Praesidius")

    assert leader.has_lone_operative()
    assert leader.has_stealth()

    leader.attach_to_unit(bodyguard)
    assert not bodyguard.has_lone_operative()
    assert not bodyguard.has_stealth()


def test_admonimortis_applies_to_bearer_melee_only():
    game, custodes_player, enemy_player = _make_game()
    bodyguard = _make_unit(
        "Custodian Guard",
        "ac-bodyguard-admonimortis",
        keywords=["Infantry", "Adeptus Custodes"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    leader = _make_unit(
        "Shield-Captain",
        "ac-admonimortis",
        keywords=["Character", "Infantry", "Adeptus Custodes", "Shield-Captain"],
        faction_keywords=["ADEPTUS CUSTODES"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    support = _make_unit(
        "Custodian Support",
        "ac-support-admonimortis",
        keywords=["Infantry", "Adeptus Custodes"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy",
        "enemy-admonimortis",
        faction_name="Enemy",
        keywords=["Infantry"],
        faction_keywords=["ENEMY"],
        toughness="7",
        wounds="10",
    )
    custodes_player.army.add_unit(bodyguard)
    custodes_player.army.add_unit(leader)
    custodes_player.army.add_unit(support)
    enemy_player.army.add_unit(enemy)
    leader.attach_to_unit(bodyguard)
    _deploy_unit(bodyguard, 0.0, 0.0)
    _deploy_unit(leader, 0.0, 0.0)
    _deploy_unit(support, 0.0, 5.0)
    _deploy_unit(enemy, 3.0, 0.0)
    game.map.units = [bodyguard, leader, support, enemy]

    _apply_enhancement(custodes_player.army, leader, "Admonimortis")

    profile = _melee_profile(strength=4, attacks=3, ap=-1, damage=1)
    leader_model = leader.models[0]
    bodyguard_model = bodyguard.models[0]

    leader_wound = profile._wound_target_with_tracking(
        enemy,
        leader_model,
        {"damage_characteristic": 1},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    bodyguard_wound = profile._wound_target_with_tracking(
        enemy,
        bodyguard_model,
        {"damage_characteristic": 1},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert leader_wound["wound"] is True
    assert bodyguard_wound["wound"] is False

    assert profile.get_effective_ap(leader_model, enemy) == -2
    assert profile.get_effective_ap(bodyguard_model, enemy) == -1

    enemy_model = enemy.models[0]
    enemy_model._wounds = enemy_model._base_wounds
    leader_damage = profile._damage_target_with_tracking(
        enemy_model,
        leader_model,
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    enemy_model._wounds = enemy_model._base_wounds
    bodyguard_damage = profile._damage_target_with_tracking(
        enemy_model,
        bodyguard_model,
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert leader_damage["damage_applied"] == 2
    assert bodyguard_damage["damage_applied"] == 1


def test_fierce_conqueror_scales_with_enemy_models_within_six():
    game, custodes_player, enemy_player = _make_game()
    bodyguard = _make_unit(
        "Custodian Guard",
        "ac-bodyguard-fierce",
        keywords=["Infantry", "Adeptus Custodes"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    leader = _make_unit(
        "Shield-Captain",
        "ac-fierce-conqueror",
        keywords=["Character", "Infantry", "Adeptus Custodes", "Shield-Captain"],
        faction_keywords=["ADEPTUS CUSTODES"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    enemy_blob = _make_unit(
        "Enemy Blob",
        "enemy-fierce",
        faction_name="Enemy",
        model_count=10,
        keywords=["Infantry"],
        faction_keywords=["ENEMY"],
        wounds="2",
    )
    custodes_player.army.add_unit(bodyguard)
    custodes_player.army.add_unit(leader)
    enemy_player.army.add_unit(enemy_blob)
    leader.attach_to_unit(bodyguard)
    _deploy_unit(bodyguard, 0.0, 0.0)
    _deploy_unit(leader, 0.0, 0.0)
    _deploy_unit(enemy_blob, 3.0, 0.0)
    game.map.units = [bodyguard, leader, enemy_blob]

    _apply_enhancement(custodes_player.army, leader, "Fierce Conqueror")

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.event_system.publish("phase_start", player=custodes_player, phase=game.phase)

    sr = leader.special_rules
    assert int(sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0) == 4

    profile = _melee_profile(attacks=3)
    leader_model = leader.models[0]
    bodyguard_model = bodyguard.models[0]

    leader_result = _make_attack_result(profile, leader_model, enemy_blob)
    leader_attacks = profile._resolve_attack_count(
        enemy_blob,
        leader_model,
        leader_result,
        publish_roll_event=False,
    )
    bodyguard_result = _make_attack_result(profile, bodyguard_model, enemy_blob)
    bodyguard_attacks = profile._resolve_attack_count(
        enemy_blob,
        bodyguard_model,
        bodyguard_result,
        publish_roll_event=False,
    )

    assert leader_attacks.num_attacks == 7
    assert bodyguard_attacks.num_attacks == 3
