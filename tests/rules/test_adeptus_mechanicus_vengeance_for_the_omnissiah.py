from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile


VENGEANCE_TEXT = (
    "If a friendly Adeptus Mechanicus Vehicle model is destroyed within 12\" of this model, "
    "until the end of the battle, this model's Omnissian axe has an Attacks characteristic of 6."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Other")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    return game, admech_army, enemy_army


def _attack_result_stub() -> AttackResult:
    return AttackResult(
        weapon_name="Test Weapon",
        attacker_name="Attacker",
        target_unit_name="Target",
        attacks_rolled=0,
        attacks_dice_expression="",
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


def _melee_profile(weapon_name: str) -> WargearProfile:
    parent = SimpleNamespace(name=weapon_name, is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _publish_model_destroyed_event(game: Game, *, attacker_unit: Unit, target_unit: Unit) -> None:
    game.event_system.publish(
        "model_destroyed",
        attacker_model=attacker_unit.models[0],
        attacker_unit=attacker_unit,
        target_model=target_unit.models[0],
        target_unit=target_unit,
        weapon_profile=None,
        game_map=game.map,
    )


def test_vengeance_for_the_omnissiah_sets_enginseer_axe_attacks_to_six_after_trigger():
    game, admech_army, enemy_army = _build_game()
    enginseer = _make_unit(
        "Tech-priest Enginseer",
        abilities=[
            {
                "name": "Vengeance for the Omnissiah",
                "description": VENGEANCE_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    friendly_vehicle = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    admech_army.add_unit(enginseer)
    admech_army.add_unit(friendly_vehicle)
    enemy_army.add_unit(enemy)
    game.map.units = [enginseer, friendly_vehicle, enemy]
    game.rebuild_entity_registry()

    enginseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly_vehicle.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(18.0, 0.0, 0.0, 0.0)

    _publish_model_destroyed_event(game, attacker_unit=enemy, target_unit=friendly_vehicle)

    enginseer_model = enginseer.models[0]
    assert int(enginseer_model.get_temporary_weapon_attacks_override("Omnissian axe")[0]) == 6
    # Datasheet weapon naming can vary; alias matching should still apply.
    assert int(enginseer_model.get_temporary_weapon_attacks_override("Enginseer axe")[0]) == 6

    profile = _melee_profile("Enginseer axe")
    attack_result = _attack_result_stub()
    attack_info = profile._resolve_attack_count(
        enemy,
        enginseer_model,
        attack_result,
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(attack_info.num_attacks or 0) == 6

    # Effect is "until the end of the battle", so phase-end cleanup should not remove it.
    enginseer_model.on_phase_end(BattleRoundPhases.FIGHT_PHASE)
    assert int(enginseer_model.get_temporary_weapon_attacks_override("Enginseer axe")[0]) == 6


def test_vengeance_for_the_omnissiah_does_not_trigger_outside_twelve_inches():
    game, admech_army, enemy_army = _build_game()
    enginseer = _make_unit(
        "Tech-priest Enginseer",
        abilities=[
            {
                "name": "Vengeance for the Omnissiah",
                "description": VENGEANCE_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    friendly_vehicle = _make_unit(
        "Skorpius Disintegrator",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    admech_army.add_unit(enginseer)
    admech_army.add_unit(friendly_vehicle)
    enemy_army.add_unit(enemy)
    game.map.units = [enginseer, friendly_vehicle, enemy]
    game.rebuild_entity_registry()

    enginseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly_vehicle.models[0].set_location(16.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(22.0, 0.0, 0.0, 0.0)

    _publish_model_destroyed_event(game, attacker_unit=enemy, target_unit=friendly_vehicle)

    enginseer_model = enginseer.models[0]
    assert int(enginseer_model.get_temporary_weapon_attacks_override("Omnissian axe")[0]) == 0
    assert int(enginseer_model.get_temporary_weapon_attacks_override("Enginseer axe")[0]) == 0
