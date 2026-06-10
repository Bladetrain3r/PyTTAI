# Session Handover - 2026-06-09

Orientation doc for future sessions (human or Claude). Update or replace
when state moves on; treat staleness as a bug.

## Where things stand

PyTTAI is at **v0.2.3 complete, unreleased/untested-in-anger**. All
v0.2.3 CHANGELIST items are done and on branch
`claude/happy-hawking-8cg337` (PR #2 merged the first two commits to
main; the CommandResult sweep + spec are on the branch awaiting dogfood
and a follow-up PR). Owner is testing 0.2.3 next, then deciding the
spec's OPEN questions before v0.2.4 work begins.

## This session's work (3 pushes)

1. **Provider modernization** (`2bc9b60`, merged via PR #2)
   - `providers.py` rebuilt on official SDKs: `anthropic`, `openai`,
     `google-genai`. One `OpenAICompatibleProvider` base covers
     LM Studio / Ollama / xAI / OpenAI; `ClaudeProvider` and
     `GeminiProvider` are separate. `LLMProvider` interface unchanged
     (`test_connection` / `stream_completion` / `get_models`).
   - API keys: config `api_key` first, then env vars
     (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`,
     `GEMINI_API_KEY`/`GOOGLE_API_KEY`).
   - Gotchas encoded in the providers: newest Claude Opus models and
     GPT-5/o-series reject `temperature` (sent conditionally); OpenAI
     uses `max_completion_tokens`; base_url gets `/v1` appended if
     missing (old config compat).

2. **Bug/cruft pass** (`4c20e62`, merged via PR #2)
   - Failed turns (no output) are popped from history - fixes the
     repeat-error-every-turn bug after an oversized image.
   - Images > ~5MB base64 auto-downscale via Pillow (1568px/JPEG q85);
     >10MB without Pillow refuses cleanly. Only the latest image keeps
     its base64 in API payloads; older ones become
     "[image omitted from history]" placeholders (stored history keeps
     everything - substitution happens in `get_messages_for_api`).
   - `/exit` flows through handler-returns-False; `packethandler.py`
     and `AudioController` deleted; default max_tokens 1024 -> 4096.

3. **CommandResult sweep + spec** (`b7ecddd`, on branch, NOT yet PR'd)
   - All command handlers return `CommandResult`; single
     `ChatController.render_result` prints. **Convention: success
     content -> stdout, errors/progress -> stderr** (keeps `-c`
     scripting pipeable).
   - Handler return contract (documented in
     `_register_builtin_commands`): `CommandResult` | `None` |
     `False` (exit signal ONLY - never return send_message/send_image
     bools from a handler or you'll exit the session).
   - New: `Pychat/lmchat/docs/slash-colon-spec.md` - draft grammar for
     the operator system. DECIDED vs OPEN sections.

## Pending decisions (owner, after dogfooding)

Spec OPEN questions: only **q2 (DATA results through pipes)** remains.
Resolved: q1 `::` dropped (token reserved); q3 pipeline `:ai` stateless
(trailing-prompt form is the permanent chat-coupled path); q4 lazy
connect for `:ai@provider`, strict fail at call time.
Also decided: `:ai@provider` syntax, statement-vs-chat line
classification, /file three forms (bare=cat / prompt=chat-coupled /
:ai=pipeline), list input via ast.literal_eval, strict-unless-
`file_skip_missing` failure semantics, TTS dropped in favour of STT
around 0.4/0.5.

## Agreed next steps (v0.2.4 order)

1. Token tracking (cheap now: Anthropic final-message usage, OpenAI
   `stream_options={"include_usage": true}`, Gemini `usage_metadata`) -
   CSV log + `/tokenuse`
2. `reasoning` config key, per-provider translation (adaptive thinking /
   reasoning_effort / thinking_config), optional
3. `:ai` operator on the CommandResult foundation
4. TTS is (Bonus) - don't let it eat the release

## Testing approach used

No test framework in repo. Sessions validated with inline scripts
spinning a fake OpenAI-compatible SSE server on localhost
(http.server + `data:` chunks), driving `ChatController` with a temp
config via `config_path=`, asserting on stdout/stderr capture. Worth
formalizing into `tests/` eventually.

## Known rough edges (not yet addressed)

- Local-provider vision unconfirmed: owner saw gemma vision fail
  pre-downscale; likely the 12.8MB payload, but retest after 0.2.3
  dogfood - if it still fails it's a real format issue.
- `Roadmap.md` (repo root) is authoritative; docs-folder roadmaps are
  archives. Root CHANGELIST is the live worklog and the owner thinks
  in it - don't clobber, merge.
- `blob/` autodocs are stale generated artifacts.
- No pyproject.toml; `sys.path` hack in main.py.
- Owner has separate memory-system plans; packethandler was retired to
  make room. Don't reintroduce.
