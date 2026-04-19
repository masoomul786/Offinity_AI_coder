# Contributing to Offinity_AI

Thank you for your interest in contributing! This document covers how to get set up, run tests, and submit changes.

---

## Development Setup

```bash
git clone https://github.com/yourusername/offinity_ai
cd offinity_ai
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env — set your provider and API key
```

---

## Running Tests

```bash
# With pytest (recommended)
pytest tests/ -v

# With stdlib unittest (no install needed)
python -m unittest discover tests/ -v
```

Tests live in `tests/`. Each file maps to one module:

| Test file | Covers |
|---|---|
| `test_llm.py` | `ThinkTagFilter`, `strip_think_tags`, `clean_output` |
| `test_patch.py` | `_apply_patches` — the patch-based code editor |
| `test_files.py` | `FileManager` — project CRUD, backup/undo |
| `test_config.py` | `Config.validate()`, thread-safety, budgets |
| `test_token_utils.py` | Token estimation and budget calculations |
| `test_errors.py` | Exception hierarchy |

---

## Project Structure

```
Offinity_AI/
├── main.py               — CLI entry point and all CLI commands
├── config.py             — Centralised configuration (env vars)
├── core/
│   ├── llm.py            — Multi-provider LLM client
│   ├── planner.py        — Project planner (file list, language detection)
│   ├── generator.py      — File-by-file code generator + patch editor
│   ├── files.py          — FileManager: project CRUD, backup, zip
│   ├── git_manager.py    — Git integration (auto-commit, undo, log, diff)
│   ├── test_runner.py    — Test framework detection + auto-fix loop
│   ├── importer.py       — Import existing codebases
│   ├── debugger.py       — Post-generation syntax checker
│   ├── context_builder.py— Semantic context extraction for large projects
│   ├── sync.py           — Project consistency analyser
│   ├── token_utils.py    — Token estimation and budget helpers
│   └── errors.py         — Typed exception hierarchy
├── ui/
│   ├── web.py            — Flask routes (web UI backend)
│   ├── templates/
│   │   └── index.html    — Web UI (HTML/CSS/JS frontend)
│   ├── visual_editor.py  — Visual editor page
│   └── terminal.py       — CLI colour/formatting helpers
└── tests/                — Test suite (unittest + pytest compatible)
```

---

## Key Design Decisions

**Why patch-mode editing?** Files over 120 lines are edited via `PATCH:/OLD:/NEW:/END_PATCH` diffs instead of full rewrites. This cuts output token usage by 60–80% for large files and avoids context window overflow on small models.

**Why `ThinkTagFilter`?** Reasoning models (DeepSeek-R1, Qwen3) emit `<think>...</think>` chain-of-thought before the actual code. Without filtering, that text corrupts generated files. The filter works token-by-token during streaming so it adds zero latency.

**Why no async?** The target audience is solo developers running locally. Synchronous streaming with threading (used in the web UI) is simpler to debug and avoids the asyncio complexity that confuses small model outputs.

---

## Adding a New LLM Provider

1. Add a new client class in `core/llm.py` inheriting from `LLMClient`
2. Implement `generate()`, `health()`, and `list_models()`
3. Add the provider key to `VALID_PROVIDERS` in `config.py`
4. Add the config fields (URL, API key, model) to `Config`
5. Add a case in `create_client()` factory function
6. Add the provider to the setup wizard in `main.py` (`_PROVIDER_INFO`)
7. Document it in `README.md` and `.env.example`

---

## Code Style

- Python 3.10+ — use `from __future__ import annotations` for forward refs
- `logger = logging.getLogger(__name__)` in every module — no `print()` in library code
- Typed exceptions from `core/errors.py` — never raise bare `Exception`
- Format with `black` if available (not enforced)

---

## Submitting a PR

1. Fork the repo and create a feature branch
2. Add or update tests for your change
3. Run the test suite — all 119 tests must pass
4. Open a PR with a clear description of what changed and why
