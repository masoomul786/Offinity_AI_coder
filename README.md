# ⚡ Offinity_AI

[![Tests](https://img.shields.io/badge/tests-119%20passing-brightgreen)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Providers](https://img.shields.io/badge/providers-LM%20Studio%20%7C%20Ollama%20%7C%20OpenAI%20%7C%20Anthropic%20%7C%20OpenRouter-orange)](#supported-providers)

**Production-grade AI code generator. Works offline with local models (LM Studio, Ollama) and with cloud APIs (OpenAI, Anthropic, OpenRouter). No subscription. No cloud dependency. Your code stays on your machine.**

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/yourusername/offinity_ai
cd offinity_ai
pip install -r requirements.txt
```

Or install as a package (adds `offinity_ai` command):
```bash
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set SC_PROVIDER and any required API keys
```

### 3. Run

**Web UI (recommended):**
```bash
python main.py --web
# Open: http://localhost:7432
```

**CLI:**
```bash
python main.py
```

**One-shot generation:**
```bash
python main.py --new "todo app with dark mode and local storage"
```

---

## Supported Providers

| Provider | Setup | Cost |
|----------|-------|------|
| **LM Studio** | Download app + load a model | Free |
| **Ollama** | `ollama pull codellama:13b` | Free |
| **OpenRouter** | Get API key at openrouter.ai | Free tier available |
| **OpenAI** | Set `OPENAI_API_KEY` | Paid |
| **Anthropic** | Set `ANTHROPIC_API_KEY` | Paid |

### Recommended Local Models (8B–13B)
- `deepseek-coder-v2-lite-instruct` — best for code
- `qwen2.5-coder:7b` — fast, strong at code (Ollama)
- `codellama:13b` — reliable, widely tested (Ollama)
- `llama3:8b` — good general purpose fallback

---

## CLI Commands

```
/new <description>         → Generate a new project from scratch
/add <feature>             → Add a feature, page, or backend to current project
/edit <file> <change>      → Edit a specific file
/import <folder> [name]    → Import any existing codebase
/test                      → Detect test framework and run your tests
/test --fix                → Run tests + AI auto-repairs failures (up to 3 rounds)
/run                       → Execute the project entry point
/undo                      → Undo last AI commit (git-powered, unlimited history)
/undo <filename>           → Restore a single file to last committed state
/undo <n>                  → Undo last n commits (e.g. /undo 3)
/log                       → Full git commit history with timestamps
/diff [file]               → Real unified diff of changes since last commit
/files                     → List project files
/view <filename>           → Show file contents
/plan                      → Show current project plan
/download                  → Create project zip
/load [<project>]          → Load a saved project
/projects                  → List all saved projects
/status                    → Check LLM connection
/setup                     → Configure provider interactively
/web                       → Launch web UI
/help                      → Show all commands
/exit                      → Quit
```

---

## Key Features

### 🧠 Smart for Small Models
Designed specifically for 8B–13B local models. Uses semantic context compression, dynamic token budgeting, and patch-based editing to stay within tight context windows.

### 🔄 Patch-Mode Editing
Files over 120 lines are edited via surgical `PATCH:/OLD:/NEW:/END_PATCH` diffs instead of full rewrites — 60–80% fewer output tokens, no more truncated files.

### 💭 Think-Tag Filtering
Built-in streaming filter strips `<think>...</think>` reasoning blocks from DeepSeek-R1, Qwen3, and other reasoning models in real time, preventing corrupt output.

### 🔀 Git-Powered History
Every AI generation commits to a local git repo. `/log` shows full history, `/undo` rolls back commits, `/undo app.py` restores one file, `/diff` shows exactly what changed.

### 🧪 Test Runner + Auto-Fix Loop
Supports pytest, npm test, cargo test, go test, Maven, and more. `/test --fix` runs tests, feeds failures to the AI, auto-repairs, and re-runs — up to 3 rounds.

### 📥 Import Any Project
Drop Offinity_AI onto any existing codebase with `/import ~/my-existing-app`. It scans files, generates a plan using AI, and makes everything available to `/add`, `/edit`, `/test`.

### 🔗 Full-Stack Linking
When you add a backend or database to a frontend project, Offinity_AI auto-updates form actions, API fetch calls, and route handlers to wire everything together correctly.

---

## Running Tests

```bash
# With pytest
pytest tests/ -v

# With stdlib unittest (zero dependencies)
python -m unittest discover tests/ -v
```

**119 tests** covering: LLM output processing, patch application, FileManager, Config thread-safety, token budgets, and the exception hierarchy.

---

## Environment Variables

```bash
SC_PROVIDER=lmstudio          # lmstudio|ollama|openai|anthropic|openrouter
SC_URL=http://localhost:1234/v1  # LM Studio URL
SC_MODEL=                      # Model name (auto-detect if blank)
SC_MAX_TOKENS=8192             # Output tokens per file
SC_TEMPERATURE=0.1             # Lower = more reliable code
SC_RETRIES=3                   # Auto-retry on failure
SC_CONTEXT_WINDOW=4096         # CRITICAL: must match your model's context size
SC_PORT=7432                   # Web UI port
SC_LOG_LEVEL=INFO              # DEBUG|INFO|WARNING|ERROR
```

## Tips for Best Results with Local Models

1. **Be specific** — detailed prompts produce better results
2. **Set context window correctly** — `SC_CONTEXT_WINDOW` must match your model's n_ctx setting
3. **Use low temperature** — `SC_TEMPERATURE=0.1` gives more deterministic output
4. **Increase retries** — `SC_RETRIES=3` automatically retries failed generations
5. **Use /test --fix** after generation — catches and auto-repairs common LLM mistakes

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, architecture, and how to add new providers.
