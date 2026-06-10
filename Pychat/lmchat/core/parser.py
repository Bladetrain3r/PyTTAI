#!/usr/bin/env python3
"""
Statement parser for the slash-colon command system.

Implements the tokenizer and statement splitting defined in
docs/slash-colon-spec.md. Lines starting with '/' are statements and get
parsed here; everything else is chat and never touches this module.

Tokenizer states: normal, in-quotes, bracket-list. Per the spec, if it
needs more states than that, scope has crept.
"""

from dataclasses import dataclass
from typing import List, Optional


class ParseError(Exception):
    """A statement failed to parse. Raised before any execution."""
    pass


@dataclass
class Token:
    text: str       # unescaped content (quotes stripped for quoted tokens)
    start: int      # index into the original line
    quoted: bool = False


@dataclass
class AISegment:
    provider: Optional[str]   # None = current provider
    prompt: str


@dataclass
class Statement:
    command_raw: str          # the /command portion, verbatim
    chain: List[AISegment]    # operator segments, in order


# Operator registry - :r/:rr/:i/:s/:ss arrive in v0.3.0
OPERATORS = {"ai"}
# Reserved tokens: parse errors today, may gain meaning later
RESERVED_TOKENS = {"::", ":json"}


def tokenize(line: str) -> List[Token]:
    """Split a statement into tokens, honouring quotes and bracket lists."""
    tokens = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c.isspace():
            i += 1
            continue
        start = i

        if c == '"':
            # Quoted token: contents are literal, \" escapes a quote
            i += 1
            buf = []
            closed = False
            while i < n:
                ch = line[i]
                if ch == '\\' and i + 1 < n and line[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                if ch == '"':
                    closed = True
                    i += 1
                    break
                buf.append(ch)
                i += 1
            if not closed:
                raise ParseError("Unclosed quote in statement")
            tokens.append(Token("".join(buf), start, quoted=True))

        elif c == '[':
            # Bracket list: one token, scanned before operator splitting
            # so a ':' inside a quoted filename can't read as an operator
            depth = 0
            quote = None
            j = i
            closed = False
            while j < n:
                ch = line[j]
                if quote:
                    if ch == quote and line[j - 1] != '\\':
                        quote = None
                elif ch in "\"'":
                    quote = ch
                elif ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        j += 1
                        closed = True
                        break
                j += 1
            if not closed:
                raise ParseError("Unclosed bracket list in statement")
            tokens.append(Token(line[i:j], start))
            i = j

        else:
            j = i
            while j < n and not line[j].isspace():
                j += 1
            tokens.append(Token(line[i:j], start))
            i = j

    return tokens


def parse_statement(line: str) -> Statement:
    """Parse a /-prefixed line into a command segment and operator chain.

    Raises ParseError on unknown/reserved operator tokens, bad quoting,
    or malformed provider selection - before anything executes.
    """
    if not line.startswith('/'):
        raise ValueError("parse_statement expects a /-prefixed statement")

    tokens = tokenize(line)
    if not tokens:
        raise ParseError("Empty statement")

    # Locate operator tokens (never the command itself at index 0)
    ops = []  # (token_index, opname, provider)
    for idx in range(1, len(tokens)):
        t = tokens[idx]
        if t.quoted or not t.text.startswith(':'):
            continue
        if t.text in RESERVED_TOKENS:
            raise ParseError(
                f"'{t.text}' is reserved and has no behavior yet")
        name, at, provider = t.text[1:].partition('@')
        if name not in OPERATORS:
            raise ParseError(
                f"Unknown operator '{t.text}' - quote it if it's prompt text")
        if at and not provider:
            raise ParseError(f"Missing provider name after '{t.text}'")
        ops.append((idx, name, provider or None))

    if not ops:
        return Statement(command_raw=line, chain=[])

    first_op_start = tokens[ops[0][0]].start
    command_raw = line[:first_op_start].rstrip()

    chain = []
    for k, (idx, name, provider) in enumerate(ops):
        end = ops[k + 1][0] if k + 1 < len(ops) else len(tokens)
        prompt = " ".join(t.text for t in tokens[idx + 1:end])
        chain.append(AISegment(provider=provider, prompt=prompt))

    return Statement(command_raw=command_raw, chain=chain)


def preprocess_script(lines: List[str]) -> List[str]:
    """Script preprocessing: drop comment lines, join continuations.

    Comments: lines whose first non-blank char is '#' (scripts only -
    interactive input never reaches this function).
    Continuation: a statement line ending in '\\' joins the next line
    with a single space. Applies to statements only; chat lines are
    never continued.
    """
    lines = [ln for ln in lines if not ln.lstrip().startswith('#')]

    result = []
    pending = ""
    for line in lines:
        candidate = pending + line
        stripped = line.rstrip()
        if candidate.lstrip().startswith('/') and stripped.endswith('\\'):
            pending = pending + stripped[:-1] + ' '
        else:
            result.append(candidate)
            pending = ""
    if pending:
        result.append(pending.rstrip())
    return result
