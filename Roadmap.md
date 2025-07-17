# Pyttai Project Status & Roadmap

*AI-native shell for developers - safe, extensible, cross-platform*
THIS IS TO BE TREATED AS MOST CURRENT - ROADMAPS IN DOCS FOLDER ARE ARCHIVE COPIES

## 🎯 Project Vision

An AI-native terminal that reimagines the command line experience. A full-featured shell where AI assistance is naturally integrated through operators, making complex tasks simple while maintaining the power and composability of traditional Unix tools. Deployable standalone or as a container for debugging, operations, and development.

## ✅ Current State (v0.2.2)

### Working Features
1. **Multi-provider AI system**
   - `LMStudioProvider` - Local models via LM Studio
   - `ClaudeProvider` - Anthropic's Claude API
   - `OpenAIProvider` - GPT-3.5/GPT-4 (requires billing)
   - Clean abstraction for adding providers
   - Context preserved across provider switches

2. **Core Commands**
   - `/help` - Show available commands
   - `/config [key=value]` - Nested configuration support
   - `/model` - List available models
   - `/provider [switch NAME]` - Manage AI providers
   - `/paste [prompt]` - Send clipboard content
   - `/file <path> [prompt]` - Read and send files
   - `clear` - Clear conversation
   - `exit` - Quit application

3. **Architecture**
   - MVC structure with plugin system
   - UTF-8 enforcement throughout
   - CommandResult standardization (partial)
   - Feature plugin system
   - Verbose mode (`-v` flag)

### Discovered Behaviors
- Models treat full conversation history as their own
- Seamless context handoff between providers
- Natural "cognitive flow" between different AI models

## 🚧 Critical Design Principles

1. **Slash commands and operators DO NOT send output to AI unless explicitly requested with `:ai`**
   ```bash
   /ls                    # Shows files to user only
   /ls :ai                # Sends file list to AI
   ```

2. **Container-First Design**
   - `/workspace` - Ephemeral read/write during session
   - `/sessions` - Persistent storage (explicit saves only)
   - All other mounts read-only by default

3. **Safe by Default**
   - No destructive operations
   - Explicit persistence via `/persist`
   - Read-only mounts for production data

---

## 📋 Development Roadmap

### Phase 1: File Operations & Container Support (Next 3-4 weeks) 🗂️

**Goal**: Implement file operations with container-aware security model

#### Core File Commands
```bash
/ls [pattern]          # List files/directories with glob support
/cd <path>             # Change working directory  
/pwd                   # Print working directory
/find <pattern>        # Recursive file search
/cat <file>            # Display file contents (rename from /file)
/persist <file> <name> # Save workspace file to /sessions
/checkout <file>       # Duplicate /data to /workspace for modification.
```

#### Container File Model
```
/workspace/            # Read/write (ephemeral)
/sessions/             # Write via /persist only
/data/                 # Read-only mount
/logs/                 # Read-only mount
/config/               # Read-only mount
```

#### Implementation Details
- Use `pathlib` for cross-platform support
- Track working directory in ChatController
- Permission checking based on path
- Glob patterns: `*.py`, `**/*.log`, `src/**/*.js`
- All commands return `CommandResult` with structured data

### Phase 2: Operator System (Weeks 5-7) 🔗

**Goal**: Enable command composition with security awareness

#### Core Operators
| Operator | Function | Example |
|----------|----------|---------|
| `:p` | Pipe output | `/ls *.log :p grep ERROR` |
| `:r` | Redirect (workspace only) | `/cat log :r /workspace/analysis.txt` |
| `:rr` | Append (workspace only) | `/ls :rr /workspace/files.txt` |
| `:c` | Read file as input | `analyze :c /data/prompt.txt` |
| `:ai` | Send to current AI | `/ls *.py :ai "review these"` |

#### Provider Operators (Available: claude, local, openai)
| Operator | Function | Notes |
|----------|----------|-------|
| `:claude` | Use Claude | Transient - doesn't change default |
| `:local` | Use local model | Transient - doesn't change default |
| `:gpt` | Use OpenAI GPT | Transient - requires billing setup |

#### Future Operator Considerations
| Operator | Function | Example |
|----------|----------|---------|
| `:s`     | Success Conditional | /find . "jim.txt" :s /cat "jim.txt" :ai Summarise |
| `:ss`    | Failure Conditional | /cat "jim.txt" :ss /find .. "jim.txt"


### Phase 3: SSH Interface & Context Preloading (Weeks 8-10) 🔐

**Goal**: Enable SSH attachment to running containers

#### Features
- SSH server mode for remote access
- Context preloading from mounted configs
- Session management across SSH connections
- Workspace isolation per connection

#### Usage Pattern
```bash
# SSH into Pyttai agent attached to app
ssh -p 2222 pyttai@app-server

# Preloaded with app context
/context                        # Shows loaded context
/ls /logs/*.log :ai "errors?"  # Analyze app logs
/persist report.md daily-check  # Save findings
```

### Phase 4: Memory Management & Production Features (Weeks 11-13) 🧠

**Goal**: Production-ready features for long-running sessions

#### Commands
```bash
/trim <n>              # Keep last n messages
/context               # Show token count and loaded contexts
/context estimate      # Estimate API costs
/compress              # AI-generated summary replacement
/workspace clear       # Clean ephemeral storage
```

#### Production Safety
- Auto-trim before limits
- Workspace size monitoring
- Session rotation
- Audit logging for /persist operations

---

## 🔧 Implementation Priorities

### Immediate Next Steps

1. **ComandResult Standardisation**
All outputs in a structured format for easy handling and AI ingestion.

2. **File Operations with Container Awareness**
```python
class FileOpsController:
    def __init__(self, chat_controller):
        self.chat = chat_controller
        self.cwd = Path("/workspace")  # Default to workspace
        self.workspace = Path("/workspace")
        self.sessions = Path("/sessions")
        self.read_only_paths = ["/data", "/logs", "/config"]
    
    def can_write(self, path: Path) -> bool:
        return path.is_relative_to(self.workspace)
    
    def list_files(self, pattern="*") -> CommandResult
    def change_directory(self, path: str) -> CommandResult
    def persist_file(self, source: str, name: str) -> CommandResult
```

3. **Refactor Command Processor**
Needs to avoid using AI unless specified. Implement :ai early?

4. **Container Detection**
```python
def detect_environment():
    if os.path.exists('/.dockerenv'):
        return "container"
    return "host"
```

---

## 🏗️ Architecture for Container Deployment

### Directory Structure (Container)
```
/app/                  # Pyttai application (read-only)
├── main.py
└── lmchat/

/workspace/            # Ephemeral workspace (read/write)

/sessions/             # Persistent storage (mounted)

/data/                 # Application data (mounted, read-only)
/logs/                 # Application logs (mounted, read-only)
/config/               # Application config (mounted, read-only)
```

### Docker Compose Example
```yaml
services:
  target-app:
    image: myapp:latest
    
  pyttai-debug:
    image: pyttai:latest
    volumes:
      - ./sessions:/sessions:rw
      - app-data:/data:ro
      - app-logs:/logs:ro
      - app-config:/config:ro
    environment:
      - PRELOAD_CONTEXT=/config/app.context
    ports:
      - "2222:22"  # SSH access
```

---

## 🐛 Known Issues

1. **OpenAI Provider** - Requires active billing
2. **Mixed Return Types** - Need CommandResult everywhere
3. **No Working Directory Tracking** - File ops assume current directory

---

## ✅ Testing Checklist

### Phase 1 (File Operations)
- [ ] Basic file listing works
- [ ] Glob patterns work
- [ ] Directory navigation respects boundaries
- [ ] Write operations limited to /workspace
- [ ] /persist saves to /sessions correctly
- [ ] Read-only mounts enforced

### Phase 2 (Container Integration)
- [ ] Container detection works
- [ ] SSH interface accessible
- [ ] Context preloading functions
- [ ] Workspace isolation per session
- [ ] No data leaks between sessions

### Phase 5: Core Utilities & Shell Features (Weeks 14-18) 🛠️

**Goal**: Build essential utilities that make Pyttai a practical daily-driver terminal

#### Text Processing
```bash
/grep <p> [files]      # Pattern matching
/sed <p> <r> [files]   # Stream editing
/awk '{print $1}'      # Field processing
/sort [options]        # Sort lines
/uniq                  # Remove duplicates
/wc                    # Word/line count
```

#### Data Processing
```bash
/json <path>           # JSON parsing/querying
/csv <file>            # CSV operations
/diff <f1> <f2>        # File comparison
/hash <file>           # Checksums
```

#### Network & System
```bash
/curl <url>            # HTTP requests
/ping <host>           # Network test
/ps                    # Process list
/env                   # Environment vars
/which <cmd>           # Find executables
```

All utilities:
- Work with operators (`:p`, `:ai`, etc.)
- Return structured CommandResult
- Cross-platform implementation
- AI-enhancement ready
- Clean Python implementation, not trying to replicate shell applications.
- Output in a standard object format for handling by AI and scripts
- Consider making it less confusing than powershell object handling... 
- :str pipe to only output the plaintext body portion of the object to stdout?

### Phase 6: Advanced Shell Features (Weeks 19-24) 🚀

**Goal**: Features that surpass traditional shells

#### AI-Enhanced Utilities
```bash
/explain <command>     # Explain any command
/suggest              # Context-aware suggestions
/optimize <script>    # Improve code/commands
/translate <fr> <to>  # Language translation
```

#### Package Management
```bash
/install <util>       # Add new utilities
/update               # Update Pyttai
/plugin add <name>    # Community extensions
```

---

## Long-Term Vision 🌟

### Pyttai as Primary Shell
- Full POSIX compatibility layer
- Native OS integration
- Performance optimizations
- Rich TUI elements

### Pyttai OS
- Minimal Linux distro with Pyttai as init
- AI-native system management
- Natural language configuration
- Containerized by default

### Principle Consistency
- Least Privilege First Principle
- AI use is explicit unless it's a regular conversation without commands
- Useful tool, not a brain replacement for fools

### Use Cases
1. **Development** - AI pair programming in terminal
2. **Operations** - Smart system management
3. **Data Science** - Pipeline processing with AI
4. **Education** - Learn by conversation
5. **Debugging** - Attach to any system
6. **Automation** - Natural language scripts