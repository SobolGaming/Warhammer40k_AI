import os
import unittest


class TestSupportMatrixAegisDeployment(unittest.TestCase):
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
    def _normalize_name(text: str) -> str:
        value = str(text or "").replace("\u2019", "'").strip().lower()
        return " ".join(value.split())

    def _deployment_status_for_faction(self, gsm, *, faction_id: str):
        datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
        datasheet_by_id = {str(row.get("id", "") or "").strip(): row for row in datasheets}
        datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
        for row in datasheet_abilities:
            if self._normalize_name(row.get("name", "")) != "deployment":
                continue
            datasheet_id = str(row.get("datasheet_id", "") or "").strip()
            datasheet = datasheet_by_id.get(datasheet_id, {})
            if str(datasheet.get("faction_id", "") or "").strip().upper() != str(faction_id).upper():
                continue
            if self._normalize_name(datasheet.get("name", "")) != "aegis defence line":
                continue
            return gsm._classify_ability(
                row.get("name", ""),
                row.get("description", ""),
                ability_id=row.get("ability_id", ""),
                faction_id=faction_id,
                datasheet_id=datasheet_id,
            )
        raise AssertionError(f"Could not find Aegis DEPLOYMENT for faction {faction_id}.")

    def test_aegis_deployment_is_supported_for_astra_militarum_and_genestealer_cults(self):
        gsm = self._seed_support_maps()
        for faction_id in ("AM", "GC"):
            with self.subTest(faction_id=faction_id):
                status, notes = self._deployment_status_for_faction(gsm, faction_id=faction_id)
                self.assertEqual(status, "Supported")
                self.assertIn("Aegis Defence Line deployment enforces", str(notes))


if __name__ == "__main__":
    unittest.main()
