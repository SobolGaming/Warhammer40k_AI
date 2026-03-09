from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.dice import DiceCollection


DEVASTATING_REFRAIN_TEXT = (
    "In your Shooting phase, after this model has shot, if one or more of those attacks made with an Indirect Fire "
    "weapon scored a hit against an enemy unit, that unit must take a Battle-shock test. Each time such an attack "
    "destroys an enemy model that has the Deadly Demise ability, that model's Deadly Demise ability inflicts mortal "
    "wounds on a D6 roll of 5+ instead of on a 6."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        leadership: int = 7,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "9",
                "Sv": "3",
                "W": "12",
                "Ld": str(int(leadership)),
                "OC": "3",
                "base_size": "120 x 92mm",
                "inv_sv": "7",
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
    abilities=None,
    keywords=None,
    faction_keywords=None,
    leadership: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            leadership=leadership,
        ),
        quantity=1,
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    as_army = Army("Adepta Sororitas", detachment_type="Hallowed Martyrs")
    as_army.faction_id = "AS"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    as_player = Player("AS", PlayerControl.REMOTE, army=as_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(as_player)
    game.add_player(enemy_player)
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 1
    return game, as_army, enemy_army


class _StubProfile:
    def __init__(self, weapon_name: str, *, indirect: bool):
        self.parent_wargear = SimpleNamespace(name=weapon_name)
        self.name = weapon_name
        self._indirect = bool(indirect)

    def is_indirect_fire(self) -> bool:
        return bool(self._indirect)


class _StubWargear:
    def __init__(self, weapon_name: str, *, indirect: bool):
        self.name = weapon_name
        self.profiles = {"default": _StubProfile(weapon_name, indirect=indirect)}
        self._is_ranged = True

    def is_ranged(self) -> bool:
        return bool(self._is_ranged)


def test_devastating_refrain_forces_battleshock_on_indirect_hit():
    game, as_army, enemy_army = _build_game()
    exorcist = _make_unit(
        "Exorcist",
        abilities=[
            {
                "name": "Devastating Refrain",
                "description": DEVASTATING_REFRAIN_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _make_unit(
        "Enemy Target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership=7,
    )
    as_army.add_unit(exorcist)
    enemy_army.add_unit(target)
    game.map.units = [exorcist, target]
    game.rebuild_entity_registry()

    model = exorcist.models[0]
    model.wargear = [_StubWargear("Exorcist Missile Launcher", indirect=True)]
    calls = []
    target.take_battle_shock_test = lambda current_turn=1: calls.append(int(current_turn))

    weapon_key = exorcist._normalize_keyword_phrase("Exorcist Missile Launcher")
    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=exorcist,
        hits_by_target={target: 1},
        hit_models_by_target={target: {model}},
        hit_models_by_target_weapon={target: {weapon_key: {model}}},
        killing_models_by_target={},
    )

    assert calls == [1]


def test_devastating_refrain_lowers_deadly_demise_trigger_to_five(monkeypatch):
    from warhammer40k_ai.units.unit_mixins import damage_death_mixin as death_mod

    game, as_army, enemy_army = _build_game()
    exorcist = _make_unit(
        "Exorcist",
        abilities=[
            {
                "name": "Devastating Refrain",
                "description": DEVASTATING_REFRAIN_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    attacker_without_rule = _make_unit(
        "Other Vehicle",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    target_vehicle = _make_unit(
        "Enemy Vehicle",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    as_army.add_unit(exorcist)
    enemy_army.add_unit(attacker_without_rule)
    enemy_army.add_unit(target_vehicle)
    game.map.units = [exorcist, attacker_without_rule, target_vehicle]
    game.rebuild_entity_registry()

    target_vehicle.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target_vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    target_vehicle._last_destroyed_by_weapon_profile = _StubProfile("Exorcist Missile Launcher", indirect=True)
    monkeypatch.setattr(death_mod, "get_roll", lambda _expr: 5)

    explosions = {"count": 0}
    target_vehicle._apply_deadly_demise_explosion = lambda **_kwargs: explosions.__setitem__(
        "count", int(explosions["count"]) + 1
    )

    target_vehicle._last_destroyed_by_unit = exorcist
    target_vehicle._trigger_deadly_demise(target_vehicle.models[0], game.map)
    assert int(explosions["count"]) == 1

    explosions["count"] = 0
    target_vehicle._last_destroyed_by_unit = attacker_without_rule
    target_vehicle._trigger_deadly_demise(target_vehicle.models[0], game.map)
    assert int(explosions["count"]) == 0
