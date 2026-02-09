import os
import unittest


class TestSupportMatrixOvercharge(unittest.TestCase):
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
        return gsm

    def test_overcharge_datasheet_ability_is_supported(self):
        gsm = self._seed_support_maps()
        datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
        row = next(
            r
            for r in datasheet_abilities
            if str(r.get("name", "") or "").strip() == "Overcharge"
            and str(r.get("type", "") or "").strip().lower() == "wargear profile"
            and "hazardous test" in str(r.get("description", "") or "").lower()
        )

        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("ability_id", ""),
            faction_id="LOV",
            datasheet_id=row.get("datasheet_id", ""),
        )

        self.assertEqual(status, "Supported")
        self.assertIn("hazardous", notes.lower())

    def test_overcharge_keyword_is_supported(self):
        gsm = self._seed_support_maps()
        status, notes = gsm._wargear_keywords_support([{"description": "Hazardous, Overcharge"}])
        self.assertEqual(status, "Supported")
        self.assertIn("supported", notes.lower())


if __name__ == "__main__":
    unittest.main()
