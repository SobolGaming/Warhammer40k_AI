from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping, Protocol, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request

from ..engine.ai_controller_router import AI_POLICY_COMPONENTS, AIControllerRouter
from ..engine.ai_domain_agents import (
    action_id_is_legal,
    default_ai_domain_rankers,
    first_legal_action_id,
    legal_candidates,
)
from ..engine.decisions import CandidateAction, DecisionRequest


class LLMConfigurationError(ValueError):
    """Raised when an LLM agent configuration cannot be used."""


class LLMTransportError(RuntimeError):
    """Raised when an LLM request fails before a usable response is available."""


class LLMResponseError(ValueError):
    """Raised when an LLM response is malformed."""


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    endpoint_url: str
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""
    timeout_seconds: float = 30.0
    temperature: float = 0.0
    max_prompt_chars: int = 20000
    max_candidates: int = 32
    component_names: tuple[str, ...] = field(default_factory=lambda: AI_POLICY_COMPONENTS)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LLMProviderConfig":
        data = dict(payload or {})
        provider = str(data.get("provider", "openai_compatible_chat") or "openai_compatible_chat").strip()
        endpoint_url = str(data.get("endpoint_url", "") or "").strip()
        if not endpoint_url:
            raise LLMConfigurationError("LLM config requires endpoint_url.")
        model = str(data.get("model", os.environ.get("WARHAMMER40K_AI_LLM_MODEL", "")) or "").strip()
        if not model:
            raise LLMConfigurationError("LLM config requires model or WARHAMMER40K_AI_LLM_MODEL.")
        raw_components = data.get("components", list(AI_POLICY_COMPONENTS))
        if not isinstance(raw_components, list):
            raise LLMConfigurationError("LLM config components must be a JSON array.")
        component_names = tuple(
            sorted(
                {
                    str(component or "").strip()
                    for component in raw_components
                    if str(component or "").strip() in AI_POLICY_COMPONENTS
                }
            )
        )
        if not component_names:
            raise LLMConfigurationError("LLM config components did not include any known AI policy components.")
        return cls(
            provider=provider,
            endpoint_url=endpoint_url,
            model=model,
            api_key_env=str(data.get("api_key_env", "OPENAI_API_KEY") or "OPENAI_API_KEY").strip(),
            api_key=str(data.get("api_key", "") or ""),
            timeout_seconds=max(0.1, float(data.get("timeout_seconds", 30.0) or 30.0)),
            temperature=float(data.get("temperature", 0.0) or 0.0),
            max_prompt_chars=max(1000, int(data.get("max_prompt_chars", 20000) or 20000)),
            max_candidates=max(1, int(data.get("max_candidates", 32) or 32)),
            component_names=component_names,
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "LLMProviderConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise LLMConfigurationError("LLM config file must contain a JSON object.")
        return cls.from_dict(payload)

    def resolved_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        env_name = str(self.api_key_env or "").strip()
        if not env_name:
            return ""
        return str(os.environ.get(env_name, "") or "").strip()


@dataclass(frozen=True)
class LLMActionChoice:
    action_id: str
    rationale: str = ""


@dataclass(frozen=True)
class LLMDecisionTrace:
    component_name: str
    decision_id: str
    decision_type: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    selected_action_id: str
    legal: bool
    elapsed_ms: int
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_name": self.component_name,
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "request_payload": dict(self.request_payload),
            "response_payload": dict(self.response_payload),
            "selected_action_id": self.selected_action_id,
            "legal": bool(self.legal),
            "elapsed_ms": int(self.elapsed_ms),
            "error": str(self.error or ""),
        }


class LLMTransport(Protocol):
    def choose_action(self, *, component_name: str, payload: Mapping[str, Any]) -> LLMActionChoice:
        """Return an action choice from an LLM provider."""


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


def candidate_payload(candidate: CandidateAction) -> dict[str, Any]:
    return {
        "action_id": str(getattr(candidate, "action_id", "") or ""),
        "params": _json_safe(dict(getattr(candidate, "params", {}) or {})),
        "metadata": _json_safe(dict(getattr(candidate, "metadata", {}) or {})),
    }


def request_payload_for_llm(
    request: DecisionRequest,
    *,
    component_name: str,
    max_candidates: int = 32,
) -> dict[str, Any]:
    legal = legal_candidates(request)[: max(1, int(max_candidates or 1))]
    return {
        "component_name": str(component_name),
        "decision_id": str(getattr(request, "decision_id", "") or ""),
        "decision_type": str(getattr(request, "decision_type", "") or ""),
        "player_id": str(getattr(request, "player_id", "") or ""),
        "prompt": str(getattr(request, "prompt", "") or ""),
        "context": _json_safe(dict(getattr(request, "context", {}) or {})),
        "legal_candidates": [candidate_payload(candidate) for candidate in legal],
        "candidate_count": int(len(legal)),
        "response_contract": {
            "format": "json",
            "required": {"action_id": "one of legal_candidates[].action_id"},
            "optional": {"rationale": "brief reason using only the provided payload"},
        },
    }


def _trim_payload(payload: dict[str, Any], *, max_chars: int) -> dict[str, Any]:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(text) <= int(max_chars):
        return payload
    trimmed = dict(payload)
    trimmed["context"] = {
        "trimmed": True,
        "reason": "context exceeded max_prompt_chars",
        "decision_type": payload.get("decision_type"),
    }
    return trimmed


def parse_llm_action_choice(raw_payload: Mapping[str, Any]) -> LLMActionChoice:
    payload = dict(raw_payload or {})
    action_id = str(payload.get("action_id", "") or "").strip()
    if not action_id:
        raise LLMResponseError("LLM response did not include action_id.")
    rationale = str(payload.get("rationale", "") or "")
    return LLMActionChoice(action_id=action_id, rationale=rationale)


class OpenAICompatibleChatTransport:
    """Minimal OpenAI-compatible chat transport using only the standard library."""

    def __init__(self, config: LLMProviderConfig) -> None:
        if str(config.provider) != "openai_compatible_chat":
            raise LLMConfigurationError(
                f"Unsupported LLM provider {config.provider!r}; expected 'openai_compatible_chat'."
            )
        self._config = config

    def choose_action(self, *, component_name: str, payload: Mapping[str, Any]) -> LLMActionChoice:
        api_key = self._config.resolved_api_key()
        if not api_key:
            raise LLMConfigurationError(
                f"LLM API key is required via api_key or {self._config.api_key_env}."
            )
        request_payload = {
            "model": self._config.model,
            "temperature": float(self._config.temperature),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Warhammer 40,000 AI domain agent. "
                        "Choose exactly one legal action_id from the provided legal_candidates. "
                        "Return only JSON with keys action_id and rationale."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"component_name": component_name, "decision": payload},
                        sort_keys=True,
                        ensure_ascii=True,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(request_payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        http_request = urllib_request.Request(
            self._config.endpoint_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib_request.urlopen(http_request, timeout=float(self._config.timeout_seconds)) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            raise LLMTransportError(f"LLM HTTP request failed with status {exc.code}.") from exc
        except urllib_error.URLError as exc:
            raise LLMTransportError(f"LLM HTTP request failed: {exc.reason}.") from exc
        except TimeoutError as exc:
            raise LLMTransportError("LLM HTTP request timed out.") from exc
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"LLM HTTP response was not valid JSON: {exc.msg}.") from exc

        try:
            content = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("LLM HTTP response did not include choices[0].message.content.") from exc
        try:
            choice_payload = json.loads(str(content or ""))
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"LLM message content was not valid JSON: {exc.msg}.") from exc
        if not isinstance(choice_payload, dict):
            raise LLMResponseError("LLM message content must decode to a JSON object.")
        return parse_llm_action_choice(choice_payload)


class StaticLLMTransport:
    """Test/helper transport that returns preloaded action ids without network I/O."""

    def __init__(self, action_ids: Sequence[str] | Mapping[str, str]) -> None:
        if isinstance(action_ids, Mapping):
            self._by_component = {str(key): str(value) for key, value in dict(action_ids).items()}
            self._action_ids: list[str] = []
        else:
            self._by_component = {}
            self._action_ids = [str(value) for value in list(action_ids or [])]
        self.calls: list[dict[str, Any]] = []

    def choose_action(self, *, component_name: str, payload: Mapping[str, Any]) -> LLMActionChoice:
        self.calls.append({"component_name": component_name, "payload": dict(payload or {})})
        if component_name in self._by_component:
            return LLMActionChoice(action_id=self._by_component[component_name], rationale="static component choice")
        if self._action_ids:
            return LLMActionChoice(action_id=self._action_ids.pop(0), rationale="static queued choice")
        legal = list(dict(payload or {}).get("legal_candidates", []) or [])
        action_id = str(dict(legal[0] if legal else {}).get("action_id", "") or "")
        return LLMActionChoice(action_id=action_id, rationale="static first legal")


class LLMDecisionAgent:
    """Candidate ranker backed by an LLM transport with deterministic fallback."""

    def __init__(
        self,
        *,
        component_name: str,
        transport: LLMTransport,
        fallback_ranker: object | None = None,
        max_candidates: int = 32,
        max_prompt_chars: int = 20000,
    ) -> None:
        self.component_name = str(component_name or "")
        self._transport = transport
        self._fallback_ranker = fallback_ranker
        self._max_candidates = max(1, int(max_candidates or 1))
        self._max_prompt_chars = max(1000, int(max_prompt_chars or 1000))
        self._traces: list[LLMDecisionTrace] = []

    def choose_action_id(self, request: DecisionRequest) -> str:
        payload = request_payload_for_llm(
            request,
            component_name=self.component_name,
            max_candidates=self._max_candidates,
        )
        payload = _trim_payload(payload, max_chars=self._max_prompt_chars)
        started_at = time.perf_counter()
        response_payload: dict[str, Any] = {}
        selected_action_id = ""
        error = ""
        try:
            choice = self._transport.choose_action(component_name=self.component_name, payload=payload)
            selected_action_id = str(choice.action_id or "")
            response_payload = {
                "action_id": selected_action_id,
                "rationale": str(choice.rationale or ""),
            }
        except (LLMConfigurationError, LLMTransportError, LLMResponseError) as exc:
            error = str(exc)
        elapsed_ms = int(round((time.perf_counter() - started_at) * 1000.0))
        legal = action_id_is_legal(request, selected_action_id)
        self._traces.append(
            LLMDecisionTrace(
                component_name=self.component_name,
                decision_id=str(getattr(request, "decision_id", "") or ""),
                decision_type=str(getattr(request, "decision_type", "") or ""),
                request_payload=payload,
                response_payload=response_payload,
                selected_action_id=selected_action_id,
                legal=legal,
                elapsed_ms=elapsed_ms,
                error=error,
            )
        )
        if legal:
            return selected_action_id
        return self._fallback_action_id(request)

    def _fallback_action_id(self, request: DecisionRequest) -> str:
        choose = getattr(self._fallback_ranker, "choose_action_id", None)
        if callable(choose):
            action_id = str(choose(request) or "")
            if action_id_is_legal(request, action_id):
                return action_id
        return first_legal_action_id(request)

    def traces(self) -> tuple[LLMDecisionTrace, ...]:
        return tuple(self._traces)

    def pop_traces(self) -> tuple[LLMDecisionTrace, ...]:
        traces = tuple(self._traces)
        self._traces.clear()
        return traces


def build_llm_router(
    config: LLMProviderConfig,
    *,
    transport: LLMTransport | None = None,
) -> AIControllerRouter:
    fallback_rankers = default_ai_domain_rankers()
    resolved_transport = transport if transport is not None else OpenAICompatibleChatTransport(config)
    components: dict[str, object] = {}
    fallbacks: dict[str, tuple[object, ...]] = {}
    for component_name in AI_POLICY_COMPONENTS:
        fallback = fallback_rankers.get(component_name)
        if component_name in set(config.component_names):
            components[component_name] = LLMDecisionAgent(
                component_name=component_name,
                transport=resolved_transport,
                fallback_ranker=fallback,
                max_candidates=int(config.max_candidates),
                max_prompt_chars=int(config.max_prompt_chars),
            )
            if fallback is not None:
                fallbacks[component_name] = (fallback,)
        elif fallback is not None:
            components[component_name] = fallback
    return AIControllerRouter(components=components, fallbacks=fallbacks)


def build_llm_router_from_config_file(path: str | Path) -> AIControllerRouter:
    return build_llm_router(LLMProviderConfig.from_json_file(path))


def llm_training_example_from_decision_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Build a JSON-safe supervised example from a DecisionRecord-like payload."""
    data = dict(record or {})
    return {
        "decision_id": str(data.get("decision_id", "") or ""),
        "decision_type": str(data.get("decision_type", "") or ""),
        "actor_player_id": str(data.get("actor_player_id", "") or ""),
        "context": _json_safe(dict(data.get("context", {}) or {})),
        "candidates": _json_safe(list(data.get("candidates", []) or [])),
        "mask": [bool(value) for value in list(data.get("mask", []) or [])],
        "chosen_action_id": str(data.get("chosen_action_id", "") or ""),
        "rules_bundle_id": str(data.get("rules_bundle_id", "") or ""),
        "descriptor_bundle_id": str(data.get("descriptor_bundle_id", "") or ""),
        "reward": _json_safe(dict(data.get("reward", {}) or {})),
        "outcome": _json_safe(dict(data.get("outcome", {}) or {})),
    }


def llm_training_examples_from_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for record in list(records or []):
        data = dict(record or {})
        chosen_action_id = str(data.get("chosen_action_id", "") or "")
        if not chosen_action_id:
            continue
        examples.append(llm_training_example_from_decision_record(data))
    return examples

