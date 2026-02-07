import pytest
from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        inv_sv: str = "7",
        toughness: str = "4",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": str(inv_sv),
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    inv_sv: str = "7",
    toughness: str = "4",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        inv_sv=inv_sv,
        toughness=toughness,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    unit.round_state.fought_this_round = False
    return unit


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    daemon_army = Army("Chaos Daemons", "Scintillating Legion")
    daemon_army.faction_id = "CD"
    daemon_army.detachment_type = "Scintillating Legion"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    daemon_player = Player("P1", control=PlayerControl.LOCAL, army=daemon_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(daemon_player)
    game.add_player(enemy_player)

    daemon_player.command_points = 3
    enemy_player.command_points = 3
    return game, daemon_player, enemy_player, daemon_army, enemy_army


def test_ficklefire_allows_targeting_out_of_engagement():
    game, daemon_player, _enemy_player, daemon_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Shooter",
        keywords=["TZEENTCH"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    engaged_enemy = _make_unit("Engaged Enemy")
    other_enemy = _make_unit("Other Enemy")

    daemon_army.add_unit(shooter)
    enemy_army.add_unit(engaged_enemy)
    enemy_army.add_unit(other_enemy)
    game.map.units.extend([shooter, engaged_enemy, other_enemy])

    _deploy_unit(shooter, 0.0, 0.0)
    _deploy_unit(engaged_enemy, 0.5, 1.0)
    _deploy_unit(other_enemy, 10.0, 0.0)

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]
    attacker_model = shooter.models[0]

    assert shooter._can_model_shoot_weapon_at_target(attacker_model, profile, other_enemy, game.map) is False

    ok = daemon_player.stratagems.use(
        "FICKLEFIRE",
        unit=shooter,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert shooter._can_model_shoot_weapon_at_target(attacker_model, profile, other_enemy, game.map) is True


def test_flickering_reality_ends_attack_on_match(monkeypatch):
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    target = _make_unit(
        "Target",
        keywords=["TZEENTCH"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    attacker = _make_unit("Attacker")
    daemon_army.add_unit(target)
    enemy_army.add_unit(attacker)

    game.map.units.extend([target, attacker])
    _deploy_unit(target, 0.0, 0.0)
    _deploy_unit(attacker, 1.0, 0.0)

    game.turn = 1
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1

    target.special_rules = {
        "flickering_reality_active": True,
        "flickering_reality_hit_roll": 6,
        "flickering_reality_expires_phase": "FIGHT_PHASE",
        "flickering_reality_turn_owner": str(daemon_player.id),
        "flickering_reality_turn": int(game.turn),
    }

    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 6)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: 6)

    hit_result = profile._hit_target_with_tracking(target, attacker.models[0], {})
    assert hit_result["hit"] is False
    assert any("Flickering Reality" in eff for eff in hit_result.get("special_effects", []))


def test_pyrogenesis_strength_and_ap_bonus():
    game, daemon_player, _enemy_player, daemon_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Shooter",
        keywords=["TZEENTCH"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    target = _make_unit("Target", toughness="5")

    daemon_army.add_unit(shooter)
    enemy_army.add_unit(target)
    game.map.units.extend([shooter, target])
    _deploy_unit(shooter, 0.0, 0.0)
    _deploy_unit(target, 6.0, 0.0)

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    ok = daemon_player.stratagems.use(
        "PYROGENESIS",
        unit=shooter,
        phase_name="Shooting phase",
    )
    assert ok is True

    wound_result = profile._wound_target_with_tracking(
        target,
        shooter.models[0],
        {},
        roll_value=4,
        log_roll=False,
    )
    assert wound_result.get("needed") == 3
    assert any("pyrogenesis" in m.lower() for m in wound_result.get("modifiers", []))

    shooter.special_rules.update(
        {
            "pyrogenesis_active": True,
            "pyrogenesis_strength_bonus": 3,
            "pyrogenesis_ap_bonus": 1,
            "pyrogenesis_expires_phase": "SHOOTING_PHASE",
            "pyrogenesis_turn_owner": str(daemon_player.id),
            "pyrogenesis_turn": int(game.turn),
            "pyrogenesis_source": "Pyrogenesis",
        }
    )
    assert profile.get_effective_ap(shooter.models[0], target) == -1


def test_impossible_eclipse_overrides_shadow_of_chaos():
    game, daemon_player, _enemy_player, daemon_army, _enemy_army = _build_game()
    monster = _make_unit(
        "Monster",
        keywords=["TZEENTCH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    daemon_army.add_unit(monster)
    game.map.units.append(monster)
    _deploy_unit(monster, 0.0, 0.0)

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    ok = daemon_player.stratagems.use(
        "IMPOSSIBLE ECLIPSE",
        unit=monster,
        zone="nml",
        phase_name="Shooting phase",
    )
    assert ok is True

    overrides = getattr(game, "_shadow_of_chaos_zone_overrides", {})
    assert str(daemon_player.id) in overrides
    assert "nml" in overrides[str(daemon_player.id)]
    assert "nml" in game._shadow_of_chaos_zones(daemon_player)

    game.event_system.publish("phase_end", player=daemon_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    assert not getattr(game, "_shadow_of_chaos_zone_overrides", {})


def test_delirium_unmade_moves_unit_to_reserves():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Tzeentch Unit",
        keywords=["TZEENTCH"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy")

    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 10.0, 0.0)

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1

    ok = daemon_player.stratagems.use(
        "DELIRIUM UNMADE",
        units=[daemon_unit],
        phase_name="Fight phase",
    )
    assert ok is True
    assert daemon_unit.reserve_status == "strategic_reserves"
    assert daemon_unit not in game.map.units
