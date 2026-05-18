import ast
import builtins
from pathlib import Path

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.deathstrike import DeathstrikeManager
from warhammer40k_ai.rules.detachment_registry import DETACHMENT_MANAGER_CLASSES


_ABILITY_HANDLER_ALLOWED_ARMY_ATTRS = {
    "battle_focus",
    "blessings_of_khorne",
    "bondsman",
    "cabal_of_sorcerers",
    "code_chivalric",
    "combat_doctrines",
    "doctrina_imperatives",
    "emperors_children",
    "gate_of_infinity",
    "harbingers_of_dread",
    "nurgles_gift",
    "oath_of_moment",
    "player",
    "power_from_pain",
    "prioritised_efficiency",
    "schedule_reborn_in_blood",
    "shadow_of_chaos",
    "templar_vows",
    "units",
    "voice_of_command",
    "wrathful_presence",
}


def test_genestealer_cults_configures_deathstrike_manager() -> None:
    army = Army.with_detachment("Genestealer Cults", detachment_type="Brood Brother Auxilia")
    army.faction_id = "GC"
    army.configure_rule_managers(force=True)

    assert isinstance(army.deathstrike, DeathstrikeManager)


def test_all_registered_detachment_managers_configure_on_army() -> None:
    for attr_name, manager_cls in DETACHMENT_MANAGER_CLASSES.items():
        faction_id = str(getattr(manager_cls, "faction_id", "") or "").strip()
        assert faction_id, f"{attr_name} is missing faction_id"

        army = Army.with_detachment(faction_id, detachment_type="Audit Detachment")
        army.faction_id = faction_id
        army.configure_rule_managers(force=True)

        manager = getattr(army, attr_name, None)
        assert isinstance(manager, manager_cls), f"{attr_name} did not configure for {faction_id}"
        assert army.detachment_managers.get(attr_name) is manager
        assert army.get_detachment_manager_for_faction(faction_id) is manager


def test_live_detachment_lookup_does_not_reimport_runtime_module(monkeypatch) -> None:
    army = Army.with_detachment("World Eaters", detachment_type="Berzerker Warband")

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.endswith("army_runtime") or (level and name == "army_runtime"):
            raise AssertionError("live detachment lookup should not re-import army_runtime")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    detachments = army.get_detachment_instances_for_faction("WE")

    assert [detachment.detachment_type for detachment in detachments] == ["Berzerker Warband"]


def test_ability_decision_handlers_use_registered_detachment_manager_attrs() -> None:
    handler_path = Path("src/warhammer40k_ai/engine/decision_handlers/abilities.py")
    tree = ast.parse(handler_path.read_text(encoding="utf-8"))
    registered_attrs = set(DETACHMENT_MANAGER_CLASSES)
    unknown_attrs: dict[str, list[int]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "getattr":
            continue
        if len(node.args) < 2:
            continue
        base, attr = node.args[0], node.args[1]
        if not isinstance(base, ast.Name) or base.id != "army":
            continue
        if not isinstance(attr, ast.Constant) or not isinstance(attr.value, str):
            continue
        attr_name = attr.value
        if attr_name in registered_attrs or attr_name in _ABILITY_HANDLER_ALLOWED_ARMY_ATTRS:
            continue
        unknown_attrs.setdefault(attr_name, []).append(int(node.lineno))

    assert unknown_attrs == {}
