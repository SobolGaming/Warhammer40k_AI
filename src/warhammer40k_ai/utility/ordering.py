from __future__ import annotations

from typing import Callable, Iterable, List, TypeVar

from .entity_ids import get_entity_id

T = TypeVar("T")


def sorted_by_key(items: Iterable[T], key: Callable[[T], str]) -> List[T]:
    return sorted(list(items), key=lambda item: str(key(item)))


def sorted_by_id(items: Iterable[T]) -> List[T]:
    return sorted_by_key(items, get_entity_id)
