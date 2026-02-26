import os
import unittest


class TestSupportMatrixDeathstrikeGC(unittest.TestCase):
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

    @staticmethod
    def _gc_deathstrike_datasheet_id(gsm) -> str:
        datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
        row = next(
            r
            for r in datasheets
            if str(r.get("name", "") or "").strip() == "Deathstrike"
            and str(r.get("faction_id", "") or "").strip().upper() == "GC"
        )
        return str(row.get("id", "") or "").strip()

    def test_gc_deathstrike_missile_is_supported(self):
        gsm = self._seed_support_maps()
        datasheet_id = self._gc_deathstrike_datasheet_id(gsm)
        datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
        row = next(
            r
            for r in datasheet_abilities
            if str(r.get("datasheet_id", "") or "").strip() == datasheet_id
            and str(r.get("name", "") or "").strip() == "Deathstrike Missile"
        )

        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("ability_id", ""),
            faction_id="GC",
            datasheet_id=row.get("datasheet_id", ""),
        )

        self.assertEqual(status, "Supported")
        self.assertIn("designate", notes.lower())
        self.assertIn("deathstrike marker", notes.lower())

    def test_gc_plasma_warhead_is_supported(self):
        gsm = self._seed_support_maps()
        datasheet_id = self._gc_deathstrike_datasheet_id(gsm)
        datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
        row = next(
            r
            for r in datasheet_abilities
            if str(r.get("datasheet_id", "") or "").strip() == datasheet_id
            and str(r.get("name", "") or "").strip() == "Plasma Warhead"
            and str(r.get("type", "") or "").strip().lower() == "wargear profile"
        )

        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("ability_id", ""),
            faction_id="GC",
            datasheet_id=row.get("datasheet_id", ""),
        )

        self.assertEqual(status, "Supported")
        self.assertIn("marker-based firing", notes.lower())

    def test_plasma_warhead_keyword_is_supported_for_wargear_summary(self):
        gsm = self._seed_support_maps()
        status, notes = gsm._wargear_keywords_support(
            [{"description": "Blast, One Shot, Plasma Warhead"}]
        )

        self.assertEqual(status, "Supported")
        self.assertIn("supported", notes.lower())


if __name__ == "__main__":
    unittest.main()
