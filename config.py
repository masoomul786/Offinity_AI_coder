"""
Offinity_AI - Configuration
Optimized for 8B-13B local models. Zero bloat. Just works.

Providers: LM Studio | Ollama | OpenAI | Anthropic | OpenRouter
"""
import os
import re
import threading
from pathlib import Path


def _int(k, d):
    try: return int(os.getenv(k, d))
    except: return d

def _float(k, d):
    try: return float(os.getenv(k, d))
    except: return d

def _bool(k, d):
    return os.getenv(k, str(d)).lower() in ("1", "true", "yes")


VALID_PROVIDERS = {"lmstudio", "ollama", "openai", "anthropic", "openrouter"}

TOKEN_BUDGETS = {
    "javascript": 8192,
    "typescript": 8192,
    "jsx":        8192,
    "tsx":        8192,
    "python":     6144,
    "html":       4096,
    "css":        4096,
    "vue":        6144,
    "svelte":     6144,
    "java":       6144,
    "csharp":     6144,
    "go":         6144,
    "rust":       6144,
    "default":    4096,
}

# Tokens to reserve for system+user prompt at each context window size
PROMPT_RESERVE = {
    4096:  900,
    8192:  1200,
    16384: 1800,
    32768: 2500,
}

CONTEXT_WINDOW_OPTIONS = [4096, 8192, 16384, 32768]


class Config:
    BASE_DIR     = Path(__file__).parent
    PROJECTS_DIR = BASE_DIR / "projects"
    ENV_PATH     = BASE_DIR / ".env"

    # Thread-safety: protect hot-reload of class attributes in web (multi-threaded) mode
    _lock: threading.Lock = threading.Lock()

    PROVIDER = os.getenv("SC_PROVIDER", "lmstudio").lower()

    _raw_url      = os.getenv("SC_URL", os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")).rstrip("/")
    LM_STUDIO_URL = _raw_url if _raw_url.endswith("/v1") else _raw_url + "/v1"
    MODEL_NAME    = os.getenv("SC_MODEL", os.getenv("MODEL_NAME", ""))

    OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "codellama:13b")

    OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY",  "")
    OPENAI_MODEL    = os.getenv("OPENAI_MODEL",    "gpt-4o-mini")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL",   "claude-sonnet-4-6")

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL",   "deepseek/deepseek-coder-v2-lite-instruct:free")
    OPENROUTER_URL     = "https://openrouter.ai/api/v1"

    MAX_TOKENS   = _int(  "SC_MAX_TOKENS",   8192)
    TEMPERATURE  = _float("SC_TEMPERATURE",  0.10)
    TIMEOUT      = _int(  "SC_TIMEOUT",      240)
    MAX_RETRIES  = _int(  "SC_RETRIES",      3)
    STREAM       = _bool( "SC_STREAM",       True)

    # Context window: 4096 | 8192 | 16384 | 32768
    # Controls output token budget and prompt compression level
    CONTEXT_WINDOW = _int("SC_CONTEXT_WINDOW", 4096)

    WEB_HOST = os.getenv("SC_HOST", "0.0.0.0")
    WEB_PORT = _int("SC_PORT", 7432)
    LOG_LEVEL = os.getenv("SC_LOG_LEVEL", "INFO").upper()

    @classmethod
    def configure_logging(cls) -> None:
        """Configure Python logging once at application start."""
        import logging
        level = getattr(logging, cls.LOG_LEVEL, logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        # Suppress noisy third-party loggers
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    @classmethod
    def output_budget(cls, lang: str, current_lines: int = 0) -> int:
        """
        Compute max_tokens for LLM output, respecting the context window.

        Uses token_utils.budget_for_file() which accounts for file language,
        current file size (when editing), and the configured context window.
        """
        from core.token_utils import budget_for_file
        return budget_for_file(lang, current_lines, cls.CONTEXT_WINDOW)

    @classmethod
    def prompt_budget(cls) -> int:
        """Max chars to include for file context in prompts."""
        return cls.CONTEXT_WINDOW * 2

    @classmethod
    def token_budget_for(cls, lang: str, current_file_lines: int = 0) -> int:
        """Backward compat alias."""
        return cls.output_budget(lang, current_file_lines)

    @classmethod
    def save_to_env(cls, updates: dict) -> bool:
        """Persist settings to .env file AND update in-memory class state immediately.

        Thread-safe: uses a class-level lock so concurrent web requests cannot
        corrupt the in-memory config during a hot-reload.
        """
        with cls._lock:
            env_path = cls.ENV_PATH
            existing: dict = {}
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        existing[k.strip()] = v.strip()
            existing.update({k: str(v) for k, v in updates.items() if v is not None and str(v).strip()})
            try:
                env_path.write_text(
                    "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
                    encoding="utf-8",
                )
            except Exception as e:
                import logging as _log
                _log.getLogger(__name__).error("Failed to save .env: %s", e)
                return False

            _attr_map = {
                "SC_PROVIDER":       ("PROVIDER",       str),
                "SC_MODEL":          ("MODEL_NAME",      str),
                "SC_TEMPERATURE":    ("TEMPERATURE",     float),
                "SC_MAX_TOKENS":     ("MAX_TOKENS",      int),
                "SC_CONTEXT_WINDOW": ("CONTEXT_WINDOW",  int),
                "SC_TIMEOUT":        ("TIMEOUT",         int),
                "SC_RETRIES":        ("MAX_RETRIES",     int),
                "SC_PORT":           ("WEB_PORT",        int),
                "SC_HOST":           ("WEB_HOST",        str),
                "ANTHROPIC_API_KEY": ("ANTHROPIC_API_KEY", str),
                "ANTHROPIC_MODEL":   ("ANTHROPIC_MODEL",   str),
                "OPENAI_API_KEY":    ("OPENAI_API_KEY",  str),
                "OPENAI_MODEL":      ("OPENAI_MODEL",    str),
                "OPENAI_BASE_URL":   ("OPENAI_BASE_URL", str),
                "OPENROUTER_API_KEY":("OPENROUTER_API_KEY", str),
                "OPENROUTER_MODEL":  ("OPENROUTER_MODEL",   str),
                "OLLAMA_URL":        ("OLLAMA_URL",      str),
                "OLLAMA_MODEL":      ("OLLAMA_MODEL",    str),
            }
            for env_key, new_val in updates.items():
                if new_val is None:
                    continue
                if env_key in _attr_map:
                    attr, cast = _attr_map[env_key]
                    try:
                        setattr(cls, attr, cast(new_val))
                    except (ValueError, TypeError):
                        pass
            return True

    @classmethod
    def model_family(cls) -> str:
        """
        Detect the model family from the current model name.
        Returns: 'reasoning' | 'large' | 'small' | 'standard'

        Used to select appropriate system prompt variants:
          - reasoning: DeepSeek-R1, Qwen3-thinking, QwQ — shorter prompts, let it think
          - large:     32B+ models — trust the model, less hand-holding
          - small:     7B and under — more explicit rules, more examples
          - standard:  everything else (13B-20B)
        """
        model = (cls.MODEL_NAME or "").lower()
        # Reasoning / thinking models
        if any(x in model for x in ("r1", "-r2", "qwq", "thinking", "-think",
                                     "deepseek-r", "o1", "o3", "o4")):
            return "reasoning"
        # Large models (32B+)
        if any(x in model for x in ("32b", "70b", "72b", "110b", "671b",
                                     "claude-opus", "gpt-4o", "gpt-4-turbo",
                                     "sonnet", "opus", "mistral-large")):
            return "large"
        # Small models (≤8B) — careful not to match 13b, 14b, 18b as small
        if any(re.search(r'\b' + re.escape(x) + r'\b', model)
               for x in ("1b", "2b", "3b", "4b", "7b", "8b",
                          "phi-3", "phi3", "tinyllama",
                          "qwen2-0.5b", "qwen2-1.5b")) or "gemma-2b" in model:
            return "small"
        return "standard"

    @classmethod
    def validate(cls):
        warnings = []
        if cls.PROVIDER not in VALID_PROVIDERS:
            warnings.append(
                f"Unknown SC_PROVIDER='{cls.PROVIDER}'. "
                f"Valid: {', '.join(sorted(VALID_PROVIDERS))}. Defaulting to 'lmstudio'."
            )
            cls.PROVIDER = "lmstudio"
        if cls.PROVIDER == "openai" and not cls.OPENAI_API_KEY:
            warnings.append("SC_PROVIDER=openai but OPENAI_API_KEY is not set.")
        if cls.PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
            warnings.append("SC_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")
        if cls.PROVIDER == "openrouter" and not cls.OPENROUTER_API_KEY:
            warnings.append("SC_PROVIDER=openrouter but OPENROUTER_API_KEY is not set.")
        return warnings
