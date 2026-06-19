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
- `/persist@context [name]` - save the conversation; `/sessions` lists
  saved contexts, `/restore <name>` loads one (the `@` variant selector
  generalizes from `:ai@provider`)

### v0.2.6 - File Ops Grow
- `/find` [DONE] - recursive name search (substring or glob), confined to
  the workspace root, no match -> NOTHING
- Path traversal mitigation [DONE] - `safe_resolve` collapses `..`/symlinks;
  optional `workspace_root` confines all file commands. Opt-in standalone
  (default off = current behavior), auto-`/workspace` in a container. The
  app enforces the boundary - it does not rely on container mounts.
- Working directory tracking (`/cd`, `/pwd`) - deferred to a later 0.2.x
- **Context preload files** [DONE]: top-level `context_file` config key
  (list of absolute paths) whose contents append to the system prompt -
  like skills, but pre-decided in config rather than model-invoked.
  - Appended to `system_prompt`, or becomes the system prompt if none set
  - mtime-cached live reads - editing a file takes effect next turn, no
    restart; missing files warn once and are skipped (non-fatal)
  - Applied on **every** turn including stateless `:ai`/`:ai@provider`:
    statelessness drops conversation history, not identity. The effective
    system prompt is the provider's persona and always loaded.
  - Preload tokens count on every turn - visible in `/tokenuse`
  - Deferred: per-provider `context_file` blocks (top-level only for now);
    pairs with the container `PRELOAD_CONTEXT` idea from the SSH phase
- **Token estimator + oversized-input guard** (deferred to a later 0.2.x;
  not in the committed 0.2.6 patch): estimate tokens before
  sending (cheap chars/4 heuristic by default; real per-provider count
  where cheap - Anthropic/Gemini count_tokens). When an input (e.g. a
  big `/file`) exceeds `token_warn_threshold`, act:
  - Interactive: prompt - proceed / truncate / cancel
  - Non-interactive: config policy (warn-and-proceed default, or abort)
    since scripts can't be prompted
  - Mirrors the existing image auto-downscale precedent (size-based
    pre-send action) and feeds `/tokenuse` visibility

### v0.2.8 - Logging
A proper logger module in `core`, before the operator surface grows.
- Replaces ad-hoc `print(..., file=sys.stderr)` with structured, levelled
  logging on stdlib `logging`. Nothing fancy - clean ISO-8601 (UTC)
  timestamp + a few flat fields, rsyslog-parsable out of the box.
- A CommandResult logs as fields: `status` (SUCCESS/NOTHING/ERROR),
  `code`, `format`, a short `msg`. The result tri-state maps to severity
  (ERROR -> error, NOTHING/SUCCESS -> info). Example line:
  `2026-06-14T19:35:22Z ERROR pyttai: status=ERROR code=FILE_NOT_FOUND fmt=error msg="File not found: x"`
- Default destination a log file (`~/.pyttai/pyttai.log`); optional syslog
  handler. Config: log level + destination.
- Retrofit existing flows (provider/stream errors, persist, pipeline
  execution, token recording) to log through it.
- **Do this pre-0.3.0 deliberately**: wiring logging in while the codebase
  is still small is far cheaper than after the operator and utility
  machinery lands. The stdout-result / stderr-status split stays; logging
  is a separate diagnostic channel alongside it.

### v0.2.9 - Tests
A real `tests/` suite (pytest), after logging so it covers the
instrumented code too.
- Fake OpenAI-compatible SSE server fixture - the pattern already used in
  development - exercises the full streaming path with no real keys.
- Coverage targets: parser (tokenize / parse_statement / preprocess),
  CommandResult states + rendering, pipeline (`:ai` stateless, chains,
  NOTHING short-circuit, lazy `@provider`), `/file` three forms + list
  input, `/ls`, `/persist` + `/persist@context` + `/restore`, token
  tracking.

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

### v0.3.1+ candidate - Config management utility
A standalone assist for the config lifecycle - **not** full automation,
and not a replacement for the in-app `/config` (which already does
runtime show + nested `key=value` edits). This covers what `/config`
doesn't: getting a config to exist and validating it. Earns its keep for
new-user setup, testing, and experimental iteration.

Natural scope:
- `init` - scaffold a starter config from a template (the current
  auto-created default is bare; this offers providers + key/env-var
  prompts). Light interactivity, not a wizard maze.
- `validate <path>` - structural check + provider-type check against
  `ProviderManager.PROVIDERS` + key-presence (config or env var). Reuses
  the clear errors providers already raise on missing keys.
- `doctor` - which providers actually connect (existing `test_connection`),
  which keys resolve from env. The "why won't my provider load" answer.
- `list-types` - available provider types and their required/optional fields.

Reuses existing pieces (`Config` load/save, the provider registry,
`test_connection`), so it's low-coupling - pickup-able in an interim or
polish window rather than a dedicated milestone.

**Open question:** delivery shape - a subcommand mode on `main.py`
(`main.py config <verb>`) vs a separate entry (`python -m lmchat.config`).
Lean subcommand-on-main (one binary, shares the codepaths) - decide at build.

Synergy: feeds the README new-user path (currently hand-write JSON) and
the 0.2.9 test work (quick throwaway/validated configs).

### v0.3.2-0.3.3 candidate - Sequai (the tool surface / action layer)
A slash command (`/sequai@model "goal"`) that asks a model to produce a
**sequence of PyTTAI commands from a bounded list** - the layer at which
an LLM can recommend or drive action *within a fence*, instead of emitting
raw shell. Distilled from the ML-Extras MLAgent pattern (LLM constrained to
numbered menu selections); reimplement the idea, the ML codebases stay
separate.

Why it fits PyTTAI cleanly:
- The bounded list is **the command registry** (`CommandController`), which
  already self-describes via `get_help()`. No separate menu file needed.
- Sequai's output is a PyTTAI statement sequence - effectively an NL -> `.ptt`
  generator. The **existing parser is the fence**: any off-registry command
  fails as "unknown command" before execution. No new execution/security
  path to build.

Principle reconciliation (this is the inverse of the BBS's "AI never acts"):
AI proposing actions stays consistent with "AI is explicit" via three locks -
(1) explicit invocation, (2) **recommend-first** (the sequence is shown for
review; running it is a separate explicit step), (3) bounded vocabulary, no
raw shell. Auto-execute is the opt-in, clearly-riskier mode.

Open questions to pin before building:
- **Loop semantics**: one-shot + validation-retry (re-ask on off-menu output)
  vs a true observe-act loop (run step, feed result back, generate next). Lean
  one-shot-then-review first; observe-act as a later opt-in.
- **Execute model**: review-then-run default; auto-run opt-in.
- **Action set**: full registry vs a curated safe subset.

Deferred further: Magic Launcher / MLMenu proper - a GUI launcher driven by
vision + cursor/keyboard models. Inline text-bounded (command-registry)
version first; it needs no vision models. Post-operators target so there's a
rich-enough action vocabulary to be worth generating. Worth a full design doc
(like bbs-design.md) when locking.

### v0.4-0.5 candidate - Speech to Text
TTS is dropped (was a 0.2.4 bonus; cut for focus). STT is the more
useful direction: generate transcripts from audio files, or feed a
meeting recording into the conversation for discussion. Provider-style
config like the LLM providers (local whisper + cloud options), likely
`:stt@provider` operator form. Plan properly when 0.3.x stabilizes.

### v0.4+ candidate - Referential Memory: the BBS
A persistent, threaded, explicitly-queried store - "files, but threaded,
persistent, and cross-session." The long-term referential layer above
ephemeral conversation and `/persist@context` snapshots. Commands live
under the existing `@variant` grammar (`/bbs@post`, `/bbs@read`,
`/bbs@search`) - no parser change needed.

**The locked principle**: the AI never reads or writes the BBS on its
own. It is a USER tool for retrieve/update/query. `/bbs@search` returns
titles/ids only (never injects content); `/bbs@read <id>` is the explicit
pull (the `/file` of the BBS); the user sees what exists, then chooses
what to send to a model. Every model-bound byte stays explicit - same
rule as the rest of PyTTAI, NOT an agentic memory the model invokes.

Post-0.3.0 at the earliest. Full locked/deferred decisions, the command
surface, and what to keep vs strip from the existing core are in
`Pychat/lmchat/docs/bbs-design.md`.

## Parked - Needs Its Own Planning Before Any Build

Each of these was in the old Phase 5/6 sweep; they're real ideas but not
roadmap items until they get a design pass:

| Item | Why parked |
|---|---|
| `/grep`, `/sed`, `/awk` | Mini-languages with deep surface area; overlap `/find` and the shell. Need scoping: what subset, and why not `:p` to system grep? |
| `/curl`, `/ping`, network utils | Network egress from an AI-adjacent tool needs a security story first |
| `/json`, `/csv` query tools | Wait until DATA-through-pipes semantics (spec OPEN q2) are settled |
| SSH server mode / context preloading | Still attractive for the container story; needs auth/session-isolation design |
| Memory management (`/compress`, context layers) | Separate memory experiments planned; don't preempt them. (The BBS referential layer is now specced - see v0.4+; this row is the *other* experiments.) |
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
