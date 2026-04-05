from __future__ import annotations

from warhammer40k_ai.engine.path_witness import detect_tight_clearance_orientation_violations


def test_tight_clearance_enforces_yaw_band_for_elliptical_base() -> None:
    start_positions = [
        {
            "model_id": "m1",
            "position": [0.0, 0.0, 0.0],
            "facing": 0.0,
            "radius": [2.0, 1.0],
            "base_type": "ELLIPTICAL",
        }
    ]
    end_positions = [
        {
            "model_id": "m1",
            "position": [4.0, 0.0, 0.0],
            "facing": 30.0,
            "radius": [2.0, 1.0],
            "base_type": "ELLIPTICAL",
        }
    ]
    enemy_bases = [{"x": 2.0, "y": 1.2, "z": 0.0, "radius": 0.0}]
    errors, profiles = detect_tight_clearance_orientation_violations(
        start_positions=start_positions,
        end_positions=end_positions,
        enemy_bases=enemy_bases,
        yaw_band_deg=15.0,
    )
    assert errors
    steps = [float(step["step_inches"]) for step in profiles["m1"]["adaptive_steps"]]
    assert 0.25 in steps


def test_tight_clearance_uses_very_tight_step_size() -> None:
    start_positions = [
        {
            "model_id": "m1",
            "position": [0.0, 0.0, 0.0],
            "facing": 0.0,
            "radius": [2.0, 1.0],
            "base_type": "ELLIPTICAL",
        }
    ]
    end_positions = [
        {
            "model_id": "m1",
            "position": [4.0, 0.0, 0.0],
            "facing": 5.0,
            "radius": [2.0, 1.0],
            "base_type": "ELLIPTICAL",
        }
    ]
    enemy_bases = [{"x": 2.0, "y": 0.8, "z": 0.0, "radius": 0.0}]
    errors, profiles = detect_tight_clearance_orientation_violations(
        start_positions=start_positions,
        end_positions=end_positions,
        enemy_bases=enemy_bases,
        yaw_band_deg=15.0,
    )
    assert errors == []
    steps = [float(step["step_inches"]) for step in profiles["m1"]["adaptive_steps"]]
    assert 0.1 in steps
