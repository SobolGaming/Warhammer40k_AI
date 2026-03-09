from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear
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
                "M": "10",
                "T": "6",
                "Sv": "2",
                "W": "8",
                "Ld": "6",
                "OC": "4",
                "base_size": "50mm",
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


def _make_profile(*, weapon_name: str, is_melee: bool, attacks: str = "1"):
    data = {
        "name": str(weapon_name),
        "type": "Melee" if is_melee else "Ranged",
        "range": "Melee" if is_melee else "24",
        "A": str(attacks),
        "BS_WS": "2+",
        "S": "8",
        "AP": "-2",
        "D": "2",
        "description": "",
    }
    return Wargear(data).profiles["default"]


def _attack_result(profile, attacker, target_unit) -> AttackResult:
    return AttackResult(
        weapon_name=str(getattr(profile, "name", "") or "Weapon"),
        attacker_name=str(getattr(attacker, "name", "") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(getattr(profile, "attacks", "")),
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


def test_righteous_repugnance_fight_selection_discards_miracle_and_buffs_named_weapons():
    game, sororitas_army, enemy_army, sororitas_player = _build_game()
    morvenn = _make_unit(
        "Morvenn Vahl",
        abilities=[
            {
                "name": "Righteous Repugnance",
                "description": (
                    "Each time this model's unit is selected to shoot or fight, you can discard 1 Miracle dice. "
                    "If you do, until the end of the phase, add 3 to the Attacks characteristic of Fidelis and the "
                    "Lance of Illumination. Each time an enemy unit is destroyed by this model, you gain 1 Miracle dice."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "VEHICLE", "ADEPTA SORORITAS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sororitas_army.add_unit(morvenn)
    enemy_army.add_unit(enemy)
    game.map.units = [morvenn, enemy]
    game.rebuild_entity_registry()

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    sororitas_army.acts_of_faith.miracle_dice = [2, 6]
    game.map.miracle_dice_pool_reroll_provider = lambda **_kwargs: {"indices": [0]}

    sororitas_army.acts_of_faith.on_fight_unit_selected(morvenn, game=game, selecting_player=sororitas_player)

    assert list(sororitas_army.acts_of_faith.miracle_dice) == [6]
    assert int(morvenn.special_rules.get("righteous_repugnance_bonus", 0) or 0) == 3
    assert str(morvenn.special_rules.get("righteous_repugnance_source_model_id", "") or "") == str(
        get_entity_id(morvenn.models[0])
    )

    attacker = morvenn.models[0]
    fidelis = _make_profile(weapon_name="Fidelis", is_melee=False, attacks="1")
    lance = _make_profile(weapon_name="Lance of Illumination", is_melee=True, attacks="1")
    other = _make_profile(weapon_name="Other Weapon", is_melee=True, attacks="1")

    fidelis_count = fidelis._resolve_attack_count(
        enemy,
        attacker,
        _attack_result(fidelis, attacker, enemy),
        publish_roll_event=False,
    )
    lance_count = lance._resolve_attack_count(
        enemy,
        attacker,
        _attack_result(lance, attacker, enemy),
        publish_roll_event=False,
    )
    other_count = other._resolve_attack_count(
        enemy,
        attacker,
        _attack_result(other, attacker, enemy),
        publish_roll_event=False,
    )
    assert int(fidelis_count.num_attacks) == 4
    assert int(lance_count.num_attacks) == 4
    assert int(other_count.num_attacks) == 1

    game.phase = BattleRoundPhases.COMMAND_PHASE
    expired_count = fidelis._resolve_attack_count(
        enemy,
        attacker,
        _attack_result(fidelis, attacker, enemy),
        publish_roll_event=False,
    )
    assert int(expired_count.num_attacks) == 1


def test_righteous_repugnance_shoot_selection_and_enemy_destroyed_gain_miracle_die():
    game, sororitas_army, enemy_army, sororitas_player = _build_game()
    morvenn = _make_unit(
        "Morvenn Vahl",
        abilities=[
            {
                "name": "Righteous Repugnance",
                "description": (
                    "Each time this model's unit is selected to shoot or fight, you can discard 1 Miracle dice. "
                    "If you do, until the end of the phase, add 3 to the Attacks characteristic of Fidelis and the "
                    "Lance of Illumination. Each time an enemy unit is destroyed by this model, you gain 1 Miracle dice."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "VEHICLE", "ADEPTA SORORITAS"],
    )
    other_friendly = _make_unit(
        "Other Friendly",
        abilities=[],
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sororitas_army.add_unit(morvenn)
    sororitas_army.add_unit(other_friendly)
    enemy_army.add_unit(enemy)
    game.map.units = [morvenn, other_friendly, enemy]
    game.rebuild_entity_registry()

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 3
    sororitas_army.acts_of_faith.miracle_dice = [1]
    game.map.miracle_dice_pool_reroll_provider = lambda **_kwargs: {"indices": [0]}

    sororitas_army.acts_of_faith.on_shoot_unit_selected(morvenn, game=game, selecting_player=sororitas_player)

    assert list(sororitas_army.acts_of_faith.miracle_dice) == []
    assert int(morvenn.special_rules.get("righteous_repugnance_bonus", 0) or 0) == 3

    sororitas_army.acts_of_faith.miracle_dice = []
    sororitas_army.acts_of_faith.on_unit_destroyed(
        enemy,
        game=game,
        destroyed_by_unit=morvenn,
        destroyed_by_model=morvenn.models[0],
        destroyed_by_weapon_profile=None,
    )
    assert len(list(sororitas_army.acts_of_faith.miracle_dice)) == 1

    sororitas_army.acts_of_faith.miracle_dice = []
    sororitas_army.acts_of_faith.on_unit_destroyed(
        enemy,
        game=game,
        destroyed_by_unit=other_friendly,
        destroyed_by_model=other_friendly.models[0],
        destroyed_by_weapon_profile=None,
    )
    assert list(sororitas_army.acts_of_faith.miracle_dice) == []
