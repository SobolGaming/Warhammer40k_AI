from __future__ import annotations

from types import MethodType, SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


SHOKK_BOOSTA_TEXT = (
    "You can re-roll Advance rolls made for this model's unit. In addition, each time this model's unit makes a Normal, "
    "Advance or Fall Back move, models in that unit can move through models and terrain features. When doing so, they can "
    "move within Engagement Range of such models but cannot end that move within Engagement Range of them, and any "
    "Desperate Escape test is automatically passed."
)
KUSTOM_FORCE_FIELD_TEXT = "While the bearer is leading a unit, models in that unit have a 4+ invulnerable save against ranged attacks."
GROT_ASSISTANT_TEXT = "Once per battle, after rolling to determine how many attacks the bearer's shokk attack gun makes, you can re-roll that dice."
BOOM_BOMB_TEXT = (
    "Each time this model ends a Normal move, you can select one enemy unit it moved over during that move and roll one D6: "
    "on a 4+, that unit suffers D6 mortal wounds."
)
DUST_TRAILS_TEXT = (
    "While an enemy unit (excluding MONSTERS and VEHICLES) is within 6\" of this model, each time a model in that unit "
    "makes an attack, subtract 1 from the Hit roll."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Orks",
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "4",
        inv_sv: str = "7",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": str(inv_sv),
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


def _make_unit(
    name: str,
    *,
    ability_name: str | None = None,
    ability_desc: str | None = None,
    faction_name: str = "Orks",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    inv_sv: str = "7",
) -> Unit:
    abilities = []
    if ability_desc:
        abilities.append(
            {
                "name": ability_name or name,
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        )
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            inv_sv=inv_sv,
        )
    )


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]


def _make_profile(*, weapon_name: str, range_val: str, is_ranged: bool, attacks: str = "1", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name=weapon_name,
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": str(attacks),
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": str(damage),
        "description": "",
    }
    return WargearProfile("default", wargear_data=data, parent_wargear=parent)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", "Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    return game, ork_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.1 * idx), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


class _MapStub:
    def __init__(self, units, enemies):
        self.units = list(units)
        self._enemies = list(enemies)

    def get_enemy_units(self, _unit):
        return list(self._enemies)


def _setup_stub_players(unit, enemies):
    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=list(enemies))
    player.army = army
    enemy_player.army = enemy_army
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    unit.set_parent_army(army)
    for enemy in enemies:
        enemy.set_parent_army(enemy_army)
    return player, enemy_player


def test_shokk_boosta_grants_phase_move_and_auto_pass_desperate_escape():
    leader = _make_unit(
        "Big Mek",
        ability_name="Shokk-boosta",
        ability_desc=SHOKK_BOOSTA_TEXT,
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    bodyguard = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=3,
    )
    _attach_leader(bodyguard, leader)

    bodyguard._refresh_bearer_unit_common_modifiers()

    assert bodyguard.can_reroll_advance_roll() is True

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=bodyguard)
    assert move_rules.get("can_move_through_enemy_models") is True
    assert move_rules.get("can_move_through_friendly_models") is True
    assert move_rules.get("can_move_through_terrain") is True
    assert move_rules.get("cannot_move_within_engagement_range") is False
    assert move_rules.get("cannot_end_in_engagement_range") is True

    fall_back_rules = get_validation_rules(MovementType.FALL_BACK, moving_unit=bodyguard)
    assert fall_back_rules.get("check_desperate_escape", True) is False
    assert bodyguard.take_desperate_escape_test() == 0


def test_kustom_force_field_applies_only_against_ranged_attacks():
    leader = _make_unit(
        "Big Mek In Mega Armour",
        ability_name="Kustom Force Field",
        ability_desc=KUSTOM_FORCE_FIELD_TEXT,
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    bodyguard = _make_unit(
        "Meganobz",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=3,
        inv_sv="7",
    )
    _attach_leader(bodyguard, leader)
    bodyguard._refresh_bearer_unit_common_modifiers()

    ork_army = Army.with_detachment("Orks", "Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_army.add_unit(leader)
    ork_army.add_unit(bodyguard)
    enemy = _make_unit("Enemy", faction_name="Enemy", faction_keywords=["EN"], model_count=1)
    enemy_army.add_unit(enemy)

    ranged_profile = _make_profile(weapon_name="Test Gun", range_val="24", is_ranged=True)
    ranged_save = ranged_profile._save_with_tracking(
        bodyguard.models[0],
        {"attacker_model": enemy.models[0], "target_unit": bodyguard},
        ap=-3,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert ranged_save.get("save_type") == "invulnerable"
    assert int(ranged_save.get("final_save", 0) or 0) == 4

    melee_profile = _make_profile(weapon_name="Test Klaw", range_val="2", is_ranged=False)
    melee_save = melee_profile._save_with_tracking(
        bodyguard.models[0],
        {"attacker_model": enemy.models[0], "target_unit": bodyguard},
        ap=-3,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert melee_save.get("save_type") != "invulnerable"
    assert int(melee_save.get("final_save", 0) or 0) == 7


def test_grot_assistant_rerolls_shokk_attack_gun_attacks_once_per_battle():
    game, ork_army, enemy_army = _build_game()
    ork_player = ork_army.player

    ability = Ability("Grot Assistant", "ORK", GROT_ASSISTANT_TEXT, "Datasheet", "")
    unit = _make_unit(
        "Big Mek With Shokk Attack Gun",
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    unit.possible_abilities = [ability]
    model = unit.models[0]
    model.abilities = {"Grot Assistant": ability}
    ork_army.add_unit(unit)

    target_unit = _make_unit("Enemy Target", faction_name="Enemy", faction_keywords=["EN"], model_count=1)
    enemy_army.add_unit(target_unit)

    game.install_decision_providers(roll_reroll_provider=lambda **_kwargs: True)
    model.return_closest_model_in_unit = lambda _unit: (target_unit.models[0], 12.0)

    weapon = Wargear(
        {
            "name": "Shokk Attack Gun",
            "type": "Ranged",
            "range": "60",
            "A": "D6",
            "BS_WS": "4+",
            "S": "9",
            "AP": "-4",
            "D": "D6",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    attack_rolls = iter([(1, [1]), (6, [6]), (2, [2])])
    profile.attacks.resolve_detailed = lambda: next(attack_rolls)

    info = profile.preview_attack_count(target_unit, model, publish_roll_event=False)
    assert int(info.num_attacks or 0) == 6
    assert any("Grot Assistant" in str(text or "") for text in list(info.special_modifiers or []))
    assert model.has_used_once_per_battle("grot_assistant") is True

    second = profile.preview_attack_count(target_unit, model, publish_roll_event=False)
    assert int(second.num_attacks or 0) == 2
    assert not any("Grot Assistant" in str(text or "") for text in list(second.special_modifiers or []))


def test_boom_bomb_queues_move_over_threshold_roll_and_applies_mortal_wounds(monkeypatch):
    unit = _make_unit(
        "Blitza-bommer",
        ability_name="Boom Bomb",
        ability_desc=BOOM_BOMB_TEXT,
        keywords=["ORKS", "VEHICLE", "FLY"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    enemy = _make_unit("Enemy", faction_name="Enemy", faction_keywords=["EN"], model_count=1)
    unit.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_stub_players(unit, [enemy])

    mover = unit.models[0]
    target = enemy.models[0]
    mover.set_location(0.0, 0.0, 0.0, 0.0)
    target.set_location(5.0, 0.0, 0.0, 0.0)
    mover.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.players = [player, enemy_player]
    game.map = _MapStub([unit, enemy], [enemy])

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    unit._apply_mortal_wounds_to_unit = MethodType(_apply, unit)

    game._on_unit_move_ended_move_over_mortal_wounds(unit=unit, action="move")

    requests = list(game.decision_queue.list() or [])
    assert len(requests) == 1
    assert requests[0].decision_type == DECISION_CHOOSE_QUARRY
    target_id = get_entity_id(enemy)
    option_id = next(
        opt.option_id
        for opt in list(requests[0].options or [])
        if opt.payload.get("target_unit_id") == target_id
    )
    resolve_decision_command(game, requests[0], option_id, player_id=player.id)

    roll_request = next(req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_REQUEST_DICE_ROLL)
    roll_id = roll_request.context.get("roll_id")
    state = game.roll_manager.get_roll(int(roll_id))
    state.spec["fixed_dice"] = [4]

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda die: 5 if die == "D6" else 0)
    resolve_decision_command(game, roll_request, roll_request.options[0].option_id, player_id=player.id)

    assert applied["target"] is enemy
    assert applied["amount"] == 5


def test_dust_trails_applies_hit_penalty_to_non_monster_non_vehicle_units_only():
    game, ork_army, enemy_army = _build_game()
    source = _make_unit(
        "Boomdakka Snazzwagon",
        ability_name="Dust Trails (Aura)",
        ability_desc=DUST_TRAILS_TEXT,
        keywords=["ORKS", "VEHICLE"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    source.possible_abilities = [Ability("Dust Trails (Aura)", "ORK", DUST_TRAILS_TEXT, "Datasheet", "")]
    ork_army.add_unit(source)

    attacker = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["EN"],
        model_count=3,
    )
    monster = _make_unit(
        "Enemy Monster",
        faction_name="Enemy",
        keywords=["MONSTER"],
        faction_keywords=["EN"],
        model_count=1,
    )
    target = _make_unit("Target", faction_name="Enemy", faction_keywords=["EN"], model_count=1)
    enemy_army.add_unit(attacker)
    enemy_army.add_unit(monster)
    enemy_army.add_unit(target)

    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, attacker, 14.0, 10.0)
    _deploy_unit(game, monster, 14.0, 14.0)
    _deploy_unit(game, target, 20.0, 10.0)
    game.rebuild_entity_registry()

    profile = _make_profile(weapon_name="Test Gun", range_val="24", is_ranged=True)

    infantry_mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game.map)
    assert int(getattr(infantry_mods, "hit", 0) or 0) == -1

    monster_mods = get_aura_attack_modifiers(monster, target, profile, game_map=game.map)
    assert int(getattr(monster_mods, "hit", 0) or 0) == 0
