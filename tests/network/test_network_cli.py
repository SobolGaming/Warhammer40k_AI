from warhammer40k_ai.network.cli import _build_parser


def test_network_cli_parses_client_headless_mode() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "client-headless",
            "--server",
            "wss://localhost:8765",
            "--role",
            "player1",
        ]
    )
    assert args.mode == "client-headless"
    assert args.server == "wss://localhost:8765"
    assert args.role == "player1"
    assert float(args.max_reserves_arrival_seconds) == 10.0
