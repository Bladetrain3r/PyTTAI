# PyTTAI - A Python Terminal with added AI
#### Version 0.2.5: File Ops Begin

## Introduction
PyTTAI (Python Text Terminal with AI) is a terminal chat client aimed at making
language models feel natural to use, without forcing them into your workflow.
AI is a first-class feature but never an ambient one: nothing reaches a model
unless you explicitly send it there. It runs interactively or non-interactively,
and is built to compose *with* your shell rather than replace it.

### Core Principles

**AI is explicit.** Output only reaches a model when you ask. A slash command on
its own never invokes AI - you either type a chat message, add a prompt to a
command (`/file notes.md what's missing?`), or pipe a command into the `:ai`
operator (`/file notes.md :ai summarise`).

**Offline unless desired.** Minimal dependencies and OpenAI-compatible API
support mean local models (LM Studio, Ollama) work out of the box. No phone home,
no registration. API keys live in config or in the conventional environment
variables.

**Transient unless persisted.** Container-first and ephemeral by default.
Conversations and artifacts vanish when the session ends unless you explicitly
save them - `/persist <file>` for an artifact, `/persist@context` for the
conversation itself.

**A useful tool, not a brain replacement for fools.** An augmented terminal for
the individual improving their own capabilities. Extensible, modular, and
scriptable for automation. It is not Cursor and will not rewrite your codebase
off a single prompt.

## Dependencies
### Prerequisites
- Python 3.10+
- For local models: LM Studio, Ollama, or any OpenAI-compatible API server

### Python Modules
Providers are built on the official SDKs:
- `anthropic>=0.40.0` (Claude)
- `openai>=1.60.0` (ChatGPT, plus LM Studio/Ollama/xAI via OpenAI-compatible endpoints)
- `google-genai>=1.0.0` (Gemini)
- `pyperclip>=1.8.2` (clipboard; `Pillow` optional for image clipboard/resizing)

API keys can be set per provider in config, or via the conventional environment
variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY`.

## Setup
Create a `config.json` in `~/.pyttai` (or `%USERPROFILE%\.pyttai`). Without one,
PyTTAI defaults `model` to `local-model`, which you'll need to load manually in
LM Studio. Below is an example with multiple local and cloud providers.

```json
{
  "base_url": "http://localhost:1234",
  "model": "gemma-3-4b-it-qat",
  "max_tokens": 4096,
  "temperature": 0.7,
  "system_prompt": "You are a helpful assistant.",
  "providers": {
    "claude": {
      "type": "claude",
      "api_key": "keyhere-or-set-ANTHROPIC_API_KEY",
      "model": "claude-opus-4-8",
      "max_tokens": 4096
    },
    "gpt": {
      "type": "openai",
      "api_key": "keyhere-or-set-OPENAI_API_KEY",
      "model": "gpt-5",
      "max_tokens": 4096
    },
    "grok": {
      "type": "xai",
      "api_key": "keyhere-or-set-XAI_API_KEY",
      "model": "grok-4"
    },
    "gemini": {
      "type": "gemini",
      "api_key": "keyhere-or-set-GEMINI_API_KEY",
      "model": "gemini-2.5-flash"
    },
    "local": {
      "type": "lmstudio",
      "base_url": "http://localhost:1234",
      "model": "gemma-3-4b-it-qat",
      "timeout": 60.0
    },
    "ollama": {
      "type": "ollama",
      "base_url": "http://localhost:11434",
      "model": "llama3.2",
      "timeout": 120.0
    }
  }
}
```

Optional config keys: `reasoning` (`off`/`low`/`medium`/`high`, per provider or
top-level), `active_provider`, `max_conversation_length`, `token_log` (default
true), `track_usage` (default true), `file_skip_missing` (default false),
`context_file` (list of absolute paths whose contents are appended to
`system_prompt` - or become the system prompt if none is set; re-read live when
edited, and applied on every turn including `:ai` pipelines).

Install dependencies (a venv is recommended):
```bash
cd Pychat
pip install -r requirements.txt
python3 main.py
```

Or build the container (provide your own config.json; bind-mount for persistence):
```bash
docker build -t pyttai:latest .
docker run -it --rm --mount type=bind,src=$(pwd)/sessions,dst=/sessions \
  --mount type=bind,src=$(pwd)/data,dst=/data,ro pyttai:latest
```

## Commands

| Command | Aliases | What it does |
|---|---|---|
| `/file <path\|[list]> [prompt]` | `/f`, `/read` | Read a file (or list of files). Bare = show it; with a prompt = send to AI in conversation; with `:ai` = pipeline. |
| `/paste [prompt]` | `/p`, `/clip` | Send clipboard contents (text or image). |
| `/ls [pattern]` | `/dir` | List files; globs like `*.py`, `**/*.log`; a bare directory lists its contents. |
| `/persist <file> [name]` | | Copy a file into the persistent sessions directory. |
| `/persist@context [name]` | | Save the current conversation for later retrieval. |
| `/sessions` | | List saved conversations. |
| `/restore <name>` | | Load a saved conversation. |
| `/provider [switch NAME]` | `/p` | List providers, or switch the active one. |
| `/model` | `/m` | List available models for the active provider. |
| `/config [key=value]` | | Show config, or set a key (nested: `providers.claude.model=...`). |
| `/tokenuse` | `/tokens` | Show token usage this session (also logged to `~/.pyttai/tokens.csv`). |
| `/clear` | `/c` | Clear conversation history. |
| `/help` | `/h`, `/?` | List commands. |
| `/exit` | `/quit`, `/bye` | Quit. |

## Operators

Operators chain off a command with `:`. They use the preceding output as input -
no AI is involved unless you use `:ai`.

| Operator | What it does |
|---|---|
| `:ai [prompt]` | Send the preceding output (plus optional prompt) to the **current** provider. Stateless - it does not join or read the conversation. |
| `:ai@provider [prompt]` | Same, but via a named provider for this segment only (transient). |

The `@` selector also works on commands as a variant: `/persist@context`. More
operators (`:r` write, `:i` read, `:s`/`:ss` conditionals) are specified in
`Pychat/lmchat/docs/slash-colon-spec.md` and arrive in v0.3.0.

### Getting started
```
/file document.txt summarise this for me        # file + prompt -> conversation
/file notes.md :ai one-line summary             # pipeline, stateless
/file ["a.py", "b.py"] where do these differ?   # multiple files
/ls **/*.py :ai which looks riskiest to refactor?
/paste give me a bash one-liner for this
/provider switch claude
/persist@context worklog                         # save the conversation
/exit
```

## Non-interactive use

PyTTAI runs as a pipeline component: status goes to stderr, results to stdout, so
output redirects and pipes cleanly. Pass a command string, `-` for stdin, or a
`.ptt` script path.

```bash
# command string
python3 main.py -c "/file report.md :ai summarise" > summary.txt

# stdin
echo "What is this?" | python3 main.py -c -

# script file
python3 main.py -c pipeline.ptt
```

A `.ptt` script: `/commands` start a line, `#` lines are comments, and a trailing
`\` continues a statement onto the next line. Plain lines are chat messages.
```ptt
# Review a spec across two models, save the result
/provider switch claude
/file design.md :ai@gpt Draft an implementation plan from this spec :ai@claude Review and tighten the plan
/persist@context design-review
```

## Other References
- `Roadmap.md` - authoritative roadmap and current state
- `CHANGELIST` - per-version worklog
- `TECHNICAL_BRIEF.md` - architecture and conventions
- `Pychat/lmchat/docs/slash-colon-spec.md` - the command/operator grammar

## License
MIT License for now. Download and use implies no warranty of fitness for purpose;
use is at your own risk.

## Contributing
Found a bug? Log an issue with reproduction steps. Collaboration is invite-only
while the project matures, but forks and reuse of the ideas are welcome.
