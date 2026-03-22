#!/usr/bin/env python3
"""
Inzyts First-Run Setup Wizard.

Interactive setup that guides new users through creating a .env file with all
required configuration.  Called by start_app.sh / start_app.ps1 on first run.

Can also be invoked directly:
    python scripts/setup_wizard.py            # interactive
    python scripts/setup_wizard.py --check    # exit 0 if .env exists, 1 otherwise
    python scripts/setup_wizard.py --force    # overwrite existing .env
"""

from __future__ import annotations

import os
import re
import sys
import secrets
import string
import textwrap
from pathlib import Path
from typing import Optional


# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / "config" / ".env.example"


# ── ANSI colours (disabled when stdout is not a tty) ─────────────────────────

_NO_COLOR = not sys.stdout.isatty() or os.getenv("NO_COLOR")

def _c(code: str, text: str) -> str:
    return text if _NO_COLOR else f"\033[{code}m{text}\033[0m"

def green(t: str) -> str:  return _c("32", t)
def yellow(t: str) -> str: return _c("1;33", t)
def blue(t: str) -> str:   return _c("34", t)
def red(t: str) -> str:    return _c("31", t)
def bold(t: str) -> str:   return _c("1", t)
def dim(t: str) -> str:    return _c("2", t)


# ── LLM provider definitions ────────────────────────────────────────────────

PROVIDERS = {
    "anthropic": {
        "display": "Anthropic (Claude)",
        "key_env": "INZYTS__LLM__ANTHROPIC_API_KEY",
        "key_prefix": "sk-ant-",
        "model_env": "INZYTS__LLM__ANTHROPIC_MODEL",
        "models": [
            ("claude-sonnet-4-6", "Claude Sonnet 4.6 (recommended)"),
            ("claude-opus-4-6", "Claude Opus 4.6 (most capable)"),
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5 (fastest / cheapest)"),
        ],
        "default_model": "claude-sonnet-4-6",
    },
    "openai": {
        "display": "OpenAI (GPT)",
        "key_env": "OPENAI_API_KEY",
        "key_prefix": "sk-",
        "model_env": "INZYTS__LLM__OPENAI_MODEL",
        "models": [
            ("gpt-4o", "GPT-4o (recommended)"),
            ("gpt-4o-mini", "GPT-4o Mini (faster / cheaper)"),
            ("gpt-4-turbo", "GPT-4 Turbo"),
            ("o3-mini", "o3-mini (reasoning)"),
        ],
        "default_model": "gpt-4o",
    },
    "gemini": {
        "display": "Google Gemini",
        "key_env": "GOOGLE_API_KEY",
        "key_prefix": "",
        "model_env": "INZYTS__LLM__GEMINI_MODEL",
        "models": [
            ("gemini-2.5-pro-preview-06-05", "Gemini 2.5 Pro (recommended)"),
            ("gemini-2.5-flash-preview-05-20", "Gemini 2.5 Flash (faster / cheaper)"),
            ("gemini-1.5-pro", "Gemini 1.5 Pro"),
        ],
        "default_model": "gemini-2.5-pro-preview-06-05",
    },
    "ollama": {
        "display": "Ollama (local, no API key needed)",
        "key_env": None,
        "key_prefix": "",
        "model_env": "INZYTS__LLM__OLLAMA_MODEL",
        "models": [
            ("qwen2.5:32b", "Qwen 2.5 32B (recommended)"),
            ("llama3.1:70b", "Llama 3.1 70B"),
            ("llama3.1:8b", "Llama 3.1 8B (lightweight)"),
            ("deepseek-coder-v2:16b", "DeepSeek Coder V2 16B"),
        ],
        "default_model": "qwen2.5:32b",
        "extra_env": {
            "INZYTS__LLM__OLLAMA_BASE_URL": "http://localhost:11434",
        },
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def generate_hex(n: int = 32) -> str:
    """Generate a cryptographically secure hex token."""
    return secrets.token_hex(n)


def generate_password(length: int = 16) -> str:
    """Generate a random password with mixed characters."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def prompt(label: str, *, default: str = "", secret: bool = False,
           validate: Optional[callable] = None) -> str:
    """Prompt user for input with optional default and validation."""
    if default:
        suffix = dim(f" [{default}]") if not secret else dim(" [generated]")
    else:
        suffix = ""

    while True:
        try:
            raw = input(f"  {label}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(130)

        value = raw if raw else default

        if not value:
            print(red("    This field is required."))
            continue

        if validate:
            err = validate(value)
            if err:
                print(red(f"    {err}"))
                continue

        return value


def prompt_choice(label: str, choices: list[tuple[str, str]],
                  default_value: str = "") -> str:
    """Prompt user to pick from a numbered list."""
    print(f"\n  {label}")
    default_idx = 0
    for i, (value, description) in enumerate(choices, 1):
        marker = " *" if value == default_value else ""
        print(f"    {blue(str(i))}. {description}{green(marker)}")
        if value == default_value:
            default_idx = i

    while True:
        try:
            raw = input(f"  Choice [{default_idx}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(130)

        if not raw:
            return choices[default_idx - 1][0]

        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1][0]

        # Allow typing the value directly
        for value, _ in choices:
            if raw.lower() == value.lower():
                return value

        print(red(f"    Please enter 1-{len(choices)}."))


def prompt_yes_no(label: str, default: bool = True) -> bool:
    """Prompt for yes/no."""
    hint = "Y/n" if default else "y/N"
    try:
        raw = input(f"  {label} [{hint}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(130)
    if not raw:
        return default
    return raw in ("y", "yes")


def section(title: str) -> None:
    """Print a section header."""
    print(f"\n{bold(blue(f'── {title} '))}" + blue("─" * max(1, 56 - len(title))))


# ── Core wizard logic ────────────────────────────────────────────────────────

def run_wizard(force: bool = False) -> bool:
    """Run the interactive setup wizard. Returns True if .env was written."""

    print()
    print(bold(blue("╔══════════════════════════════════════════════════════════╗")))
    print(bold(blue("║")) + bold("       Inzyts — First-Run Setup Wizard                  ") + bold(blue("║")))
    print(bold(blue("╚══════════════════════════════════════════════════════════╝")))
    print()
    print(
        "  This wizard will create the " + bold(".env") + " file with all required\n"
        "  configuration to run the Inzyts application.\n"
    )
    print(dim("  Press Enter to accept defaults shown in [brackets]."))
    print(dim("  Press Ctrl+C at any time to abort.\n"))

    env_vars: dict[str, str] = {}

    # ── 1. LLM Provider ─────────────────────────────────────────────────

    section("LLM Provider")

    provider_choices = [(k, v["display"]) for k, v in PROVIDERS.items()]
    provider = prompt_choice(
        "Which LLM provider do you want to use?",
        provider_choices,
        default_value="anthropic",
    )
    prov_cfg = PROVIDERS[provider]
    env_vars["INZYTS__LLM__DEFAULT_PROVIDER"] = provider

    # ── 2. LLM API Key ──────────────────────────────────────────────────

    if prov_cfg["key_env"]:
        section("LLM API Key")
        prefix = prov_cfg["key_prefix"]
        hint = f" (starts with '{prefix}')" if prefix else ""

        def _validate_key(v: str) -> Optional[str]:
            if prefix and not v.startswith(prefix):
                return f"Key should start with '{prefix}'. Proceed anyway? Enter the key again or fix it."
            return None

        # Don't hard-fail on prefix mismatch — just warn
        api_key = prompt(
            f"{prov_cfg['display']} API key{hint}",
            secret=True,
        )
        env_vars[prov_cfg["key_env"]] = api_key

        if prefix and not api_key.startswith(prefix):
            print(yellow(f"    Warning: Key doesn't start with '{prefix}' — continuing anyway."))

    # ── 3. LLM Model ────────────────────────────────────────────────────

    section("LLM Model")
    model = prompt_choice(
        f"Choose the {prov_cfg['display']} model:",
        prov_cfg["models"],
        default_value=prov_cfg["default_model"],
    )
    env_vars[prov_cfg["model_env"]] = model

    # Extra env for Ollama
    if "extra_env" in prov_cfg:
        section("Ollama Configuration")
        ollama_url = prompt(
            "Ollama server URL",
            default="http://localhost:11434",
        )
        env_vars["INZYTS__LLM__OLLAMA_BASE_URL"] = ollama_url

    # ── 4. Admin Credentials ─────────────────────────────────────────────

    section("Admin Account")
    print(dim("  These credentials are used to create the initial admin user."))
    admin_user = prompt("Admin username", default="admin")
    env_vars["ADMIN_USERNAME"] = admin_user

    generated_admin_pw = generate_password()
    admin_pass = prompt(
        "Admin password",
        default=generated_admin_pw,
        secret=True,
        validate=lambda v: "Password must be at least 8 characters." if len(v) < 8 else None,
    )
    env_vars["ADMIN_PASSWORD"] = admin_pass

    # ── 5. Database ──────────────────────────────────────────────────────

    section("PostgreSQL Database")
    print(dim("  The database runs inside Docker — you just need to set a password."))
    db_user = prompt("Database user", default="postgres")
    env_vars["POSTGRES_USER"] = db_user

    generated_db_pw = generate_password()
    db_pass = prompt("Database password", default=generated_db_pw, secret=True)
    env_vars["POSTGRES_PASSWORD"] = db_pass

    db_name = prompt("Database name", default="inzyts")
    env_vars["POSTGRES_DB"] = db_name
    env_vars["POSTGRES_HOST"] = "localhost"
    env_vars["POSTGRES_PORT"] = "5432"

    # ── 6. Auto-generated Secrets ────────────────────────────────────────

    section("Security Tokens")
    print(dim("  These are auto-generated. Press Enter to accept (recommended)."))

    jwt_secret = prompt("JWT secret key", default=generate_hex())
    env_vars["JWT_SECRET_KEY"] = jwt_secret

    api_token = prompt("API token (server-to-server)", default=generate_hex())
    env_vars["INZYTS_API_TOKEN"] = api_token

    jupyter_token = prompt("Jupyter token", default=generate_hex())
    env_vars["JUPYTER_TOKEN"] = jupyter_token

    # ── 7. Optional: Datasets directory ──────────────────────────────────

    section("Data Directories (optional)")
    print(dim("  Leave blank to use defaults."))

    datasets_dir = ""
    if prompt_yes_no("Do you have an existing datasets directory to mount?", default=False):
        datasets_dir = prompt(
            "Path to datasets directory",
            validate=lambda v: "Directory not found." if not Path(v).expanduser().is_dir() else None,
        )
    if datasets_dir:
        env_vars["DATASETS_DIR"] = datasets_dir

    # ── 8. Static defaults ───────────────────────────────────────────────

    env_vars.setdefault("REDIS_URL", "redis://localhost:6379/0")
    env_vars.setdefault(
        "ALLOWED_ORIGINS",
        '["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:5173"]',
    )
    env_vars.setdefault("PYTHONPYCACHEPREFIX", ".cache/pycache")

    # ── Write .env ───────────────────────────────────────────────────────

    section("Summary")
    print(f"  LLM Provider : {green(provider)}")
    print(f"  LLM Model    : {green(model)}")
    print(f"  Admin User   : {green(admin_user)}")
    print(f"  DB User      : {green(db_user)} / DB Name: {green(db_name)}")
    if datasets_dir:
        print(f"  Datasets Dir : {green(datasets_dir)}")
    print(f"  Secrets      : {green('auto-generated')}")
    print()

    if not prompt_yes_no("Write .env and start the application?", default=True):
        print(yellow("\n  Setup cancelled. No files were written.\n"))
        return False

    _write_env_file(env_vars)

    print(green(f"\n  .env written to {ENV_FILE}"))
    print(dim("  You can edit it later or re-run this wizard with: python scripts/setup_wizard.py --force\n"))
    return True


def _write_env_file(env_vars: dict[str, str]) -> None:
    """Write the .env file using the template as a base, filling in values."""

    # Read the example template
    if ENV_EXAMPLE.exists():
        template = ENV_EXAMPLE.read_text(encoding="utf-8")
    else:
        template = ""

    lines = template.splitlines()
    output_lines: list[str] = []
    written_keys: set[str] = set()

    for line in lines:
        # Match active assignments: KEY=value
        match = re.match(r"^([A-Z][A-Z0-9_]*)\s*=", line)
        # Match commented-out assignments: # KEY=value
        commented_match = re.match(r"^#\s*([A-Z][A-Z0-9_]*)\s*=", line)

        if match and match.group(1) in env_vars:
            key = match.group(1)
            output_lines.append(f"{key}={env_vars[key]}")
            written_keys.add(key)
        elif commented_match and commented_match.group(1) in env_vars:
            key = commented_match.group(1)
            output_lines.append(f"{key}={env_vars[key]}")
            written_keys.add(key)
        else:
            output_lines.append(line)

    # Append any keys not found in template
    extras = set(env_vars.keys()) - written_keys
    if extras:
        output_lines.append("")
        output_lines.append("# ── Additional Settings (added by setup wizard) ──────────")
        for key in sorted(extras):
            output_lines.append(f"{key}={env_vars[key]}")

    ENV_FILE.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> int:
    force = "--force" in sys.argv or "--reconfigure" in sys.argv

    # --check mode: just test if .env exists
    if "--check" in sys.argv:
        return 0 if ENV_FILE.exists() else 1

    # If .env already exists, ask whether to reconfigure
    if ENV_FILE.exists() and not force:
        print(green(f"\n  .env already exists at {ENV_FILE}"))
        if not prompt_yes_no("  Do you want to reconfigure?", default=False):
            print(dim("  Skipping setup — using existing .env\n"))
            return 0
        # Back up existing .env
        backup = ENV_FILE.with_suffix(".env.bak")
        ENV_FILE.rename(backup)
        print(dim(f"  Backed up existing .env to {backup.name}"))

    wrote = run_wizard(force=force)
    return 0 if wrote else 1


if __name__ == "__main__":
    sys.exit(main())
