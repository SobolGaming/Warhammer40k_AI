from types import SimpleNamespace

import warhammer40k_ai.units.wargear as wargear_mod
from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.dice import DiceCollection


ROLLING_FORTRESS_TEXT = (
    "Each time a ranged attack is allocated to an ASTRA MILITARUM model from your army, if that model is not "
    "fully visible to every model in the attacking unit because of this BANEBLADE model, that model has the "
    "Benefit of Cover against that attack."
)

CADIA_STANDS_TEXT = (
    "While this unit contains an OFFICER, each time a ranged attack targets this unit, if this unit is within "
    "range of an objective marker you control, models in this unit have the Benefit of Cover against that attack."
)

EARTHSHAKER_ROUNDS_TEXT = (
    "In your Shooting phase, after this model has shot, if one or more of those attacks made with its earthshaker "
    "cannon scored a hit against an enemy INFANTRY unit, until the start of your next Shooting phase, that unit is "
    "shaken. While a unit is shaken, subtract 2\" from its Move characteristic and subtract 2 from Charge rolls made for it."
)

TREMOR_QUAKE_TEXT = (
    "In your Shooting phase, just after selecting a target for this model's tremor cannon, the target unit and every "
    "other enemy INFANTRY unit within 3\" of that unit must take a Battle-shock test."
)

ARMOUR_OBLITERATION_TEXT = (
    "Each time an attack made with this model's quake cannon destroys an enemy model that has the Deadly Demise "
    "ability, that model's Deadly Demise ability inflicts mortal wounds on a D6 roll of 3+ instead of on a 6."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
        datasheet_id: str | None = None,
        save: int = 4,
        move: int = 6,
        wounds: int = 3,
        base_size: str = "32mm",
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": "9",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    *,
    x: float = 0.0,
    y: float = 0.0,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    attached_to=None,
    datasheet_id: str | None = None,
    save: int = 4,
    move: int = 6,
    wounds: int = 3,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            datasheet_id=datasheet_id,
            save=save,
            move=move,
            wounds=wounds,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, am_army, enemy_army, am_player, enemy_player


def _attach_simple_map(units_a: list[Unit], units_b: list[Unit]) -> Map:
    game_map = Map(width=48, height=72)
    army_a = Army.with_detachment("Army A", "Detachment A")
    army_b = Army.with_detachment("Army B", "Detachment B")
    for unit in list(units_a or []):
        army_a.add_unit(unit)
    for unit in list(units_b or []):
        army_b.add_unit(unit)
    game_map.units = list(units_a or []) + list(units_b or [])
    game = SimpleNamespace(map=game_map)
    army_a.player = SimpleNamespace(game=game, name="P1", id="P1")
    army_b.player = SimpleNamespace(game=game, name="P2", id="P2")
    return game_map


class _StubProfile:
    def __init__(self, weapon_name: str):
        self.parent_wargear = SimpleNamespace(name=weapon_name)
        self.name = weapon_name

    def is_indirect_fire(self) -> bool:
        return False


def _ranged_profile() -> WargearProfile:
    return WargearProfile(
        "default",
        {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""},
    )


def test_rolling_fortress_grants_cover_when_baneblade_obscures_friendly_model(monkeypatch):
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 3)

    baneblade = _make_unit(
        "Baneblade",
        x=20.0,
        y=10.0,
        abilities=[{"name": "Rolling Fortress", "description": ROLLING_FORTRESS_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM", "BANEBLADE"],
        faction_keywords=["ASTRA MILITARUM"],
        base_size="120 x 92mm",
        wounds=16,
    )
    shielded = _make_unit(
        "Shielded",
        x=30.0,
        y=10.0,
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    exposed = _make_unit(
        "Exposed",
        x=30.0,
        y=30.0,
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    attacker = _make_unit("Attacker", x=5.0, y=10.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    _attach_simple_map([baneblade, shielded, exposed], [attacker])

    profile = _ranged_profile()
    shielded_result = profile._save_with_tracking(
        shielded.models[0],
        {"mortal_wound": False, "attacker_unit": attacker},
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    exposed_result = profile._save_with_tracking(
        exposed.models[0],
        {"mortal_wound": False, "attacker_unit": attacker},
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(shielded_result.get("saved")) is True
    assert bool(exposed_result.get("saved")) is False


def test_cadia_stands_requires_officer_in_unit(monkeypatch):
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 3)

    with_officer = _make_unit(
        "Cadian Command Squad",
        x=10.0,
        y=10.0,
        datasheet_id="cadia-with-officer",
        abilities=[{"name": "Cadia Stands!", "description": CADIA_STANDS_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "REGIMENT", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    without_officer = _make_unit(
        "Cadian Command Squad 2",
        x=14.0,
        y=10.0,
        datasheet_id="cadia-without-officer",
        abilities=[{"name": "Cadia Stands!", "description": CADIA_STANDS_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "REGIMENT", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    officer = _make_unit(
        "Officer",
        x=10.0,
        y=10.0,
        datasheet_id="officer",
        keywords=["OFFICER", "CHARACTER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        attached_to=["cadia-with-officer"],
    )
    attacker = _make_unit("Attacker", x=30.0, y=10.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    _attach_simple_map([with_officer, without_officer, officer], [attacker])
    officer.attach_to_unit(with_officer)
    with_officer._within_controlled_objective_range = lambda game_map=None: True
    without_officer._within_controlled_objective_range = lambda game_map=None: True

    profile = _ranged_profile()
    with_result = profile._save_with_tracking(
        with_officer.models[0],
        {"mortal_wound": False, "attacker_unit": attacker},
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    without_result = profile._save_with_tracking(
        without_officer.models[0],
        {"mortal_wound": False, "attacker_unit": attacker},
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(with_result.get("saved")) is True
    assert bool(without_result.get("saved")) is False


def test_earthshaker_rounds_auto_apply_and_clear_on_owner_shooting_phase_start():
    game, am_army, enemy_army, am_player, enemy_player = _build_game()
    basilisk = _make_unit(
        "Basilisk",
        x=0.0,
        y=0.0,
        abilities=[{"name": "Earthshaker Rounds", "description": EARTHSHAKER_ROUNDS_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        move=10,
        wounds=11,
    )
    enemy = _make_unit("Enemy Infantry", x=20.0, y=0.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"], move=6)
    am_army.add_unit(basilisk)
    enemy_army.add_unit(enemy)
    game.map.units = [basilisk, enemy]
    game.rebuild_entity_registry()

    weapon_key = basilisk._normalize_keyword_phrase("earthshaker cannon")
    game._on_unit_shooting_resolved_post_shoot_shocked(
        attacker_unit=basilisk,
        hits_by_target={enemy: 1},
        hit_models_by_target_weapon={enemy: {weapon_key: {basilisk.models[0]}}},
    )

    sr = dict(getattr(enemy, "special_rules", {}) or {})
    assert bool(sr.get("shocked_active")) is True
    assert str(sr.get("shocked_expires_timing", "") or "") == "OWNER_NEXT_SHOOTING_START"
    assert int(sr.get("shocked_advance_penalty", 0) or 0) == 0
    assert int(sr.get("shocked_charge_penalty", 0) or 0) == -2
    assert int(enemy.get_effective_model_characteristic(enemy.models[0], "movement")) == 4

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game._on_phase_end_shocked_cleanup(player=enemy_player, phase=game.phase)
    assert bool(getattr(enemy, "special_rules", {}).get("shocked_active")) is True

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_phase_start_post_shoot_duration_cleanup(player=am_player, phase=game.phase)
    assert bool(getattr(enemy, "special_rules", {}).get("shocked_active")) is False
    assert int(enemy.get_effective_model_characteristic(enemy.models[0], "movement")) == 6


def test_tremor_quake_forces_target_and_nearby_infantry_to_take_battle_shock_tests():
    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
    banehammer = _make_unit(
        "Banehammer",
        x=0.0,
        y=0.0,
        abilities=[{"name": "Tremor Quake", "description": TREMOR_QUAKE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        base_size="120 x 92mm",
        wounds=16,
    )
    target_vehicle = _make_unit("Target Vehicle", x=20.0, y=20.0, keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds=12)
    nearby_infantry = _make_unit("Nearby Infantry", x=24.0, y=20.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    far_infantry = _make_unit("Far Infantry", x=30.0, y=20.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    nearby_vehicle = _make_unit("Nearby Vehicle", x=24.0, y=24.0, keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds=12)
    am_army.add_unit(banehammer)
    for enemy in (target_vehicle, nearby_infantry, far_infantry, nearby_vehicle):
        enemy_army.add_unit(enemy)
    game.map.units = [banehammer, target_vehicle, nearby_infantry, far_infantry, nearby_vehicle]
    game.rebuild_entity_registry()

    calls: list[str] = []
    target_vehicle.take_battle_shock_test = lambda current_turn=1: calls.append(f"target:{int(current_turn)}")
    nearby_infantry.take_battle_shock_test = lambda current_turn=1: calls.append(f"nearby:{int(current_turn)}")
    far_infantry.take_battle_shock_test = lambda current_turn=1: calls.append(f"far:{int(current_turn)}")
    nearby_vehicle.take_battle_shock_test = lambda current_turn=1: calls.append(f"vehicle:{int(current_turn)}")

    game._on_shooting_targets_selected_tremor_quake(
        attacking_unit=banehammer,
        target_units=[target_vehicle],
        weapon_declarations=[{"weapon_profile": _StubProfile("tremor cannon"), "target_unit": target_vehicle, "models": banehammer.models}],
    )

    assert calls == ["target:1", "nearby:1"]


def test_armour_obliteration_lowers_deadly_demise_trigger_to_three(monkeypatch):
    from warhammer40k_ai.units.unit_mixins import damage_death_mixin as death_mod

    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
    banesword = _make_unit(
        "Banesword",
        x=0.0,
        y=0.0,
        abilities=[{"name": "Armour Obliteration", "description": ARMOUR_OBLITERATION_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds=16,
    )
    other_attacker = _make_unit("Other Attacker", x=10.0, y=0.0, keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds=12)
    target_vehicle = _make_unit("Enemy Vehicle", x=20.0, y=0.0, keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds=12)
    am_army.add_unit(banesword)
    enemy_army.add_unit(other_attacker)
    enemy_army.add_unit(target_vehicle)
    game.map.units = [banesword, other_attacker, target_vehicle]
    game.rebuild_entity_registry()

    target_vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    target_vehicle._last_destroyed_by_weapon_profile = _StubProfile("quake cannon")
    monkeypatch.setattr(death_mod, "get_roll", lambda _expr: 3)

    explosions = {"count": 0}
    target_vehicle._apply_deadly_demise_explosion = lambda **_kwargs: explosions.__setitem__(
        "count", int(explosions["count"]) + 1
    )

    target_vehicle._last_destroyed_by_unit = banesword
    target_vehicle._trigger_deadly_demise(target_vehicle.models[0], game.map)
    assert int(explosions["count"]) == 1

    explosions["count"] = 0
    target_vehicle._last_destroyed_by_unit = other_attacker
    target_vehicle._trigger_deadly_demise(target_vehicle.models[0], game.map)
    assert int(explosions["count"]) == 0
