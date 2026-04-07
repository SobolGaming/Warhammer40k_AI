from __future__ import annotations

import os

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


INTERCEPTION_STRIKE_DESCRIPTION = (
    'Each time this model makes a ranged attack that targets an enemy unit within 12" of one or more '
    'ADEPTUS ASTARTES units from your army, you can re-roll the Hit roll.'
)

_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": "2",
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


def _actual_unit(name: str, *, datasheet_id: str | None = None, faction_id: str = "SM") -> Unit:
    return Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id=faction_id))


def _mock_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )


def _build_game() -> tuple[Game, Army, Army]:
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[sm_player, enemy_player])
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * float(spacing)), float(y), 0.0, 0.0)


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm


def test_interception_strike_applies_when_target_is_within_12_of_the_repulsor_executioner() -> None:
    game, sm_army, enemy_army = _build_game()
    attacker = _actual_unit("Repulsor Executioner", datasheet_id="000002790")
    enemy = _mock_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy(attacker, 0.0, 0.0, spacing=0.0)
    _deploy(enemy, 8.0, 0.0, spacing=0.0)
    game.map.units = [attacker, enemy]
    game.rebuild_entity_registry()

    mods = attacker.get_model_hit_reroll_modifiers(
        attacker.models[0],
        attack_type="ranged",
        target=enemy,
    )

    assert bool(mods.get("reroll_hit_full")) is True
    assert any("Interception Strike" in reason for reason in list(mods.get("reroll_hit_full_reasons", ()) or ()))


def test_interception_strike_applies_when_target_is_only_near_another_friendly_adeptus_astartes_unit() -> None:
    game, sm_army, enemy_army = _build_game()
    attacker = _actual_unit("Repulsor Executioner", datasheet_id="000002790")
    ally = _mock_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _mock_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(attacker)
    sm_army.add_unit(ally)
    enemy_army.add_unit(enemy)
    _deploy(attacker, 0.0, 0.0, spacing=0.0)
    _deploy(ally, 24.0, 0.0, spacing=0.0)
    _deploy(enemy, 30.0, 0.0, spacing=0.0)
    game.map.units = [attacker, ally, enemy]
    game.rebuild_entity_registry()

    mods = attacker.get_model_hit_reroll_modifiers(
        attacker.models[0],
        attack_type="ranged",
        target=enemy,
    )

    assert bool(mods.get("reroll_hit_full")) is True
    assert any("Interception Strike" in reason for reason in list(mods.get("reroll_hit_full_reasons", ()) or ()))


def test_interception_strike_does_not_apply_when_target_is_only_near_non_adeptus_astartes_friendly_units() -> None:
    game, sm_army, enemy_army = _build_game()
    attacker = _actual_unit("Repulsor Executioner", datasheet_id="000002790")
    ally = _mock_unit(
        "Allied Agents",
        keywords=["INFANTRY"],
        faction_keywords=["AGENTS OF THE IMPERIUM"],
    )
    enemy = _mock_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(attacker)
    sm_army.add_unit(ally)
    enemy_army.add_unit(enemy)
    _deploy(attacker, 0.0, 0.0, spacing=0.0)
    _deploy(ally, 24.0, 0.0, spacing=0.0)
    _deploy(enemy, 30.0, 0.0, spacing=0.0)
    game.map.units = [attacker, ally, enemy]
    game.rebuild_entity_registry()

    mods = attacker.get_model_hit_reroll_modifiers(
        attacker.models[0],
        attack_type="ranged",
        target=enemy,
    )

    assert bool(mods.get("reroll_hit_full")) is False
    assert not any("Interception Strike" in reason for reason in list(mods.get("reroll_hit_full_reasons", ()) or ()))


def test_support_matrix_classifies_interception_strike_as_supported() -> None:
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability("Interception Strike", INTERCEPTION_STRIKE_DESCRIPTION, faction_id="SM")

    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "within 12" in lowered
    assert "adeptus astartes" in lowered
    assert "repulsor executioner" in lowered
