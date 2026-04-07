from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
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
        wounds: int = 2,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": "4",
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


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, keywords=None, faction_keywords=None, wounds: int = 2) -> Unit:
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
    return game, sm_army, enemy_army


def test_judiciar_silent_fury_grants_persistent_executioner_relic_blade_attacks_bonus():
    game, sm_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    judiciar = _actual_unit("Judiciar", datasheet_id="000002707")
    enemy_character = _mock_unit("Enemy Character", keywords=["CHARACTER"], faction_keywords=["ENEMY"], wounds=4)
    sm_army.add_unit(judiciar)
    enemy_army.add_unit(enemy_character)
    game.map.units = [judiciar, enemy_character]
    game.rebuild_entity_registry()

    judiciar_model = judiciar.models[0]
    enemy_model = enemy_character.models[0]

    specs = judiciar.get_kill_reward_specs(model=judiciar_model)
    attack_bonus_spec = next(spec for spec in specs if spec.get("type") == "weapon_attacks_bonus_on_destroy")
    assert str(attack_bonus_spec.get("weapon_name", "") or "") == "executioner relic blade"
    assert int(attack_bonus_spec.get("attacks_bonus", 0) or 0) == 1

    relic_blade = next(
        wargear for wargear in list(judiciar_model.wargear or []) if str(getattr(wargear, "name", "") or "").lower() == "executioner relic blade"
    )
    melee_profile = relic_blade.profiles["default"]

    game._on_model_destroyed_rules(
        attacker_model=judiciar_model,
        attacker_unit=judiciar,
        target_model=enemy_model,
        target_unit=enemy_character,
        weapon_profile=melee_profile,
    )

    bonus, reasons = judiciar_model.get_temporary_weapon_attacks_bonus("Executioner relic blade")
    assert int(bonus or 0) == 1
    assert any("Silent Fury" in str(reason or "") for reason in list(reasons or []))
