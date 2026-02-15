import copy
import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.player import DEFAULT_PLAYER_UI_COLOR_PALETTE


class _Player:
    def __init__(self, name: str):
        self.name = name
        self.id = f"player-{name}"
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.army = None
        self.ui_color_rgb = [0, 0, 0]
        self.ui_color_hue_degrees = None
        self.ui_color_selected = False
        self.ui_color_source = "default"

    def set_game(self, game):
        self.game = game

    def get_army(self):
        return self.army

    def assign_default_ui_color(self, slot_index: int) -> None:
        palette = list(DEFAULT_PLAYER_UI_COLOR_PALETTE or [])
        if not palette:
            color = [128, 128, 128]
        else:
            index = int(slot_index) % len(palette)
            color = list(palette[index])
        self.ui_color_rgb = [int(color[0]), int(color[1]), int(color[2])]
        self.ui_color_hue_degrees = None
        self.ui_color_selected = False
        self.ui_color_source = "default"


class _Army:
    def __init__(self, faction_id: str, player: _Player):
        self.faction_id = faction_id
        self.id = f"army-{faction_id}-{player.id}"
        self.units = []
        self.player = player

    def add_unit(self, unit) -> None:
        try:
            unit.set_parent_army(self)
        except Exception:
            pass
        self.units.append(unit)


class _CultUnit:
    def __init__(self, name: str, army: _Army, count: int = 5):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        self.name = name
        self._id = name
        self._army = army
        self.possible_abilities = [SimpleNamespace(name="Cult Ambush")]
        self.models = [
            Model(
                name=f"{name} {idx}",
                movement=6,
                toughness=4,
                save=5,
                wounds=1,
                leadership=7,
                objective_control=1,
                model_base=Base(BaseType.CIRCULAR, 1.0),
            )
            for idx in range(count)
        ]
        self.models_lost = []
        self.starting_model_count = count
        self.deployed = True
        self.reserve_status = "deployed"

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def is_alive(self):
        return True

    def clone_for_cult_ambush(self):
        clone = _CultUnit(self.name, self._army, self.starting_model_count)
        for model in clone.models:
            setattr(model, "_one_shot_used", {"used"})
        return clone


class _StubGame:
    def __init__(self, players):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize

        self.players = list(players)
        self.battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        self.map = SimpleNamespace(get_height_at_point=lambda _x, _y: 0.0)

    def get_enemy_units(self, player):
        for p in self.players:
            if p is player:
                continue
            army = p.get_army()
            if army is not None:
                return list(getattr(army, "units", []) or [])
        return []


class TestCultAmbush(unittest.TestCase):
    def test_resurgence_points_by_size(self):
        from warhammer40k_ai.rules.cult_ambush import CultAmbushManager
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize

        player = _Player("GSC")
        army = _Army("GC", player)
        player.army = army
        mgr = CultAmbushManager(army)

        game = SimpleNamespace(battlefield=Battlefield(BattlefieldSize.STRIKE_FORCE))
        mgr.on_battle_round_start(1, game=game)

        self.assertEqual(mgr.resurgence_points, 10)

    def test_spend_resurgence_creates_unit_and_marker(self):
        from warhammer40k_ai.rules.cult_ambush import CultAmbushManager

        p1 = _Player("GSC")
        p2 = _Player("Enemy")
        army = _Army("GC", p1)
        enemy_army = _Army("ENEMY", p2)
        p1.army = army
        p2.army = enemy_army

        mgr = CultAmbushManager(army)
        mgr.resurgence_points = 6

        unit = _CultUnit("Neophyte Hybrids", army, count=10)
        army.units.append(unit)

        game = _StubGame([p1, p2])
        new_unit = mgr.spend_resurgence_for_unit(unit, game=game)
        self.assertIsNotNone(new_unit)
        self.assertEqual(int(getattr(mgr, "resurgence_points", 0)), 3)
        self.assertTrue(bool(getattr(new_unit, "_cult_ambush", False)))
        self.assertEqual(getattr(new_unit, "reserve_status", ""), "strategic_reserves")

        marker = mgr.place_marker_at(game, 10.0, 10.0)
        self.assertIsNotNone(marker)
        self.assertEqual(len(mgr.get_active_markers()), 1)

        for model in getattr(new_unit, "models", []) or []:
            used = getattr(model, "_one_shot_used", set())
            self.assertEqual(len(used), 0)

    def test_marker_removed_on_enemy_move(self):
        from warhammer40k_ai.rules.cult_ambush import CultAmbushManager, CultAmbushMarker
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        p1 = _Player("GSC")
        p2 = _Player("Enemy")
        army = _Army("GC", p1)
        enemy_army = _Army("ENEMY", p2)
        p1.army = army
        p2.army = enemy_army

        mgr = CultAmbushManager(army)
        marker = CultAmbushMarker(marker_id="m1", x=10.0, y=10.0, z=0.0, active=True)
        mgr.markers.append(marker)

        enemy_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        enemy_model.set_location(12.0, 10.0, 0.0, 0.0)
        enemy_unit = SimpleNamespace(
            models=[enemy_model],
            deployed=True,
            reserve_status="deployed",
            embarked_in=None,
            is_alive=lambda: True,
            has_any_keyword=lambda kw: False,
            get_parent_army=lambda: enemy_army,
        )

        mgr.on_enemy_unit_move_ended(enemy_unit)
        self.assertFalse(marker.active)

        marker2 = CultAmbushMarker(marker_id="m2", x=10.0, y=10.0, z=0.0, active=True)
        mgr.markers.append(marker2)
        enemy_unit_air = SimpleNamespace(
            models=[enemy_model],
            deployed=True,
            reserve_status="deployed",
            embarked_in=None,
            is_alive=lambda: True,
            has_any_keyword=lambda kw: kw == "AIRCRAFT",
            get_parent_army=lambda: enemy_army,
        )
        mgr.on_enemy_unit_move_ended(enemy_unit_air)
        self.assertTrue(marker2.active)

    def test_reserve_denial_blocks_reserves(self):
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        p1 = _Player("P1")
        p2 = _Player("P2")
        army1 = _Army("ALLY", p1)
        army2 = _Army("ENEMY", p2)
        p1.army = army1
        p2.army = army2

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        ability = Ability(
            name="Omni-scramblers",
            faction_id="SM",
            description="Enemy units that are set up as Reinforcements cannot be set up within 12\" of this unit.",
            type="Ability",
        )
        enemy_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        enemy_model.set_location(10.0, 10.0, 0.0, 0.0)
        enemy_unit = SimpleNamespace(
            models=[enemy_model],
            possible_abilities=[ability],
            deployed=True,
            reserve_status="deployed",
            embarked_in=None,
            is_alive=lambda: True,
        )
        army2.units.append(enemy_unit)

        class _ArrivingUnit:
            def __init__(self, army):
                self._army = army
                self.models = [
                    Model(
                        name="Arriving",
                        movement=6,
                        toughness=4,
                        save=4,
                        wounds=2,
                        leadership=7,
                        objective_control=1,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]

            def get_parent_army(self):
                return self._army

            def is_in_strategic_reserves(self):
                return False

            def has_deep_strike(self):
                return True

            def calculate_model_positions(self, x, y, _game_map, **_kwargs):
                return [(x, y, 0.0, 0.0)]

            def _create_potential_base(self, x, y, z, facing, model):
                base = copy.deepcopy(model.model_base)
                base.set_position(x, y, z)
                base.set_facing(facing)
                return base

        arriving = _ArrivingUnit(army1)

        pos_blocked = (22.0, 10.0, 0.0)
        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, pos_blocked))

        pos_ok = (25.0, 10.0, 0.0)
        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, pos_ok))

    def test_reserve_denial_simple_12_inch_blocks_reserves(self):
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        p1 = _Player("P1")
        p2 = _Player("P2")
        army1 = _Army("ALLY", p1)
        army2 = _Army("ENEMY", p2)
        p1.army = army1
        p2.army = army2

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        ability = Ability(
            name="No Warp Zone",
            faction_id="SM",
            description="Enemy units cannot be set up within 12\" of this unit.",
            type="Ability",
        )
        enemy_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        enemy_model.set_location(10.0, 10.0, 0.0, 0.0)
        enemy_unit = SimpleNamespace(
            models=[enemy_model],
            possible_abilities=[ability],
            deployed=True,
            reserve_status="deployed",
            embarked_in=None,
            is_alive=lambda: True,
        )
        army2.units.append(enemy_unit)

        class _ArrivingUnit:
            def __init__(self, army):
                self._army = army
                self.models = [
                    Model(
                        name="Arriving",
                        movement=6,
                        toughness=4,
                        save=4,
                        wounds=2,
                        leadership=7,
                        objective_control=1,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]

            def get_parent_army(self):
                return self._army

            def is_in_strategic_reserves(self):
                return False

            def has_deep_strike(self):
                return True

            def calculate_model_positions(self, x, y, _game_map, **_kwargs):
                return [(x, y, 0.0, 0.0)]

            def _create_potential_base(self, x, y, z, facing, model):
                base = copy.deepcopy(model.model_base)
                base.set_position(x, y, z)
                base.set_facing(facing)
                return base

        arriving = _ArrivingUnit(army1)

        pos_blocked = (22.0, 10.0, 0.0)
        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, pos_blocked))

    def test_reserve_denial_from_reserves_blocks_reserves(self):
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        p1 = _Player("P1")
        p2 = _Player("P2")
        army1 = _Army("ALLY", p1)
        army2 = _Army("ENEMY", p2)
        p1.army = army1
        p2.army = army2

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        ability = Ability(
            name="Scramble Field",
            faction_id="SM",
            description=(
                "Enemy units that are set up on the battlefield from reserves cannot be set up within 12\" of this unit."
            ),
            type="Ability",
        )
        enemy_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        enemy_model.set_location(10.0, 10.0, 0.0, 0.0)
        enemy_unit = SimpleNamespace(
            models=[enemy_model],
            possible_abilities=[ability],
            deployed=True,
            reserve_status="deployed",
            embarked_in=None,
            is_alive=lambda: True,
        )
        army2.units.append(enemy_unit)

        class _ArrivingUnit:
            def __init__(self, army):
                self._army = army
                self.models = [
                    Model(
                        name="Arriving",
                        movement=6,
                        toughness=4,
                        save=4,
                        wounds=2,
                        leadership=7,
                        objective_control=1,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]

            def get_parent_army(self):
                return self._army

            def is_in_strategic_reserves(self):
                return False

            def has_deep_strike(self):
                return True

            def calculate_model_positions(self, x, y, _game_map, **_kwargs):
                return [(x, y, 0.0, 0.0)]

            def _create_potential_base(self, x, y, z, facing, model):
                base = copy.deepcopy(model.model_base)
                base.set_position(x, y, z)
                base.set_facing(facing)
                return base

        arriving = _ArrivingUnit(army1)

        pos_blocked = (22.0, 10.0, 0.0)
        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, pos_blocked))

        pos_ok = (25.0, 10.0, 0.0)
        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, pos_ok))

    def test_reserve_denial_horizontal_uses_horizontal_distance(self):
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        p1 = _Player("P1")
        p2 = _Player("P2")
        army1 = _Army("ALLY", p1)
        army2 = _Army("ENEMY", p2)
        p1.army = army1
        p2.army = army2

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        ability = Ability(
            name="Holo Jammers",
            faction_id="ELD",
            description=(
                "Enemy units that are set up on the battlefield as Reinforcements "
                "cannot be set up within 12\" horizontally of this model."
            ),
            type="Ability",
        )
        enemy_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        enemy_model.set_location(10.0, 10.0, 8.0, 0.0)
        enemy_unit = SimpleNamespace(
            models=[enemy_model],
            possible_abilities=[ability],
            deployed=True,
            reserve_status="deployed",
            embarked_in=None,
            is_alive=lambda: True,
        )
        army2.units.append(enemy_unit)

        class _ArrivingUnit:
            def __init__(self, army):
                self._army = army
                self.models = [
                    Model(
                        name="Arriving",
                        movement=6,
                        toughness=4,
                        save=4,
                        wounds=2,
                        leadership=7,
                        objective_control=1,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]

            def get_parent_army(self):
                return self._army

            def is_in_strategic_reserves(self):
                return False

            def has_deep_strike(self):
                return True

            def calculate_model_positions(self, x, y, _game_map, **_kwargs):
                return [(x, y, 0.0, 0.0)]

            def _create_potential_base(self, x, y, z, facing, model):
                base = copy.deepcopy(model.model_base)
                base.set_position(x, y, z)
                base.set_facing(facing)
                return base

        arriving = _ArrivingUnit(army1)

        pos_blocked = (22.0, 10.0, 0.0)
        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, pos_blocked))

        pos_ok = (24.0, 10.0, 0.0)
        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, pos_ok))

    def test_reserve_denial_uses_3d_without_horizontal(self):
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        p1 = _Player("P1")
        p2 = _Player("P2")
        army1 = _Army("ALLY", p1)
        army2 = _Army("ENEMY", p2)
        p1.army = army1
        p2.army = army2

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        ability = Ability(
            name="Void Screen",
            faction_id="ELD",
            description=(
                "Enemy units that are set up on the battlefield as Reinforcements "
                "cannot be set up within 12\" of this model."
            ),
            type="Ability",
        )
        enemy_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        enemy_model.set_location(10.0, 10.0, 8.0, 0.0)
        enemy_unit = SimpleNamespace(
            models=[enemy_model],
            possible_abilities=[ability],
            deployed=True,
            reserve_status="deployed",
            embarked_in=None,
            is_alive=lambda: True,
        )
        army2.units.append(enemy_unit)

        class _ArrivingUnit:
            def __init__(self, army):
                self._army = army
                self.models = [
                    Model(
                        name="Arriving",
                        movement=6,
                        toughness=4,
                        save=4,
                        wounds=2,
                        leadership=7,
                        objective_control=1,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]

            def get_parent_army(self):
                return self._army

            def is_in_strategic_reserves(self):
                return False

            def has_deep_strike(self):
                return True

            def calculate_model_positions(self, x, y, _game_map, **_kwargs):
                return [(x, y, 0.0, 0.0)]

            def _create_potential_base(self, x, y, z, facing, model):
                base = copy.deepcopy(model.model_base)
                base.set_position(x, y, z)
                base.set_facing(facing)
                return base

        arriving = _ArrivingUnit(army1)

        pos_allowed = (22.0, 10.0, 0.0)
        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, pos_allowed))
