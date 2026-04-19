#!/usr/bin/env python3
"""
Offinity_AI - Production-grade AI Code Generator
Optimized for 8B-13B local models (LM Studio, Ollama) and cloud APIs.

Usage:
  python main.py              → Interactive CLI
  python main.py --web        → Web UI (http://localhost:5000)
  python main.py --new "..."  → Generate project directly
  python main.py --status     → Check connection
"""
from __future__ import annotations
import sys
import os
from pathlib import Path

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

# Verify requests is installed
try:
    import requests
except ImportError:
    print("Missing 'requests'. Run: pip install requests")
    sys.exit(1)

from config import Config
from core.llm import create_client
from core.planner import Planner
from core.generator import Generator
from core.files import FileManager
from core import git_manager
from core.importer import import_project
from core import test_runner
from ui.terminal import (
    banner, ok, err, warn, info, step, section,
    print_plan, print_file_result, print_diff, help_menu, prompt_user,
    bold, cyan, green, red, dim, magenta,
)


cfg          = Config()
cfg.configure_logging()          # set up logging once at startup
cfg.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
file_manager = FileManager(cfg.PROJECTS_DIR)


def build_client():
    return create_client(cfg)


def check_connection(client) -> bool:
    from core.errors import LLMConnectionError as LLMConnErr
    step("Checking LLM connection...")
    try:
        healthy, info_str = client.health()
    except LLMConnErr as e:
        healthy, info_str = False, str(e)
    except Exception as e:
        healthy, info_str = False, str(e)

    if healthy:
        ok(f"Connected — {info_str}")
    else:
        err(f"Connection failed — {info_str}")
        warn(f"Provider: {cfg.PROVIDER}")
        if cfg.PROVIDER in ("lmstudio",):
            warn("Make sure LM Studio is running with a model loaded.")
            warn(f"URL: {cfg.LM_STUDIO_URL}")
        elif cfg.PROVIDER == "ollama":
            warn("Make sure Ollama is running: ollama serve")
            warn(f"URL: {cfg.OLLAMA_URL}")
    return healthy


# ── Provider setup wizard ─────────────────────────────────────────────────────

_PROVIDER_INFO = {
    "lmstudio":   ("LM Studio",   "Local — free, needs LM Studio app running"),
    "ollama":     ("Ollama",      "Local — free, needs `ollama serve` running"),
    "openrouter": ("OpenRouter",  "Cloud — free tier available, needs API key"),
    "openai":     ("OpenAI",      "Cloud — paid, needs API key"),
    "anthropic":  ("Anthropic",   "Cloud — paid, needs API key"),
}


def run_setup_wizard() -> "LLMClient | None":
    """
    Interactive provider setup wizard.
    Shown when no connection is detected so users can configure any provider
    without editing files manually. Returns a new client if configured, or
    None if the user skips.
    """
    print()
    print(f"  {bold(cyan('─' * 54))}")
    print(f"  {bold('  Provider Setup Wizard')}")
    print(f"  {dim('  Configure your LLM provider to get started.')}")
    print(f"  {bold(cyan('─' * 54))}")
    print()

    # Show provider menu
    providers = list(_PROVIDER_INFO.keys())
    print(f"  {bold('Available providers:')}")
    for i, key in enumerate(providers, 1):
        name, desc = _PROVIDER_INFO[key]
        marker = green("✓ current") if key == cfg.PROVIDER else ""
        print(f"    {bold(str(i))}) {cyan(name):<16} {dim(desc)}  {marker}")
    print(f"    {bold('s')}) {dim('Skip — I will configure .env manually')}")
    print()

    choice = prompt_user("  Select provider [1-5 or s]: ").strip().lower()
    if choice == "s" or choice == "":
        warn("Skipping setup. You can type /setup anytime or edit .env manually.")
        return None

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(providers)):
            warn("Invalid choice — skipping setup.")
            return None
    except ValueError:
        warn("Invalid choice — skipping setup.")
        return None

    provider = providers[idx]
    updates  = {"SC_PROVIDER": provider}

    # Provider-specific fields
    if provider == "lmstudio":
        url = prompt_user(f"  LM Studio URL [{cfg.LM_STUDIO_URL}]: ").strip()
        if url:
            updates["SC_URL"] = url
        model = prompt_user("  Model name (blank = auto-detect): ").strip()
        if model:
            updates["SC_MODEL"] = model
        print()
        warn("Make sure LM Studio is open and a model is loaded.")

    elif provider == "ollama":
        url = prompt_user(f"  Ollama URL [{cfg.OLLAMA_URL}]: ").strip()
        if url:
            updates["OLLAMA_URL"] = url
        model = prompt_user(f"  Model name [{cfg.OLLAMA_MODEL}]: ").strip()
        if model:
            updates["OLLAMA_MODEL"] = model
        print()
        warn("Make sure Ollama is running: ollama serve")

    elif provider == "openrouter":
        key = prompt_user("  OpenRouter API key (sk-or-...): ").strip()
        if key:
            updates["OPENROUTER_API_KEY"] = key
        default_model = cfg.OPENROUTER_MODEL
        model = prompt_user(f"  Model [{default_model}]: ").strip()
        if model:
            updates["OPENROUTER_MODEL"] = model
        if not key:
            warn("API key not entered — connection will likely fail.")

    elif provider == "openai":
        key = prompt_user("  OpenAI API key (sk-...): ").strip()
        if key:
            updates["OPENAI_API_KEY"] = key
        model = prompt_user(f"  Model [{cfg.OPENAI_MODEL}]: ").strip()
        if model:
            updates["OPENAI_MODEL"] = model

    elif provider == "anthropic":
        key = prompt_user("  Anthropic API key (sk-ant-...): ").strip()
        if key:
            updates["ANTHROPIC_API_KEY"] = key
        model = prompt_user(f"  Model [{cfg.ANTHROPIC_MODEL}]: ").strip()
        if model:
            updates["ANTHROPIC_MODEL"] = model

    # Save and apply
    if cfg.save_to_env(updates):
        ok(f"Settings saved to .env")
    else:
        warn("Could not write .env — settings applied for this session only.")

    # Build and test the new client
    new_client = build_client()
    ok(f"Switched to provider: {bold(cyan(provider.upper()))}")
    print()
    working = check_connection(new_client)
    if working:
        ok("All good! You can start generating projects.")
    else:
        warn("Still not connected — check your settings and try /setup again.")
    return new_client


# ── Session state ─────────────────────────────────────────────────────────────

class Session:
    """Holds the current project state during a CLI session."""
    def __init__(self):
        self.project_name: str | None = None
        self.plan: dict = {}
        self.files: dict[str, str] = {}   # {filename: current_code}

    @property
    def active(self) -> bool:
        return self.project_name is not None

    def load_project(self, name: str) -> bool:
        """Load an existing project from disk into the session."""
        meta = file_manager.load_meta(name)
        if meta is None:
            return False
        self.project_name = name
        self.plan = meta.get("plan", {})
        if "request" not in self.plan:
            self.plan["request"] = meta.get("request", "")
        self.files = file_manager.load_all_files(name)
        return True

    def save_meta(self):
        if self.active:
            file_manager.save_meta(self.project_name, {
                "title":   self.plan.get("title", self.project_name),
                "request": self.plan.get("request", ""),
                "plan":    self.plan,
            })

    def sync_files_from_disk(self):
        """Re-read all project files from disk (keeps session in sync after edits)."""
        if self.active:
            self.files = file_manager.load_all_files(self.project_name)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_new(client, session: Session, description: str, server_type: str = ""):
    """Generate a new project from description."""
    if not description.strip():
        err("Please provide a description. Example: /new todo app with dark mode")
        return

    planner   = Planner(client)
    generator = Generator(client, max_retries=cfg.MAX_RETRIES)

    step("Planning project...")
    plan = planner.plan(description, server_type=server_type)
    if server_type:
        plan["server_type"] = server_type
    print_plan(plan)

    title     = plan.get("title", description[:40])
    base_name = file_manager.slugify(title)
    proj_name = file_manager.unique_name(base_name)
    proj_dir  = file_manager.create_project(proj_name)

    plan["request"] = description

    step(f"Generating {len(plan['files'])} files...")
    results = generator.generate_project(
        plan         = plan,
        user_request = description,
        project_dir  = proj_dir,
        on_file_done = lambda fname, code, status: print_file_result(
            fname, len(code.splitlines()), status == "ok"
        ),
    )

    session.project_name = proj_name
    session.plan         = plan
    session.files        = results

    from datetime import datetime
    file_manager.save_meta(proj_name, {
        "title":   title,
        "request": description,
        "plan":    plan,
        "date":    datetime.now().strftime("%b %d"),
    })

    # Git: init repo and commit initial generation
    if git_manager.init(proj_dir):
        git_manager.commit(proj_dir, f"initial: {title[:60]}")
        info(f"Git: initialized — use /log, /undo, /diff for history")

    print()
    if results:
        ok(f"Project '{proj_name}' created with {len(results)} files")
        info(f"Location: {proj_dir}")
        info("Tip: Use /add <feature> to expand, /edit <file> <change> to modify, /test to run tests.")
    else:
        err("No files were generated. Check your LLM connection and model.")


def _fi_from_plan(fname: str, plan: dict) -> dict:
    """Get or create file_info dict for a filename from the plan."""
    fi = next((f for f in plan.get("files", []) if f["filename"] == fname), None)
    if fi:
        return fi
    ext = fname.rsplit(".", 1)[-1].lower()
    lang = {"html":"html","css":"css","js":"javascript","py":"python","sql":"sql","ts":"typescript","jsx":"jsx"}.get(ext, ext)
    return {"filename": fname, "lang": lang, "purpose": ""}


def cmd_add(client, session: Session, feature: str):
    """
    Add a feature, page, backend server, or database to the current project.
    - Backend/server request → plan_add_backend() with auto-linking
    - Database request       → plan_add_database() with schema auto-linking
    - New page request       → plan_new_page() with cross-link nav
    - Normal feature         → affected_files() + patch/rewrite
    """
    if not feature.strip():
        err("Please describe the feature. Example: /add dark mode toggle")
        return

    session.sync_files_from_disk()

    generator = Generator(client, max_retries=cfg.MAX_RETRIES, cfg=cfg)
    planner   = Planner(client)
    proj_dir  = file_manager.project_path(session.project_name)

    file_list = list(session.files.keys())
    if not file_list:
        err("No files found in project. Try /files to check.")
        return

    # Priority: backend > database > new_page > feature (consistent with web.py)
    is_backend    = planner.is_backend_request(feature, file_list)
    is_database   = (not is_backend) and planner.is_database_request(feature, file_list)
    is_new_page   = (not is_backend and not is_database) and planner.is_new_page_request(feature, file_list)
    needs_bk_link = is_new_page and planner.new_page_needs_backend_link(feature, file_list)

    # ── Backend / Database ──────────────────────────────────────────────
    if is_backend or is_database:
        kind = "backend server" if is_backend else "database"
        step(f"Planning {kind} with auto-linking…")

        if is_backend:
            stack_plan     = planner.plan_add_backend(file_list, feature, session.plan, session.files)
            stack_manifest = stack_plan.get("stack_manifest", {})
        else:
            stack_plan     = planner.plan_add_database(file_list, feature, session.plan, session.files)
            stack_manifest = session.plan.get("stack_manifest", {})
            stack_manifest["db_tables"] = stack_plan.get("db_tables", [])

        new_files       = stack_plan.get("new_files", [])
        files_to_update = stack_plan.get("files_to_update", [])
        session.plan["stack_manifest"] = stack_manifest
        for nf in new_files:
            if not any(f["filename"] == nf["filename"] for f in session.plan.get("files", [])):
                session.plan.setdefault("files", []).append(nf)

        info(f"New files: {[f['filename'] for f in new_files]}")
        info(f"Updating: {files_to_update}")

        changed = 0
        all_to_process = (
            [(f, True) for f in files_to_update if f in session.files] +
            [(fi["filename"], False) for fi in new_files]
        )
        for fname, is_existing in all_to_process:
            fi = _fi_from_plan(fname, session.plan)
            if is_existing:
                file_manager.backup_file(session.project_name, fname)
            old_code = session.files.get(fname, "")
            instr = feature if not is_existing else (
                f"Update this page for the new {kind}. "
                f"Update form actions / fetch() calls to use the correct API routes. "
                f"Keep all existing content."
            )
            print(f"\n  {'Updating' if is_existing else 'Creating'} {fname} ...")
            new_code = generator.regenerate_file(
                plan=session.plan, file_info=fi,
                user_request=session.plan.get("request", feature),
                generated=session.files, extra_instruction=instr,
                project_dir=proj_dir, stack_manifest=stack_manifest,
            )
            if new_code:
                session.files[fname] = new_code
                print_file_result(fname, len(new_code.splitlines()), True)
                if is_existing: print_diff(fname, old_code, new_code)
                changed += 1
            else:
                print_file_result(fname, 0, False)

        print()
        ok(f"{kind.title()} added. {changed}/{len(all_to_process)} files created/updated.")
        info("Use /undo to revert if something went wrong.")
        session.save_meta()
        return

    # ── New page ────────────────────────────────────────────────────────
    if is_new_page:
        step(f"Planning new page with cross-links…")
        manifest     = session.plan.get("page_manifest", [])
        page_plan    = planner.plan_new_page(file_list, feature, manifest)
        new_pages    = page_plan.get("new_pages", [])
        to_update    = page_plan.get("pages_needing_link_update", [])
        new_manifest = page_plan.get("page_manifest", manifest)

        session.plan["page_manifest"] = new_manifest
        for np in new_pages:
            if not any(f["filename"] == np["filename"] for f in session.plan.get("files", [])):
                session.plan.setdefault("files", []).append(np)

        info(f"New pages: {[p['filename'] for p in new_pages]} | Updating nav in: {to_update}")
        changed = 0
        all_pg = [(_fi_from_plan(f, session.plan), True) for f in to_update] + [(np, False) for np in new_pages]
        for fi, is_existing in all_pg:
            fname = fi["filename"]
            if is_existing:
                file_manager.backup_file(session.project_name, fname)
            old_code = session.files.get(fname, "")
            instr = ""
            if is_existing:
                instr = (f"Update nav to include links to: {', '.join([p['filename'] for p in new_pages])}. "
                         f"Keep all existing content.")
            print(f"\n  {'Updating nav in' if is_existing else 'Creating'} {fname} ...")
            new_code = generator.regenerate_file(
                plan=session.plan, file_info=fi,
                user_request=session.plan.get("request", feature),
                generated=session.files, extra_instruction=instr,
                project_dir=proj_dir, page_manifest=new_manifest,
            )
            if new_code:
                session.files[fname] = new_code
                print_file_result(fname, len(new_code.splitlines()), True)
                if is_existing: print_diff(fname, old_code, new_code)
                changed += 1
            else:
                print_file_result(fname, 0, False)
        # ── If pages need backend routes too, update the server ───────────
        if needs_bk_link:
            server_files = [
                f for f in file_list
                if f in ("app.py", "server.py", "server.js", "index.js")
            ]
            if server_files:
                step(f"Updating server with routes for new pages…")
                stack_manifest = session.plan.get("stack_manifest", {})
                for sf in server_files:
                    fi_sv = _fi_from_plan(sf, session.plan)
                    file_manager.backup_file(session.project_name, sf)
                    new_page_names = [p["filename"] for p in new_pages]
                    route_instr = (
                        f"Add API routes for these new pages: {', '.join(new_page_names)}.\n"
                        f"Keep ALL existing routes and code."
                    )
                    print(f"\n  Updating {sf} ...")
                    new_sv = generator.regenerate_file(
                        plan=session.plan, file_info=fi_sv,
                        user_request=session.plan.get("request", feature),
                        generated=session.files, extra_instruction=route_instr,
                        project_dir=proj_dir, stack_manifest=stack_manifest,
                    )
                    if new_sv:
                        session.files[sf] = new_sv
                        print_file_result(sf, len(new_sv.splitlines()), True)
                    else:
                        print_file_result(sf, 0, False)

        print()
        ok(f"Page added. {changed}/{len(all_pg)} files updated.")
        info("Use /undo to revert if something went wrong.")
        session.save_meta()
        return

    # ── Normal feature add ──────────────────────────────────────────────
    step(f"Determining affected files for: {feature}")
    affected = planner.affected_files(file_list, feature)
    info(f"Affected files: {', '.join(affected)}")

    if not affected:
        warn("No files identified as needing changes.")
        return

    changed = 0
    for fname in affected:
        fi = _fi_from_plan(fname, session.plan)
        file_manager.backup_file(session.project_name, fname)

        print(f"\n  Updating {fname} ...")
        old_code  = session.files.get(fname, "")
        n_lines   = len(old_code.splitlines())
        instruction = (
            f"ADD THIS FEATURE to the existing code: {feature}\n"
            f"Keep all existing functionality. Only add/modify what is needed."
        )
        if n_lines >= 80:
            info(f"  {fname} is {n_lines} lines → using patch mode (outputs diffs only)")

        new_code = generator.regenerate_file(
            plan              = session.plan,
            file_info         = fi,
            user_request      = session.plan.get("request", feature),
            generated         = session.files,
            extra_instruction = instruction,
            project_dir       = proj_dir,
            stack_manifest    = session.plan.get("stack_manifest"),
            page_manifest     = session.plan.get("page_manifest", []),
        )

        if new_code:
            session.files[fname] = new_code
            print_file_result(fname, len(new_code.splitlines()), True)
            print_diff(fname, old_code, new_code)
            changed += 1
        else:
            print_file_result(fname, 0, False)

    if changed:
        session.save_meta()


def cmd_edit(client, session: Session, args: str):
    """Edit a specific file: /edit filename.ext what to change"""
    parts = args.strip().split(" ", 1)
    if len(parts) < 2:
        err("Usage: /edit <filename> <what to change>")
        return

    fname, change = parts[0], parts[1]

    session.sync_files_from_disk()

    backed_up = file_manager.backup_file(session.project_name, fname)
    if not backed_up:
        warn(f"Could not backup {fname} (file may not exist yet — will create it)")

    old_code = session.files.get(fname, "")

    fi = next((f for f in session.plan.get("files", []) if f["filename"] == fname), None)
    if not fi:
        ext_to_lang = {"html": "html", "css": "css", "js": "javascript", "py": "python"}
        ext = fname.rsplit(".", 1)[-1].lower()
        fi = {"filename": fname, "lang": ext_to_lang.get(ext, ext), "purpose": ""}

    step(f"Editing {fname}...")
    generator = Generator(client, max_retries=cfg.MAX_RETRIES, cfg=cfg)
    proj_dir  = file_manager.project_path(session.project_name)

    # Pass stack_manifest and page_manifest so the LLM preserves API connections,
    # form actions, and nav links when editing frontend files in fullstack projects.
    new_code = generator.regenerate_file(
        plan              = session.plan,
        file_info         = fi,
        user_request      = session.plan.get("request", ""),
        generated         = session.files,
        extra_instruction = change,
        project_dir       = proj_dir,
        stack_manifest    = session.plan.get("stack_manifest"),
        page_manifest     = session.plan.get("page_manifest", []),
    )

    if new_code:
        session.files[fname] = new_code
        ok(f"{fname} updated ({len(new_code.splitlines())} lines)")
        print_diff(fname, old_code, new_code)
        # Git commit
        proj_dir = file_manager.project_path(session.project_name)
        git_manager.commit(proj_dir, f"edit {fname}: {change[:60]}")
        info("Use /undo to revert this change.")
        session.save_meta()
    else:
        err(f"Failed to edit {fname}")


def cmd_undo(session: Session, filename: str = "", steps: int = 1):
    """
    Undo using git history (preferred) or file backups (fallback).

    /undo           — undo last commit (all files)
    /undo script.js — restore just this file to last committed state
    /undo 2         — undo last 2 commits
    """
    if not session.active:
        warn("No active project.")
        return

    proj_dir = file_manager.project_path(session.project_name)

    # Try git undo first
    if git_manager.is_available() and (proj_dir / ".git").exists():
        if filename and not filename.isdigit():
            # Single-file git restore
            step(f"Restoring {filename} from git history...")
            success, msg = git_manager.undo_file(proj_dir, filename)
            if success:
                new_content = file_manager.read_file(session.project_name, filename)
                if new_content:
                    old_code = session.files.get(filename, "")
                    session.files[filename] = new_content
                    ok(msg)
                    print_diff(filename, old_code, new_content)
                return
            else:
                warn(f"Git restore failed: {msg} — trying file backup...")
        else:
            # Multi-commit undo
            n = int(filename) if filename and filename.isdigit() else steps
            step(f"Undoing last {n} commit(s) via git...")
            success, msg = git_manager.undo(proj_dir, n)
            if success:
                session.sync_files_from_disk()
                ok(msg)
                info(f"Project restored to {n} commit(s) ago.")
                return
            else:
                warn(f"Git undo failed: {msg}")
                return

    # Fallback: file-based backup system
    if filename and not filename.isdigit():
        step(f"Undoing {filename}...")
        old_code = session.files.get(filename, "")
        restored = file_manager.restore_backup(session.project_name, filename)
        if restored is not None:
            session.files[filename] = restored
            ok(f"{filename} restored to previous version")
            print_diff(filename, old_code, restored)
        else:
            warn(f"No backup found for {filename}")
    else:
        available = file_manager.list_backups(session.project_name)
        if not available:
            warn("No backups available for this project.")
            return
        section("Available undos")
        for f in available:
            print(f"  {cyan(f)}")
        print()
        info("Usage: /undo <filename>  — to restore a specific file")


def cmd_diff(session: Session, filename: str):
    """Show diff between current file and its last backup."""
    if not filename:
        err("Usage: /diff <filename>")
        return

    current = file_manager.read_file(session.project_name, filename)
    if current is None:
        err(f"File not found: {filename}")
        return

    backup_result = file_manager.get_last_backup(session.project_name, filename)
    if backup_result is None:
        warn(f"No backup found for {filename} — no diff available.")
        return

    _, backup_content = backup_result
    print_diff(filename, backup_content, current)


def cmd_load(session: Session, project_name: str):
    """Load an existing project into the session."""
    projects = file_manager.list_projects()

    if not project_name:
        if not projects:
            warn("No saved projects found.")
            return
        section("Saved Projects")
        for p in projects:
            meta  = file_manager.load_meta(p)
            title = meta.get("title", p) if meta else p
            req   = meta.get("request", "")[:50] if meta else ""
            files = file_manager.list_files(p)
            print(f"  {cyan(p.ljust(30))} {dim(f'{len(files)} files')}  {dim(req)}")
        print()
        info("Usage: /load <project-name>")
        return

    if project_name not in projects:
        err(f"Project '{project_name}' not found. Use /projects to list all.")
        return

    step(f"Loading project '{project_name}'...")
    if session.load_project(project_name):
        ok(f"Loaded '{project_name}' — {len(session.files)} files in memory")
        if session.plan:
            print_plan(session.plan)
    else:
        err(f"Failed to load project '{project_name}' (no metadata found).")
        warn("The project directory may exist but was not created by Offinity_AI.")


def cmd_projects(session: Session):
    """List all saved projects."""
    projects = file_manager.list_projects()
    if not projects:
        warn("No saved projects yet. Use /new to create one.")
        return
    section("Saved Projects")
    for p in projects:
        marker = green("*") if session.project_name == p else " "
        meta   = file_manager.load_meta(p)
        title  = meta.get("title", p) if meta else p
        files  = file_manager.list_files(p)
        print(f"  {marker} {cyan(p.ljust(32))} {dim(f'{len(files)} files')}  {dim(title)}")
    print()
    info("Use /load <n> to resume a project.")


def cmd_files(session: Session):
    files = file_manager.list_files(session.project_name)
    if not files:
        warn("No files in project")
        return
    section(f"Files in '{session.project_name}'")
    for f in files:
        content = file_manager.read_file(session.project_name, f)
        size = dim(f"({len(content.splitlines())} lines)") if content else ""
        print(f"    {cyan(f)}  {size}")
    print()


def cmd_view(session: Session, filename: str):
    content = file_manager.read_file(session.project_name, filename)
    if content is None:
        err(f"File not found: {filename}")
        return
    section(f"Contents of {filename}")
    for i, line in enumerate(content.splitlines(), 1):
        print(f"  {dim(str(i).rjust(3))}  {line}")
    print()


def cmd_download(session: Session):
    step("Creating zip archive...")
    zip_path = file_manager.make_zip(session.project_name)
    if zip_path:
        ok(f"Saved: {zip_path}")
    else:
        err("Failed to create zip")


def cmd_chat(client, session: Session, user_input: str):
    """
    Handle free-text input when a project is active.
    FIX: Improved intent detection — uses an LLM classification call
    instead of a brittle startswith() check.
    """
    step("Interpreting your request...")
    info(f"Active project: {session.project_name}")

    # Use LLM to classify intent: "question" vs "feature request"
    intent = _classify_intent(client, user_input, session)

    if intent == "question":
        from core.llm import clean_output
        system = (
            "You are an expert code assistant. The user has an active project. "
            "Answer their question concisely and helpfully."
        )
        context = "\n".join(
            f"=== {k} ===\n{v[:300]}" for k, v in list(session.files.items())[:3]
        )
        user_prompt = (
            f"Project: {session.plan.get('title', '')}\n"
            f"Files: {', '.join(list(session.files.keys()))}\n\n"
            f"{context}\n\n"
            f"Question: {user_input}"
        )
        response = client.generate(system, user_prompt)
        print(f"\n  {response.strip()}\n")
    else:
        # Treat as feature-add request
        info("Treating as feature request. Use /add <feature> explicitly if needed.")
        cmd_add(client, session, user_input)


def _classify_intent(client, user_input: str, session: Session) -> str:
    """
    Use a quick LLM call to determine if user_input is a question or a feature request.
    Falls back to 'feature' if the call fails.
    """
    system = (
        "You classify user messages as either 'question' or 'feature'.\n"
        "- 'question': asking for explanation, information, or what something does\n"
        "- 'feature': requesting a change, addition, fix, or new functionality\n"
        "Output ONLY the single word: question OR feature"
    )
    prompt = f"Message: {user_input[:200]}"
    try:
        result = client.generate(system, prompt).strip().lower()
        if "question" in result:
            return "question"
    except Exception:
        pass
    return "feature"


def cmd_log(session: Session):
    """Show git commit history for the current project."""
    if not session.active:
        warn("No active project.")
        return

    proj_dir = file_manager.project_path(session.project_name)
    if not git_manager.is_available():
        warn("git is not installed — history unavailable.")
        return

    entries = git_manager.log(proj_dir)
    if not entries:
        warn("No git history yet for this project.")
        return

    section(f"Git history — {session.project_name}")
    for e in entries:
        print(f"  {dim(e['short_hash'])}  {cyan(e['date'])}  {e['message']}")
    print()
    info("Use /undo <n> to revert n commits, /undo <file> to restore one file.")


def cmd_git_diff(session: Session, filename: str = ""):
    """Show real unified diff between HEAD and working tree."""
    if not session.active:
        warn("No active project.")
        return

    proj_dir = file_manager.project_path(session.project_name)

    if not git_manager.is_available():
        # Fall back to old diff method
        if filename:
            cmd_diff(session, filename)
        else:
            warn("git not available — use /diff <filename> for file diffs.")
        return

    out = git_manager.diff(proj_dir, filename or None)
    if not out:
        ok("No changes since last commit.")
        return

    section(f"git diff{' — ' + filename if filename else ''}")
    # Colorize the diff output
    for line in out.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            print(f"  {green(line)}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"  {red(line)}")
        elif line.startswith("@@"):
            print(f"  {cyan(line)}")
        else:
            print(f"  {line}")
    print()


def cmd_test(client, session: Session, flags: str = ""):
    """
    Run project tests and optionally auto-fix failures.

    /test           — run tests, show results
    /test --fix     — run tests + auto-fix failures with AI (up to 3 rounds)
    """
    if not session.active:
        warn("No active project.")
        return

    session.sync_files_from_disk()
    proj_dir  = file_manager.project_path(session.project_name)
    file_list = list(session.files.keys())
    auto_fix  = "--fix" in flags

    step("Detecting test framework...")
    result = test_runner.run_tests(proj_dir, file_list, timeout=60)

    section(f"Test Results — {result.framework}")
    print(f"  {result.summary()}")
    if result.run_result and result.run_result.output:
        print()
        for line in result.run_result.output.splitlines()[-40:]:
            print(f"  {dim(line)}")
    print()

    if result.all_passed:
        ok("All tests passing ✅")
        return

    if not auto_fix:
        info("Tip: Run /test --fix to let AI automatically repair failures.")
        return

    # Auto-fix loop
    step("Starting AI auto-fix loop...")
    generator = Generator(client, max_retries=cfg.MAX_RETRIES, cfg=cfg)

    def on_status(msg):
        info(msg)

    updated_files, all_results = test_runner.auto_fix_loop(
        generator=generator,
        plan=session.plan,
        files=session.files,
        project_dir=proj_dir,
        max_rounds=3,
        on_status=on_status,
    )

    session.files = updated_files
    session.save_meta()

    # Git commit the fixes
    last = all_results[-1] if all_results else None
    if last and last.all_passed:
        git_manager.commit(proj_dir, "fix: auto-repair test failures")
        ok("Tests fixed and committed to git ✅")
    else:
        git_manager.commit(proj_dir, "fix: partial auto-repair of test failures")
        warn("Some tests still failing — try /test --fix again or fix manually.")


def cmd_run(session: Session, flags: str = ""):
    """
    Run the project's entry point and show output.
    /run  — execute and show stdout/stderr
    """
    if not session.active:
        warn("No active project.")
        return

    session.sync_files_from_disk()
    proj_dir  = file_manager.project_path(session.project_name)
    file_list = list(session.files.keys())

    step("Running project...")
    result = test_runner.run_project(proj_dir, file_list, timeout=20)

    section(f"Output — {result.command}")
    if result.output:
        for line in result.output.splitlines():
            print(f"  {line}")
    else:
        print(f"  {dim('(no output)')}")
    print()

    if result.success:
        ok(f"Exited successfully (0)  [{result.duration_ms}ms]")
    else:
        err(f"Exited with code {result.returncode}")
        if result.stderr:
            info("Tip: Use /test --fix to auto-repair errors with AI.")


def cmd_import(client, session: Session, args: str):
    """
    Import an existing project folder into Offinity_AI.

    /import /path/to/project
    /import /path/to/project my-project-name
    """
    parts = args.strip().split(None, 1)
    if not parts:
        err("Usage: /import <folder-path> [project-name]")
        return

    source_path = parts[0]
    target_name = parts[1] if len(parts) > 1 else None

    if not Path(source_path).expanduser().exists():
        err(f"Folder not found: {source_path}")
        return

    def on_status(msg):
        info(msg)

    step(f"Importing from {source_path}...")
    success, proj_name, plan = import_project(
        source_dir=source_path,
        target_name=target_name,
        file_manager=file_manager,
        client=client,
        on_status=on_status,
    )

    if not success:
        err("Import failed — check the folder path and try again.")
        return

    # Load into session
    session.project_name = proj_name
    session.plan         = plan
    session.files        = file_manager.load_all_files(proj_name)

    # Git init for the imported project
    proj_dir = file_manager.project_path(proj_name)
    if git_manager.init(proj_dir):
        git_manager.commit(proj_dir, f"import: {Path(source_path).name}")

    print()
    ok(f"Project '{proj_name}' ready — {len(session.files)} files loaded")
    info("You can now use /add, /edit, /test on this project.")
    if session.plan:
        print_plan(session.plan)


# ── Main CLI loop ─────────────────────────────────────────────────────────────

def run_cli():
    """Interactive CLI mode."""
    banner()

    # Validate config before building client
    config_warnings = cfg.validate()
    for w in config_warnings:
        warn(w)

    client  = build_client()
    connected = check_connection(client)

    if not connected:
        print()
        answer = prompt_user("  Run setup wizard to configure a provider? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            new_client = run_setup_wizard()
            if new_client is not None:
                client = new_client
        else:
            warn("No problem — you can type /setup anytime to configure a provider.")

    session = Session()
    help_menu()

    while True:
        prompt_prefix = f"  [{session.project_name}] > " if session.active else "  > "
        line = prompt_user(prompt_prefix)
        line = line.strip()

        if not line:
            continue

        if line in ("/exit", "/quit", "exit", "quit"):
            print(f"\n  {green('Bye!')} See you next time.\n")
            break

        elif line in ("/help", "help"):
            help_menu()

        elif line in ("/status",):
            check_connection(client)

        elif line in ("/setup",):
            new_client = run_setup_wizard()
            if new_client is not None:
                client = new_client

        elif line.startswith("/web"):
            print()
            try:
                from ui.web import run_server
                planner   = Planner(client)
                generator = Generator(client)
                run_server(client, planner, generator, file_manager, cfg)
            except ImportError as e:
                err(f"Web UI requires Flask: pip install flask\n  Error: {e}")

        elif line.startswith("/new "):
            cmd_new(client, session, line[5:].strip())

        elif line.startswith("/add "):
            if not session.active:
                warn("No active project. Use /new first.")
            else:
                cmd_add(client, session, line[5:].strip())

        elif line.startswith("/edit "):
            if not session.active:
                warn("No active project. Use /new first.")
            else:
                cmd_edit(client, session, line[6:])

        elif line.startswith("/undo"):
            if not session.active:
                warn("No active project.")
            else:
                fname = line[5:].strip()
                cmd_undo(session, fname)

        elif line.startswith("/load"):
            proj = line[5:].strip()
            cmd_load(session, proj)

        elif line in ("/projects",):
            cmd_projects(session)

        elif line in ("/files",):
            if not session.active:
                warn("No active project. Use /new first.")
            else:
                cmd_files(session)

        elif line.startswith("/view "):
            if not session.active:
                warn("No active project. Use /new first.")
            else:
                cmd_view(session, line[6:].strip())

        elif line in ("/plan",):
            if not session.plan:
                warn("No active project. Use /new first.")
            else:
                print_plan(session.plan)

        elif line in ("/log",):
            cmd_log(session)

        elif line.startswith("/diff"):
            if not session.active:
                warn("No active project.")
            else:
                fname = line[5:].strip()
                cmd_git_diff(session, fname)

        elif line.startswith("/test"):
            if not session.active:
                warn("No active project. Use /new first.")
            else:
                cmd_test(client, session, line[5:].strip())

        elif line.startswith("/run"):
            if not session.active:
                warn("No active project. Use /new first.")
            else:
                cmd_run(session, line[4:].strip())

        elif line.startswith("/import "):
            cmd_import(client, session, line[8:].strip())

        elif line in ("/download",):
            if not session.active:
                warn("No active project. Use /new first.")
            else:
                cmd_download(session)

        elif line.startswith("/"):
            warn(f"Unknown command: {line.split()[0]}. Type /help for commands.")

        else:
            if session.active:
                cmd_chat(client, session, line)
            else:
                cmd_new(client, session, line)


def run_web():
    """Web UI mode — starts even if LLM is not connected."""
    banner()

    config_warnings = cfg.validate()
    for w in config_warnings:
        warn(w)

    # Try to build a client, but NEVER crash if the LLM is unreachable.
    # The web UI Settings panel lets users configure & reconnect at any time.
    try:
        client = build_client()
        try:
            ok_flag, info_str = client.health()
            if ok_flag:
                ok(f"LLM connected: {info_str}")
            else:
                warn(f"LLM not reachable: {info_str}")
                warn("Web UI starting anyway — configure your provider in Settings.")
        except Exception as conn_err:
            warn(f"LLM connection error: {conn_err}")
            warn("Web UI starting anyway — configure your provider in Settings.")
    except Exception as client_err:
        warn(f"Could not create LLM client: {client_err}")
        warn("Web UI starting anyway — configure your provider in Settings.")
        # Create a dummy no-op client so the web server can still start
        from core.llm import LLMClient
        class _OfflineClient(LLMClient):
            def generate(self, system, user, on_token=None, max_tokens=None):
                return "⚠ LLM not configured. Go to Settings to set your provider."
            def health(self):
                return False, "Not connected — configure in Settings"
        client = _OfflineClient(model="none", temperature=0.1, max_tokens=512,
                                timeout=30, retries=1, stream=False)

    try:
        from ui.web import run_server
        planner   = Planner(client)
        generator = Generator(client)
        run_server(client, planner, generator, file_manager, cfg)
    except ImportError:
        err("Flask not installed. Run: pip install flask")
        sys.exit(1)


def main():
    args = sys.argv[1:]

    if "--web" in args or "-w" in args:
        run_web()
    elif "--status" in args:
        banner()
        config_warnings = cfg.validate()
        for w in config_warnings:
            warn(w)
        client = build_client()
        check_connection(client)
    elif "--new" in args:
        idx = args.index("--new")
        if idx + 1 < len(args):
            desc = args[idx + 1]
            banner()
            config_warnings = cfg.validate()
            for w in config_warnings:
                warn(w)
            client  = build_client()
            session = Session()
            if check_connection(client):
                cmd_new(client, session, desc)
        else:
            err("Usage: python main.py --new 'project description'")
    elif "--help" in args or "-h" in args:
        banner()
        help_menu()
    else:
        run_cli()


if __name__ == "__main__":
    main()
