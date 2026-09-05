# PyTTAI — Session Handover

Orientation for future sessions (human or Claude). Newest first. Treat
staleness as a bug: update when state moves. See `CLAUDE.md` for the working
conventions and `BILL_OF_PARTS.md` for the component inventory.

## 2026-09-05 — handed off from the Village architect session

**Where things stand.** On `develop` (= `main`), post two merged PRs. The
provider layer is on official SDKs (`anthropic`, `openai`, `google-genai`)
with one `OpenAICompatibleProvider` base; registry covers lmstudio, ollama,
openai, xai, claude/anthropic, gemini/google. Cloud keys now resolve from env
(owner removed the cleartext keys from `config.json`). Local (ollama) path is
the focus.

**This session's work.**
1. **ollama `num_ctx`** (PR #6, merged): `OllamaProvider` overrides
   `stream_completion` to use ollama's native `/api/chat` so it can pass
   `options.num_ctx` (the OpenAI `/v1` path silently drops it). Verified via
   `/api/ps`. Drafted by a local model (ornith:35b).
2. **config doctor** (PR #7, merged): `python3 main.py config doctor`
   validates `~/.pyttai/config.json` against the provider registry and key
   presence — unknown type, missing required key (config or env), and a
   cleartext-key lint pushing secrets to env/secret-manager. Exit 1 on error,
   so it works as a CI gate. `lmchat/core/config_doctor.py` + tests. Chosen
   from a 3-model local bake-off (ornith:35b and qwen3.6:27b passed;
   gpt-oss:20b failed on reasoning-budget exhaustion).
3. Established the **local-model delegate loop** (see `CLAUDE.md`), the
   **deploy-key push** setup, and this doc packet.

**Next.**
1. **config `init` verb** (roadmap v0.3.1): scaffold a starter config from a
   template; sits beside `doctor` under `main.py config <verb>`. Good next
   delegate — small, and its acceptance test is "the scaffolded config passes
   `doctor`".
2. **A locals applet** (`/models` or `/ollama`): live-list installed ollama
   models via `/api/tags` (name, size, context), `use <model>` to switch the
   current provider, optionally `pull`. Follows the `file_ops.py` handler
   pattern. Directly kills the stale-config-vs-reality drift.
3. Minor: `OllamaProvider`'s `/v1` strip is `base_url[:-3]`, fragile if a
   config gives a trailing slash (`.../v1/`); default configs are fine.

**How to work.** Branch `feature/*` off `develop`, PR back. Push works via the
`architect.pem` deploy key (details in `CLAUDE.md`). Build with the delegate
loop: spec + acceptance test, local model drafts, test gates, then integrate.
Run `config doctor` before trusting a config.

---
*Prior handover (v0.2.4 on the since-merged `claude/happy-hawking-8cg337`
branch) is in git history if needed.*
