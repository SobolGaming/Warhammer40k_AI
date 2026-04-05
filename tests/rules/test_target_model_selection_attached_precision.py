import unittest


class TestTargetModelSelectionAttachedPrecision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        import pygame
        try:
            pygame.font.quit()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass

    def test_precision_candidates_include_attached_character_models(self):
        # Import here so the test fails loudly if the dialog module is broken.
        from warhammer40k_ai.UI.dialogs.target_model_selection_dialog import TargetModelSelectionDialog

        class _Unit:
            def __init__(self, name: str, *, is_character: bool = False):
                self.name = name
                self.is_character = is_character
                self.keywords = (["Character"] if is_character else [])
                self.models = []
                self.attached_leaders = []
                self.attached_to = None
                self.is_leader = False

            def get_attached_unit_root(self):
                if self.is_leader and self.attached_to is not None:
                    return self.attached_to
                return self

            def get_attached_unit_models(self):
                root = self.get_attached_unit_root()
                models = list(getattr(root, "models", []) or [])
                for l in list(getattr(root, "attached_leaders", []) or []):
                    models.extend(list(getattr(l, "models", []) or []))
                return models

            def get_models_for_wound_allocation(self):
                # For this test, bodyguard always has alive models, so allocation candidates are bodyguards only.
                return [m for m in self.models if getattr(m, "is_alive", False)]

        class _Model:
            def __init__(self, name: str, parent_unit):
                self.name = name
                self.parent_unit = parent_unit
                self._base_wounds = 2
                self.wounds = 2

            @property
            def is_alive(self):
                return self.wounds > 0

        bodyguard = _Unit("Howling Banshees", is_character=False)
        leader = _Unit("Jain Zar", is_character=True)
        leader.is_leader = True
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        bg_model = _Model("Banshee", bodyguard)
        leader_model = _Model("Jain Zar", leader)
        bodyguard.models = [bg_model]
        leader.models = [leader_model]

        dlg = TargetModelSelectionDialog(800, 600)
        dlg.target_unit = bodyguard
        dlg.selection_type = "precision"

        eligible = dlg._get_eligible_models()
        self.assertEqual([m.name for m in eligible], ["Jain Zar"])


if __name__ == "__main__":
    unittest.main()


