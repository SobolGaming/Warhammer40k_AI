from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Skitarii Hunter Cohort")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    return game, admech_army, enemy_army


def _set_location(unit: Unit, x: float, y: float, z: float = 0.0) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), float(z), 0.0)


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Galvanic Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Ranged",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Claw", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_stealth_optimisation_grants_stealth_to_eligible_units():
    game, admech_army, _enemy_army = _build_game()
    skitarii_infantry = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii_mounted = _make_unit(
        "Serberys Raiders",
        keywords=["MOUNTED", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    ironstrider_name_match = _make_unit(
        "Ironstrider Ballistarii",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    non_eligible = _make_unit(
        "Kataphron Destroyers",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )

    for unit in (skitarii_infantry, skitarii_mounted, ironstrider_name_match, non_eligible):
        admech_army.add_unit(unit)
    game.map.units = [skitarii_infantry, skitarii_mounted, ironstrider_name_match, non_eligible]
    game.rebuild_entity_registry()

    assert skitarii_infantry.has_stealth() is True
    assert skitarii_mounted.has_stealth() is True
    assert ironstrider_name_match.has_stealth() is True
    assert non_eligible.has_stealth() is False


def test_stealth_optimisation_grants_cover_to_sicarian_beyond_12_for_ranged_attacks():
    game, admech_army, enemy_army = _build_game()
    sicarian = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SICARIAN"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["SPACE MARINES"],
    )
    admech_army.add_unit(sicarian)
    enemy_army.add_unit(attacker)
    game.map.units = [sicarian, attacker]
    _set_location(sicarian, 0.0, 0.0)
    _set_location(attacker, 20.0, 0.0)
    game.rebuild_entity_registry()

    attack_instance = {"attacker_model": attacker.models[0], "attacker_unit": attacker}
    _ranged_profile()._save_with_tracking(
        sicarian.models[0],
        attack_instance,
        ap=0,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("benefit_of_cover", False)) is True
    assert "Stealth Optimisation" in str(attack_instance.get("benefit_of_cover_source", ""))


def test_stealth_optimisation_cover_not_applied_within_12_inches():
    game, admech_army, enemy_army = _build_game()
    sicarian = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SICARIAN"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["SPACE MARINES"],
    )
    admech_army.add_unit(sicarian)
    enemy_army.add_unit(attacker)
    game.map.units = [sicarian, attacker]
    _set_location(sicarian, 0.0, 0.0)
    _set_location(attacker, 8.0, 0.0)
    game.rebuild_entity_registry()

    attack_instance = {"attacker_model": attacker.models[0], "attacker_unit": attacker}
    _ranged_profile()._save_with_tracking(
        sicarian.models[0],
        attack_instance,
        ap=0,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("benefit_of_cover", False)) is False


def test_stealth_optimisation_cover_not_applied_for_melee_attacks():
    game, admech_army, enemy_army = _build_game()
    sicarian = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SICARIAN"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Assault Squad",
        keywords=["INFANTRY"],
        faction_keywords=["SPACE MARINES"],
    )
    admech_army.add_unit(sicarian)
    enemy_army.add_unit(attacker)
    game.map.units = [sicarian, attacker]
    _set_location(sicarian, 0.0, 0.0)
    _set_location(attacker, 20.0, 0.0)
    game.rebuild_entity_registry()

    attack_instance = {"attacker_model": attacker.models[0], "attacker_unit": attacker}
    _melee_profile()._save_with_tracking(
        sicarian.models[0],
        attack_instance,
        ap=0,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("benefit_of_cover", False)) is False
