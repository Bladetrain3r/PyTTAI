# PyTTAI Technical Brief

**Reflects**: v0.2.3 (post provider-modernization and CommandResult
standardization)
**Companions**: `Roadmap.md` (direction), root `CHANGELIST` (per-version
worklog), `Pychat/lmchat/docs/slash-colon-spec.md` (operator grammar)

## What PyTTAI Is

A Python terminal chat client where AI is explicit: slash commands and
operators form a small command language, and nothing reaches a language
model unless deliberately piped there. It runs interactively or
non-interactively (`-c` string / stdin / `.ptt` scripts) and is designed
to compose with a real shell rather than replace one.

## Component Map

```
Pychat/
├── main.py                     Entry point: argparse, interactive loop,
│                               non-interactive (-c) dispatch
└── lmchat/
    ├── core/
    │   ├── chat.py             ChatController - orchestrates everything:
    │   │                       provider setup, builtin commands, streaming,
    │   │                       result rendering, pipeline execution
    │   ├── parser.py           Slash-colon statement tokenizer/parser +
    │   │                       script preprocessing (comments, continuation)
    │   ├── providers.py        LLMProvider ABC + implementations +
    │   │                       ProviderManager registry
    │   ├── controllers.py      Clipboard/File/Session/Command controllers
    │   └── models.py           CommandResult, Conversation, Message, Config
    ├── features/               Plugin modules; register_commands(chat)
    │   ├── clipboard.py        /paste (text + image clipboard)
    │   └── file_input.py       /file (text + vision)
    ├── config/                 config_example.json
    └── docs/                   Spec, reference docs, archived roadmaps
```

Startup flow: `main.py` builds a `ChatController` (loads
`~/.pyttai/config.json`, registers providers and builtin commands),
registers feature modules, tests the active provider (skippable with
`-a`), then enters either the interactive loop or command mode.

## Provider Layer

`LLMProvider` interface: `test_connection() -> bool`,
`stream_completion(messages, **kwargs) -> Generator[str]`,
`get_models() -> Optional[List[Dict]]`.

Implementations sit on the official SDKs:

| Provider type(s) | Class | SDK | Notes |
|---|---|---|---|
| `lmstudio`, `ollama`, `xai`, `openai_compatible` | `OpenAICompatibleProvider` (+subclasses) | `openai` | One base class, parameterized by base_url; `/v1` auto-appended for old configs |
| `openai` | `OpenAIProvider` | `openai` | Uses `max_completion_tokens`; skips `temperature` for gpt-5/o-series |
| `claude`, `anthropic` | `ClaudeProvider` | `anthropic` | Live `/v1/models`; skips `temperature` on newest Opus models; converts OpenAI-style image blocks to Anthropic format |
| `gemini`, `google` | `GeminiProvider` | `google-genai` | system_instruction extraction, role mapping, image Part conversion |

Conventions:
- **Keys**: provider config `api_key` first, then env vars
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`,
  `GEMINI_API_KEY`/`GOOGLE_API_KEY`).
- **Message format**: OpenAI chat-completions shape is the internal
  lingua franca; non-OpenAI providers convert at their boundary.
- **Missing SDKs degrade per-provider** with an actionable error rather
  than crashing startup.
- SDK typed exceptions propagate out of `stream_completion`; the
  streaming layer catches and renders them.

## Core Conventions (the contracts that matter)

**CommandResult everywhere.** Every command handler returns a
`CommandResult` (`success`, `format`, `content` | `error`/`code`/
`suggestion`), `None` (pure side effect), or `False` - which is the
session-exit signal ONLY. Never return a raw `send_message`/`send_image`
bool from a handler: `False` would quit the app.

**stdout/stderr split.** One renderer (`ChatController.render_result`)
prints success content to stdout; errors, suggestions, and progress
chatter go to stderr. This keeps `python3 main.py -c script.ptt > out`
clean. Startup banners are already stderr.

**Streaming + history hygiene** (`ChatController._stream_and_record`):
- Streams chunks to stdout, records the assistant turn on success.
- Empty response -> explicit warning, user turn popped.
- Exception with no output -> error printed with provider name, user
  turn popped (prevents a rejected payload from re-failing every
  subsequent turn). Partial output is kept.

**Image pipeline**:
- Inputs >5MB base64 are downscaled via Pillow (1568px long edge,
  JPEG q85); >10MB without Pillow is refused with guidance.
- Stored history keeps full payloads, but `get_messages_for_api`
  substitutes `[image omitted from history]` for all but the most
  recent image - the latest stays live for follow-ups.

**Line classification** (per the slash-colon spec): `/`-prefixed lines
are statements (parsed by `parser.py`), everything else is chat sent
verbatim. Operators are never parsed inside chat messages. Unknown or
reserved (`::`, `:json`) operator tokens are parse errors raised before
any execution.

**Operators (v0.2.4)**: `:ai [prompt]` and `:ai@provider [prompt]` -
stateless (no conversation history in or out), chainable, output streams
live. `@provider` resolves lazily: configured-but-unconnected providers
are constructed on first use with no connection test; unavailability is
a strict segment failure. The command segment must return a
CommandResult (bare form) to feed a chain. Pipe content: TEXT verbatim,
DATA as pretty JSON (plain renderings per spec when commands grow them).

**Invocation forms**: `/file path` = cat (images return MIME metadata,
never base64 to the terminal); `/file path prompt` = chat-coupled turn
with full history; `/file path :ai prompt` = stateless pipeline.

**Token tracking**: providers expose `last_usage` after each stream
(Anthropic final-message usage, OpenAI-compat `stream_options
include_usage` - disable with `track_usage: false` for servers that
reject it, Gemini `usage_metadata`). `ChatController._record_usage`
appends to session memory and `~/.pyttai/tokens.csv`
(timestamp,provider,model,tokens_in,tokens_out); `/tokenuse` reports
session totals. `token_log: false` disables the file.

**Reasoning config**: optional `"reasoning": "off"|"low"|"medium"|"high"`
per provider (top-level applies to the default provider). Claude maps
any on-value to adaptive thinking; OpenAI/xAI send `reasoning_effort`;
Gemini sets `thinking_config` (0 budget for off, dynamic otherwise).
Unset = parameter omitted entirely.

## Configuration

`~/.pyttai/config.json` (or `config_path` argument). Top-level keys
(`base_url`, `model`, `max_tokens`, `temperature`, `system_prompt`,
`max_conversation_length`) define the implicit default LM Studio
provider; the `providers` map adds named providers with `type` selecting
the class from `ProviderManager.PROVIDERS`. `/config key=value` supports
nested dotted keys (`providers.claude.model=...`) and persists
immediately. `active_provider` selects the startup provider.

## Execution Modes

| Mode | Invocation | Notes |
|---|---|---|
| Interactive | `python3 main.py` | readline history where available |
| Command | `-c "/file x.md summarise"` | single command |
| stdin | `-c -` | newline-separated commands |
| Script | `-c script.ptt` | one command/message per line |

Flags: `-v` verbose, `-a` skip connection tests.

## Testing Approach

No formal suite yet (roadmap debt). Validation pattern used during
development: spin a fake OpenAI-compatible SSE server on localhost via
`http.server`, point a `ChatController` at it with a temp `config_path`,
drive `process_input`, and assert on captured stdout/stderr. This covers
the full streaming path without real keys and should be the seed of a
`tests/` directory.

## Known Limitations

- `:r`/`:rr`/`:i`/`:s`/`:ss` operators are specified but land in v0.3.0;
  pipelines currently abort on first failure.
- `/file` list input (`["a", "b"]`) is specified but lands in v0.2.5;
  bracket syntax is recognized and politely refused until then.
- Backslash continuation works in scripts (`-c` file/stdin); interactive
  continuation is not implemented.
- `SessionController` exists but `/persist` and session save/load
  commands aren't wired yet (v0.2.5).
- Local-provider vision pending a post-downscale retest.
- No pyproject.toml/packaging; path manipulation in main.py.

## Out of Scope Here

The AI community workspace concept is a separate initiative with its own
future planning - deliberately not part of this brief or the roadmap.
