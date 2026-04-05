from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adepta Sororitas",
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": name,
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
                "Ld": "6",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "4",
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adepta Sororitas",
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
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
    sororitas_army = Army("Adepta Sororitas", "Champions of Faith")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sororitas_player = Player("Sororitas", control=PlayerControl.REMOTE, army=sororitas_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sororitas_army, enemy_army, sororitas_player


def _make_profile(*, weapon_name: str, is_melee: bool):
    parent = SimpleNamespace(name=weapon_name, is_melee=lambda: is_melee, is_ranged=lambda: not is_melee)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _palatine_with_rapturous_blows() -> Unit:
    return _make_unit(
        "Palatine",
        abilities=[
            {
                "name": "Rapturous Blows",
                "description": (
                    "Each time this model's unit is selected to fight, you can discard 1 Miracle dice. "
                    "If you do, then until the end of the phase, each time a melee attack made by this model "
                    "scores a wound, the target of that attack suffers 1 mortal wound in addition to any normal damage."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"],
    )


def test_rapturous_blows_fight_selection_discards_miracle_and_marks_source():
    game, sororitas_army, enemy_army, sororitas_player = _build_game()
    palatine = _palatine_with_rapturous_blows()
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sororitas_army.add_unit(palatine)
    enemy_army.add_unit(enemy)
    game.map.units = [palatine, enemy]
    game.rebuild_entity_registry()

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    sororitas_army.acts_of_faith.miracle_dice = [2, 6]
    game.map.miracle_dice_pool_reroll_provider = lambda **_kwargs: {"indices": [0]}

    sororitas_army.acts_of_faith.on_fight_unit_selected(palatine, game=game, selecting_player=sororitas_player)

    assert list(sororitas_army.acts_of_faith.miracle_dice) == [6]
    sr = dict(getattr(palatine, "special_rules", {}) or {})
    assert bool(sr.get("rapturous_blows_active", False))
    assert int(sr.get("rapturous_blows_extra_mortals", 0) or 0) == 1
    assert str(sr.get("rapturous_blows_expires_phase", "") or "").strip().upper() == "FIGHT_PHASE"
    assert str(sr.get("rapturous_blows_source_model_id", "") or "") == str(get_entity_id(palatine.models[0]))


def test_rapturous_blows_applies_to_melee_wounds_and_respects_scope():
    game, sororitas_army, enemy_army, sororitas_player = _build_game()
    palatine = _palatine_with_rapturous_blows()
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sororitas_army.add_unit(palatine)
    enemy_army.add_unit(enemy)
    game.map.units = [palatine, enemy]
    game.rebuild_entity_registry()

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 3
    sororitas_army.acts_of_faith.miracle_dice = [1]
    game.map.miracle_dice_pool_reroll_provider = lambda **_kwargs: {"indices": [0]}
    sororitas_army.acts_of_faith.on_fight_unit_selected(palatine, game=game, selecting_player=sororitas_player)

    attacker = palatine.models[0]
    melee_profile = _make_profile(weapon_name="Palatine Blade", is_melee=True)
    ranged_profile = _make_profile(weapon_name="Bolt Pistol", is_melee=False)

    attack_instance_melee = {"_aura_attack_mods": SimpleNamespace()}
    wound_result = melee_profile._wound_target_with_tracking(
        enemy,
        attacker,
        attack_instance_melee,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound"))
    assert int(attack_instance_melee.get("successful_wound_extra_mortal_wounds", 0) or 0) == 1
    assert any("Rapturous Blows" in str(effect) for effect in list(wound_result.get("special_effects", []) or []))

    attack_instance_ranged = {"_aura_attack_mods": SimpleNamespace()}
    ranged_profile._wound_target_with_tracking(
        enemy,
        attacker,
        attack_instance_ranged,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_instance_ranged.get("successful_wound_extra_mortal_wounds", 0) or 0) == 0

    game.phase = BattleRoundPhases.COMMAND_PHASE
    attack_instance_expired = {"_aura_attack_mods": SimpleNamespace()}
    melee_profile._wound_target_with_tracking(
        enemy,
        attacker,
        attack_instance_expired,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_instance_expired.get("successful_wound_extra_mortal_wounds", 0) or 0) == 0

    game.phase = BattleRoundPhases.FIGHT_PHASE
    palatine.special_rules["rapturous_blows_source_model_id"] = "different-model"
    attack_instance_wrong_source = {"_aura_attack_mods": SimpleNamespace()}
    melee_profile._wound_target_with_tracking(
        enemy,
        attacker,
        attack_instance_wrong_source,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_instance_wrong_source.get("successful_wound_extra_mortal_wounds", 0) or 0) == 0
