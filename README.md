# PyTTAI - A Python Terminal with added AI
#### Version 0.2.2: Scripting Is Go

## Introduction
You're looking at the readme file for PyTTAI - a Python based terminal aimed at making the use of Langauge Models feel natural, without forcing it into workflows unnecessarily.
To that end, PyTTAI follows a few core principles which need to be established first and foremost:

### PyTTAI?
Python Text Terminal with AI

### AI Is Explicit
When giving a command, output is only processed by AI when explicitly piped into it. 
This will be achieved with two key types of interface:
- Slash commands which explicitly call on application-like functionality
- Colon delimited operators allowing redirection, piping and processing through specific AI providers.

### Offline unless Desired
Relatively minimal dependencies and a compatibility with standard OpenAI APIs means that providers are easy to add, and easy to configure in a standard fashion.
No phone home, no registrations or linkages, purely programmatic access via API keys stored in config or (later on) ingestable as environment variables.

### Transience unless persisted.
Targeted at an easy to build, easy to run, easy to isolate container first architecture.
The user can utilise pipes or redirects to write to workspace folders, and an explicit /persist command copies out conversations and artifacts.

### A useful tool, not a brain replacement for fools
This will focus on being an augmented terminal first and foremost, with design decisions and scope targeted at the individual improving their own capabilities.
It is meant to be extensible, modular and easily integrated into automation with non-interactive modes.
However it is not Cursor and will not by itself rewrite an entire codebase or build one from scratch off a single prompt.

## Dependencies
For a default config without a cloud provider (or Claude provider aha) you will need:
### Prerequisites
- Python 3.10+
- LM Studio (or compatible OpenAI API server, such as Ollama)

#### Python Modules
- httpx>=0.25.0
- pyperclip>=1.8.2

## Setup
Create a config.json file in ~/.pyttai or %USERPROFILE%\.pyttai
Without one it will default "model" to local-model which will need manual loading in LMStudio.
Below is an example config with multiple local and cloud providers.
Ollama is also supported but you will need to adjust your port.
```json
{
  "base_url": "http://localhost:1234",
  "model": "llama-3.2-3b-instruct",
  "max_tokens": 4096,
  "temperature": 0.7,
  "system_prompt": "You are a helpful assistant.",
  "providers": {
    "claude": {
      "type": "claude",
      "api_key": "skskskskskAA",
      "model": "claude-3-5-sonnet-20241022",
      "max_tokens": 1024,
      "temperature": 0.5
    },
    "gpt4": {
      "type": "openai",
      "api_key": "gggggA",
      "model": "gpt-4.1-nano",
      "max_tokens": 1024,
      "temperature": 0.5
    },
    "local": {
      "type": "lmstudio",
      "base_url": "http://localhost:1234",
      "model": "gemma-3-4b-it-qat",
      "timeout": 60.0
    },
    "tinyllama": {
      "type": "lmstudio",
      "base_url": "http://localhost:1234",
      "model": "llama-3.2-1b-instruct",
      "timeout": 120.0
    }
  }
}
```

After creating the config file, in the Pychat folder, set up a venv or just install the packages with pip if you don't mind them on your system:
```bash
cd Pychat
pip install -r requirements.txt
```

Alternatively, you can use the Dockerfile to build an image and run it. Note you'll need to provide a config.json.
You will need to create a bind mount to write new files.
May produce inconsistent behaviour with /paste and /file right now.
```bash
docker build -t pyttai:latest .
docker run -it --rm --mount type=bind,src=$(pwd)/sessions,dst=/sessions --mount type=bind,src=$(pwd)/data,dst=/data,ro pyttai:latest
```

### Getting started
- Feeding a file in (relative path):
```
/file document.txt summarise this file for me
```

- Feeding the clipboard to the AI (vision not enabled yet):
```
/paste Give me a bash one liner to convert this CSV to JSON
```

- Switching provider (full context preserved for now - watch token usage)
```
/provider switch claude
```

Quit
```
/exit
```

## Noninteractive use

You can also pipe command output to PyTTAI, input a string as a command, or read in a file.
Currently very experimental and unstable. Multiline handling is odd.

- stdin
```bash
#!/bin/bash
echo "This is a test!" | python3 main.py -c -
```
- Command Evaluation
```bash
#!/bin/bash
python3 main.py -c "/paste What is this?"
```

- File input
```bash
#!/bin/bash
python3 -c script.ptt
```
- Example of ptt script (working extension)
```
/provider switch claude
/file README.md Summarise this readme
/clear
Remind me what we were talking about again?
```

Non-interactive commands will output to stdout and can be redirected or piped as part of shell scripts.
Preliminary, but this demonstrates some of the utility behind the design.

## Other References
Code should be reasonably well documented but commands within the terminal are not as of yet.
In the docs folder is the roadmap, change log/planned changes, and general reference docs.

## License
For the moment, MIT License. If another license is found to be more permissive, it may be updated.

Download and use of PyTTAI implies no warranty of fitness for purpose and use is at your own risk.

## Contributing
If you find any issues, please log an issue within the repo and describe reproduction steps as closely as you can.
Initially collaboration will be invite only until it's more mature and it's up to at least phase 3 on the roadmap.