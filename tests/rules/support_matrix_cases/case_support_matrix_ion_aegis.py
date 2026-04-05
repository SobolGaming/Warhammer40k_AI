import os
import unittest


class TestSupportMatrixIonAegisAura(unittest.TestCase):
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
    def _faction_by_datasheet_id(gsm):
        datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
        return {
            str(row.get("id", "") or "").strip(): str(row.get("faction_id", "") or "").strip()
            for row in datasheets
        }

    def test_ion_aegis_aura_is_supported(self):
        gsm = self._seed_support_maps()
        datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
        faction_by_datasheet = self._faction_by_datasheet_id(gsm)
        row = next(
            r
            for r in datasheet_abilities
            if str(r.get("name", "") or "").strip() == "Ion Aegis (Aura)"
            and "friendly Armiger model is within 6" in str(r.get("description", "") or "")
        )

        faction_id = faction_by_datasheet.get(str(row.get("datasheet_id", "") or "").strip(), "")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("ability_id", ""),
            faction_id=faction_id,
            datasheet_id=row.get("datasheet_id", ""),
        )

        self.assertEqual(status, "Supported")
        self.assertIn("benefit of cover", notes.lower())
        self.assertIn("armiger", notes.lower())


if __name__ == "__main__":
    unittest.main()
