from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AELDARI"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "14",
                "T": "4",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
                "base_size": "60x35mm",
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


class _TestZone:
    def __init__(self, predicate):
        self._predicate = predicate

    def contains_point(self, x: float, y: float) -> bool:
        return bool(self._predicate(float(x), float(y)))


def _make_unit(name: str, army: Army, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    army.add_unit(unit)
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_profile(*, name: str, keywords: str):
    weapon = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
    )
    return weapon.profiles["default"]


def _build_game():
    army = Army.with_detachment("Aeldari", detachment_type="Windrider Host")
    army.faction_id = "AE"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"

    player = Player("Aeldari", PlayerControl.REMOTE, army=army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    return game, army, enemy_army, player, enemy_player


def test_windrider_host_enhancements_have_tool_descriptors():
    expected = {
        "000009903002": ("Firstdrawn Blade", "grant_scouts_to_bearer_unit"),
        "000009903003": ("Mirage Field", "bearer_unit_target_hit_penalty"),
        "000009903004": ("Seersight Strike", "bearer_psychic_weapon_gain_anti"),
        "000009903005": ("Echoes of Ulthanesh", "cp_gain_roll_with_deployment_zone_modifiers"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_firstdrawn_blade_grants_scouts_nine():
    army = Army.with_detachment("Aeldari", detachment_type="Windrider Host")
    army.faction_id = "AE"
    bearer = _make_unit(
        "Farseer Skyrunner",
        army,
        keywords=["MOUNTED", "CHARACTER", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enhancement = Enhancement(
        id="000009903002",
        name="Firstdrawn Blade",
        faction_id="AE",
        detachment="Windrider Host",
        description="Asuryani Mounted model only. Models in the bearer's unit have the Scouts 9\" ability.",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)

    has_scout, distance = bearer.has_scout()
    assert has_scout
    assert float(distance) == 9.0


def test_mirage_field_applies_unit_target_hit_penalty():
    army = Army.with_detachment("Aeldari", detachment_type="Windrider Host")
    army.faction_id = "AE"
    bearer = _make_unit(
        "Warlock Skyrunner",
        army,
        keywords=["MOUNTED", "CHARACTER", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enhancement = Enhancement(
        id="000009903003",
        name="Mirage Field",
        faction_id="AE",
        detachment="Windrider Host",
        description="Asuryani Mounted model only. Each time an attack targets the bearer's unit, subtract 1 from the Hit roll.",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)

    penalty, reasons = bearer.get_target_hit_roll_penalty("ranged")
    assert int(penalty) == 1
    assert any("mirage field" in str(reason).lower() for reason in tuple(reasons))


def test_seersight_strike_grants_anti_only_to_bearer_psychic_weapons():
    army = Army.with_detachment("Aeldari", detachment_type="Windrider Host")
    army.faction_id = "AE"
    bearer = _make_unit(
        "Farseer Skyrunner",
        army,
        keywords=["MOUNTED", "CHARACTER", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enhancement = Enhancement(
        id="000009903004",
        name="Seersight Strike",
        faction_id="AE",
        detachment="Windrider Host",
        description="Asuryani Mounted Psyker model only. Psychic weapons equipped by the bearer have the [anti-monster 2+] and [anti-vehicle 2+] abilities.",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)

    bearer_model = bearer.models[0]
    psychic_profile = _make_profile(name="Mind Lance", keywords="Psychic")
    normal_profile = _make_profile(name="Shuriken Catapult", keywords="")

    psychic_bonuses = bearer.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer_model,
        weapon_profile=psychic_profile,
        weapon_name="Mind Lance",
    )
    normal_bonuses = bearer.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer_model,
        weapon_profile=normal_profile,
        weapon_name="Shuriken Catapult",
    )

    assert ("MONSTER", 2) in list(psychic_bonuses.get("anti_specs", []) or [])
    assert ("VEHICLE", 2) in list(psychic_bonuses.get("anti_specs", []) or [])
    assert not bool(normal_bonuses.get("anti_specs"))


def test_echoes_of_ulthanesh_command_phase_roll_uses_zone_modifiers():
    game, army, _enemy_army, player, enemy_player = _build_game()
    bearer = _make_unit(
        "Autarch Skyrunner",
        army,
        keywords=["MOUNTED", "CHARACTER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enhancement = Enhancement(
        id="000009903005",
        name="Echoes of Ulthanesh",
        faction_id="AE",
        detachment="Windrider Host",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)

    game.deployment_zones = {
        str(player.id): {"mission_zones": [_TestZone(lambda x, y: x <= 10.0)]},
        str(enemy_player.id): {"mission_zones": [_TestZone(lambda x, y: x >= 90.0)]},
    }

    game.turn = 1
    _set_model_location(bearer, x=5.0, y=5.0)
    before_own = int(player.command_points or 0)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)
    assert int(player.command_points or 0) == before_own

    game.turn = 2
    _set_model_location(bearer, x=50.0, y=5.0)
    before_mid = int(player.command_points or 0)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)
    assert int(player.command_points or 0) == before_mid + 1

    game.turn = 3
    _set_model_location(bearer, x=95.0, y=5.0)
    before_enemy = int(player.command_points or 0)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)
    assert int(player.command_points or 0) == before_enemy + 1
