from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


REPULSOR_GRID_TEXT = (
    "Each time a ranged attack is allocated to a KASTELAN ROBOT model in this unit, "
    "on an unmodified saving throw of 6, the attacking unit suffers 1 mortal wound after it has "
    "finished making its attacks."
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
                "T": "7",
                "Sv": "2",
                "W": "7",
                "Ld": "7",
                "OC": "2",
                "base_size": "60mm",
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


def _make_profile(*, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Gun" if is_ranged else "Test Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    return WargearProfile(
        "Profile",
        {
            "range": "24" if is_ranged else "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


def _repulsor_grid_ability():
    return {
        "name": "Repulsor Grid",
        "description": REPULSOR_GRID_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def test_repulsor_grid_queues_and_applies_mortals_after_attacker_finishes_shooting():
    game, admech_army, enemy_army = _build_game()
    defender = _make_unit(
        "Kastelan Robots",
        abilities=[_repulsor_grid_ability()],
        keywords=["VEHICLE", "KASTELAN ROBOT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    game.map.units = [defender, attacker]
    game.rebuild_entity_registry()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    profile = _make_profile(is_ranged=True)
    save_result = profile._save_with_tracking(
        defender.models[0],
        {"attacker_model": attacker.models[0], "attacker_unit": attacker, "target_unit": defender},
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Repulsor Grid" in str(entry) for entry in save_result.get("special_effects", []))

    attacker_id = str(attacker._id)
    pending = dict(getattr(defender, "special_rules", {}).get("repulsor_grid_pending_by_attacker", {}) or {})
    assert int(pending.get(attacker_id, 0) or 0) == 1

    applied = []
    defender._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: applied.append((unit, int(amount)))
    game._on_unit_shooting_resolved_repulsor_grid(attacker_unit=attacker)

    assert applied == [(attacker, 1)]
    assert "repulsor_grid_pending_by_attacker" not in getattr(defender, "special_rules", {})


def test_repulsor_grid_does_not_queue_on_non_six_save_roll():
    game, admech_army, enemy_army = _build_game()
    defender = _make_unit(
        "Kastelan Robots",
        abilities=[_repulsor_grid_ability()],
        keywords=["VEHICLE", "KASTELAN ROBOT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    game.map.units = [defender, attacker]
    game.rebuild_entity_registry()

    profile = _make_profile(is_ranged=True)
    profile._save_with_tracking(
        defender.models[0],
        {"attacker_model": attacker.models[0], "attacker_unit": attacker, "target_unit": defender},
        ap=0,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )

    assert "repulsor_grid_pending_by_attacker" not in getattr(defender, "special_rules", {})


def test_repulsor_grid_does_not_queue_for_melee_attacks():
    game, admech_army, enemy_army = _build_game()
    defender = _make_unit(
        "Kastelan Robots",
        abilities=[_repulsor_grid_ability()],
        keywords=["VEHICLE", "KASTELAN ROBOT"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    game.map.units = [defender, attacker]
    game.rebuild_entity_registry()

    profile = _make_profile(is_ranged=False)
    profile._save_with_tracking(
        defender.models[0],
        {"attacker_model": attacker.models[0], "attacker_unit": attacker, "target_unit": defender},
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert "repulsor_grid_pending_by_attacker" not in getattr(defender, "special_rules", {})

