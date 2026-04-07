from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        faction_name: str = "Chaos Daemons",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "6",
                "Sv": "4",
                "W": "10",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
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
    def __init__(self, *, melee: bool, ranged: bool):
        self._melee = bool(melee)
        self._ranged = bool(ranged)

    def is_melee(self) -> bool:
        return self._melee

    def is_ranged(self) -> bool:
        return self._ranged


def _setup_game():
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))
    plague_army = Army.with_detachment("Chaos Daemons", detachment_type="Plague Legion")
    plague_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
    enemy_army.faction_id = "SM"

    plague_player = Player("Plague", PlayerControl.REMOTE, plague_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, enemy_army)
    game.add_player(plague_player)
    game.add_player(enemy_player)
    return game, plague_player, enemy_player


def _make_unit(name: str, army: Army, *, keywords=None, faction_keywords=None, faction_name: str = "Chaos Daemons") -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            faction_name=faction_name,
        )
    )
    unit.deployed = True
    army.add_unit(unit)
    return unit


def _apply_plague_enhancement(unit: Unit, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="CD",
        detachment="Plague Legion",
    ).apply_to_unit(unit)


def _ranged_profile(*, ap: int = 0) -> WargearProfile:
    return WargearProfile(
        profile_name="Test Gun",
        wargear_data={
            "range": "36",
            "A": "2",
            "BS_WS": "3+",
            "S": "6",
            "AP": str(ap),
            "D": "2",
            "description": "",
        },
        parent_wargear=_Wargear(melee=False, ranged=True),
    )


def _melee_profile(*, ap: int = -1) -> WargearProfile:
    return WargearProfile(
        profile_name="Test Blade",
        wargear_data={
            "range": "Melee",
            "A": "4",
            "BS_WS": "3+",
            "S": "6",
            "AP": str(ap),
            "D": "2",
            "description": "",
        },
        parent_wargear=_Wargear(melee=True, ranged=False),
    )


def test_plague_legion_enhancement_descriptors_registered():
    ids_to_names = {
        "000009819002": "Cankerblight",
        "000009819003": "Maggot Maws",
        "000009819004": "Droning Shroud (Aura)",
        "000009819005": "Font of Spores (Aura)",
    }
    for enhancement_id, expected_name in ids_to_names.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == expected_name


def test_droning_shroud_restricts_ranged_targeting_to_18_inches():
    game, plague_player, enemy_player = _setup_game()
    bearer = _make_unit(
        "GUO Bearer",
        plague_player.army,
        keywords=["LEGIONES DAEMONICA", "NURGLE", "MONSTER"],
    )
    protected = _make_unit(
        "Protected Unit",
        plague_player.army,
        keywords=["LEGIONES DAEMONICA", "NURGLE", "INFANTRY"],
    )
    not_protected = _make_unit(
        "Not Protected",
        plague_player.army,
        keywords=["LEGIONES DAEMONICA", "TZEENTCH", "INFANTRY"],
    )
    shooter = _make_unit("Shooter", enemy_player.army, faction_name="Enemies")

    _apply_plague_enhancement(bearer, "000009819004", "Droning Shroud (Aura)")

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    protected.models[0].set_location(0.0, 4.0, 0.0, 0.0)
    not_protected.models[0].set_location(2.0, 4.0, 0.0, 0.0)
    shooter.models[0].set_location(0.0, 30.0, 0.0, 0.0)

    game.map.units = [bearer, protected, not_protected, shooter]
    game.rebuild_entity_registry()

    profile = _ranged_profile()
    assert shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, protected, game.map) is False
    assert shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, not_protected, game.map) is True

    shooter.models[0].set_location(0.0, 15.0, 0.0, 0.0)
    assert shooter._can_model_shoot_weapon_at_target(shooter.models[0], profile, protected, game.map) is True


def test_font_of_spores_improves_ap_for_melee_and_ranged_attacks_within_6():
    game, plague_player, enemy_player = _setup_game()
    bearer = _make_unit(
        "Rotigus Bearer",
        plague_player.army,
        keywords=["LEGIONES DAEMONICA", "NURGLE", "MONSTER"],
    )
    attacker = _make_unit(
        "Plaguebearers",
        plague_player.army,
        keywords=["LEGIONES DAEMONICA", "NURGLE", "INFANTRY"],
    )
    enemy = _make_unit("Enemy", enemy_player.army, faction_name="Enemies")

    _apply_plague_enhancement(bearer, "000009819005", "Font of Spores (Aura)")

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    attacker.models[0].set_location(0.0, 4.0, 0.0, 0.0)
    enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)

    game.map.units = [bearer, attacker, enemy]
    game.rebuild_entity_registry()

    ranged = _ranged_profile(ap=0)
    melee = _melee_profile(ap=-1)

    assert int(ranged.get_effective_ap(attacker.models[0], enemy)) == -1
    assert int(melee.get_effective_ap(attacker.models[0], enemy)) == -2

    attacker.models[0].set_location(0.0, 8.0, 0.0, 0.0)
    assert int(ranged.get_effective_ap(attacker.models[0], enemy)) == 0
    assert int(melee.get_effective_ap(attacker.models[0], enemy)) == -1
