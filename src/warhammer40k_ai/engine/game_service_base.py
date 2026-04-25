from __future__ import annotations

from types import MethodType
import inspect


class GameServiceBase:
    """Delegate service state access to the owning Game instance.

    Legacy Game methods moved behind services often read and write attributes as
    if they are still methods on Game. This base preserves that behavior while
    letting services remain explicit composition objects.
    """

    bind_methods_to_game = False

    def __init__(self, game):
        object.__setattr__(self, "_game", game)

    def __getattribute__(self, name: str):
        if name in {"_game", "bind_methods_to_game", "__class__", "__dict__", "__setattr__", "__getattr__", "__deepcopy__"}:
            return object.__getattribute__(self, name)
        game = object.__getattribute__(self, "__dict__").get("_game")
        if game is not None:
            game_attrs = getattr(game, "__dict__", None)
            if isinstance(game_attrs, dict) and name in game_attrs:
                return game_attrs[name]
            if bool(object.__getattribute__(self, "bind_methods_to_game")):
                class_attr = inspect.getattr_static(type(self), name, None)
                if inspect.isfunction(class_attr):
                    return MethodType(class_attr, game)
        return object.__getattribute__(self, name)

    def __getattr__(self, name: str):
        return getattr(self._game, name)

    def __setattr__(self, name: str, value) -> None:
        if name == "_game":
            object.__setattr__(self, name, value)
            return
        setattr(self._game, name, value)

    def __delattr__(self, name: str) -> None:
        if name == "_game":
            object.__delattr__(self, name)
            return
        delattr(self._game, name)

    def __deepcopy__(self, memo):
        return self
