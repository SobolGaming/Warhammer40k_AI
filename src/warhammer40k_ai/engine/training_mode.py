from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import random
import time
from typing import Any, Iterable, Mapping, Sequence

from .ai_controller_router import COMPONENT_DEPLOYMENT_RANKER, COMPONENT_SHOOTING_RANKER
from .decision_kinds import DECISION_DECLARE_RESERVES, DECISION_DECLARE_SHOTS
from .decisions import CandidateAction, DecisionOption, DecisionRequest

TRAINING_MODE_SCHEMA_VERSION = "1.0.0"
TRAINING_STAGE_SHOOTING = "shooting_phase"
TRAINING_STAGE_DEPLOYMENT_RESERVES = "deployment_reserves"
TRAINING_STAGE_MIXED = "mixed"

SUPPORTED_TRAINING_STAGES: tuple[str, ...] = (
    TRAINING_STAGE_SHOOTING,
    TRAINING_STAGE_DEPLOYMENT_RESERVES,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()[:16]


def _stable_action_id(stage: str, payload: Mapping[str, Any]) -> str:
    return f"training:{stage}:{_stable_digest(dict(payload or {}))}"


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _success_probability(threshold: int) -> float:
    return _clamp_float((7 - int(threshold)) / 6.0, 0.0, 1.0)


def _wound_threshold(strength: int, toughness: int) -> int:
    s = max(1, int(strength))
    t = max(1, int(toughness))
    if s >= 2 * t:
        return 2
    if s > t:
        return 3
    if s == t:
        return 4
    if s * 2 <= t:
        return 6
    return 5


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        return [_json_safe(inner) for inner in sorted(value, key=lambda entry: str(entry))]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    return str(value)


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _numeric_metadata(candidate: CandidateAction) -> dict[str, float]:
    values: dict[str, float] = {}
    for key, value in sorted(dict(candidate.metadata or {}).items(), key=lambda item: str(item[0])):
        if isinstance(value, bool):
            values[str(key)] = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            values[str(key)] = float(value)
    return values


@dataclass(frozen=True)
class TrainingScenarioConfig:
    stage: str = TRAINING_STAGE_MIXED
    seed: int = 0
    session_id: str = ""
    user_side: str = "player1"
    opponent_mode: str = "ai"
    point_limit: int = 2000
    candidate_count: int = 6
    time_budget_ms: int = 250

    def normalized_stage_for_index(self, index: int) -> str:
        stage = str(self.stage or TRAINING_STAGE_MIXED).strip().lower()
        if stage == TRAINING_STAGE_MIXED:
            return SUPPORTED_TRAINING_STAGES[int(index) % len(SUPPORTED_TRAINING_STAGES)]
        if stage not in SUPPORTED_TRAINING_STAGES:
            allowed = ", ".join((TRAINING_STAGE_MIXED, *SUPPORTED_TRAINING_STAGES))
            raise ValueError(f"Unsupported training stage {self.stage!r}; expected one of: {allowed}.")
        return stage

    def normalized_session_id(self) -> str:
        explicit = str(self.session_id or "").strip()
        if explicit:
            return explicit
        basis = {
            "stage": str(self.stage or ""),
            "seed": int(self.seed),
            "user_side": str(self.user_side or ""),
            "opponent_mode": str(self.opponent_mode or ""),
            "point_limit": int(self.point_limit),
        }
        return f"training:{_stable_digest(basis)}"


@dataclass(frozen=True)
class TrainingScenario:
    scenario_id: str
    stage: str
    component_name: str
    request: DecisionRequest
    situation: dict[str, Any]
    evaluation_profile_id: str

    def to_ui_payload(self) -> dict[str, Any]:
        candidates = []
        for index, candidate in enumerate(list(self.request.candidates or [])):
            metadata = dict(candidate.metadata or {})
            candidates.append(
                {
                    "action_id": str(candidate.action_id),
                    "legal": bool(index < len(self.request.mask) and self.request.mask[index]),
                    "label": str(metadata.get("ui_label", "") or candidate.action_id),
                    "summary": str(metadata.get("ui_summary", "") or ""),
                    "score_hint": _safe_float(metadata.get("training_evaluation_score"), default=0.0),
                    "params": _json_safe(dict(candidate.params or {})),
                    "metadata": _json_safe(metadata),
                }
            )
        return {
            "scenario_id": str(self.scenario_id),
            "stage": str(self.stage),
            "component_name": str(self.component_name),
            "prompt": str(self.request.prompt),
            "request": self.request.to_dict(),
            "situation": _json_safe(dict(self.situation or {})),
            "candidates": candidates,
        }


@dataclass(frozen=True)
class TrainingEvaluation:
    selected_action_id: str
    selected_score: float
    best_action_id: str
    best_score: float
    reward: float
    matched_best: bool
    feedback: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_action_id": str(self.selected_action_id),
            "selected_score": float(self.selected_score),
            "best_action_id": str(self.best_action_id),
            "best_score": float(self.best_score),
            "reward": float(self.reward),
            "matched_best": bool(self.matched_best),
            "feedback": _json_safe(dict(self.feedback or {})),
        }


@dataclass(frozen=True)
class TrainingObservation:
    observation_id: str
    session_id: str
    scenario_id: str
    stage: str
    component_name: str
    decision_type: str
    request: dict[str, Any]
    chosen_action_id: str
    legal: bool
    source: str
    created_at: float
    wall_clock_ms: int
    evaluation: TrainingEvaluation

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TRAINING_MODE_SCHEMA_VERSION,
            "observation_id": str(self.observation_id),
            "session_id": str(self.session_id),
            "scenario_id": str(self.scenario_id),
            "stage": str(self.stage),
            "component_name": str(self.component_name),
            "decision_type": str(self.decision_type),
            "request": _json_safe(dict(self.request or {})),
            "chosen_action_id": str(self.chosen_action_id),
            "legal": bool(self.legal),
            "source": str(self.source),
            "created_at": float(self.created_at),
            "wall_clock_ms": int(max(0, self.wall_clock_ms)),
            "evaluation": self.evaluation.to_dict(),
            "supervised_example": {
                "component_name": str(self.component_name),
                "decision": _json_safe(dict(self.request or {})),
                "chosen_action_id": str(self.chosen_action_id),
                "reward": float(self.evaluation.reward),
            },
        }


@dataclass
class TrainingPreferenceModel:
    model_schema_id: str = "training_preference_model:v1"
    component_weights: dict[str, dict[str, float]] = field(default_factory=dict)
    component_counts: dict[str, int] = field(default_factory=dict)

    def update(self, scenario: TrainingScenario, observation: TrainingObservation) -> None:
        candidate = _candidate_for_action_id(scenario.request, observation.chosen_action_id)
        if candidate is None or not observation.legal:
            return
        component = str(scenario.component_name)
        current = dict(self.component_weights.get(component, {}) or {})
        count = int(self.component_counts.get(component, 0) or 0)
        reward = float(observation.evaluation.reward)
        features = _numeric_metadata(candidate)
        for key, value in features.items():
            old = float(current.get(key, 0.0))
            current[key] = old + ((float(value) * reward) - old) / float(count + 1)
        self.component_weights[component] = current
        self.component_counts[component] = count + 1

    def score_candidate(self, component_name: str, candidate: CandidateAction) -> float:
        weights = dict(self.component_weights.get(str(component_name), {}) or {})
        if not weights:
            return 0.0
        features = _numeric_metadata(candidate)
        return sum(float(weights.get(key, 0.0)) * float(value) for key, value in features.items())

    def choose_action_id(self, scenario: TrainingScenario) -> str:
        best = ("", float("-inf"))
        for index, candidate in enumerate(list(scenario.request.candidates or [])):
            if index < len(scenario.request.mask) and not bool(scenario.request.mask[index]):
                continue
            score = self.score_candidate(scenario.component_name, candidate)
            key = (float(score), str(candidate.action_id))
            if key > (best[1], best[0]):
                best = (str(candidate.action_id), float(score))
        return best[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_schema_id": str(self.model_schema_id),
            "component_weights": {
                str(component): {str(key): float(value) for key, value in sorted(weights.items())}
                for component, weights in sorted(self.component_weights.items())
            },
            "component_counts": {
                str(component): int(count)
                for component, count in sorted(self.component_counts.items())
            },
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TrainingPreferenceModel":
        data = dict(payload or {})
        raw_weights = dict(data.get("component_weights", {}) or {})
        weights: dict[str, dict[str, float]] = {}
        for component, component_weights in raw_weights.items():
            values = dict(component_weights or {})
            weights[str(component)] = {str(key): _safe_float(value) for key, value in values.items()}
        raw_counts = dict(data.get("component_counts", {}) or {})
        counts = {str(component): int(_safe_float(count)) for component, count in raw_counts.items()}
        return cls(
            model_schema_id=str(data.get("model_schema_id", "training_preference_model:v1") or ""),
            component_weights=weights,
            component_counts=counts,
        )

    @classmethod
    def load(cls, path: str | Path) -> "TrainingPreferenceModel":
        model_path = Path(path)
        if not model_path.is_file():
            return cls()
        payload = json.loads(model_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Training preference model file must contain a JSON object.")
        return cls.from_dict(payload)

    def save(self, path: str | Path) -> None:
        model_path = Path(path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


class TrainingObservationStore:
    def __init__(
        self,
        *,
        session_id: str,
        output_path: str | Path | None = None,
        model: TrainingPreferenceModel | None = None,
        model_output_path: str | Path | None = None,
    ) -> None:
        self.session_id = str(session_id or "")
        self.output_path = Path(output_path) if output_path is not None else None
        self.model = model or TrainingPreferenceModel()
        self.model_output_path = Path(model_output_path) if model_output_path is not None else None
        self.observations: list[TrainingObservation] = []

    def record_selection(
        self,
        scenario: TrainingScenario,
        action_id: str,
        *,
        source: str = "ui",
        wall_clock_ms: int = 0,
    ) -> TrainingObservation:
        chosen_action_id = str(action_id or "").strip()
        legal = _action_id_is_legal(scenario.request, chosen_action_id)
        evaluation = evaluate_training_selection(scenario, chosen_action_id)
        observation_id = f"training_observation:{_stable_digest([self.session_id, scenario.scenario_id, chosen_action_id, len(self.observations)])}"
        observation = TrainingObservation(
            observation_id=observation_id,
            session_id=self.session_id,
            scenario_id=str(scenario.scenario_id),
            stage=str(scenario.stage),
            component_name=str(scenario.component_name),
            decision_type=str(scenario.request.decision_type),
            request=scenario.request.to_dict(),
            chosen_action_id=chosen_action_id,
            legal=legal,
            source=str(source or "ui"),
            created_at=time.time(),
            wall_clock_ms=int(max(0, wall_clock_ms)),
            evaluation=evaluation,
        )
        self.observations.append(observation)
        self.model.update(scenario, observation)
        self._append_jsonl(observation)
        if self.model_output_path is not None:
            self.model.save(self.model_output_path)
        return observation

    def _append_jsonl(self, observation: TrainingObservation) -> None:
        if self.output_path is None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(observation.to_dict(), sort_keys=True) + "\n")


class TrainingScenarioGenerator:
    def __init__(self, config: TrainingScenarioConfig) -> None:
        self.config = config

    def generate(self, index: int) -> TrainingScenario:
        stage = self.config.normalized_stage_for_index(index)
        seed = int(self.config.seed) + (int(index) * 7919)
        rng = random.Random(seed)
        if stage == TRAINING_STAGE_SHOOTING:
            return _generate_shooting_scenario(self.config, rng=rng, index=index, seed=seed)
        if stage == TRAINING_STAGE_DEPLOYMENT_RESERVES:
            return _generate_deployment_reserves_scenario(self.config, rng=rng, index=index, seed=seed)
        raise ValueError(f"Unsupported training stage: {stage}")


class TrainingSession:
    def __init__(
        self,
        config: TrainingScenarioConfig,
        *,
        store: TrainingObservationStore | None = None,
    ) -> None:
        self.config = config
        self.session_id = config.normalized_session_id()
        self.generator = TrainingScenarioGenerator(config)
        self.store = store or TrainingObservationStore(session_id=self.session_id)
        self._index = 0

    def next_scenario(self) -> TrainingScenario:
        scenario = self.generator.generate(self._index)
        self._index += 1
        return scenario

    def record_selection(
        self,
        scenario: TrainingScenario,
        action_id: str,
        *,
        source: str = "ui",
        wall_clock_ms: int = 0,
    ) -> TrainingObservation:
        return self.store.record_selection(
            scenario,
            action_id,
            source=source,
            wall_clock_ms=wall_clock_ms,
        )


def best_training_action_id(scenario: TrainingScenario) -> str:
    legal_candidates = _legal_candidates(scenario.request)
    if not legal_candidates:
        return ""
    return max(
        legal_candidates,
        key=lambda candidate: (
            _safe_float(candidate.metadata.get("training_evaluation_score"), default=0.0),
            str(candidate.action_id),
        ),
    ).action_id


def evaluate_training_selection(scenario: TrainingScenario, action_id: str) -> TrainingEvaluation:
    legal_candidates = _legal_candidates(scenario.request)
    if not legal_candidates:
        return TrainingEvaluation(
            selected_action_id=str(action_id or ""),
            selected_score=0.0,
            best_action_id="",
            best_score=0.0,
            reward=0.0,
            matched_best=False,
            feedback={"reason": "no legal candidates"},
        )
    best_candidate = max(
        legal_candidates,
        key=lambda candidate: (
            _safe_float(candidate.metadata.get("training_evaluation_score"), default=0.0),
            str(candidate.action_id),
        ),
    )
    selected = _candidate_for_action_id(scenario.request, action_id)
    selected_score = 0.0
    selected_feedback: dict[str, Any] = {"legal": False}
    if selected is not None and _action_id_is_legal(scenario.request, str(selected.action_id)):
        selected_score = _safe_float(selected.metadata.get("training_evaluation_score"), default=0.0)
        selected_feedback = dict(selected.metadata.get("training_feedback", {}) or {})
        selected_feedback["legal"] = True
    best_score = _safe_float(best_candidate.metadata.get("training_evaluation_score"), default=0.0)
    reward = selected_score / best_score if best_score > 0 else 0.0
    reward = _clamp_float(reward, 0.0, 1.0)
    matched_best = str(action_id or "") == str(best_candidate.action_id)
    selected_feedback["best_action_id"] = str(best_candidate.action_id)
    selected_feedback["best_score"] = float(best_score)
    return TrainingEvaluation(
        selected_action_id=str(action_id or ""),
        selected_score=float(selected_score),
        best_action_id=str(best_candidate.action_id),
        best_score=float(best_score),
        reward=float(reward),
        matched_best=matched_best,
        feedback=selected_feedback,
    )


def load_training_observations(path: str | Path) -> list[dict[str, Any]]:
    observation_path = Path(path)
    if not observation_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(observation_path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError(f"Training observation line {line_number} must be a JSON object.")
        records.append(payload)
    return records


def _candidate_for_action_id(request: DecisionRequest, action_id: str) -> CandidateAction | None:
    target = str(action_id or "")
    for candidate in list(request.candidates or []):
        if str(candidate.action_id) == target:
            return candidate
    return None


def _action_id_is_legal(request: DecisionRequest, action_id: str) -> bool:
    target = str(action_id or "")
    if not target:
        return False
    for index, candidate in enumerate(list(request.candidates or [])):
        if str(candidate.action_id) != target:
            continue
        return bool(index < len(request.mask) and request.mask[index])
    return False


def _legal_candidates(request: DecisionRequest) -> list[CandidateAction]:
    candidates: list[CandidateAction] = []
    for index, candidate in enumerate(list(request.candidates or [])):
        if index < len(request.mask) and bool(request.mask[index]):
            candidates.append(candidate)
    return candidates


def _option_for_candidate(candidate: CandidateAction) -> DecisionOption:
    metadata = dict(candidate.metadata or {})
    label = str(metadata.get("ui_label", "") or candidate.action_id)
    payload = dict(candidate.params or {})
    payload["action_id"] = str(candidate.action_id)
    return DecisionOption(
        option_id=f"training_option:{_stable_digest([candidate.action_id, payload])}",
        label=label,
        payload=payload,
    )


def _request_from_candidates(
    decision_type: str,
    prompt: str,
    *,
    player_id: str,
    context: Mapping[str, Any],
    candidates: Sequence[CandidateAction],
    mask: Sequence[bool],
) -> DecisionRequest:
    ordered = sorted(list(candidates or []), key=lambda candidate: str(candidate.action_id))
    mask_by_action_id = {
        str(candidate.action_id): bool(mask[index]) if index < len(mask) else True
        for index, candidate in enumerate(list(candidates or []))
    }
    ordered_mask = [bool(mask_by_action_id.get(str(candidate.action_id), True)) for candidate in ordered]
    request = DecisionRequest.create(
        decision_type,
        prompt,
        player_id=player_id,
        options=[_option_for_candidate(candidate) for candidate in ordered],
        context=dict(context or {}),
        candidates=ordered,
        mask=ordered_mask,
        mask_reasons=[None if legal else "training_scenario_policy" for legal in ordered_mask],
        timeout_seconds=None,
    )
    request.decision_id = f"training_decision:{_stable_digest([decision_type, player_id, context, [c.action_id for c in ordered]])}"
    return request


def _generate_shooting_scenario(
    config: TrainingScenarioConfig,
    *,
    rng: random.Random,
    index: int,
    seed: int,
) -> TrainingScenario:
    scenario_id = f"training:shooting:{int(seed)}:{int(index)}"
    shooter = _random_shooter(rng, index=index)
    targets = [_random_target(rng, target_index=i) for i in range(3)]
    candidates: list[CandidateAction] = []
    for profile in shooter["weapon_profiles"]:
        for target in targets:
            params = {
                "action": "declare_shots",
                "shooter_unit_id": shooter["unit_id"],
                "target_unit_id": target["unit_id"],
                "weapon_profile_id": profile["profile_id"],
                "declarations": [
                    {
                        "weapon_profile_id": profile["profile_id"],
                        "target_unit_id": target["unit_id"],
                        "attacks_allocated": int(profile["attacks"]),
                    }
                ],
            }
            score, feedback = _score_shooting_candidate(profile, target)
            label = f"{profile['name']} into {target['name']}"
            summary = (
                f"EV {feedback['expected_damage']:.2f}, "
                f"target OC {target['objective_control']}, "
                f"{'objective' if target['on_objective'] else 'field'}"
            )
            metadata = {
                "ui_label": label,
                "ui_summary": summary,
                "training_evaluation_score": round(score, 4),
                "training_feedback": feedback,
                "projected_trade_ev": round(feedback["expected_damage"], 4),
                "projected_score_delta_next_window": round(feedback["objective_swing"], 4),
                "target_objective_control": int(target["objective_control"]),
                "target_wounds_remaining": int(target["wounds_remaining"]),
                "target_on_objective": bool(target["on_objective"]),
                "profile_strength": int(profile["strength"]),
                "profile_ap": int(profile["ap"]),
                "profile_damage": int(profile["damage"]),
            }
            candidates.append(
                CandidateAction(
                    action_id=_stable_action_id(TRAINING_STAGE_SHOOTING, params),
                    params=params,
                    metadata=metadata,
                )
            )

    limit = max(2, int(config.candidate_count or 6))
    candidates = sorted(
        candidates,
        key=lambda candidate: (
            -_safe_float(candidate.metadata.get("training_evaluation_score"), default=0.0),
            str(candidate.action_id),
        ),
    )[:limit]
    context = {
        "training_mode": True,
        "training_stage": TRAINING_STAGE_SHOOTING,
        "phase_name": "SHOOTING_PHASE",
        "phase_step": "DECLARE_SHOTS",
        "unit_id": shooter["unit_id"],
        "seed": int(seed),
        "time_budget_ms": int(max(0, config.time_budget_ms)),
        "user_side": str(config.user_side or "player1"),
        "opponent_mode": str(config.opponent_mode or "ai"),
        "shooter": shooter,
        "targets": targets,
    }
    request = _request_from_candidates(
        DECISION_DECLARE_SHOTS,
        f"Shooting drill: choose target and weapon profile for {shooter['name']}.",
        player_id="player-1",
        context=context,
        candidates=candidates,
        mask=[True] * len(candidates),
    )
    return TrainingScenario(
        scenario_id=scenario_id,
        stage=TRAINING_STAGE_SHOOTING,
        component_name=COMPONENT_SHOOTING_RANKER,
        request=request,
        situation={"shooter": shooter, "targets": targets},
        evaluation_profile_id="shooting_expected_damage_objective_v1",
    )


def _random_shooter(rng: random.Random, *, index: int) -> dict[str, Any]:
    chassis = [
        ("Intercessor Squad", "bolt rifle", 10, 3, 4, -1, 1),
        ("Havocs", "lascannon", 4, 4, 12, -3, 5),
        ("Crisis Battlesuits", "plasma rifle", 6, 4, 8, -3, 3),
        ("Fire Prism", "focused lance", 2, 3, 18, -4, 6),
        ("Exocrine", "bio-plasmic cannon", 6, 3, 8, -2, 3),
    ]
    name, weapon_name, attacks, skill, strength, ap, damage = rng.choice(chassis)
    alt_strength = max(3, int(strength) - rng.randint(1, 3))
    alt_attacks = int(attacks) + rng.randint(2, 6)
    return {
        "unit_id": f"training_shooter_{int(index)}",
        "name": name,
        "ballistic_skill": int(skill),
        "weapon_profiles": [
            {
                "profile_id": f"{weapon_name.replace(' ', '_')}_primary",
                "name": weapon_name.title(),
                "attacks": int(attacks),
                "ballistic_skill": int(skill),
                "strength": int(strength),
                "ap": int(ap),
                "damage": int(damage),
            },
            {
                "profile_id": f"{weapon_name.replace(' ', '_')}_volume",
                "name": f"{weapon_name.title()} Saturation",
                "attacks": int(alt_attacks),
                "ballistic_skill": int(skill),
                "strength": int(alt_strength),
                "ap": int(max(ap + 1, -1)),
                "damage": max(1, int(damage) - 1),
            },
        ],
    }


def _random_target(rng: random.Random, *, target_index: int) -> dict[str, Any]:
    templates = [
        ("Objective Infantry", 4, 3, 2, 10, 2, True, 2),
        ("Elite Terminators", 5, 2, 3, 15, 1, True, 3),
        ("Light Skirmishers", 3, 5, 1, 8, 2, False, 1),
        ("Battle Tank", 10, 3, 12, 12, 5, True, 4),
        ("Monster", 9, 3, 10, 14, 4, False, 4),
    ]
    name, toughness, save, wounds_per_model, wounds_remaining, oc, on_objective, threat = rng.choice(templates)
    cover = bool(rng.randint(0, 1))
    return {
        "unit_id": f"training_target_{target_index}_{_stable_digest([name, toughness, wounds_remaining])[:6]}",
        "name": name,
        "toughness": int(toughness),
        "save": int(save),
        "wounds_per_model": int(wounds_per_model),
        "wounds_remaining": int(wounds_remaining),
        "objective_control": int(oc),
        "on_objective": bool(on_objective),
        "in_cover": cover,
        "threat_rating": int(threat),
    }


def _score_shooting_candidate(profile: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[float, dict[str, Any]]:
    attacks = int(profile.get("attacks", 0) or 0)
    ballistic_skill = int(profile.get("ballistic_skill", 4) or 4)
    strength = int(profile.get("strength", 4) or 4)
    ap = int(profile.get("ap", 0) or 0)
    damage = int(profile.get("damage", 1) or 1)
    toughness = int(target.get("toughness", 4) or 4)
    save = int(target.get("save", 4) or 4)
    cover_bonus = 1 if bool(target.get("in_cover", False)) else 0
    effective_save = max(2, min(7, int(save) + abs(min(0, ap)) - cover_bonus))
    expected_unsaved = attacks * _success_probability(ballistic_skill) * _success_probability(
        _wound_threshold(strength, toughness)
    ) * (1.0 - _success_probability(effective_save))
    expected_damage = min(float(target.get("wounds_remaining", 0) or 0), expected_unsaved * damage)
    wounds_remaining = max(1.0, float(target.get("wounds_remaining", 1) or 1))
    kill_probability_proxy = _clamp_float(expected_damage / wounds_remaining, 0.0, 1.0)
    objective_swing = (
        float(target.get("objective_control", 0) or 0) * kill_probability_proxy
        if bool(target.get("on_objective", False))
        else 0.0
    )
    threat_reduction = float(target.get("threat_rating", 0) or 0) * kill_probability_proxy
    overkill_penalty = max(0.0, (expected_unsaved * damage) - wounds_remaining) * 0.15
    score = expected_damage + (1.4 * objective_swing) + (0.55 * threat_reduction) - overkill_penalty
    feedback = {
        "expected_unsaved_wounds": round(expected_unsaved, 4),
        "expected_damage": round(expected_damage, 4),
        "effective_save": int(effective_save),
        "kill_probability_proxy": round(kill_probability_proxy, 4),
        "objective_swing": round(objective_swing, 4),
        "threat_reduction": round(threat_reduction, 4),
        "overkill_penalty": round(overkill_penalty, 4),
    }
    return round(score, 4), feedback


def _generate_deployment_reserves_scenario(
    config: TrainingScenarioConfig,
    *,
    rng: random.Random,
    index: int,
    seed: int,
) -> TrainingScenario:
    scenario_id = f"training:deployment_reserves:{int(seed)}:{int(index)}"
    army = _random_2000_point_army(rng, point_limit=int(config.point_limit or 2000))
    reserve_cap = max(0, int(config.point_limit or 2000) // 4)
    plans = _candidate_reserve_plans(army, reserve_cap=reserve_cap, rng=rng)
    candidates: list[CandidateAction] = []
    mask: list[bool] = []
    for plan in plans:
        params = {
            "action": "declare_reserves",
            "reserve_unit_ids": list(plan["reserve_unit_ids"]),
            "strategic_reserve_unit_ids": list(plan["strategic_reserve_unit_ids"]),
            "deploy_now_unit_ids": [
                str(unit["unit_id"])
                for unit in army
                if str(unit["unit_id"]) not in set(plan["reserve_unit_ids"])
            ],
        }
        score, feedback = _score_reserve_plan(army, plan, reserve_cap=reserve_cap)
        reserve_points = int(feedback["reserve_points"])
        legal = reserve_points <= reserve_cap
        label = str(plan["label"])
        summary = f"{reserve_points} pts reserved, threat {feedback['reserve_threat']:.1f}, presence {feedback['board_presence']:.1f}"
        metadata = {
            "ui_label": label,
            "ui_summary": summary,
            "training_evaluation_score": round(score, 4),
            "training_feedback": feedback,
            "projected_score_delta_next_window": round(feedback["board_presence"], 4),
            "projected_trade_ev": round(feedback["reserve_threat"], 4),
            "reserve_points": reserve_points,
            "reserve_unit_count": len(plan["reserve_unit_ids"]),
            "deep_strike_count": int(feedback["deep_strike_count"]),
            "board_presence": round(feedback["board_presence"], 4),
        }
        candidates.append(
            CandidateAction(
                action_id=_stable_action_id(TRAINING_STAGE_DEPLOYMENT_RESERVES, params),
                params=params,
                metadata=metadata,
            )
        )
        mask.append(bool(legal))

    limit = max(2, int(config.candidate_count or 6))
    candidates_with_mask = sorted(
        zip(candidates, mask),
        key=lambda pair: (
            -_safe_float(pair[0].metadata.get("training_evaluation_score"), default=0.0),
            str(pair[0].action_id),
        ),
    )[:limit]
    candidates = [candidate for candidate, _legal in candidates_with_mask]
    mask = [bool(legal) for _candidate, legal in candidates_with_mask]
    context = {
        "training_mode": True,
        "training_stage": TRAINING_STAGE_DEPLOYMENT_RESERVES,
        "phase_name": "DECLARE_BATTLE_FORMATIONS",
        "phase_step": "DECLARE_RESERVES",
        "seed": int(seed),
        "time_budget_ms": int(max(0, config.time_budget_ms)),
        "user_side": str(config.user_side or "player1"),
        "opponent_mode": str(config.opponent_mode or "ai"),
        "point_limit": int(config.point_limit or 2000),
        "reserve_cap_points": int(reserve_cap),
        "army": army,
    }
    request = _request_from_candidates(
        DECISION_DECLARE_RESERVES,
        f"Deployment drill: choose reserves for a {int(config.point_limit or 2000)} point army.",
        player_id="player-1",
        context=context,
        candidates=candidates,
        mask=mask,
    )
    return TrainingScenario(
        scenario_id=scenario_id,
        stage=TRAINING_STAGE_DEPLOYMENT_RESERVES,
        component_name=COMPONENT_DEPLOYMENT_RANKER,
        request=request,
        situation={"army": army, "reserve_cap_points": reserve_cap},
        evaluation_profile_id="deployment_reserve_pressure_presence_v1",
    )


def _random_2000_point_army(rng: random.Random, *, point_limit: int) -> list[dict[str, Any]]:
    templates = [
        ("Battleline Infantry", 100, "battleline", 4, 7, False),
        ("Fast Skirmishers", 90, "fast", 7, 5, True),
        ("Deep Strike Elites", 160, "elite", 6, 8, True),
        ("Fire Support", 145, "ranged", 3, 9, False),
        ("Melee Hammer", 180, "melee", 5, 10, False),
        ("Transport", 85, "transport", 8, 4, False),
        ("Battle Tank", 210, "vehicle", 4, 11, False),
        ("Objective Utility", 75, "utility", 6, 3, True),
    ]
    units: list[dict[str, Any]] = []
    points = 0
    index = 0
    while points < int(point_limit):
        remaining = int(point_limit) - int(points)
        possible = [
            template
            for template in templates
            if int(template[1]) - 20 <= remaining
        ]
        if not possible:
            break
        name, base_cost, role, speed, threat, deep_strike = rng.choice(possible)
        cost = int(base_cost) + (10 * rng.randint(-2, 3))
        if cost > remaining:
            cost = remaining
        if cost <= 0:
            break
        units.append(
            {
                "unit_id": f"training_unit_{index:02d}",
                "name": f"{name} {index + 1}",
                "points": int(cost),
                "role": role,
                "speed": int(speed),
                "threat_rating": int(threat),
                "deep_strike": bool(deep_strike),
                "objective_control": 2 if role in {"battleline", "utility"} else 1,
            }
        )
        points += int(cost)
        index += 1
    return units


def _candidate_reserve_plans(
    army: Sequence[Mapping[str, Any]],
    *,
    reserve_cap: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    units = [dict(unit) for unit in list(army or [])]
    by_id = {str(unit["unit_id"]): unit for unit in units}

    def _plan(label: str, selected: Iterable[str]) -> dict[str, Any]:
        selected_ids = sorted({str(unit_id) for unit_id in selected if str(unit_id) in by_id})
        deep_ids = [
            unit_id
            for unit_id in selected_ids
            if bool(dict(by_id.get(unit_id, {}) or {}).get("deep_strike", False))
        ]
        strategic_ids = [unit_id for unit_id in selected_ids if unit_id not in set(deep_ids)]
        return {
            "label": label,
            "reserve_unit_ids": selected_ids,
            "strategic_reserve_unit_ids": strategic_ids,
        }

    deep_strike = sorted(
        units,
        key=lambda unit: (
            -int(unit.get("threat_rating", 0) or 0),
            int(unit.get("points", 0) or 0),
            str(unit.get("unit_id", "")),
        ),
    )
    deep_ids = [
        str(unit["unit_id"])
        for unit in deep_strike
        if bool(unit.get("deep_strike", False))
    ][:3]
    fast_ids = [
        str(unit["unit_id"])
        for unit in sorted(units, key=lambda unit: (-int(unit.get("speed", 0) or 0), str(unit.get("unit_id", ""))))
    ][:3]
    threat_ids = [
        str(unit["unit_id"])
        for unit in sorted(
            units,
            key=lambda unit: (-int(unit.get("threat_rating", 0) or 0), str(unit.get("unit_id", ""))),
        )
    ][:2]
    utility_ids = [
        str(unit["unit_id"])
        for unit in sorted(
            units,
            key=lambda unit: (
                0 if str(unit.get("role", "")) in {"utility", "battleline"} else 1,
                int(unit.get("points", 0) or 0),
                str(unit.get("unit_id", "")),
            ),
        )
    ][:2]
    shuffled = [str(unit["unit_id"]) for unit in units]
    rng.shuffle(shuffled)
    random_mix = sorted(shuffled[:3])
    plans = [
        _plan("Deploy everything", []),
        _plan("Reserve deep strike threats", deep_ids),
        _plan("Hold fast flankers", fast_ids),
        _plan("Reserve highest threat units", threat_ids),
        _plan("Keep utility units flexible", utility_ids),
        _plan("Mixed hidden reserve package", random_mix),
    ]
    over_cap = sorted(
        units,
        key=lambda unit: (-int(unit.get("points", 0) or 0), str(unit.get("unit_id", ""))),
    )[:4]
    if sum(int(unit.get("points", 0) or 0) for unit in over_cap) > int(reserve_cap):
        plans.append(_plan("Overloaded reserves stress test", [str(unit["unit_id"]) for unit in over_cap]))
    return plans


def _score_reserve_plan(
    army: Sequence[Mapping[str, Any]],
    plan: Mapping[str, Any],
    *,
    reserve_cap: int,
) -> tuple[float, dict[str, Any]]:
    units = [dict(unit) for unit in list(army or [])]
    reserved = {str(unit_id) for unit_id in list(plan.get("reserve_unit_ids", []) or [])}
    reserve_units = [unit for unit in units if str(unit.get("unit_id", "")) in reserved]
    deployed_units = [unit for unit in units if str(unit.get("unit_id", "")) not in reserved]
    reserve_points = sum(int(unit.get("points", 0) or 0) for unit in reserve_units)
    deployed_points = sum(int(unit.get("points", 0) or 0) for unit in deployed_units)
    reserve_threat = sum(float(unit.get("threat_rating", 0) or 0) for unit in reserve_units)
    fast_reserve = sum(float(unit.get("speed", 0) or 0) for unit in reserve_units) / 10.0
    deep_strike_count = sum(1 for unit in reserve_units if bool(unit.get("deep_strike", False)))
    board_presence = (
        deployed_points / 100.0
        + sum(float(unit.get("objective_control", 0) or 0) for unit in deployed_units)
        + (0.2 * len(deployed_units))
    )
    reserve_pressure = reserve_threat + fast_reserve + (1.5 * deep_strike_count)
    over_cap_penalty = max(0.0, float(reserve_points - int(reserve_cap))) / 25.0
    empty_reserve_bonus = 1.0 if reserve_points == 0 else 0.0
    score = board_presence + reserve_pressure - over_cap_penalty + empty_reserve_bonus
    feedback = {
        "reserve_points": int(reserve_points),
        "reserve_cap_points": int(reserve_cap),
        "deployed_points": int(deployed_points),
        "reserve_threat": round(reserve_pressure, 4),
        "board_presence": round(board_presence, 4),
        "deep_strike_count": int(deep_strike_count),
        "over_cap_penalty": round(over_cap_penalty, 4),
    }
    return round(score, 4), feedback


__all__ = [
    "SUPPORTED_TRAINING_STAGES",
    "TRAINING_MODE_SCHEMA_VERSION",
    "TRAINING_STAGE_DEPLOYMENT_RESERVES",
    "TRAINING_STAGE_MIXED",
    "TRAINING_STAGE_SHOOTING",
    "TrainingEvaluation",
    "TrainingObservation",
    "TrainingObservationStore",
    "TrainingPreferenceModel",
    "TrainingScenario",
    "TrainingScenarioConfig",
    "TrainingScenarioGenerator",
    "TrainingSession",
    "best_training_action_id",
    "evaluate_training_selection",
    "load_training_observations",
]
