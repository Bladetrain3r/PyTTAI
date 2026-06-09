# The Slash-Colon Command System
### Draft specification v0.1 - for PyTTAI v0.2.4 through v0.3.x

Yes, the name is both a technical pun and puerile. It stays.

This document specifies the grammar and semantics of PyTTAI's command
language: slash commands (`/command`) composed with colon operators
(`:op`). It exists so the parser is written against rules, not vibes.

Sections are marked **DECIDED** (build against this) or **OPEN**
(needs a call before v0.3.0).

---

## 1. Core principles (DECIDED)

1. **AI is explicit.** No output reaches a model unless piped there
   with `:ai`. Slash commands alone never invoke AI.
2. **Lines are the unit of execution.** A statement starts at the
   beginning of a line and runs to the end of the (possibly continued)
   line. `/commands` must always start on a new line.
3. **No shell cosplay.** No variables, loops, globbing, or arrays.
   Iteration and composition beyond a single pipeline belong to a real
   shell driving PyTTAI via `-c` and `.ptt` scripts.
4. **Everything yields a CommandResult.** Every segment of a statement
   produces `{success, format, content | error}`. Operators consume the
   preceding segment's result. This is what makes `:s`/`:ss` and `:r`
   possible.

## 2. Line classification (DECIDED)

Each input line is exactly one of:

| Line starts with | Classified as | Operator parsing |
|---|---|---|
| `/`              | **Statement** | Yes |
| `#` (scripts only) | Comment - ignored | No |
| anything else    | **Chat message** | **No** |

Chat messages are sent to the current provider verbatim. A plain
conversational message containing ` :s ` or `note: this` is never
parsed for operators. This rule is what keeps operators from
contaminating natural language.

Blank lines are ignored in scripts and no-ops interactively.

### Line continuation

A statement ending in a single backslash (`\`) continues on the next
line. The backslash and newline are replaced with a single space.
Continuation applies to statements only - chat messages are single
lines (multiline chat input is a UI concern, not a grammar concern).

## 3. Statement structure (DECIDED)

```
/command [input] [params...] [:op [opargs]]...
```

- A statement is a **pipeline** of segments separated by operator
  tokens.
- The first segment is always a slash command: `command -> input ->
  params` in that order (e.g. `/file roadmap.txt` = command `file`,
  input `roadmap.txt`).
- Each subsequent segment begins with an operator token and consumes
  the **CommandResult of the preceding segment** as its input.
- Operator tokens are recognized only as whitespace-delimited words
  beginning with `:` that match the operator registry. Unknown `:words`
  in a statement are a parse error (fail loudly, before execution).

### Quoting

Double quotes make text literal: operators, backslashes and `#` inside
`"..."` are not interpreted. `\"` escapes a quote inside quotes. This
is the escape hatch for prompts that legitimately contain `:tokens`:

```ptt
/file notes.txt :ai "Explain what :s means in this file"
```

### Execution and short-circuit

Segments run left to right. If a segment fails (CommandResult with
success=false), execution skips forward to the next conditional
operator (`:s` / `:ss`); if there is none, the statement aborts and the
error is rendered to stderr. `:s` after a failure does not run its
segment; `:ss` after a success does not run its segment.

## 4. Operator registry

### v0.2.4 - the foundation

| Operator | Function | Status |
|---|---|---|
| `:ai [prompt]` | Send preceding output (plus optional prompt) to the **current** provider. Result = the model's response. | DECIDED |
| `:ai@provider [prompt]` | Same, but via a named provider for this segment only. Transient - does not change the active provider. | DECIDED (syntax - see note) |

**Why `:ai@claude` and not `:ai claude`:** with a bare word, the parser
can't distinguish a provider name from the first word of the prompt
without consulting runtime config - and "adding a provider named `add`
changes how scripts parse" is a footgun. The `@` makes provider
selection syntactic. By extension `:tts@elevenlabs` etc. later.

### v0.3.0 - composition

| Operator | Function | Status |
|---|---|---|
| `:r <path>`  | Redirect (write) preceding output to file. Result = success/failure of the write. | DECIDED |
| `:rr <path>` | Append preceding output to file. | DECIDED |
| `:i <path>`  | Insert file content as the segment's input (supplements /file). | DRAFT |
| `:s`  | Run the following segment only if the preceding result succeeded. | DECIDED |
| `:ss` | Run the following segment only if the preceding result failed. | DECIDED |
| `:p <cmd>` | Pipe output to an internal command. | DEFERRED until /ls, /grep etc. exist |

A conditional may be followed by a `/command` segment mid-statement
(the one place a slash command is not at line start):

```ptt
/file styles.css :ai@claude "Only output the corrected CSS" :r styles.css :s \
/persist styles.css :ss /print "Ruh-Roh!"
```

### v0.2.4 behavioral change to /file (DECIDED)

`/file <path>` **without** a trailing prompt or `:ai` becomes a plain
read (cat-equivalent): text content is the result, non-text files
return MIME/metadata as a DATA result. It only reaches a model when
piped: `/file x.md :ai summarise`. The current "prompt argument sends
to AI" form (`/file x.md summarise this`) is **deprecated**: it keeps
working through v0.2.x with a stderr warning, and is removed at v0.3.0
in favour of the operator form.

## 5. OPEN questions

1. **`::` statement terminator.** With statements-are-lines plus `\`
   continuation, `::` only matters if we want multiple statements on
   one line. Recommendation: drop it from v0.3.0 scope; reserve the
   token. Decide before parser work begins.
2. **Result format through pipes.** `:ai` receives the preceding
   CommandResult - as what? Proposal: TEXT results pass content
   verbatim; DATA results pass pretty-printed JSON; a future `:str`
   forces plain-text body only. Needs a worked example with /ls output.
3. **Conversation coupling.** Does a `:ai` segment inside a pipeline
   join the ongoing conversation history, or run stateless? Proposal:
   stateless by default (pipelines are plumbing, not chat), with the
   result printed and *not* added to history. Counter-argument: losing
   pipeline context from chat may surprise. Decide at implementation.
4. **`:ai@provider` connection lifetime.** Transient switch implies the
   named provider must already be configured and connected at startup.
   Lazy-connect on first use is nicer but complicates failure handling
   mid-pipeline.

## 6. Non-goals (DECIDED)

- Variables, loops, conditionals beyond `:s`/`:ss`, globbing, arrays.
- Replacing the system shell. PyTTAI composes *with* bash/pwsh via
  `-c`, stdin, and `.ptt` files; it does not reimplement it.
- Backwards compatibility with pre-0.3.0 implicit-AI behavior once the
  deprecation window closes.

## 7. Grammar sketch (informative)

```
script      := line*
line        := comment | blank | statement | chat
comment     := "#" .*                          ; scripts only
statement   := "/" word segment-args (operator segment-args)*
chat        := <any line not starting with "/" or "#">
operator    := ":" opname [ "@" word ]         ; from registry only
segment-args:= (word | quoted)*
quoted      := '"' (escaped | <not '"'>)* '"'
```

Implementation note: the tokenizer needs exactly three states
(normal, in-quotes, after-backslash). If it grows more, scope has
crept - stop and check this document.
