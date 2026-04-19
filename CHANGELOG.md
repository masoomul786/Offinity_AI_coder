# Offinity_AI Changelog

## v2.1.0 — 2026-03-08 (9.5/10 Release)

### 🎨 UI — Monaco Editor (VS Code in the browser)
- Replaced plain `<pre>` code viewer with full Monaco editor
- Syntax highlighting for Python, JS/TS, HTML, CSS, SQL, Rust, Go, C# and 20+ more
- Line numbers, code folding, bracket pair colorization, minimap
- Live token streaming directly into Monaco during generation
- **Monaco diff view** — side-by-side before/after comparison (`⟷ Diff` button)
- Custom `offinity_ai-dark` theme matching the GitHub Dark palette

### 👁 Live Preview
- HTML/CSS/JS files show a split-pane rendered preview alongside the editor
- Preview updates automatically when generation completes
- CSS previewer wraps styles in a demo page (headings, buttons, inputs)
- JS sandbox mode for quick script testing
- Toggle with `👁 Preview` button or `Ctrl+P`

### ⌨️ Keyboard Shortcuts
- `Ctrl+Enter` — Generate / Add feature
- `Ctrl+S` — Save direct edit
- `Ctrl+E` — Toggle edit mode
- `Ctrl+Shift+Z` — Git undo (project-level)
- `Ctrl+P` — Toggle live preview
- `Escape` — Close modals, exit edit/diff/preview modes

### 📊 Token Progress Counter
- Shows live token count during generation (`1,240 tokens`)
- Progress bar fills proportionally to estimated file size
- Fades out 3 seconds after generation completes

### 🧠 Backend — Context Quality
- **tree-sitter support** in `context_builder.py` — dramatically better JS/TS extraction
  - Handles template literals, destructuring, default exports correctly
  - Install: `pip install tree-sitter tree-sitter-javascript tree-sitter-python`
  - Graceful fallback to enhanced regex if not installed
- **Aider-style repo map** (`core/repomap.py`) — cross-file dependency awareness
  - Shows which functions each file defines and which files import from which
  - Optional networkx dependency graph: `pip install networkx`
  - Injected automatically for projects with 3+ files
- **HTML element ID extraction** — all `id=` attributes now extracted for JS cross-reference
- **HTML/JS cross-reference validation** — debugger catches `getElementById('wrong-id')` mismatches
- **html5lib validation** in debugger (optional): `pip install html5lib`

### 🤖 Dynamic Prompts by Model Size
- `Config.model_family()` detects: `reasoning` | `large` | `small` | `standard`
- Reasoning models (DeepSeek-R1, QwQ, o1): shorter prompts, less hand-holding
- Small 7B models: extra reminders prepended (DOMContentLoaded, null checks, etc.)
- `core/planner.get_lang_system()` now accepts `model_family` parameter

### 📝 Edit History Memory
- `FileManager.append_edit_history()` records each edit to `.offinity_ai.json`
- `FileManager.get_edit_history_summary()` returns compact summary for LLM injection
- Keeps last 10 edits — prevents AI from undoing its own previous changes

### 📦 Updated Model Recommendations (`.env.example`)
- **Ollama/LM Studio best models for 2025:**
  - `qwen2.5-coder:32b` — top open-source coder, beats GPT-4 on HumanEval
  - `qwen2.5-coder:7b` — fast + strong, 256k context
  - `codestral:22b` — 86.6% HumanEval, fill-in-middle
  - `deepseek-coder-v2:16b` — excellent reasoning + code
- Updated `SC_CONTEXT_WINDOW` default to 8192
- Documented free OpenRouter models

### 🧪 Tests
- Added 39 new tests in `tests/test_new_features.py`
- **Total: 158 tests, all passing**
- Covers: model_family, dynamic prompts, repo map, edit history, HTML validation

### 🔧 Dependencies
- All new deps are **optional** — zero breaking changes
- `requirements.txt` documents optional installs with comments
- `pyproject.toml` `[dev]` extras updated
