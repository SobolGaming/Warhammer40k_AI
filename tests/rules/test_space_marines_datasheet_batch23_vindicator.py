from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(self, name: str, *, datasheet_id: str) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Enemy"}
        self.keywords = []
        self.faction_keywords = ["ENEMY"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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
        self.attached_to = []
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_MockDatasheet(name, datasheet_id=datasheet_id))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def test_vindicator_siege_shield_allows_demolisher_blast_into_own_engagement_only() -> None:
    vindicator = _actual_unit("Vindicator", datasheet_id="000001188")
    target = _mock_unit("Enemy Unit", datasheet_id="enemy-target")
    other_friendly = _mock_unit("Friendly Squad", datasheet_id="friendly-other")

    army = Army.with_detachment("Space Marines", detachment_type="Other")
    army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    player = Player("Space Marines", PlayerControl.LOCAL, army=army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    army.add_unit(vindicator)
    army.add_unit(other_friendly)
    enemy_army.add_unit(target)
    game.map.units = [vindicator, other_friendly, target]
    game.rebuild_entity_registry()

    vindicator.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(0.4, 0.0, 0.0, 0.0)
    other_friendly.models[0].set_location(20.0, 20.0, 0.0, 0.0)

    profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "Blast",
        },
        parent_wargear=SimpleNamespace(name="Demolisher Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    assert vindicator.has_siege_shield() is True
    assert vindicator.ignores_big_guns_never_tire_hit_penalty() is True
    assert vindicator._can_model_shoot_weapon_at_target(vindicator.models[0], profile, target, game.map) is True

    other_friendly.models[0].set_location(0.5, 0.0, 0.0, 0.0)
    assert vindicator._can_model_shoot_weapon_at_target(vindicator.models[0], profile, target, game.map) is False
