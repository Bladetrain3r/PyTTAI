# BBS - Referential Memory Layer (design notes)

**Status:** planned, post-0.3.0 at the earliest. Decisions are LOCKED where
marked; DEFERRED items need a call at implementation time.

This is a clean-room distillation of an existing filesystem BBS core, adapted
to PyTTAI's model. The existing swarm/work BBS implementations stay separate
codebases - this reimplements the *ideas*, it does not import them.

## What it is

A persistent, threaded, explicitly-queried store. The one-line framing: **"files,
but threaded, persistent, and cross-session."** It's the long-term referential
tier PyTTAI otherwise lacks.

The memory hierarchy it completes:

| Tier | Lifetime | Mechanism |
|---|---|---|
| Conversation | This session only | in-memory `Conversation` |
| Saved context | Retrievable snapshots | `/persist@context` + `/restore` |
| **BBS** | **Cross-session, structured, queryable** | **this doc** |

## The non-negotiable principle (LOCKED)

**The AI never reads or writes the BBS on its own.** It is a USER tool for
retrieve / update / query - not an agentic memory the model can call. Every
model-bound byte stays explicit, the same rule as the rest of PyTTAI:

- `/bbs@search <term>` returns matching **titles/ids only** - it never injects
  thread content into context.
- `/bbs@read <id>` is the explicit pull - the `/file` of the BBS.
- The user sees what exists (search), then chooses what to send to a model (read).

If a future feature ever lets a model query the BBS autonomously, that is a
different, opt-in thing with its own design - the default and the core stay
user-driven.

## Command surface (LOCKED unless noted)

BBS verbs live under the existing `@variant` selector as a namespace
(`/bbs@<verb>`). This already parses today - `/bbs@read 3 :ai summarise`
tokenizes as command `bbs`, args `@read 3`, operator `:ai summarise`. No parser
change required.

**Query (no AI, user-facing):**
- `/bbs@list [status]` - threads as titles/ids/meta. DATA result with a
  plain-text render (one per line); NOTHING if empty. Default status `active`.
- `/bbs@search <term>` - matching titles/ids ONLY. No content, no AI.

**Read (three forms, exactly like `/file`):**
- `/bbs@read <id|n>` - bare = show to user; `+ prompt` = chat-coupled turn
  (full history); `:ai` = stateless pipeline.
- Integer shorthand: small `n` = the nth thread from the last `/bbs@list`.

**Write (user-authored):**
- `/bbs@post "<title>" <body>` - create a thread (quoted title uses existing
  quote support; body is the rest).
- `/bbs@reply <id> <body>` - reply to a thread.

**Manage:**
- `/bbs@archive <id>`, `/bbs@pin <id>`, `/bbs@unpin <id>`, `/bbs@delete <id>`.

**Deferred / anticipated (NOT locked):**
- `:bbs@post "<title>"` / `:bbs@reply <id>` as pipeline **sinks** that post the
  running value - the BBS parallel to `:r`. Natural and likely wanted (post an
  `:ai` result straight to a thread), but decide at implementation.
- Summary reads: return a thread's stored summary instead of full content, for
  token-cheap recall. Pairs with the token estimator (0.2.6). Syntax TBD -
  nested `@` is awkward, maybe a flag.
- `fork` / `collapse` / promote-to-artifact - curation niceties, defer.

## Keep vs strip (from the existing core)

**KEEP** (fits PyTTAI's ethos):
- Filesystem-based, stdlib-only, "debuggable with `cat`."
- Thread = directory with `meta.json` + `posts/NNNN.json`.
- Per-status index files (active / archived / pinned).
- Integer shorthand resolution (nth active thread).
- Pinned threads as canonical/reference material - suits referential memory.
- Per-thread summaries (`.txt`) - for token-cheap reads.
- Artifacts (promoted canonical content) - finalized reference vs discussion.

**SIMPLIFY / DROP for v1:**
- **Roles/permissions** (admin/documenter/poster/observer) - a swarm
  multi-agent feature. PyTTAI is single-user: the only actor is the user. Drop
  in v1; leave a seam if multi-user / SSH mode ever lands.
- **POST_CAP / MAX_ACTIVE auto-lock** - swarm-tuned churn control. For a
  personal referential store, relax or disable by default; make configurable.
- **fork / collapse** - defer (see above).

## Storage & config (LOCKED)

- Default root: `~/.pyttai/bbs/` (cross-session, persistent).
- Configurable via config (`bbs_root`) and/or `BBS_ROOT` env var.
- Container: mount the bbs dir to persist across ephemeral containers, like
  `/sessions`. A natural fit for the container-first model - the BBS is the
  durable layer the ephemeral container reads/writes.

## Implementation considerations

- **Locking is the main portability snag.** The existing core uses `fcntl`
  (unix-only); PyTTAI supports Windows. Need a cross-platform advisory lock or
  graceful degradation (portable lockfile, or skip-with-warning where
  unavailable). Matters because script/CI usage can hit one BBS concurrently.
- **Results follow the established conventions.** `@list`/`@search` return DATA
  with a plain-text `render` (titles/ids one per line) so they show and pipe
  cleanly; no matches -> NOTHING. `@read` returns thread content as TEXT, three
  forms like `/file`.
- **Heavy threads -> token estimator** (0.2.6) guards a `@read` the same way it
  guards a big `/file`.
- **Traversal safety:** thread ids are generated (`ts_hash`), not user paths;
  `@read` resolves by id/shorthand, so validate the id and never treat it as a
  path. Aligns with the 0.2.6 traversal-mitigation work.
- **Module shape:** `core/bbs.py` (the store) + `features/bbs.py` (the
  commands), mirroring the existing controllers/features split.

## Why it fits PyTTAI

- The `@variant` verb namespace is already in the grammar.
- `@read` is just another `/file`-shaped source: three forms, pipeline-ready.
- Search-then-read keeps every model-bound byte explicit.
- It extends the file/persist machinery rather than introducing an ambient
  paradigm.
- Persistent + cross-session = the long-term referential tier that conversation
  and `/persist@context` don't cover.
