# PyTTAI — orientation for a Code session

PyTTAI ("Python Text Terminal with AI") is a terminal chat client where **AI
is explicit**: slash commands and colon operators form a small language, and
nothing reaches a model unless deliberately piped there. Runs interactively or
non-interactively. Code lives under `Pychat/`, package `lmchat`.

## Read these first
- `BILL_OF_PARTS.md` — inventory: entry points, module tree, providers,
  commands, operators, deps, config schema.
- `HANDOVER.md` — current state, what's done, what's next (treat staleness as
  a bug; update it when state moves).
- `TECHNICAL_BRIEF.md`, `Pychat/lmchat/docs/architecture.md`,
  `function_ref.md`, `slash-colon-spec.md` — design, API, operator grammar.
- `Roadmap.md` — direction (next config verb is `init`; then Sequai).

## Run it
```
cd Pychat
python3 main.py                       # interactive
python3 main.py -a -c "prompt"        # non-interactive (-a skips the connection test)
python3 main.py config doctor         # validate ~/.pyttai/config.json (exit 1 on error)
python3 -m unittest discover -s tests # tests
```
Local models are served by ollama at `localhost:11434`; the default provider
speaks the OpenAI-compatible path. `OllamaProvider` overrides to ollama's
native `/api/chat` so it can pass `num_ctx`.

## Git workflow (owner's convention)
- `main` = canon, `develop` = working branch, spawn `feature/*` off `develop`,
  merge back by PR.
- Push uses a GitHub **deploy key = `/data/NuCode/Village_Fossil/architect.pem`**:
  origin's *push* URL is SSH (`git@github.com:Bladetrain3r/PyTTAI.git`) and
  `core.sshCommand` points at that key; *fetch* stays HTTPS. So `git push`
  just works from here.

## The local-model delegate loop (how features got built this session)
Small local models are used as **verifiable delegates**, never for open-ended
judgment. The method:
1. Write a tight spec and a **deterministic acceptance test** first.
2. Send the spec to one or more local models via ollama `/api/chat` with
   `"think": false` (reasoning models otherwise spend the whole `num_predict`
   thinking and return empty — set it, or retry without for non-thinkers).
3. Auto-grade each submission with the test; ship the one that passes.
- **ornith:35b** is the fast, reliable default; **qwen3.6:27b** a solid slower
  second; **gpt-oss:20b** is a heavy reasoner and a poor fit for bounded
  codegen (it exhausts its budget mid-reasoning).
- Facts the model needs (provider lists, etc.) go IN the prompt — supply
  facts, let the model structure them; don't let it invent them.
- Desktop has ~30GB RAM and a large zoo; run models one at a time, don't
  saturate memory. Local inference is free; verification is the gate.

## Secrets
Cloud API keys come from **env vars** (or a secret manager), never cleartext
in `config.json`. The owner keeps them in an OpenBao vault under
`village/cloudkeys`; inject with `bao-kit with`. `config doctor` lints any
cleartext `api_key` and flags unknown provider types and missing keys — run it
before trusting a config.

## Note
This repo was handed off from the Village architect Code session (2026-09-05).
The delegate-loop method above and the two most recent features (ollama
`num_ctx`, `config doctor`) came from there.
