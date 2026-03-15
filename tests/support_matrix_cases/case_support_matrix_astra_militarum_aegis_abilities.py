import os


class TestSupportMatrixAstraMilitarumAegisAbilities:
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

    def test_am_aegis_defence_line_and_emplacement_platform_are_supported(self):
        gsm = self._seed_support_maps()
        for ability_name in ("Defence Line", "Emplacement Platform", "Reinforced Cover"):
            status, notes = gsm._classify_ability(
                ability_name,
                "",
                ability_id="",
                faction_id="AM",
                datasheet_id="000002619",
            )
            assert status == "Supported"
            assert str(notes or "").strip()
