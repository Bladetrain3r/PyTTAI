# PyTTAI Roadmap

*An AI-augmented terminal that composes with your shell - not a replacement for it.*

THIS IS THE AUTHORITATIVE ROADMAP. Copies in the docs folder are archives.
The root CHANGELIST is the live per-version worklog; this document is the
wider arc. For the operator grammar, see `Pychat/lmchat/docs/slash-colon-spec.md`.

## Vision

A terminal chat client where language models are first-class but never
implicit: output reaches a model only when explicitly piped there. PyTTAI
provides the conversation, provider switching, and a small operator
language for composing AI into pipelines; everything else - iteration,
globbing, variables, the thousand GNU utilities - belongs to the real
shell driving PyTTAI through `-c`, stdin, and `.ptt` scripts.

Deployable standalone or container-first for debugging, operations, and
development workflows.

## Design Principles

1. **AI is explicit.** Slash commands never invoke AI on their own; only
   `:ai` (and future operator kin) sends anything to a model.
2. **Compose with the shell, don't replace it.** If bash/pwsh already does
   it well, PyTTAI's job is to pipe in and out of it cleanly, not to
   reimplement it.
3. **Structured everywhere.** Every command yields a CommandResult;
   success content goes to stdout, errors and progress to stderr, so
   scripts stay pipeable.
4. **Safe by default, container-first.** Read-only mounts, explicit
   persistence via `/persist`, no destructive surprises.
5. **Transient unless persisted.** Conversations and artifacts are
   ephemeral until deliberately saved.

## Current State: v0.2.3 (complete)

- **Providers on official SDKs**: Claude (`anthropic`), OpenAI (`openai`),
  Gemini (`google-genai`), xAI/LM Studio/Ollama via OpenAI-compatible
  endpoints. Env-var key fallback, live model listing, streaming.
- **Vision**: `/file image.png` and `/paste` with auto-downscaling of
  oversized images; older image payloads replaced by placeholders in API
  requests.
- **Error handling**: provider errors surface with provider name; empty
  responses warn; failed turns are removed from history.
- **CommandResult standardization**: all command handlers return
  structured results rendered through one path (stdout/stderr split).
- **Scripting**: non-interactive `-c` (string / stdin / `.ptt` file),
  startup chatter on stderr.

## Near-Term Releases

### v0.2.4 - Implicit to Explicit
The pivot release: AI use becomes operator-driven.
- Token tracking per turn to CSV log; `/tokenuse` for session totals
  (SDKs report real usage now - no estimation needed)
- Optional `reasoning` config key, translated per provider
  (adaptive thinking / reasoning_effort / thinking_config)
- **`:ai` operator** - the first operator, built on CommandResults;
  stateless (no conversation history in or out)
- `/file` three-form behavior: bare = cat, trailing prompt =
  chat-coupled turn (permanent, full history, content not re-echoed),
  `:ai` = stateless pipeline. Same pattern for similar commands.

### v0.2.5 - File Ops Begin
- `/ls` with glob support
- Multiple file handling for `/file`: Python-style list input
  (`/file ["a.md", "b.py"] compare`), strict on unreadable paths unless
  `file_skip_missing` is set - see spec for grammar
- `/persist <file> <name>` - explicit save to /sessions
- Logging improvements

### v0.2.6 - File Ops Grow
- `/find`
- Path traversal mitigation (`..` etc.) - don't over-rely on the container
- Working directory tracking (`/cd`, `/pwd`)
- **Context preload files**: per-provider config key (e.g.
  `"context_files": ["~/.pyttai/contexts/myproject.md"]`) whose contents
  append to the system prompt - like skills, but pre-decided in config
  rather than model-invoked. Design notes:
  - Per-provider block and/or top-level (default provider), same
    precedence pattern as `reasoning`
  - Read at call time with mtime caching, so editing the file mid-session
    takes effect without restart
  - Applies to **every** turn for that provider - chat-coupled AND
    stateless `:ai`/`:ai@provider` segments. Statelessness is about
    conversation history, not identity; a provider's preload is part of
    its persona and always loaded.
  - Preload tokens count on every turn - surface in `/tokenuse` so the
    cost is visible
  - Pairs with the container `PRELOAD_CONTEXT` idea from the SSH phase
- README refresh: version header and feature list still describe 0.2.2
  (operators, Gemini, env-var keys, /tokenuse all missing)

### v0.3.0 - Initial Operators
Grammar per the slash-colon spec (decide its OPEN questions first):
- `:r` / `:rr` - write/append output to file
- `:i` - read file as segment input
- `:s` / `:ss` - success/failure conditionals
- Pipe and redirect essentials
- Parser built against the spec's three-state tokenizer; predictable
  behavior over feature count

### v0.3.x - Small Utilities (kept deliberately boring)
Pure-Python, trivially structured, operator-friendly text helpers only:
- `/wc`, `/uniq`, `/sort`, `/head`, `/tail`
- `/hash`, `/diff` (candidates - confirm during 0.3.x planning)

These earn their place because they operate on CommandResult content
in-pipeline without shelling out. Anything more is the shell's job.

### v0.4-0.5 candidate - Speech to Text
TTS is dropped (was a 0.2.4 bonus; cut for focus). STT is the more
useful direction: generate transcripts from audio files, or feed a
meeting recording into the conversation for discussion. Provider-style
config like the LLM providers (local whisper + cloud options), likely
`:stt@provider` operator form. Plan properly when 0.3.x stabilizes.

## Parked - Needs Its Own Planning Before Any Build

Each of these was in the old Phase 5/6 sweep; they're real ideas but not
roadmap items until they get a design pass:

| Item | Why parked |
|---|---|
| `/grep`, `/sed`, `/awk` | Mini-languages with deep surface area; overlap `/find` and the shell. Need scoping: what subset, and why not `:p` to system grep? |
| `/curl`, `/ping`, network utils | Network egress from an AI-adjacent tool needs a security story first |
| `/json`, `/csv` query tools | Wait until DATA-through-pipes semantics (spec OPEN q2) are settled |
| SSH server mode / context preloading | Still attractive for the container story; needs auth/session-isolation design |
| Memory management (`/compress`, context layers) | Owner has separate memory-system experiments planned; don't preempt them |
| `/explain`, `/suggest`, AI-enhanced utils | Revisit after operators prove the composition model |
| Package/plugin management | Premature before a plugin API exists |

Out of scope for this roadmap entirely: the AI community workspace
concept - related interest, separate project, separate planning.

## Container Architecture (target shape)

```
/app/         Pyttai application (read-only)
/workspace/   Ephemeral read/write during session
/sessions/    Persistent, written via /persist only
/data/        Read-only mount
/logs/        Read-only mount
/config/      Read-only mount
```

```yaml
services:
  pyttai-debug:
    image: pyttai:latest
    volumes:
      - ./sessions:/sessions:rw
      - app-data:/data:ro
      - app-logs:/logs:ro
      - app-config:/config:ro
```

## Known Issues / Debt

- Local-provider vision needs a retest post-downscaling (pre-0.2.3
  failure was likely the oversized payload)
- No test framework; sessions are validated with ad-hoc fake-server
  scripts - formalize into `tests/` during 0.2.x
- No pyproject.toml; `sys.path` insertion in main.py
- `blob/` generated artifacts are stale

## Longer Arc

If the operator model proves out: richer TUI elements, deeper container
integration (attach-to-anything debugging), and non-interactive agentic
scripts as a first-class use case. The measure for any addition stays
the same: does it make composing AI with the existing shell easier, or
is it rebuilding the shell? Build the former, park the latter.
