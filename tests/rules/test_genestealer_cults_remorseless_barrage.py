from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


REMORSELESS_BARRAGE_TEXT = (
    "In your Shooting phase, after this model has shot, if one or more of those attacks made with an Indirect Fire "
    "weapon scored a hit against an enemy unit, that unit must take a Battle-shock test (if an INFANTRY unit is hit "
    "by one or more attacks made by a multiple rocket launcher, they must subtract 1 from their Battle-shock test "
    "when doing so)."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        leadership: int = 7,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "6",
                "Sv": "4",
                "W": "6",
                "Ld": str(int(leadership)),
                "OC": "2",
                "base_size": "60mm",
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
    faction_name: str,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    leadership: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
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
    gsc_army = Army.with_detachment("Genestealer Cults", detachment_type="Brood Brother Auxilia")
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    gsc_player = Player("GSC", PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2
    return game, gsc_army, enemy_army


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


def test_remorseless_barrage_parses_indirect_fire_trigger_and_weapon_condition():
    artillery = _make_unit(
        "Artillery Team",
        faction_name="Genestealer Cults",
        abilities=[
            {
                "name": "Remorseless Barrage",
                "description": REMORSELESS_BARRAGE_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    model = artillery.models[0]
    specs = artillery.model_post_shoot_battleshock_specs(model)

    assert len(specs) == 1
    spec = specs[0]
    assert bool(spec.get("require_indirect_fire_hit", False))
    assert bool(spec.get("auto_each_target", False))
    assert int(spec.get("test_modifier_if_infantry_hit_by_weapon", 0) or 0) == -1
    assert str(spec.get("test_modifier_if_infantry_hit_by_weapon_name", "") or "") == "multiple rocket launcher"


def test_remorseless_barrage_applies_minus_one_only_for_infantry_hit_by_multiple_rocket_launcher():
    game, gsc_army, enemy_army = _build_game()
    artillery = _make_unit(
        "Artillery Team",
        faction_name="Genestealer Cults",
        abilities=[
            {
                "name": "Remorseless Barrage",
                "description": REMORSELESS_BARRAGE_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    infantry_rocket = _make_unit(
        "Enemy Infantry (Rocket Hit)",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    infantry_mortar = _make_unit(
        "Enemy Infantry (Mortar Hit)",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    vehicle_rocket = _make_unit(
        "Enemy Vehicle (Rocket Hit)",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    gsc_army.add_unit(artillery)
    enemy_army.add_unit(infantry_rocket)
    enemy_army.add_unit(infantry_mortar)
    enemy_army.add_unit(vehicle_rocket)
    game.map.units = [artillery, infantry_rocket, infantry_mortar, vehicle_rocket]
    game.rebuild_entity_registry()

    model = artillery.models[0]
    model.wargear = [
        _StubWargear("Multiple rocket launcher", indirect=True),
        _StubWargear("Heavy mortar", indirect=True),
    ]

    captured_modifiers = {}

    def _capture_modifier(label: str, unit):
        def _capture(current_turn=1):
            _ = int(current_turn)
            captured_modifiers[label] = int(unit.special_rules.get("battle_shock_test_modifier", 0) or 0)

        return _capture

    infantry_rocket.take_battle_shock_test = _capture_modifier("rocket_infantry", infantry_rocket)
    infantry_mortar.take_battle_shock_test = _capture_modifier("mortar_infantry", infantry_mortar)
    vehicle_rocket.take_battle_shock_test = _capture_modifier("rocket_vehicle", vehicle_rocket)

    rocket_key = artillery._normalize_keyword_phrase("Multiple rocket launcher")
    mortar_key = artillery._normalize_keyword_phrase("Heavy mortar")
    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=artillery,
        hits_by_target={
            infantry_rocket: 1,
            infantry_mortar: 1,
            vehicle_rocket: 1,
        },
        hit_models_by_target={
            infantry_rocket: {model},
            infantry_mortar: {model},
            vehicle_rocket: {model},
        },
        hit_models_by_target_weapon={
            infantry_rocket: {rocket_key: {model}},
            infantry_mortar: {mortar_key: {model}},
            vehicle_rocket: {rocket_key: {model}},
        },
        killing_models_by_target={},
    )

    assert int(captured_modifiers.get("rocket_infantry", 999)) == -1
    assert int(captured_modifiers.get("mortar_infantry", 999)) == 0
    assert int(captured_modifiers.get("rocket_vehicle", 999)) == 0
