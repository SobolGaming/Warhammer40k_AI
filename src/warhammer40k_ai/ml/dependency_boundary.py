from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import re
from typing import Iterable


ML_EXTRA_NAME = "ml"
ML_OPTIONAL_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("torch", "torch"),
    ("torchrl", "torchrl"),
    ("torch-geometric", "torch_geometric"),
    ("ray[rllib]", "ray"),
    ("wandb", "wandb"),
)
FORBIDDEN_CORE_DEPENDENCIES: tuple[str, ...] = (
    "torch",
    "torchrl",
    "torch-geometric",
    "ray",
    "wandb",
)
_NAME_SPLIT_RE = re.compile(r"[<>=!~\s]+")


class MLDependencyBoundaryError(RuntimeError):
    """Raised when optional ML dependencies are required but unavailable."""


@dataclass(frozen=True)
class MLDependencyStatus:
    missing_packages: tuple[str, ...]
    available_packages: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_packages

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "missing_packages": list(self.missing_packages),
            "available_packages": list(self.available_packages),
        }


def normalize_dependency_name(requirement: str) -> str:
    token = str(requirement or "").strip()
    if not token or token.startswith("#"):
        return ""
    token = token.split(";", 1)[0].strip()
    if not token:
        return ""
    base = _NAME_SPLIT_RE.split(token, maxsplit=1)[0]
    if "[" in base:
        base = base.split("[", 1)[0]
    return base.replace("_", "-").strip().lower()


def find_forbidden_core_dependencies(
    requirements: Iterable[str],
    *,
    forbidden: Iterable[str] = FORBIDDEN_CORE_DEPENDENCIES,
) -> list[str]:
    forbidden_names = {normalize_dependency_name(name) for name in forbidden if normalize_dependency_name(name)}
    found: set[str] = set()
    for item in list(requirements or []):
        normalized = normalize_dependency_name(str(item))
        if normalized and normalized in forbidden_names:
            found.add(normalized)
    return sorted(found)


def detect_ml_dependency_status() -> MLDependencyStatus:
    missing: list[str] = []
    available: list[str] = []
    for package_name, import_name in ML_OPTIONAL_DEPENDENCIES:
        if importlib.util.find_spec(import_name) is None:
            missing.append(package_name)
        else:
            available.append(package_name)
    return MLDependencyStatus(
        missing_packages=tuple(sorted(missing)),
        available_packages=tuple(sorted(available)),
    )


def require_ml_dependencies() -> None:
    status = detect_ml_dependency_status()
    if status.ready:
        return
    missing = ", ".join(status.missing_packages)
    raise MLDependencyBoundaryError(
        "Optional ML dependencies are not installed "
        f"(missing: {missing}). Install with: pip install \"warhammer40k_ai[{ML_EXTRA_NAME}]\""
    )
