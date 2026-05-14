import pytest

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
    assert float(args.response_timeout) == 10.0
    assert args.llm_adapter_config == ""


def test_network_cli_parses_headless_llm_adapter_config() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "client-headless",
            "--server",
            "wss://localhost:8765",
            "--role",
            "player2",
            "--llm-policy-adapter-config",
            "data/llm_adapter_config.json",
        ]
    )
    assert args.llm_adapter_config == "data/llm_adapter_config.json"


def test_network_cli_rejects_removed_headless_llm_config_flag() -> None:
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "client-headless",
                "--server",
                "wss://localhost:8765",
                "--role",
                "player2",
                "--llm-" + "agent-config",
                "data/llm_adapter_config.json",
            ]
        )
