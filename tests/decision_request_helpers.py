from __future__ import annotations


def install_decision_request_support(game: object) -> object:
    """Add minimal DecisionRequest plumbing to lightweight test game doubles."""
    from warhammer40k_ai.engine.command_dispatcher import dispatch_command
    from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
    from warhammer40k_ai.engine.decisions import DecisionQueue

    if getattr(game, "decision_queue", None) is None:
        game.decision_queue = DecisionQueue()

    def request_decision(request) -> None:
        game.decision_queue.add(request)

    def resolve_decision(result):
        request = game.decision_queue.get(result.decision_id)
        if request is None:
            return None
        apply_result = dispatch_decision(game, request, result)
        setattr(request, "_resolved_decision_result", result)
        setattr(request, "_resolved_decision_apply_result", apply_result)
        setattr(request, "_resolved_decision_value", getattr(apply_result, "value", None))
        if bool(getattr(apply_result, "ok", False)):
            game.decision_queue.pop(result.decision_id)
        return apply_result

    game.request_decision = request_decision
    game.resolve_decision = resolve_decision
    game.apply_command = lambda command: dispatch_command(game, command)
    return game
