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
5. **Three result states.** A result is one of:
   - **SUCCESS** - operation ran and produced actionable content.
   - **NOTHING** - operation ran fine but produced nothing to action
     (search with no matches, empty file, empty clipboard). `success`
     is true; `is_nothing` is true.
   - **ERROR** - the operation itself failed (bad path, provider down).
   This separates "no result" from "failed," which is what lets
   conditionals and data operators behave predictably (see §4).

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
selection syntactic. By extension, future media operators inherit it
(`:stt@whisper` etc.).

### v0.3.0 - composition

Operators fall into two kinds, mirroring the shell's distinction between
`|` and `&&`/`||`:

- **Data operators** consume the running pipeline value and produce a new
  one: `:ai`, `:r`, `:rr`, `:i`.
- **Control operators** gate whether the next segment runs, based on the
  running success status; they do **not** alter the value: `:s`, `:ss`.

| Operator | Kind | Function | Status |
|---|---|---|---|
| `:r <path>`  | data | Write running value to file. Result = success/failure of the write (not the content). | DECIDED |
| `:rr <path>` | data | Append running value to file. | DECIDED |
| `:i <path>`  | data | Read `<path>` and emit its content as the running value (TEXT, or DATA/MIME for non-text - same as `/file` bare). The explicit path means it ignores the preceding value; it is `/file`-bare usable mid-pipeline. Primary use: read back a file just written with `:r` to keep processing it. Missing/unreadable = strict failure. | DECIDED |
| `:s`  | control | Run the following segment only if the running result **succeeded** (bash `&&`). | DECIDED |
| `:ss` | control | Run the following segment only if the running result **failed** (bash `||`). | DECIDED |
| `:p <cmd>` | data | Pipe value to an internal command. | DEFERRED until /ls, /grep etc. exist |

#### Conditionals follow bash `&&` / `||` semantics (DECIDED)

The statement carries a **running result** (the CommandResult of the last
segment that actually executed). Control operators test its success bool:

- `:s` runs its segment only if the running result is **SUCCESS** (ran
  with content); otherwise skipped, and the running result **passes
  through** unchanged.
- `:ss` runs its segment only if the running result is **ERROR**;
  otherwise skipped, result passes through.
- **NOTHING falls through both.** A no-result is neither acted on (`:s`
  wants content) nor recovered from (`:ss` wants a failure). So
  `/find x :s /persist x :ss /alert` with no match runs neither branch -
  exactly "nothing found, nothing went wrong." Data operators
  (`:ai`/`:r`/...) also propagate NOTHING without executing, so a model
  is never asked to process emptiness.

Because skipped segments preserve status, conditionals chain
left-associatively exactly as in bash:

```
A :s B :ss C     ==     A && B || C
```

A control operator gates a **`/command`** (run fresh - it does not
consume the running value, like the right-hand side of `&&`) or a data
operator (which does consume it). The statement's overall success is the
status of the last segment that ran.

```ptt
# Write the cleaned file, then persist it only if the write succeeded.
/file styles.css :ai@claude "Only output the corrected CSS" :r styles.css :s /persist styles.css
```

`:ss` mirrors this for the failure branch - it gates a recovery
`/command`. There is deliberately **no `/print`**: the tail of every
pipeline already renders to the client, so emitting output is implicit
in the final segment; a literal-message sink is not a core command.

The grep-vs-find question dissolves with three states: a search with no
matches returns **NOTHING**, not ERROR and not SUCCESS. `:s` (found
something, act on it) and `:ss` (the search itself broke) both stay
meaningful and neither misfires on an empty result. Commands choose
SUCCESS / NOTHING / ERROR for their own outcomes; this is the convention
they follow.

### Command invocation forms (DECIDED)

Every content-producing slash command has three invocation forms. `/file`
is the model case; the same pattern applies to similar commands
(`/paste`, future `/ls` etc.):

| Form | Example | Behavior |
|---|---|---|
| **Bare** | `/file notes.md` | Output only. Result rendered to the client (cat-equivalent for text; DATA/MIME metadata for non-text). No AI. |
| **Chat-coupled** (trailing prompt) | `/file notes.md anything missing?` | Command output + prompt join the **ongoing conversation with full history** as a chat turn. The content is **not echoed to the client** (you have it already) - it lives in conversation context; only the model's reply renders. |
| **Pipeline** (`:ai`) | `/file notes.md :ai summarise` | Stateless plumbing: the segment result goes to the model **without** conversation history, and the response does not join it (see OPEN q3 - resolved). |

The discriminator is purely syntactic: bare path(s) only = output;
trailing text = chat-coupled; `:ai` = pipeline. The chat-coupled form is
**permanent**, not a deprecation candidate - it is how a model can ask
for a file mid-conversation and receive it in context:

```
aimodel: Can you pass the files through so I can confirm XYZ?
/file ["foo.bar", "/home/bar.food"] Take a look
aimodel: I've taken a look and XYZ does apply.
```

### Multi-file input (DECIDED)

Commands taking file inputs accept either a single bare path or a
Python-style list:

```ptt
/file notes.md                          single path, as today
/file ["a.md", '/home/b.py'] compare    list - single or double quotes
```

- Lists are parsed with `ast.literal_eval` (Pythonic: both quote styles
  work). Input not starting with `[` is a single bare path - first
  whitespace ends it; paths with spaces use the list form.
- The tokenizer treats a bracketed list as one token **before** operator
  splitting - a `:` inside a quoted filename is never an operator.
- Each file becomes an ordered block in one message; text files get
  `--- <name> ---` headers (same headers in bare/cat output, so pipeline
  mode inherits the format).
- **Failure semantics: strict by default** - any unreadable path fails
  the whole command with an error naming it. Config flag
  `file_skip_missing: true` switches to skip-and-warn (warning to
  stderr, readable files still sent).

## 5. Formerly OPEN questions - all RESOLVED

No open questions remain; the spec is build-ready for v0.2.4 parser
work.

1. **`::` statement terminator.** ~~Multiple statements on one line?~~
   **RESOLVED: dropped.** Statements-are-lines plus `\` continuation
   covers everything. The `::` token stays **reserved** (parse error,
   not valid text) in case a use ever materializes.
2. **Result format through pipes.** **RESOLVED: what you saw on screen
   is what flows down the pipe.** TEXT results pass content verbatim.
   DATA results pass their plain-text rendering - the same human
   display the renderer produces (e.g. /ls -> one name per line); a
   DATA result with no rendering falls back to pretty-printed JSON.
   This is the Unix-pipe rule, deliberately not the PowerShell
   object-flow rule. The `:json` operator is **reserved** (parse
   error today) for the day a pipeline needs the structured form
   explicitly.
3. **Conversation coupling.** ~~Does a `:ai` segment join conversation
   history or run stateless?~~ **RESOLVED** by the invocation-forms
   design above: history-coupling has its own syntax (the trailing-
   prompt chat form), so pipeline `:ai` is **stateless** - it neither
   reads nor writes conversation history. No flag needed.
4. **`:ai@provider` connection lifetime.** **RESOLVED: lazy.** Named
   providers are not connection-tested at startup (saves test calls);
   the client connects at call time. If the provider/model is
   unavailable when the segment runs, the segment **fails strictly**
   like any other failure - it short-circuits to `:ss` or aborts the
   statement. No retries, no fallback provider.

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
