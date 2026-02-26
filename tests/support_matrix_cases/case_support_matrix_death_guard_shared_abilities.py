import os
import unittest


class TestSupportMatrixDeathGuardSharedAbilities(unittest.TestCase):
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

    def _status_for_name_and_faction(self, gsm, *, faction_id: str, ability_name: str):
        target_name = self._normalize_name(ability_name)
        datasheets = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets.json"))
        datasheet_faction_by_id = {
            str(row.get("id", "") or "").strip(): str(row.get("faction_id", "") or "").strip()
            for row in datasheets
        }
        datasheet_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
        for row in datasheet_abilities:
            row_name = self._normalize_name(row.get("name", ""))
            if row_name != target_name:
                continue
            datasheet_id = str(row.get("datasheet_id", "") or "").strip()
            if datasheet_faction_by_id.get(datasheet_id) != str(faction_id):
                continue
            return gsm._classify_ability(
                row.get("name", ""),
                row.get("description", ""),
                ability_id=row.get("ability_id", ""),
                faction_id=faction_id,
                datasheet_id=datasheet_id,
            )
        raise AssertionError(f"Could not find ability '{ability_name}' for faction {faction_id}.")

    def test_death_guard_shared_abilities_are_supported(self):
        gsm = self._seed_support_maps()
        expected_supported = (
            "Barrage of Filth",
            "Boon of Death",
            "Curse of the Walking Pox",
            "Death's Heads",
            "DEPLOYMENT",
            "Deluge of Nurgle (Aura)",
            "Diseased Influence",
            "Diseased Cover",
            "Explosive Blight",
            "Extraction of Fresh Disease",
            "Foul Infusion",
            "Fire Support",
            "Gift of Contagion (Psychic)",
            "Grotesque Regeneration",
            "Hail of Corrosive Disease",
            "Infused with the Blessings of Nurgle",
            "Icon of Despair (Aura)",
            "Inflamed Infections",
            "Inflamed Reprisal",
            "Lethal Ichor",
            "Lord of the Death Guard",
            "Malicious Calculations",
            "Nurgle's Rot (Psychic)",
            "Tank Hunters",
            "Vector of Disease",
            "Virulent Blessing (Psychic)",
        )
        for ability_name in expected_supported:
            with self.subTest(ability_name=ability_name):
                status, _notes = self._status_for_name_and_faction(
                    gsm,
                    faction_id="DG",
                    ability_name=ability_name,
                )
                self.assertEqual(status, "Supported")


if __name__ == "__main__":
    unittest.main()
