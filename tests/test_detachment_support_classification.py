import os
import unittest


class TestDetachmentSupportClassification(unittest.TestCase):
    @staticmethod
    def _seed_support_maps():
        import scripts.generate_ability_support_matrix as gsm

        abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
        detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
        gsm.DETACHMENT_ABILITY_IDS = {
            str(row.get("id", "") or "").strip()
            for row in detachment_abilities
            if str(row.get("id", "") or "").strip()
        }
        gsm._seed_ability_support_maps(abilities, detachment_abilities)
        return gsm, detachment_abilities

    def test_quicksilver_grace_remains_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Quicksilver Grace")
        status, _notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")

    def test_pledges_to_the_dark_prince_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Pledges to the Dark Prince")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("pledge", notes.lower())

    def test_internal_rivalries_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Internal Rivalries")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("favoured champions", notes.lower())


if __name__ == "__main__":
    unittest.main()
