import unittest
from types import SimpleNamespace


class TestPossessedLordPromptHook(unittest.TestCase):
    def test_prompt_hook_controls_activation_at_fight_phase_start(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.ability import Ability
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        possessed = Ability(
            name="Possessed Lord",
            faction_id="",
            description="Once per battle, at the start of the Fight phase, this model can use this ability...",
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self):
                self.name = "Slaughterbound"
                self._id = "Slaughterbound"
                self.possible_abilities = [possessed]
                self.models = [
                    Model(
                        name="Slaughterbound",
                        movement=6,
                        toughness=5,
                        save=3,
                        wounds=6,
                        leadership=6,
                        objective_control=2,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]
                for m in self.models:
                    m.parent_unit = self

            def is_alive(self):
                return True

        class _Army:
            def __init__(self, unit):
                self.id = None
                self.units = [unit]
                self.player = None

            def set_player(self, p):
                self.player = p
                self.id = f"army-{p.id}"

            def on_battle_round_start(self, *_a, **_k):
                return None

        u = _Unit()
        army = _Army(u)
        p1 = Player("P1", control=PlayerControl.LOCAL, army=army)
        p2 = Player("P2", control=PlayerControl.LOCAL, army=_Army(_Unit()))

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        g = Game(bf, players=[p1, p2])

        # Ensure current player is p1
        g.current_player_index = 0

        # Decision: do NOT activate
        p1.decision_hook = lambda _p, key, _ctx: False

        # Publish start of fight phase
        g.phase = SimpleNamespace(name="FIGHT_PHASE")
        g.event_system.publish("phase_start", player=p1, phase=g.phase)

        m = u.models[0]
        self.assertEqual(int(m.get_temporary_melee_attacks_bonus()), 0)

        # Now choose YES and publish again (simulate a later turn; reset by new model instance is not needed here)
        p1.decision_hook = lambda _p, key, _ctx: key == "POSSESSED_LORD"
        g.event_system.publish("phase_start", player=p1, phase=g.phase)
        self.assertEqual(int(m.get_temporary_melee_attacks_bonus()), 3)


if __name__ == "__main__":
    unittest.main()


