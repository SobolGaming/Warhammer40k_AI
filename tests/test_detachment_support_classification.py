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

    def test_murdercall_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Murdercall")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("blood legion", notes.lower())

    def test_blood_tainted_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Blood Tainted")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("sticky", notes.lower())

    def test_beguiling_aura_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Beguiling Aura")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("fell back", notes.lower())

    def test_seductive_gambit_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Seductive Gambit")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("fights first", notes.lower())

    def test_melancholic_miasma_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Melancholic Miasma")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("battle-shock", notes.lower())

    def test_thralls_of_the_first_prince_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(
            r for r in detachment_abilities if str(r.get("name", "") or "") == "Thralls of the First Prince"
        )
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("shadow legion", notes.lower())

    def test_first_prince_of_chaos_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "First Prince of Chaos")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("dark pacts", notes.lower())

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

    def test_blood_of_martyrs_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "The Blood of Martyrs")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("hallowed martyrs", notes.lower())

    def test_mastered_doctrines_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Mastered Doctrines")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("blade of ultramar", notes.lower())

    def test_legacy_of_the_angel_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Legacy of the Angel")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("angelic inheritors", notes.lower())

    def test_shield_of_the_imperium_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Shield of the Imperium")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("anvil siege force", notes.lower())

    def test_interlocking_tactics_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Interlocking Tactics")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("bastion task force", notes.lower())

    def test_lightning_assault_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Lightning Assault")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("stormlance task force", notes.lower())

    def test_righteous_fervour_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Righteous Fervour")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("companions of vehemence", notes.lower())

    def test_masters_of_manoeuvre_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Masters Of Manoeuvre")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("company of hunters", notes.lower())

    def test_close_range_eradication_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Close-range Eradication")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("firestorm assault force", notes.lower())

    def test_storm_swift_onslaught_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Storm-swift Onslaught")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("spearpoint task force", notes.lower())

    def test_wrath_of_the_first_khan_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Wrath of the First Khan")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("spearpoint task force", notes.lower())

    def test_red_thirst_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Red Thirst")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("liberator assault group", notes.lower())

    def test_shadow_masters_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Shadow Masters")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("vanguard spearhead", notes.lower())

    def test_masters_of_shadow_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Masters of Shadow")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("shadowmark talon", notes.lower())

    def test_unparalleled_tactician_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Unparalleled Tactician")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("shadowmark talon", notes.lower())

    def test_shadowmark_talon_restrictions_are_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(
            r
            for r in detachment_abilities
            if str(r.get("name", "") or "") == "Restrictions"
            and "Raven Guard" in str(r.get("description", "") or "")
        )
        status, _notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")

    def test_hammer_of_avernii_restrictions_are_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(
            r
            for r in detachment_abilities
            if str(r.get("name", "") or "") == "Restrictions"
            and "Iron Hands" in str(r.get("description", "") or "")
        )
        status, _notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")

    def test_spearpoint_task_force_restrictions_are_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(
            r
            for r in detachment_abilities
            if str(r.get("name", "") or "") == "Restrictions"
            and "White Scars" in str(r.get("description", "") or "")
        )
        status, _notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")

    def test_calculated_annihilation_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Calculated Annihilation")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("hammer of avernii", notes.lower())

    def test_recalculating_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Recalculating")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("hammer of avernii", notes.lower())

    def test_wrath_of_dorn_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Wrath of Dorn")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("emperor's shield", notes.lower())

    def test_armoured_wrath_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Armoured Wrath")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("ironstorm spearhead", notes.lower())

    def test_a_noble_death_in_combat_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "A Noble Death in Combat")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("the lost brethren", notes.lower())

    def test_grim_resolve_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Grim Resolve")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("unforgiven task force", notes.lower())

    def test_vowed_target_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Vowed Target")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("inner circle task force", notes.lower())

    def test_the_great_wolf_watches_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "The Great Wolf Watches")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("champions of fenris", notes.lower())

    def test_vulkans_quest_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(
            r
            for r in detachment_abilities
            if str(r.get("name", "") or "").replace("\u2019", "'") == "Vulkan's Quest"
        )
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("forgefather", notes.lower())

    def test_shock_and_awe_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Shock and Awe")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("godhammer", notes.lower())

    def test_mission_tactics_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Mission Tactics")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("black spear task force", notes.lower())

    def test_strength_from_death_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Strength from Death")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("lethal surge", notes.lower())

    def test_bold_gallantry_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Bold Gallantry")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("valourstrike", notes.lower())

    def test_rad_bombardment_is_supported(self):
        gsm, detachment_abilities = self._seed_support_maps()
        row = next(r for r in detachment_abilities if str(r.get("name", "") or "") == "Rad-bombardment")
        status, notes = gsm._classify_ability(
            row.get("name", ""),
            row.get("description", ""),
            ability_id=row.get("id", ""),
            faction_id=row.get("faction_id", ""),
        )
        self.assertEqual(status, "Supported")
        self.assertIn("rad-zone corps", notes.lower())


if __name__ == "__main__":
    unittest.main()
