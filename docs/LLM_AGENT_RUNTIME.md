# LLM Agent Runtime

This document describes the implemented LLM-backed domain-agent runtime for headless, replay-derived, and human-vs-AI training workflows.

## Status

LLM agents are runtime adapters behind the existing hierarchical AI components. They do not replace the engine, legality checks, decision masks, or deterministic replay.

Implemented surfaces:
- `src/warhammer40k_ai/ml/llm_agents.py`
- `scripts/run_headless_self_play.py --llm-agent-config <path>`
- `python -m warhammer40k_ai.network.cli client-headless --llm-agent-config <path> ...`
- `scripts/build_llm_agent_dataset.py`

## Runtime Flow

1. The engine emits and decorates a `DecisionRequest`.
2. `AIControllerRouter` maps the request to a component such as `movement_ranker`, `shooting_ranker`, or `reaction_ranker`.
3. `LLMDecisionAgent` serializes the request into JSON containing:
   - decision id/type
   - player id
   - serializable context
   - legal candidates only (`mask=True`)
   - response contract
4. The configured LLM transport returns JSON:

```json
{
  "action_id": "candidate-action-id",
  "rationale": "brief reason"
}
```

5. The returned `action_id` is accepted only if it still matches a legal candidate.
6. Invalid/missing/failed LLM output falls back to the deterministic domain ranker for that component.
7. The existing controller submits the normal `RESOLVE_DECISION` command; the engine validates and records `DecisionRecord` telemetry.

When `--report-output` is enabled for headless self-play, per-game report entries include `llm_agent_traces` and the top-level report includes `llm_agent_trace_counts`. These traces are audit/debug data for prompts and provider responses; supervised learning should still use authoritative `DecisionRecord` examples because those records reflect the engine-validated outcome.

## Config

LLM agent runtime is local-first. The built-in transport speaks the common Chat Completions HTTP
request/response shape so it can target local servers such as llama.cpp, vLLM, LM Studio, or Ollama
Chat Completions endpoints. It does not require the OpenAI SDK and does not contact any external
service unless `endpoint_url` is explicitly set to one.

Local endpoint example:

```json
{
  "provider": "chat_completions",
  "endpoint_url": "http://127.0.0.1:8080/v1/chat/completions",
  "model": "configured-local-model-id",
  "timeout_seconds": 30,
  "temperature": 0,
  "max_prompt_chars": 20000,
  "max_candidates": 32,
  "components": [
    "movement_ranker",
    "shooting_ranker",
    "charge_ranker",
    "fight_ranker",
    "tool_ranker",
    "reaction_ranker",
    "dice_policy",
    "allocation_ranker"
  ]
}
```

No model id is hardcoded in the repository. The config must provide `model` or set `WARHAMMER40K_AI_LLM_MODEL`.
No API key is required by default. When an endpoint requires bearer auth, set either `api_key` in the
external config file or `api_key_env` to the name of an environment variable. The transport sends an
`Authorization` header only when a key resolves from those fields.

## Headless Self-Play

```bash
python scripts/run_headless_self_play.py \
  --games 10 \
  --player1-army army_lists/chaos_test.txt \
  --player2-army army_lists/aeldari_test.txt \
  --llm-agent-config data/llm_agent_config.json \
  --output data/llm_self_play_decision_records.json
```

## Human-vs-AI / Network Headless Client

```bash
python -m warhammer40k_ai.network.cli client-headless \
  --server wss://localhost:8765 \
  --role player2 \
  --llm-agent-config data/llm_agent_config.json \
  --army-file army_lists/aeldari_test.txt \
  --ready
```

## Replay/Human Data to LLM Training Examples

Any DecisionRecord source can become supervised JSONL examples:

```bash
python scripts/build_llm_agent_dataset.py \
  --input data/headless_self_play_decision_records.json \
  --output data/llm_agent_examples.jsonl
```

This works for headless self-play, replay captures, and human-vs-AI games because all of them resolve the same Decision API and write the same candidate/mask/chosen-action telemetry.

LLM traces can explain why a provider chose or failed to choose an action, while `DecisionRecord` examples remain the canonical training source.

Human training-mode observations from `scripts/run_training_mode.py` are separate one-step imitation records.
They already include a `supervised_example` block with the serialized decision payload and chosen action id for
LLM or ranker training experiments; full-game policy training should still prefer authoritative `DecisionRecord`
exports when available.

## Safety and Determinism

- LLM agents never see masked candidates.
- LLM agents never mutate state or submit commands directly.
- The engine still validates every resolved action.
- Invalid LLM output is recorded in the agent trace and falls back to deterministic rankers.
- Provider configuration lives outside the repository; API keys are read from environment variables by default.
