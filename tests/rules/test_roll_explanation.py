from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.UI.dialogs.dice_roll_dialog import DiceRollDialog
from warhammer40k_ai.engine.dice_rolls import DiceRollManager
from warhammer40k_ai.engine.roll_explanation import build_roll_explanation, infer_modifier_contributor_type


class _GameStub:
    def __init__(self) -> None:
        self.requested = []

    def request_decision(self, request) -> None:
        self.requested.append(request)


def test_build_roll_explanation_classifies_sum_contributors() -> None:
    spec = {
        "roll_type": "battle_shock",
        "sum_target": 6,
        "sum_op": "lte",
        "sum_modifier": -2,
        "sum_modifier_breakdown": [
            {
                "source": "Shadow of Chaos",
                "value": -1,
                "reason": "Enemy in Shadow of Chaos (-1)",
                "contributor_type": "faction_rule",
            },
            {
                "source": "Synaptic Imperatives",
                "value": -1,
                "reason": "Synaptic Imperatives (-1)",
            },
        ],
    }

    explanation = build_roll_explanation(spec)

    assert explanation["condition"]["kind"] == "sum"
    assert int(explanation["condition"]["target"]) == 6
    assert str(explanation["condition"]["op"]) == "lte"
    contribs = list(explanation["sum_modifier"]["contributors"] or [])
    assert len(contribs) == 2
    types = {str(item.get("contributor_type", "")) for item in contribs}
    assert "faction_rule" in types
    assert "detachment_ability" in types


def test_request_roll_includes_roll_explanation_in_context() -> None:
    mgr = DiceRollManager()
    game = _GameStub()
    request = mgr.request_roll(
        game,
        player_id="player-1",
        spec={
            "dice_count": 1,
            "faces": 6,
            "reason": "Wound roll (1D6)",
            "roll_type": "wound",
            "target": 3,
            "target_base": 4,
            "target_op": "gte",
            "target_modifier_reasons": ["Synaptic Imperatives (+1 to wound)"],
        },
        prompt="Wound roll (1D6)",
    )

    roll_spec = dict((request.context or {}).get("roll_spec", {}) or {})
    explanation = dict(roll_spec.get("roll_explanation", {}) or {})

    assert explanation.get("schema_version") == 1
    assert explanation.get("condition", {}).get("kind") == "target"
    target_mod = explanation.get("target_modifier", {})
    contributors = list(target_mod.get("contributors", []) or [])
    assert contributors
    assert contributors[0].get("contributor_type") == "detachment_ability"


def test_dialog_modifier_text_prefers_unified_roll_explanation() -> None:
    spec = {
        "roll_explanation": {
            "schema_version": 1,
            "condition": {
                "kind": "sum",
                "label": "Pass condition",
                "applies_to": "modified_sum",
                "op": "lte",
                "target": 6,
            },
            "sum_modifier": {
                "total": -2,
                "contributors": [
                    {
                        "source": "Shadow of Chaos",
                        "reason": "Enemy in Shadow of Chaos (-1)",
                        "value": -1,
                        "contributor_type": "faction_rule",
                        "applies_to": "sum",
                    },
                    {
                        "source": "Tocsin of Misery",
                        "reason": "Tocsin of Misery (-1)",
                        "value": -1,
                        "contributor_type": "aura",
                        "aura_range_inches": 12.0,
                        "aura_distance_inches": 8.5,
                        "applies_to": "sum",
                    },
                ],
            },
            "target_modifier": {
                "base_target": None,
                "final_target": None,
                "delta": None,
                "contributors": [],
            },
        }
    }
    state = SimpleNamespace(total=11)

    condition = DiceRollDialog._format_condition_text(spec)
    modifier = DiceRollDialog._format_modifier_text(spec, state)

    assert condition == "Pass condition: modified sum <= 6"
    assert "raw 11 -> 9" in modifier
    assert "Faction rule:" in modifier
    assert "Aura:" in modifier
    assert "range 12.0\"" in modifier
    assert "distance 8.5\"" in modifier


def test_contributor_type_inference_covers_requested_categories() -> None:
    assert infer_modifier_contributor_type(reason="Shadow of Chaos (-1)") == "faction_rule"
    assert infer_modifier_contributor_type(reason="Synaptic Imperatives (+1)") == "detachment_ability"
    assert infer_modifier_contributor_type(reason="Battlefield aura (+1)") == "aura"
    assert infer_modifier_contributor_type(reason="This unit ability grants +1") == "unit_ability"
