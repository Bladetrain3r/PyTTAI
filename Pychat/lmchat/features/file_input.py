#!/usr/bin/env python3
"""
File input feature - adds file reading commands
"""

import ast
import sys
from pathlib import Path
from lmchat.core.models import CommandResult, OutputFormat
from lmchat.core.parser import tokenize


def _fence(chat_controller, file_path: Path, content: str) -> str:
    """Language-fenced content block with a filename header"""
    language = ""
    lr = chat_controller.file.detect_language(file_path)
    if lr.success:
        language = lr.content.get('language') or ""
    return f"--- {file_path.name} ---\n```{language}\n{content}\n```"


def _handle_multi(chat_controller, paths, prompt: str):
    """Multi-file (text) input: cat / chat-coupled / pipeline.

    Strict on unreadable paths unless config file_skip_missing is set.
    Images in a list are rejected for now (single-image use only).
    """
    skip_missing = chat_controller.config.get("file_skip_missing", False)
    blocks = []
    for raw in paths:
        fp = Path(str(raw))
        res = chat_controller.file.read_file(fp)
        if not res.success:
            if skip_missing:
                print(f"Skipping {fp}: {res.error}", file=sys.stderr)
                continue
            return res
        if res.format == OutputFormat.DATA:
            return CommandResult.error(
                f"{fp.name} is an image - multi-file lists are text-only for now",
                code="MULTIFILE_IMAGE",
                suggestion="Send images one at a time with /file <image>")
        blocks.append(_fence(chat_controller, fp, res.content))

    if not blocks:
        return CommandResult.nothing("No readable files in list")

    combined = "\n\n".join(blocks)
    if not prompt:
        # Bare (cat) or pipeline source - the :ai chain consumes this upstream
        return CommandResult.success_text(combined)

    print(f"Sending {len(blocks)} files...", file=sys.stderr)
    chat_controller.send_message(f"{prompt}\n\n{combined}")
    return None


def create_file_handler(chat_controller):
    """Create file command handler.

    Three invocation forms per the slash-colon spec:
      /file <path>            bare: cat-equivalent CommandResult, no AI
      /file <path> <prompt>   chat-coupled: joins the conversation with
                              full history (content not re-echoed)
      /file <path> :ai ...    pipeline: the bare result feeds the operator
                              (the :ai chain is handled upstream by the
                              parser - this handler just sees the bare form)

    Path may be a single bare path or a Python-style list:
      /file ["a.md", 'b.py'] compare these
    """
    def handle_file(args: str):
        if not args:
            return CommandResult.error(
                "No file path given",
                code="USAGE",
                suggestion="Usage: /file <path|[\"a\",\"b\"]> [optional prompt]"
            )

        # List input: first token is the bracket list, rest is the prompt
        if args.lstrip().startswith('['):
            toks = tokenize(args)
            try:
                paths = ast.literal_eval(toks[0].text)
            except (SyntaxError, ValueError) as e:
                return CommandResult.error(
                    f"Bad file list: {e}",
                    code="BAD_LIST",
                    suggestion='Use a Python-style list: ["a.md", "b.py"]')
            if not isinstance(paths, (list, tuple)) or not paths:
                return CommandResult.error(
                    "File list is empty or not a list",
                    code="BAD_LIST")
            prompt = " ".join(t.text for t in toks[1:])
            return _handle_multi(chat_controller, paths, prompt)

        # Single path - first whitespace ends it, rest is prompt
        parts = args.split(' ', 1)
        file_path = Path(parts[0])
        prompt = parts[1] if len(parts) > 1 else ""

        file_result = chat_controller.file.read_file(file_path)
        if not file_result.success:
            return file_result

        # Image handling
        if file_result.format == OutputFormat.DATA:
            if prompt:
                # Chat-coupled: send to the vision model in-conversation
                image_data = file_result.content
                print(f"Sending image {file_path.name}...", file=sys.stderr)
                chat_controller.send_image(
                    prompt,
                    image_data['data'],
                    image_data['format']
                )
                return None  # streamed; never return send bools
            # Bare: MIME/metadata only - no base64 dump to the terminal
            meta = {k: v for k, v in file_result.content.items() if k != "data"}
            meta["mime_type"] = f"image/{meta.get('format', 'unknown')}"
            return CommandResult.success_data(meta)

        content = file_result.content

        if not prompt:
            # Bare: cat-equivalent, raw content as the result
            return CommandResult.success_text(content)

        # Chat-coupled: language-fenced content + prompt join the conversation
        language_result = chat_controller.file.detect_language(file_path)
        language = ""
        if language_result.success:
            language = language_result.content.get('language') or ""
        message = f"{prompt}\n\n```{language}\n{content}\n```"

        print(f"Sending {file_path.name}...", file=sys.stderr)
        chat_controller.send_message(message)
        return None

    return handle_file

def register_commands(chat_controller):
    """Register file commands with the chat controller"""
    chat_controller.commands.register_command(
        "file",
        create_file_handler(chat_controller),
        "Read and send file content",
        aliases=["f", "read"]
    )
