import os
import unittest


class TestSupportMatrixVirulentBlessing(unittest.TestCase):
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
    def _find_virulent_blessing_row(gsm, *, faction_id: str):
        datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
        datasheet_faction_by_id = {
            str(r.get("id", "") or "").strip(): str(r.get("faction_id", "") or "").strip()
            for r in datasheets
        }
        datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
        for row in datasheet_abilities:
            if str(row.get("name", "") or "").strip() != "Virulent Blessing (Psychic)":
                continue
            datasheet_id = str(row.get("datasheet_id", "") or "").strip()
            if datasheet_faction_by_id.get(datasheet_id) == str(faction_id):
                return row
        raise AssertionError(f"Virulent Blessing (Psychic) row not found for faction {faction_id}.")

    def _assert_supported_for_faction(self, faction_id: str):
        gsm = self._seed_support_maps()
        row = self._find_virulent_blessing_row(gsm, faction_id=faction_id)
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("ability_id", ""),
            faction_id=faction_id,
            datasheet_id=row.get("datasheet_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("+1 damage", notes.lower())

    def test_virulent_blessing_chaos_daemons_is_supported(self):
        self._assert_supported_for_faction("CD")

    def test_virulent_blessing_death_guard_is_supported(self):
        self._assert_supported_for_faction("DG")


if __name__ == "__main__":
    unittest.main()
