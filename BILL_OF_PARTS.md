# PyTTAI - Bill of Parts

## Overview

PyTTAI is a Python terminal chat client where AI is explicit - slash commands and colon operators form a small language, nothing reaches a model unless piped; runs interactively or non-interactively.

## Entry Points

- `python3 main.py` — interactive shell
- `python3 main.py -c "CMD" | - | FILE` — non-interactive (string, stdin, or .ptt script); `-a` skips connection test; `-v` verbose
- `python3 main.py config doctor` — config lifecycle tools (validate config vs registry + keys)

## Module Tree

Under `Pychat/`:

- `main.py` — entry: argparse, interactive loop, `-c` dispatch, `config` verb
- `lmchat/core/chat.py` — ChatController: orchestration, command routing, state
- `lmchat/core/providers.py` — LLMProvider base + OpenAICompatibleProvider + per-vendor classes + ProviderManager registry
- `lmchat/core/config_doctor.py` — diagnose() + render(): structural config validation
- `lmchat/core/parser.py` — slash-colon statement parser (operators)
- `lmchat/core/controllers.py` — command registration/dispatch helpers
- `lmchat/core/models.py` — Config (load/save), CommandResult, OutputFormat
- `lmchat/features/clipboard.py` — `/paste`
- `lmchat/features/file_input.py` — `/file`
- `lmchat/features/file_ops.py` — `/ls`, `/find`, `/persist`

## Providers

| Type | Class | Requires Key | Key Env Vars | Default Model | Notes |
|---|---|---|---|---|---|
| `lmstudio` | LMStudioProvider | No | — | `local-model` | Default base URL: `http://localhost:1234/v1` |
| `ollama` | OllamaProvider | No | — | `local-model` | Native `/api/chat` override carries `num_ctx` |
| `openai_compatible` | OpenAICompatibleProvider | No | — | — | Generic OpenAI-API base |
| `openai` | OpenAIProvider | Yes | `OPENAI_API_KEY` | `gpt-5` | Uses `max_completion_tokens`; gpt-5/o-series reject temperature |
| `xai` | XAIProvider | Yes | `XAI_API_KEY` | `grok-4` | — |
| `claude` (alias: `anthropic`) | ClaudeProvider | Yes | `ANTHROPIC_API_KEY` (or config) | `claude-opus-4-8` | Native anthropic SDK |
| `gemini` (alias: `google`) | GeminiProvider | Yes | `GEMINI_API_KEY` / `GOOGLE_API_KEY` (or config) | `gemini-2.5-flash` | Native google-genai SDK |

## Commands

**Built-in:** `/help`, `/clear`, `/exit`, `/quit`, `/config`, `/tokenuse`, `/provider`, `/model`

**Feature:** `/paste`, `/file`, `/ls`, `/find`, `/persist`

## Operators

Colon operators (from parser):

- `:ai` / `:ai@provider` — send to a model, stateless/chainable
- `:json`
- `:s`, `:ss`, `:r`, `:rr`, `:i`, `:j`, `:first`, `:end` — statement/selection operators

## Dependencies

From `Pychat/requirements.txt`:

- `anthropic>=0.40.0`
- `openai>=1.60.0`
- `google-genai>=1.0.0`
- `pyperclip>=1.8.2` (openai pulls httpx)

Requires Python 3.10+.

## Config

Stored at `~/.pyttai/config.json`.

**Top-level keys:** `base_url`, `model`, `max_tokens`, `temperature`, `system_prompt`, `stream`, `timeout`, `max_conversation_length`

**Optional `providers` dict:** `name -> {type, model, base_url?, api_key?, num_ctx?, reasoning?}`

Keys resolve config `api_key` first, then env var. Prefer env/secret manager over cleartext `api_key` (see: config doctor).
