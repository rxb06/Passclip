#!/usr/bin/env python3
"""
PassCLI — A feature-rich, smart wrapper for the `pass` password manager.

Designed for normal users and power users/developers alike.

Usage:
  passcli                          # Start interactive shell
  passcli get email/gmail          # Show a password
  passcli get email/gmail --clip   # Copy to clipboard
  passcli insert web/github        # Add new entry (guided)
  passcli health                   # Password health report
  passcli otp web/github           # Generate TOTP code
  passcli run aws/prod -- aws s3 ls  # Inject secrets as env vars
  passcli import passwords.csv     # Import from Bitwarden/LastPass
  passcli sync                     # Git pull + push
  passcli wizard                   # First-time setup
"""

import argparse
import cmd
import csv
import hashlib
import io
import json
import os
import readline
import secrets
import shutil
import string
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_PATH = Path.home() / ".config" / "passcli" / "config.json"
DEFAULT_CONFIG: Dict = {
    "clip_timeout": 45,
    "default_password_length": 20,
    "default_mode": "shell",
    "pass_dir": str(Path.home() / ".password-store"),
}


def load_config() -> Dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 0o600 — owner read/write only; config contains pass_dir path
    CONFIG_PATH.touch(mode=0o600, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


CONFIG = load_config()

# ---------------------------------------------------------------------------
# Dependency detection
# ---------------------------------------------------------------------------


def check_dependencies() -> Dict[str, bool]:
    deps: Dict[str, bool] = {}
    for tool in ["pass", "gpg", "fzf", "git"]:
        deps[tool] = shutil.which(tool) is not None
    try:
        import pyperclip  # noqa: F401
        deps["pyperclip"] = True
    except ImportError:
        deps["pyperclip"] = False
    try:
        import pyotp  # noqa: F401
        deps["pyotp"] = True
    except ImportError:
        deps["pyotp"] = False
    return deps


DEPS = check_dependencies()

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def run_command(
    command_parts: List[str],
    interactive: bool = False,
    input_data: Optional[str] = None,
) -> Tuple[str, str, int]:
    """Run a subprocess safely (no shell=True). Returns (stdout, stderr, returncode)."""
    try:
        if interactive:
            result = subprocess.run(command_parts)
            return "", "", result.returncode
        result = subprocess.run(
            command_parts,
            text=True,
            capture_output=True,
            input=input_data,
            check=False,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except FileNotFoundError:
        name = command_parts[0] if command_parts else "unknown"
        return "", f"Command not found: '{name}'. Is it installed and in PATH?", 127
    except PermissionError as e:
        return "", f"Permission denied running '{command_parts[0]}': {e}", 126
    except OSError as e:
        return "", f"OS error running '{command_parts[0]}': {e}", 1


def get_all_entries() -> List[str]:
    """Return all pass entry paths, sorted."""
    pass_dir = Path(CONFIG.get("pass_dir", Path.home() / ".password-store"))
    if not pass_dir.exists():
        return []
    entries = []
    for f in pass_dir.rglob("*.gpg"):
        rel = f.relative_to(pass_dir)
        entry = str(rel)
        if entry.endswith(".gpg"):
            entry = entry[:-4]
        if not entry.startswith("."):
            entries.append(entry)
    return sorted(entries)


def get_gpg_keys() -> List[Tuple[str, str]]:
    """Return list of (key_id, user_info) for all GPG public keys."""
    out, _, _ = run_command(["gpg", "--list-keys", "--keyid-format", "LONG"])
    keys: List[Tuple[str, str]] = []
    for line in out.splitlines():
        if line.startswith("pub"):
            try:
                parts = line.split()
                key_info = parts[1]
                key_id = key_info.split("/")[1] if "/" in key_info else key_info
                user_info = " ".join(parts[2:])
                keys.append((key_id, user_info))
            except IndexError:
                continue
    return keys


# ---------------------------------------------------------------------------
# Fuzzy selection
# ---------------------------------------------------------------------------


def fuzzy_select(entries: List[str], prompt_text: str = "Select entry") -> Optional[str]:
    """Pick an entry using fzf if available, otherwise a numbered list."""
    if not entries:
        console.print("[yellow]No entries found.[/yellow]")
        return None

    if DEPS.get("fzf"):
        try:
            result = subprocess.run(
                ["fzf", "--prompt", f"{prompt_text}: ", "--height", "40%",
                 "--reverse", "--border"],
                input="\n".join(entries),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            pass

    # Fallback: numbered list with optional text filter
    filtered = entries
    if len(entries) > 15:
        term = Prompt.ask("[dim]Filter[/dim] (Enter for all)", default="")
        if term:
            filtered = [e for e in entries if term.lower() in e.lower()]
            if not filtered:
                console.print(f"[yellow]No entries matching '{term}'.[/yellow]")
                return None
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("#", style="dim", width=4)
    table.add_column("Entry", style="green")
    for i, entry in enumerate(filtered, 1):
        table.add_row(str(i), entry)
    console.print(table)
    try:
        choice = IntPrompt.ask(f"{prompt_text} (number, 0 to cancel)", default=0)
        if 1 <= choice <= len(filtered):
            return filtered[choice - 1]
    except (KeyboardInterrupt, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------


def copy_to_clipboard(text: str, timeout: Optional[int] = None) -> bool:
    """Copy text to clipboard and schedule auto-clear after `timeout` seconds."""
    timeout = timeout if timeout is not None else CONFIG.get("clip_timeout", 45)
    copied = False

    if DEPS.get("pyperclip"):
        import pyperclip
        try:
            pyperclip.copy(text)
            copied = True
        except Exception:
            pass

    if not copied:
        for cmd_args in [["pbcopy"], ["xclip", "-selection", "clipboard"], ["wl-copy"]]:
            if shutil.which(cmd_args[0]):
                try:
                    subprocess.run(cmd_args, input=text, text=True, check=True,
                                   capture_output=True)
                    copied = True
                    break
                except Exception:
                    continue

    if not copied:
        console.print(
            "[red]No clipboard tool found.[/red] "
            "Install pyperclip: [cyan]pip install pyperclip[/cyan]"
        )
        return False

    console.print(
        f"[green]Copied to clipboard.[/green] "
        f"Auto-clearing in [bold]{timeout}s[/bold]..."
    )

    def _clear():
        time.sleep(timeout)
        if DEPS.get("pyperclip"):
            import pyperclip
            try:
                if pyperclip.paste() == text:
                    pyperclip.copy("")
            except Exception:
                pass
        else:
            for cmd_args in [["pbcopy"], ["xclip", "-selection", "clipboard"], ["wl-copy"]]:
                if shutil.which(cmd_args[0]):
                    try:
                        subprocess.run(cmd_args, input="", text=True, check=True,
                                       capture_output=True)
                    except Exception:
                        pass
                    break

    threading.Thread(target=_clear, daemon=True).start()
    return True


# ---------------------------------------------------------------------------
# Structured entry format
#
# Pass stores free-form text. PassCLI treats the first line as the password
# and subsequent lines as "key: value" metadata (username, url, email, notes).
# This is compatible with pass-import and most pass extensions.
# ---------------------------------------------------------------------------


def parse_entry(content: str) -> Dict[str, str]:
    lines = content.splitlines()
    data: Dict[str, str] = {"password": lines[0] if lines else ""}
    for line in lines[1:]:
        if ": " in line:
            key, _, value = line.partition(": ")
            data[key.strip().lower()] = value.strip()
        elif line.strip():
            data.setdefault("notes", "")
            data["notes"] += line + "\n"
    return data


def format_entry(data: Dict[str, str]) -> str:
    lines = [data.get("password", "")]
    for key in ("username", "email", "url"):
        if data.get(key):
            lines.append(f"{key}: {data[key]}")
    # Any extra keys
    skip = {"password", "username", "email", "url", "notes"}
    for key, value in data.items():
        if key not in skip and value:
            lines.append(f"{key}: {value}")
    if data.get("notes"):
        lines.append(data["notes"].strip())
    return "\n".join(lines) + "\n"


def get_entry_raw(entry: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (content, error). content is None on failure."""
    out, err, rc = run_command(["pass", "show", entry])
    if rc != 0 or not out:
        msg = err or ""
        lower = msg.lower()
        if "is not in the password store" in lower or (not msg and not out):
            return None, f"Entry '{entry}' not found. Run [bold]ls[/bold] to see available entries."
        if "decryption failed" in lower or "no secret key" in lower:
            return None, f"Cannot decrypt '{entry}'. Is your GPG key unlocked? Try: gpg --card-status"
        if "public key" in lower or "unusable public key" in lower:
            return None, f"GPG key error for '{entry}'. Run [bold]gpg_list[/bold] to check your keys."
        return None, msg or f"Entry '{entry}' not found."
    return out, None


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------


def generate_password(length: int = 20, symbols: bool = True) -> str:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_letters + string.digits
    if symbols:
        alphabet += string.punctuation
    # Ensure at least one of each required character type
    pw = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
    ]
    if symbols:
        pw.append(secrets.choice(string.punctuation))
    pw += [secrets.choice(alphabet) for _ in range(length - len(pw))]
    # Shuffle to avoid predictable positions
    result = list(pw)
    secrets.SystemRandom().shuffle(result)
    return "".join(result)


# ---------------------------------------------------------------------------
# Vault encryption
# ---------------------------------------------------------------------------

VAULT_MAGIC = b"PCV1"  # 4-byte header identifying PassCLI vault files


def _derive_vault_key(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key from a passphrase using PBKDF2-SHA256 (600k iters)."""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    return kdf.derive(passphrase)


# ---------------------------------------------------------------------------
# Password strength
# ---------------------------------------------------------------------------


def password_strength(password: str) -> Tuple[int, str, str]:
    """Return (score 0-4, label, rich_color)."""
    if not password:
        return 0, "Empty", "red"
    score = 0
    n = len(password)
    if n >= 8:
        score += 1
    if n >= 14:
        score += 1
    if n >= 20:
        score += 1
    variety = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if variety >= 3:
        score += 1
    if variety == 4:
        score += 1
    score = min(score, 4)
    labels = ["Very Weak", "Weak", "Fair", "Strong", "Very Strong"]
    colors = ["red", "red", "yellow", "green", "bright_green"]
    return score, labels[score], colors[score]


def strength_bar(score: int, color: str) -> str:
    return f"[{color}]{'█' * (score + 1)}{'░' * (4 - score)}[/{color}]"


# ---------------------------------------------------------------------------
# Feature commands
# ---------------------------------------------------------------------------


def cmd_get(
    entry: Optional[str] = None,
    clip: bool = False,
    field: Optional[str] = None,
    interactive_followup: bool = False,
) -> None:
    """Retrieve a password entry, display it or copy to clipboard."""
    if not entry:
        entries = get_all_entries()
        entry = fuzzy_select(entries, "Select entry")
        if not entry:
            return

    content, error = get_entry_raw(entry)
    if error:
        console.print(f"[red]Error:[/red] {error}")
        return

    data = parse_entry(content)

    if field:
        value = data.get(field.lower())
        if value is None:
            console.print(f"[red]Field '{field}' not found in entry '{entry}'.[/red]")
            return
        if clip:
            copy_to_clipboard(value)
        else:
            console.print(value)
        return

    if clip:
        copy_to_clipboard(data["password"])
        return

    # Rich display
    score, label, color = password_strength(data["password"])
    lines = [f"[bold]Password:[/bold] {data['password']}"]
    for key in ("username", "email", "url"):
        if data.get(key):
            lines.append(f"[cyan]{key.capitalize()}:[/cyan] {data[key]}")
    skip = {"password", "username", "email", "url", "notes"}
    for key, val in data.items():
        if key not in skip:
            lines.append(f"[magenta]{key}:[/magenta] {val}")
    if data.get("notes"):
        lines.append(f"[dim]Notes:[/dim] {data['notes'].strip()}")
    lines.append(f"\n{strength_bar(score, color)} [dim]{label}[/dim]")
    console.print(Panel("\n".join(lines), title=f"[bold cyan]{entry}[/bold cyan]",
                        border_style="cyan"))

    if interactive_followup:
        hint_parts = ["[dim][cyan]c[/cyan]=copy password"]
        if data.get("username") or data.get("email"):
            hint_parts.append("[cyan]u[/cyan]=username")
        if data.get("url"):
            hint_parts.append("[cyan]l[/cyan]=URL")
        hint_parts.append("Enter=done[/dim]")
        console.print("  " + "  ".join(hint_parts))
        try:
            choice = Prompt.ask("", default="").strip().lower()
        except KeyboardInterrupt:
            return
        if choice == "c":
            copy_to_clipboard(data["password"])
        elif choice == "u":
            val = data.get("username") or data.get("email", "")
            if val:
                copy_to_clipboard(val)
        elif choice == "l" and data.get("url"):
            copy_to_clipboard(data["url"])


def cmd_insert(entry: Optional[str] = None, structured: bool = True) -> None:
    """Add a new password entry with guided prompts."""
    if not entry:
        entry = Prompt.ask("[cyan]Entry name[/cyan] (e.g. web/github, email/work)")
    if not entry.strip():
        console.print("[red]Entry name cannot be empty.[/red]")
        return

    if structured:
        console.print(Panel(
            "Fill in the fields below. Press Enter to skip optional fields.\n"
            "Leave password blank to auto-generate one.",
            title="[bold cyan]New Entry[/bold cyan]", border_style="cyan"
        ))
        password = Prompt.ask("[bold]Password[/bold] (Enter to generate)", password=True, default="")
        if not password:
            length = IntPrompt.ask(
                "[dim]Length[/dim]",
                default=CONFIG.get("default_password_length", 20),
            )
            use_symbols = Confirm.ask("[dim]Include symbols?[/dim]", default=True)
            password = generate_password(length, use_symbols)
            console.print(f"[green]Generated:[/green] {password}")
        score, label, color = password_strength(password)
        console.print(f"  Strength: {strength_bar(score, color)} [dim]{label}[/dim]")
        username = Prompt.ask("[dim]Username[/dim]", default="")
        email = Prompt.ask("[dim]Email[/dim]", default="")
        url = Prompt.ask("[dim]URL[/dim]", default="")
        notes = Prompt.ask("[dim]Notes[/dim]", default="")
        data: Dict[str, str] = {"password": password}
        if username:
            data["username"] = username
        if email:
            data["email"] = email
        if url:
            data["url"] = url
        if notes:
            data["notes"] = notes
        content = format_entry(data)
    else:
        console.print("Paste/type entry content (Ctrl-D to finish):")
        try:
            content = sys.stdin.read()
        except KeyboardInterrupt:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    proc = subprocess.Popen(
        ["pass", "insert", "-m", "-f", entry],
        stdin=subprocess.PIPE, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    _, stderr = proc.communicate(content)
    if proc.returncode == 0:
        console.print(f"[green]Saved '[bold]{entry}[/bold]' successfully.[/green]")
    else:
        console.print(f"[red]Error:[/red] {stderr.strip()}")


def cmd_generate(
    entry: Optional[str] = None,
    length: Optional[int] = None,
    no_symbols: bool = False,
    clip: bool = False,
) -> None:
    """Generate a random password for an entry."""
    if not entry:
        entry = Prompt.ask("[cyan]Entry name[/cyan]")
    if not entry.strip():
        console.print("[red]Entry name cannot be empty.[/red]")
        return
    if not length:
        length = IntPrompt.ask("Length", default=CONFIG.get("default_password_length", 20))

    args = ["pass", "generate", "-f"]
    if no_symbols:
        args.append("-n")
    args += [entry, str(length)]

    out, err, rc = run_command(args)
    if rc != 0:
        if "No public key" in err or "encryption failed" in err:
            console.print(
                "[red]GPG encryption failed.[/red] "
                "Run [bold]init[/bold] to set up your password store."
            )
        else:
            console.print(f"[red]Error:[/red] {err}")
        return

    console.print(f"[green]Generated password for '[bold]{entry}[/bold]'.[/green]")
    content, error = get_entry_raw(entry)
    if content:
        pw = parse_entry(content)["password"]
        score, label, color = password_strength(pw)
        console.print(f"  Password: {pw}")
        console.print(f"  Strength: {strength_bar(score, color)} [dim]{label}[/dim]")
        if clip:
            copy_to_clipboard(pw)


def cmd_health() -> None:
    """Scan all entries for password strength and duplicates."""
    entries = get_all_entries()
    if not entries:
        console.print("[yellow]No entries found in the password store.[/yellow]")
        return

    console.print(f"\n[bold]Scanning [cyan]{len(entries)}[/cyan] entries...[/bold]\n")

    results = []
    hash_map: Dict[str, List[str]] = {}
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analysing...", total=len(entries))
        for entry in entries:
            content, error = get_entry_raw(entry)
            if error or not content:
                errors.append(entry)
                progress.advance(task)
                continue
            data = parse_entry(content)
            pw = data.get("password", "")
            score, label, color = password_strength(pw)
            phash = hashlib.sha256(pw.encode()).hexdigest()
            hash_map.setdefault(phash, []).append(entry)
            results.append({
                "entry": entry, "score": score, "label": label,
                "color": color, "len": len(pw), "hash": phash,
            })
            progress.advance(task)

    dup_groups = {h: g for h, g in hash_map.items() if len(g) > 1}
    dup_set = {e for g in dup_groups.values() for e in g}
    results.sort(key=lambda r: r["score"])

    weak = [r for r in results if r["score"] <= 1]
    fair = [r for r in results if r["score"] == 2]
    strong = [r for r in results if r["score"] >= 3]

    console.print(Panel(
        f"[green]Strong:[/green] {len(strong)}   "
        f"[yellow]Fair:[/yellow] {len(fair)}   "
        f"[red]Weak:[/red] {len(weak)}   "
        f"[magenta]Duplicates:[/magenta] {len(dup_set)}   "
        f"[dim]Errors:[/dim] {len(errors)}",
        title="[bold]Password Health Report[/bold]",
    ))

    if weak:
        console.print("\n[bold red]Weak Passwords[/bold red] (update these):")
        t = Table(box=box.SIMPLE)
        t.add_column("Entry", style="cyan")
        t.add_column("Strength", justify="center")
        t.add_column("Len", justify="right", style="dim")
        t.add_column("Dup", justify="center")
        for r in weak:
            dup = "[red]YES[/red]" if r["entry"] in dup_set else ""
            t.add_row(r["entry"], strength_bar(r["score"], r["color"]) + f" {r['label']}",
                      str(r["len"]), dup)
        console.print(t)
        console.print("[dim]  Tip: run [bold]generate <entry>[/bold] to replace with a strong password[/dim]")

    if fair:
        console.print("\n[bold yellow]Fair Passwords[/bold yellow] (consider upgrading):")
        t = Table(box=box.SIMPLE)
        t.add_column("Entry", style="cyan")
        t.add_column("Strength", justify="center")
        t.add_column("Len", justify="right", style="dim")
        t.add_column("Dup", justify="center")
        for r in fair:
            dup = "[red]YES[/red]" if r["entry"] in dup_set else ""
            t.add_row(r["entry"], strength_bar(r["score"], r["color"]) + f" {r['label']}",
                      str(r["len"]), dup)
        console.print(t)

    if dup_groups:
        console.print("\n[bold magenta]Duplicate Passwords[/bold magenta]:")
        for i, (_, group) in enumerate(list(dup_groups.items())[:10], 1):
            console.print(
                f"  Group {i}: " + "  |  ".join(f"[cyan]{e}[/cyan]" for e in group)
            )
        console.print("[dim]  Tip: use unique passwords for each account[/dim]")

    if errors:
        console.print(
            f"\n[dim]Could not decrypt {len(errors)} entries "
            f"(wrong key or locked agent).[/dim]"
        )


def cmd_otp(entry: Optional[str] = None) -> None:
    """Generate a TOTP code from a stored OTP secret."""
    if not DEPS.get("pyotp"):
        console.print(
            "[red]pyotp not installed.[/red] Run: [cyan]pip install pyotp[/cyan]"
        )
        return

    import pyotp

    if not entry:
        entries = get_all_entries()
        entry = fuzzy_select(entries, "Select OTP entry")
        if not entry:
            return

    content, error = get_entry_raw(entry)
    if error:
        console.print(f"[red]Error:[/red] {error}")
        return

    data = parse_entry(content)
    secret = (
        data.get("otp") or data.get("totp") or
        data.get("secret") or data.get("otpauth")
    )
    if not secret:
        for val in data.values():
            if val and val.startswith("otpauth://"):
                secret = val
                break

    if not secret:
        console.print(f"[red]No OTP secret in '{entry}'.[/red]")
        console.print(
            "[dim]Add a field like [bold]otp: YOUR_SECRET[/bold] to the entry.[/dim]"
        )
        return

    try:
        totp = pyotp.parse_uri(secret) if secret.startswith("otpauth://") \
            else pyotp.TOTP(secret.upper().replace(" ", ""))
    except Exception as e:
        console.print(f"[red]Invalid OTP secret:[/red] {e}")
        return

    code = totp.now()
    remaining = 30 - (int(time.time()) % 30)
    console.print(Panel(
        f"[bold green]{code[:3]} {code[3:]}[/bold green]\n"
        f"[dim]Valid for {remaining}s  |  {entry}[/dim]",
        title="[bold]OTP Code[/bold]", border_style="green",
    ))
    copy_to_clipboard(code, timeout=remaining + 2)


def cmd_run(entry: str, command: List[str]) -> None:
    """
    Inject a pass entry's fields as environment variables, then exec `command`.

    Field mapping:  password -> PASS_PASSWORD
                    username -> PASS_USERNAME
                    url      -> PASS_URL  (etc.)
    """
    if not command:
        console.print("[red]No command supplied after entry.[/red]")
        console.print("[dim]Usage: run <entry> -- <command>[/dim]")
        return

    content, error = get_entry_raw(entry)
    if error:
        console.print(f"[red]Error:[/red] {error}")
        return

    data = parse_entry(content)
    env = os.environ.copy()
    injected = []
    for key, value in data.items():
        env_key = f"PASS_{key.upper().replace('-', '_')}"
        env[env_key] = value
        injected.append(env_key)

    console.print(f"[dim]Injecting:[/dim] {', '.join(injected)}")
    console.print(f"[dim]Running:[/dim] {' '.join(command)}\n")
    try:
        result = subprocess.run(command, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        console.print(f"[red]Command not found:[/red] {command[0]}")
    except KeyboardInterrupt:
        pass


def cmd_sync() -> None:
    """Pull then push the password store git repository."""
    console.print("[bold]Syncing password store...[/bold]")
    for action in ("pull", "push"):
        console.print(f"[dim]{action.capitalize()}ing...[/dim]")
        out, err, rc = run_command(["pass", "git", action])
        if rc != 0:
            console.print(f"[red]{action.capitalize()} failed:[/red] {err or out}")
            return
        if out:
            console.print(out)
    console.print("[bold green]Sync complete.[/bold green]")


def cmd_git_log(n: int = 10) -> None:
    """Show recent git history of the password store."""
    out, err, rc = run_command([
        "pass", "git", "log",
        "--oneline", f"-{n}",
        "--format=%C(yellow)%h%Creset %C(green)%ar%Creset %s",
    ])
    if rc != 0:
        console.print(f"[red]Error:[/red] {err}")
        return
    if not out:
        console.print("[yellow]No git history found. Run 'sync' to set up remote.[/yellow]")
        return
    console.print(Panel(out, title="[bold]Password Store History[/bold]", border_style="dim"))


def cmd_import(filepath: str, fmt: str = "auto") -> None:
    """
    Import passwords from a CSV export.
    Supports Bitwarden, LastPass, 1Password, and generic CSV formats.
    """
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {filepath}")
        return

    # Auto-detect format
    if fmt == "auto":
        with open(path, newline="", encoding="utf-8-sig") as f:
            header = f.readline().lower()
        if "login_uri" in header or "bitwarden" in filepath.lower():
            fmt = "bitwarden"
        elif "grouping" in header or "lastpass" in filepath.lower():
            fmt = "lastpass"
        elif "notesplaintext" in header or "1password" in filepath.lower():
            fmt = "1password"
        else:
            fmt = "generic"

    console.print(f"[bold]Importing[/bold] {filepath} [dim](format: {fmt})[/dim]")
    imported = skipped = 0

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.lower().strip(): v.strip() for k, v in row.items() if k}

            if fmt == "bitwarden":
                name = row.get("name", "")
                folder = row.get("folder", "")
                username = row.get("login_username", "")
                password = row.get("login_password", "")
                url = row.get("login_uri", "")
                notes = row.get("notes", "")
                otp = row.get("login_totp", "")
            elif fmt == "lastpass":
                name = row.get("name", "")
                folder = row.get("grouping", "")
                username = row.get("username", "")
                password = row.get("password", "")
                url = row.get("url", "")
                notes = row.get("extra", "")
                otp = ""
            elif fmt == "1password":
                name = row.get("title", "")
                folder = row.get("type", "")
                username = row.get("username", "")
                password = row.get("password", "")
                url = row.get("url", "")
                notes = row.get("notesplaintext", "")
                otp = row.get("totp secret key", "")
            else:  # generic
                name = row.get("name", row.get("title", ""))
                folder = row.get("folder", row.get("group", ""))
                username = row.get("username", row.get("login", ""))
                password = row.get("password", "")
                url = row.get("url", row.get("uri", ""))
                notes = row.get("notes", row.get("extra", ""))
                otp = row.get("totp", row.get("otp", ""))

            if not name or not password:
                skipped += 1
                continue

            safe_name = name.replace("/", "-").replace(" ", "_").replace("..", "-").lower()
            safe_folder = (
                folder.replace("/", "-").replace(" ", "_").replace("..", "-").lower()
                if folder else ""
            )
            # Strip leading dots/dashes to prevent hidden files or relative traversal
            safe_name = safe_name.lstrip(".-") or "unnamed"
            safe_folder = safe_folder.lstrip(".-")
            entry_path = f"{safe_folder}/{safe_name}" if safe_folder else safe_name

            data: Dict[str, str] = {"password": password}
            if username:
                data["username"] = username
            if url:
                data["url"] = url
            if notes:
                data["notes"] = notes
            if otp:
                data["otp"] = otp

            proc = subprocess.Popen(
                ["pass", "insert", "-m", "-f", entry_path],
                stdin=subprocess.PIPE, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            _, stderr = proc.communicate(format_entry(data))
            if proc.returncode == 0:
                imported += 1
                console.print(f"  [green]✓[/green] {entry_path}")
            else:
                skipped += 1
                console.print(f"  [red]✗[/red] {entry_path}: {stderr.strip()}")

    console.print(
        f"\n[bold green]Done:[/bold green] {imported} imported, {skipped} skipped."
    )


def _preview_entry_metadata(entry: str) -> None:
    """Show a brief preview of entry metadata (no password) for confirmation flows."""
    content, error = get_entry_raw(entry)
    if error:
        return
    data = parse_entry(content)
    parts = [f"[bold]{entry}[/bold]"]
    if data.get("username"):
        parts.append(f"  [dim]Username:[/dim] {data['username']}")
    if data.get("email"):
        parts.append(f"  [dim]Email:[/dim] {data['email']}")
    if data.get("url"):
        parts.append(f"  [dim]URL:[/dim] {data['url']}")
    console.print("\n".join(parts))


def _entry_action_menu(entry: str) -> None:
    """Show an action menu for a selected entry and execute the chosen action."""
    console.print(f"\n[dim]Selected:[/dim] [bold]{entry}[/bold]")
    console.print(
        "  [cyan]s[/cyan] Show          View full entry details\n"
        "  [cyan]c[/cyan] Copy          Copy password to clipboard\n"
        "  [cyan]u[/cyan] Username      Copy username to clipboard\n"
        "  [cyan]l[/cyan] URL           Copy URL to clipboard\n"
        "  [cyan]o[/cyan] OTP           Generate TOTP code\n"
        "  [cyan]e[/cyan] Edit          Open in $EDITOR\n"
        "  [cyan]d[/cyan] Delete        Delete this entry\n"
        "  [cyan]q[/cyan] Cancel"
    )
    try:
        action = Prompt.ask("Action", default="s").strip().lower()
    except KeyboardInterrupt:
        return

    if action == "s":
        cmd_get(entry)
    elif action == "c":
        cmd_get(entry, clip=True)
    elif action == "u":
        content, error = get_entry_raw(entry)
        if error:
            console.print(f"[red]Error:[/red] {error}")
        else:
            data = parse_entry(content)
            username = data.get("username") or data.get("email", "")
            if username:
                copy_to_clipboard(username)
            else:
                console.print("[yellow]No username or email found in this entry.[/yellow]")
    elif action == "l":
        content, error = get_entry_raw(entry)
        if error:
            console.print(f"[red]Error:[/red] {error}")
        else:
            data = parse_entry(content)
            url = data.get("url", "")
            if url:
                copy_to_clipboard(url)
            else:
                console.print("[yellow]No URL found in this entry.[/yellow]")
    elif action == "o":
        cmd_otp(entry)
    elif action == "e":
        run_command(["pass", "edit", entry], interactive=True)
    elif action == "d":
        if Confirm.ask(f"[red]Delete '{entry}'?[/red]", default=False):
            _, err, rc = run_command(["pass", "rm", "-r", "-f", entry])
            console.print(
                f"[green]Deleted '{entry}'.[/green]" if rc == 0
                else f"[red]Error:[/red] {err}"
            )


def cmd_browse() -> None:
    """Fuzzy-pick an entry then choose what to do with it."""
    entries = get_all_entries()
    if not entries:
        console.print("[yellow]No entries found.[/yellow]")
        return

    entry = fuzzy_select(entries, "Browse passwords")
    if not entry:
        return

    _entry_action_menu(entry)


def cmd_export_vault(output_path: str) -> None:
    """Export the entire password store to a single AES-256-GCM encrypted vault file."""
    pass_dir = Path(CONFIG.get("pass_dir", Path.home() / ".password-store"))
    if not pass_dir.exists():
        console.print("[red]Password store not found.[/red]")
        return

    out = Path(output_path).expanduser().resolve()
    if out.exists():
        if not Confirm.ask(f"[yellow]'{out}' already exists. Overwrite?[/yellow]", default=False):
            return

    # Prompt for passphrase
    passphrase = Prompt.ask("Vault passphrase", password=True)
    if not passphrase:
        console.print("[red]Passphrase cannot be empty.[/red]")
        return
    confirm = Prompt.ask("Confirm passphrase", password=True)
    if passphrase != confirm:
        console.print("[red]Passphrases do not match.[/red]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Creating vault…", total=None)

        # Build in-memory tar.gz, skipping .git/
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for item in pass_dir.rglob("*"):
                # Skip the .git directory and everything inside it
                rel = item.relative_to(pass_dir)
                if rel.parts and rel.parts[0] == ".git":
                    continue
                arcname = Path(".password-store") / rel
                tar.add(str(item), arcname=str(arcname), recursive=False)
        plaintext = buf.getvalue()

        progress.update(task, description="Encrypting…")

        # Derive key and encrypt
        salt = os.urandom(32)
        nonce = os.urandom(12)
        key = _derive_vault_key(passphrase.encode(), salt)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

        progress.update(task, description="Writing vault file…")

        # Write: magic + salt + nonce + ciphertext+tag
        with open(out, "wb") as f:
            f.write(VAULT_MAGIC)
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)
        os.chmod(out, 0o600)

    size_kb = out.stat().st_size / 1024
    entry_count = len(list(pass_dir.rglob("*.gpg")))
    console.print(Panel(
        f"[bold green]Vault exported successfully.[/bold green]\n\n"
        f"  [dim]File:[/dim]    {out}\n"
        f"  [dim]Size:[/dim]    {size_kb:.1f} KB\n"
        f"  [dim]Entries:[/dim] {entry_count}\n"
        f"  [dim]Cipher:[/dim]  AES-256-GCM · PBKDF2-SHA256 (600k iters)",
        border_style="green",
        title="Export Vault",
    ))


def cmd_import_vault(input_path: str, force: bool = False) -> None:
    """Restore the password store from an AES-256-GCM encrypted vault file."""
    inp = Path(input_path).expanduser().resolve()
    if not inp.exists():
        console.print(f"[red]Vault file not found: {inp}[/red]")
        return

    # Read and validate magic header
    with open(inp, "rb") as f:
        magic = f.read(4)
        if magic != VAULT_MAGIC:
            console.print(
                "[red]Not a valid PassCLI vault file.[/red]\n"
                "[dim]Expected magic header 'PCV1'.[/dim]"
            )
            return
        salt = f.read(32)
        nonce = f.read(12)
        ciphertext = f.read()

    if len(salt) != 32 or len(nonce) != 12 or not ciphertext:
        console.print("[red]Vault file is corrupted or truncated.[/red]")
        return

    # Prompt for passphrase
    passphrase = Prompt.ask("Vault passphrase", password=True)
    if not passphrase:
        console.print("[red]Passphrase cannot be empty.[/red]")
        return

    # Decrypt
    try:
        key = _derive_vault_key(passphrase.encode(), salt)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception:
        console.print("[red]Decryption failed. Wrong passphrase or corrupted vault.[/red]")
        return

    pass_dir = Path(CONFIG.get("pass_dir", Path.home() / ".password-store"))

    # Warn if existing entries would be overwritten
    if not force:
        existing = list(pass_dir.rglob("*.gpg")) if pass_dir.exists() else []
        if existing:
            console.print(Panel(
                f"[yellow]Your current password store has [bold]{len(existing)}[/bold] "
                f"entr{'y' if len(existing) == 1 else 'ies'}.[/yellow]\n"
                "Importing will overwrite files with the same names.",
                border_style="yellow",
                title="⚠ Existing Store Detected",
            ))
            if not Confirm.ask("Overwrite existing password store?", default=False):
                console.print("[dim]Import cancelled.[/dim]")
                return

    # Extract tar.gz into the parent of pass_dir
    # The tar archive has '.password-store/' as its top-level directory
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Restoring vault…", total=None)
        buf = io.BytesIO(plaintext)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            tar.extractall(pass_dir.parent)  # noqa: S202  (trusted self-generated archive)

    restored = len(list(pass_dir.rglob("*.gpg")))
    console.print(Panel(
        f"[bold green]Vault imported successfully.[/bold green]\n\n"
        f"  [dim]Source:[/dim]  {inp}\n"
        f"  [dim]Store:[/dim]   {pass_dir}\n"
        f"  [dim]Entries:[/dim] {restored} password{'s' if restored != 1 else ''} restored",
        border_style="green",
        title="Import Vault",
    ))


def cmd_wizard() -> None:
    """Guided first-time setup: GPG key + pass init + optional git."""
    console.print(Panel(
        "[bold cyan]PassCLI Setup Wizard[/bold cyan]\n\n"
        "This wizard will set up your GPG key and password store step by step.",
        border_style="cyan",
    ))

    # Step 1: Dependencies
    console.print("\n[bold]Step 1[/bold] — Checking dependencies")
    missing = [t for t in ("pass", "gpg") if not shutil.which(t)]
    if missing:
        console.print(f"[red]Missing:[/red] {', '.join(missing)}")
        console.print("  macOS:  [cyan]brew install gnupg pass[/cyan]")
        console.print("  Ubuntu: [cyan]sudo apt install gnupg2 pass[/cyan]")
        console.print("  Arch:   [cyan]sudo pacman -S gnupg pass[/cyan]")
        return
    console.print("[green]✓ pass and gpg are installed[/green]")

    # Step 2: GPG key
    console.print("\n[bold]Step 2[/bold] — GPG key")
    keys = get_gpg_keys()
    use_existing = False
    if keys:
        console.print(f"[green]✓ Found {len(keys)} existing GPG key(s):[/green]")
        for i, (kid, uid) in enumerate(keys, 1):
            console.print(f"  {i}. [cyan]{kid}[/cyan]  {uid}")
        use_existing = Confirm.ask("Use an existing key?", default=True)

    if not use_existing:
        console.print("\n[dim]Launching GPG key generation...[/dim]")
        console.print("[yellow]Tip: RSA 4096, no expiry is recommended.[/yellow]")
        run_command(["gpg", "--full-generate-key"], interactive=True)
        keys = get_gpg_keys()
        if not keys:
            console.print("[red]No key found after generation. Aborting.[/red]")
            return

    if len(keys) == 1:
        key_id = keys[0][0]
        console.print(f"[green]Using key: {key_id}[/green]")
    else:
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("#", width=3)
        t.add_column("Key ID", style="cyan")
        t.add_column("User")
        for i, (kid, uid) in enumerate(keys, 1):
            t.add_row(str(i), kid, uid)
        console.print(t)
        choice = IntPrompt.ask("Select key number", default=1)
        key_id = keys[max(0, choice - 1)][0]

    # Step 3: Init pass
    console.print(f"\n[bold]Step 3[/bold] — Initializing pass with key [cyan]{key_id}[/cyan]")
    out, err, rc = run_command(["pass", "init", key_id])
    if rc != 0 and "already initialized" not in (err + out):
        console.print(f"[red]Error:[/red] {err}")
        return
    console.print("[green]✓ Password store ready.[/green]")

    # Step 4: Git
    console.print("\n[bold]Step 4[/bold] — Git integration (optional)")
    if shutil.which("git") and Confirm.ask("Enable git tracking for your store?", default=True):
        run_command(["pass", "git", "init"])
        console.print("[green]✓ Git initialized.[/green]")
        remote = Prompt.ask("Remote URL (leave blank to skip)", default="")
        if remote:
            run_command(["pass", "git", "remote", "add", "origin", remote])
            console.print("[green]✓ Remote set.[/green]")

    # Step 5: First entry
    console.print("\n[bold]Step 5[/bold] — Add your first password?")
    if Confirm.ask("Add your first entry now?", default=True):
        cmd_insert()

    console.print(Panel(
        "[bold green]All done![/bold green]\n\n"
        "Quick reference:\n"
        "  [cyan]passcli[/cyan]                 — open interactive shell\n"
        "  [cyan]passcli get <entry>[/cyan]      — show a password\n"
        "  [cyan]passcli get <entry> --clip[/cyan] — copy to clipboard\n"
        "  [cyan]passcli insert <entry>[/cyan]   — add a new entry\n"
        "  [cyan]passcli health[/cyan]           — password health report\n"
        "  [cyan]passcli --help[/cyan]           — all commands",
        border_style="green",
    ))


def cmd_config_show() -> None:
    t = Table(title="PassCLI Config", box=box.SIMPLE)
    t.add_column("Key", style="cyan")
    t.add_column("Value")
    t.add_column("Description", style="dim")
    descriptions = {
        "clip_timeout": "Seconds before clipboard is cleared",
        "default_password_length": "Default length for generated passwords",
        "default_mode": "Startup mode (shell/menu)",
        "pass_dir": "Path to your password store",
    }
    for key, val in CONFIG.items():
        t.add_row(key, str(val), descriptions.get(key, ""))
    console.print(t)
    console.print(f"[dim]Config file: {CONFIG_PATH}[/dim]")


def cmd_config_set(key: str, value: str) -> None:
    if key not in DEFAULT_CONFIG:
        console.print(f"[red]Unknown key:[/red] {key}")
        console.print(f"Valid keys: {', '.join(DEFAULT_CONFIG)}")
        return
    original_type = type(DEFAULT_CONFIG[key])
    try:
        if original_type is int:
            typed_value = int(value)
        elif original_type is bool:
            typed_value = value.lower() in ("true", "1", "yes")
        else:
            typed_value = value
    except ValueError:
        console.print(f"[red]Expected {original_type.__name__} for '{key}'.[/red]")
        return
    CONFIG[key] = typed_value
    save_config(CONFIG)
    console.print(f"[green]Set[/green] {key} = {typed_value}")


# ---------------------------------------------------------------------------
# Interactive shell
# ---------------------------------------------------------------------------


class PassShell(cmd.Cmd):
    prompt = "passcli> "

    def __init__(self):
        super().__init__()
        self._setup_history()

    def _setup_history(self) -> None:
        hist = Path.home() / ".config" / "passcli" / "history"
        hist.parent.mkdir(parents=True, exist_ok=True)
        # 0o600 — owner read/write only; history contains entry names
        hist.touch(mode=0o600, exist_ok=True)
        try:
            readline.read_history_file(str(hist))
        except FileNotFoundError:
            pass
        import atexit
        atexit.register(readline.write_history_file, str(hist))
        readline.set_history_length(500)

    def _complete_entries(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return [e for e in get_all_entries() if e.startswith(text)]

    def preloop(self) -> None:
        entries = get_all_entries()
        keys = get_gpg_keys()
        console.print(Panel(
            "[bold cyan]PassCLI[/bold cyan] — Smart Password Manager\n\n"
            f"  Entries : [green]{len(entries)}[/green]   "
            f"GPG keys : [green]{len(keys)}[/green]   "
            f"fzf : {'[green]yes[/green]' if DEPS.get('fzf') else '[dim]no[/dim]'}   "
            f"OTP : {'[green]yes[/green]' if DEPS.get('pyotp') else '[dim]no[/dim]'}\n\n"
            "Type [bold]help[/bold] for all commands  |  "
            "[bold]browse[/bold] to pick an entry  |  "
            "[bold]wizard[/bold] for first-time setup",
            border_style="cyan",
        ))

    # -- Core commands -------------------------------------------------------

    def do_get(self, arg: str) -> None:
        """get [entry] [--clip] [--field FIELD]  Show a password entry."""
        parts = arg.split()
        entry, clip, field = None, False, None
        i = 0
        while i < len(parts):
            if parts[i] == "--clip":
                clip = True
            elif parts[i] == "--field" and i + 1 < len(parts):
                field = parts[i + 1]
                i += 1
            else:
                entry = parts[i]
            i += 1
        cmd_get(entry, clip, field, interactive_followup=not clip and not field)

    complete_get = _complete_entries

    def do_show(self, arg: str) -> None:
        """show [entry]  Alias for get."""
        self.do_get(arg)

    complete_show = _complete_entries

    def do_clip(self, arg: str) -> None:
        """clip [entry]  Copy password to clipboard with auto-clear."""
        cmd_get(arg.strip() or None, clip=True)

    complete_clip = _complete_entries

    def do_insert(self, arg: str) -> None:
        """insert [entry]  Add a new entry with guided prompts."""
        cmd_insert(arg.strip() or None)

    def do_add(self, arg: str) -> None:
        """add [entry]  Alias for insert."""
        self.do_insert(arg)

    def do_generate(self, arg: str) -> None:
        """generate [entry] [length] [--no-symbols] [--clip]  Generate a password."""
        parts = arg.split()
        entry, length, no_symbols, clip = None, None, False, False
        for p in parts:
            if p == "--no-symbols":
                no_symbols = True
            elif p == "--clip":
                clip = True
            elif p.isdigit() and length is None:
                length = int(p)
            elif entry is None:
                entry = p
        cmd_generate(entry, length, no_symbols, clip)

    complete_generate = _complete_entries

    def do_edit(self, arg: str) -> None:
        """edit [entry]  Edit an entry in your $EDITOR."""
        entry = arg.strip() or fuzzy_select(get_all_entries(), "Select entry to edit")
        if entry:
            run_command(["pass", "edit", entry], interactive=True)

    complete_edit = _complete_entries

    def do_delete(self, arg: str) -> None:
        """delete [entry]  Delete a password entry."""
        entry = arg.strip() or fuzzy_select(get_all_entries(), "Select entry to delete")
        if not entry:
            return
        _preview_entry_metadata(entry)
        if Confirm.ask(f"[red]Delete '{entry}'?[/red]", default=False):
            _, err, rc = run_command(["pass", "rm", "-r", "-f", entry])
            console.print(
                f"[green]Deleted '{entry}'.[/green]" if rc == 0
                else f"[red]Error:[/red] {err}"
            )

    complete_delete = _complete_entries

    def do_browse(self, arg: str) -> None:
        """browse  Fuzzy-search entries and pick an action."""
        cmd_browse()

    def do_ls(self, arg: str) -> None:
        """ls [path]  List all entries."""
        cmd_args = ["pass", "ls"] + ([arg.strip()] if arg.strip() else [])
        out, err, rc = run_command(cmd_args)
        console.print(out if rc == 0 else f"[red]{err}[/red]")

    def do_find(self, arg: str) -> None:
        """find <term>  Search entries by name, then optionally act on a result."""
        term = arg.strip() or Prompt.ask("Search term")
        out, err, rc = run_command(["pass", "find", term])
        console.print(out if rc == 0 else f"[red]{err}[/red]")
        if rc == 0:
            matches = [e for e in get_all_entries() if term.lower() in e.lower()]
            if matches:
                entry = fuzzy_select(matches, "Act on entry (0 to skip)")
                if entry:
                    _entry_action_menu(entry)

    # -- Power user commands -------------------------------------------------

    def do_otp(self, arg: str) -> None:
        """otp [entry]  Generate a TOTP code from a stored OTP secret."""
        cmd_otp(arg.strip() or None)

    complete_otp = _complete_entries

    def do_run(self, arg: str) -> None:
        """run <entry> -- <command>  Inject entry fields as env vars and run a command."""
        if " -- " in arg:
            entry_part, cmd_part = arg.split(" -- ", 1)
            cmd_run(entry_part.strip(), cmd_part.split())
        else:
            console.print("[red]Usage:[/red] run <entry> -- <command>")
            console.print("[dim]Example: run aws/prod -- aws s3 ls[/dim]")

    def do_health(self, arg: str) -> None:
        """health  Scan all passwords for strength and duplicates."""
        cmd_health()

    def do_import(self, arg: str) -> None:
        """import <file> [format]  Import from Bitwarden/LastPass/1Password CSV."""
        parts = arg.split()
        if not parts:
            console.print("[red]Usage:[/red] import <file> [bitwarden|lastpass|1password|auto]")
            return
        cmd_import(parts[0], parts[1] if len(parts) > 1 else "auto")

    def do_sync(self, arg: str) -> None:
        """sync  Git pull + push the password store."""
        cmd_sync()

    def do_gitlog(self, arg: str) -> None:
        """gitlog [n]  Show recent password store git history."""
        n = int(arg.strip()) if arg.strip().isdigit() else 10
        cmd_git_log(n)

    # -- Entry management ----------------------------------------------------

    def do_mv(self, arg: str) -> None:
        """mv <old> <new>  Move or rename an entry."""
        parts = arg.split()
        if len(parts) >= 2:
            old, new = parts[0], parts[1]
        else:
            old = Prompt.ask("Source entry")
            new = Prompt.ask("Destination")
        _, err, rc = run_command(["pass", "mv", old, new])
        console.print(
            f"[green]Moved '{old}' -> '{new}'.[/green]" if rc == 0
            else f"[red]Error:[/red] {err}"
        )

    def do_cp(self, arg: str) -> None:
        """cp <old> <new>  Copy an entry."""
        parts = arg.split()
        if len(parts) >= 2:
            old, new = parts[0], parts[1]
        else:
            old = Prompt.ask("Source entry")
            new = Prompt.ask("Destination")
        _, err, rc = run_command(["pass", "cp", old, new])
        console.print(
            f"[green]Copied '{old}' -> '{new}'.[/green]" if rc == 0
            else f"[red]Error:[/red] {err}"
        )

    def do_archive(self, arg: str) -> None:
        """archive [entry]  Move an entry to the archive/ folder."""
        entry = arg.strip() or fuzzy_select(get_all_entries(), "Select entry to archive")
        if not entry:
            return
        _, err, rc = run_command(["pass", "mv", entry, f"archive/{entry}"])
        console.print(
            f"[green]Archived '{entry}'.[/green]" if rc == 0
            else f"[red]Error:[/red] {err}"
        )

    complete_archive = _complete_entries

    def do_restore(self, arg: str) -> None:
        """restore [entry]  Restore an entry from the archive/ folder."""
        archived = [e for e in get_all_entries() if e.startswith("archive/")]
        if not archived:
            console.print("[yellow]No archived entries found.[/yellow]")
            return
        display = [e[len("archive/"):] for e in archived]
        entry = arg.strip() or fuzzy_select(display, "Select entry to restore")
        if not entry:
            return
        dest = Prompt.ask("Restore to", default=entry)
        if not dest.strip():
            console.print("[red]Destination cannot be empty.[/red]")
            return
        _, err, rc = run_command(["pass", "mv", f"archive/{entry}", dest])
        console.print(
            f"[green]Restored to '{dest}'.[/green]" if rc == 0
            else f"[red]Error:[/red] {err}"
        )

    # -- GPG & store setup ---------------------------------------------------

    def do_gpg_list(self, arg: str) -> None:
        """gpg_list  List all GPG keys."""
        keys = get_gpg_keys()
        if not keys:
            console.print("[red]No GPG keys found.[/red]")
            return
        t = Table(title="GPG Keys", box=box.SIMPLE)
        t.add_column("#", width=3)
        t.add_column("Key ID", style="cyan")
        t.add_column("User", style="magenta")
        for i, (kid, uid) in enumerate(keys, 1):
            t.add_row(str(i), kid, uid)
        console.print(t)

    def do_gpg_gen(self, arg: str) -> None:
        """gpg_gen  Generate a new GPG key (interactive)."""
        console.print("[yellow]Tip: RSA 4096, no expiry is recommended.[/yellow]")
        run_command(["gpg", "--full-generate-key"], interactive=True)

    def do_init(self, arg: str) -> None:
        """init  Initialize or re-initialize the password store."""
        keys = get_gpg_keys()
        if not keys:
            console.print("[red]No GPG keys found. Run 'gpg_gen' first.[/red]")
            return
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("#", width=3)
        t.add_column("Key ID", style="cyan")
        t.add_column("User")
        for i, (kid, uid) in enumerate(keys, 1):
            t.add_row(str(i), kid, uid)
        console.print(t)
        choice = IntPrompt.ask("Select key number", default=1)
        if 1 <= choice <= len(keys):
            key_id = keys[choice - 1][0]
            _, err, rc = run_command(["pass", "init", key_id])
            console.print(
                f"[green]Initialized with key {key_id}.[/green]" if rc == 0
                else f"[red]Error:[/red] {err}"
            )

    def do_wizard(self, arg: str) -> None:
        """wizard  Run the first-time setup wizard."""
        cmd_wizard()

    # -- Config --------------------------------------------------------------

    def do_config(self, arg: str) -> None:
        """config [key] [value]  View or change a config value."""
        parts = arg.split()
        if not parts:
            cmd_config_show()
        elif len(parts) == 1:
            val = CONFIG.get(parts[0])
            console.print(
                f"{parts[0]} = {val}" if val is not None
                else f"[red]Unknown key: {parts[0]}[/red]"
            )
        else:
            cmd_config_set(parts[0], " ".join(parts[1:]))

    # -- Misc ----------------------------------------------------------------

    def do_help(self, arg: str) -> None:
        """help  Show this help."""
        if arg:
            super().do_help(arg)
            return
        sections = {
            "Core": [
                ("get [entry] [--clip] [--field F]", "Show a password (or copy to clipboard)"),
                ("clip [entry]",                     "Copy password to clipboard + auto-clear"),
                ("insert [entry]",                   "Add new entry with guided prompts"),
                ("generate [entry] [len]",           "Generate a secure random password"),
                ("edit [entry]",                     "Open entry in $EDITOR"),
                ("delete [entry]",                   "Delete an entry"),
                ("browse",                           "Fuzzy-pick an entry and choose action"),
                ("ls [path]",                        "List all entries"),
                ("find <term>",                      "Search entries by name"),
            ],
            "Power User": [
                ("otp [entry]",                      "Generate TOTP code from stored secret"),
                ("run <entry> -- <cmd>",             "Inject entry fields as env vars and run"),
                ("health",                           "Password strength + duplicate report"),
                ("import <file> [format]",           "Import from Bitwarden/LastPass/1Password CSV"),
                ("sync",                             "Git pull + push the password store"),
                ("gitlog [n]",                       "Show recent password store git history"),
            ],
            "Entry Management": [
                ("mv <old> <new>",  "Move or rename an entry"),
                ("cp <old> <new>",  "Copy an entry"),
                ("archive [entry]", "Move entry to archive/ folder"),
                ("restore [entry]", "Restore an archived entry"),
            ],
            "Setup": [
                ("wizard",          "First-time setup (GPG key + pass init + git)"),
                ("init",            "Initialize/re-initialize password store"),
                ("gpg_gen",         "Generate a new GPG key"),
                ("gpg_list",        "List existing GPG keys"),
                ("config [k] [v]",  "View or set a config value"),
            ],
        }
        for section, commands in sections.items():
            t = Table(title=f"[bold]{section}[/bold]", box=box.SIMPLE, show_header=False,
                      padding=(0, 2))
            t.add_column("Command", style="cyan", min_width=34)
            t.add_column("Description")
            for name, desc in commands:
                t.add_row(name, desc)
            console.print(t)

    def do_export_vault(self, arg: str) -> None:
        """export-vault <file>  Export password store to an AES-encrypted vault file."""
        parts = arg.split()
        if not parts:
            console.print("[yellow]Usage: export-vault <output_file>[/yellow]")
            return
        cmd_export_vault(parts[0])

    def do_import_vault(self, arg: str) -> None:
        """import-vault <file> [--force]  Restore password store from a vault file."""
        parts = arg.split()
        if not parts:
            console.print("[yellow]Usage: import-vault <vault_file> [--force][/yellow]")
            return
        force = "--force" in parts or "-f" in parts
        cmd_import_vault(parts[0], force=force)

    def do_quit(self, arg: str) -> bool:
        """quit  Exit PassCLI."""
        console.print("[dim]Goodbye.[/dim]")
        return True

    def do_exit(self, arg: str) -> bool:
        return self.do_quit(arg)

    def do_EOF(self, arg: str) -> bool:
        console.print()
        return self.do_quit(arg)

    def emptyline(self) -> None:
        pass

    def default(self, line: str) -> None:
        console.print(
            f"[red]Unknown command:[/red] {line}  "
            "— Type [bold]help[/bold] to see available commands."
        )


# ---------------------------------------------------------------------------
# Direct CLI (argparse)
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="passcli",
        description="PassCLI — A smart pass wrapper for everyone",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  passcli                           Start interactive shell\n"
            "  passcli get email/gmail           Show a password\n"
            "  passcli get email/gmail --clip    Copy to clipboard\n"
            "  passcli insert web/github         Add new entry\n"
            "  passcli otp web/github            TOTP code\n"
            "  passcli run aws/prod -- aws s3 ls Inject secrets as env vars\n"
            "  passcli health                    Password health report\n"
            "  passcli import export.csv         Import from Bitwarden/LastPass\n"
            "  passcli sync                      Git pull + push\n"
            "  passcli wizard                    First-time setup\n"
        ),
    )
    sub = p.add_subparsers(dest="command")

    # get / show
    for name in ("get", "show"):
        sp = sub.add_parser(name, help="Retrieve a password entry")
        sp.add_argument("entry", nargs="?")
        sp.add_argument("--clip", "-c", action="store_true", help="Copy to clipboard")
        sp.add_argument("--field", "-f", help="Show a specific field only")

    # clip
    sp = sub.add_parser("clip", help="Copy password to clipboard")
    sp.add_argument("entry", nargs="?")

    # insert / add
    for name in ("insert", "add"):
        sp = sub.add_parser(name, help="Insert a new password entry")
        sp.add_argument("entry", nargs="?")
        sp.add_argument("--raw", action="store_true", help="Read raw content from stdin")

    # generate
    sp = sub.add_parser("generate", help="Generate a password")
    sp.add_argument("entry", nargs="?")
    sp.add_argument("length", nargs="?", type=int)
    sp.add_argument("--no-symbols", "-n", action="store_true")
    sp.add_argument("--clip", "-c", action="store_true")

    # edit
    sp = sub.add_parser("edit", help="Edit an entry")
    sp.add_argument("entry", nargs="?")

    # delete
    sp = sub.add_parser("delete", help="Delete an entry")
    sp.add_argument("entry", nargs="?")
    sp.add_argument("--force", "-f", action="store_true")

    # browse
    sub.add_parser("browse", help="Fuzzy-search and interact with entries")

    # health
    sub.add_parser("health", help="Password health report")

    # otp
    sp = sub.add_parser("otp", help="Generate TOTP code")
    sp.add_argument("entry", nargs="?")

    # run
    sp = sub.add_parser("run", help="Inject entry as env vars and run a command")
    sp.add_argument("entry")
    sp.add_argument("cmd", nargs=argparse.REMAINDER)

    # sync
    sub.add_parser("sync", help="Git pull + push")

    # gitlog
    sp = sub.add_parser("gitlog", help="Show git history")
    sp.add_argument("n", nargs="?", type=int, default=10)

    # import
    sp = sub.add_parser("import", help="Import from CSV")
    sp.add_argument("file")
    sp.add_argument("--format", "-f", default="auto",
                    choices=["auto", "bitwarden", "lastpass", "1password", "generic"])

    # find
    sp = sub.add_parser("find", help="Find entries by name")
    sp.add_argument("term")

    # ls
    sp = sub.add_parser("ls", help="List entries")
    sp.add_argument("path", nargs="?", default="")

    # mv
    sp = sub.add_parser("mv", help="Move/rename an entry")
    sp.add_argument("old")
    sp.add_argument("new")

    # cp
    sp = sub.add_parser("cp", help="Copy an entry")
    sp.add_argument("old")
    sp.add_argument("new")

    # archive
    sp = sub.add_parser("archive", help="Archive an entry")
    sp.add_argument("entry", nargs="?")

    # restore
    sp = sub.add_parser("restore", help="Restore an archived entry")
    sp.add_argument("entry", nargs="?")

    # wizard
    sub.add_parser("wizard", help="First-time setup wizard")

    # config
    sp = sub.add_parser("config", help="View or set config")
    sp.add_argument("key", nargs="?")
    sp.add_argument("value", nargs="?")

    # shell (explicit)
    sub.add_parser("shell", help="Start interactive shell (default when no command given)")

    # export-vault
    sp = sub.add_parser(
        "export-vault",
        help="Export password store to a single AES-256-GCM encrypted vault file",
    )
    sp.add_argument("file", help="Output vault file path (e.g. ~/backup.passvault)")

    # import-vault
    sp = sub.add_parser(
        "import-vault",
        help="Restore password store from an AES-256-GCM encrypted vault file",
    )
    sp.add_argument("file", help="Path to the vault file to import")
    sp.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing password store without prompting",
    )

    return p


def _start_shell() -> None:
    try:
        PassShell().cmdloop()
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye.[/dim]")


def main() -> None:
    if len(sys.argv) == 1:
        _start_shell()
        return

    parser = build_parser()
    args = parser.parse_args()

    if not args.command or args.command == "shell":
        _start_shell()

    elif args.command in ("get", "show"):
        cmd_get(args.entry, args.clip, args.field)

    elif args.command == "clip":
        cmd_get(args.entry, clip=True)

    elif args.command in ("insert", "add"):
        cmd_insert(args.entry, structured=not getattr(args, "raw", False))

    elif args.command == "generate":
        cmd_generate(args.entry, args.length, args.no_symbols, args.clip)

    elif args.command == "edit":
        entry = args.entry or fuzzy_select(get_all_entries(), "Select entry to edit")
        if entry:
            run_command(["pass", "edit", entry], interactive=True)

    elif args.command == "delete":
        entry = args.entry or fuzzy_select(get_all_entries(), "Select entry to delete")
        if entry:
            if not args.force:
                _preview_entry_metadata(entry)
            if args.force or Confirm.ask(f"[red]Delete '{entry}'?[/red]", default=False):
                _, err, rc = run_command(["pass", "rm", "-r", "-f", entry])
                console.print(
                    f"[green]Deleted '{entry}'.[/green]" if rc == 0
                    else f"[red]{err}[/red]"
                )

    elif args.command == "browse":
        cmd_browse()

    elif args.command == "health":
        cmd_health()

    elif args.command == "otp":
        cmd_otp(args.entry)

    elif args.command == "run":
        remainder = args.cmd
        if remainder and remainder[0] == "--":
            remainder = remainder[1:]
        cmd_run(args.entry, remainder)

    elif args.command == "sync":
        cmd_sync()

    elif args.command == "gitlog":
        cmd_git_log(args.n)

    elif args.command == "import":
        cmd_import(args.file, args.format)

    elif args.command == "find":
        out, err, rc = run_command(["pass", "find", args.term])
        console.print(out if rc == 0 else f"[red]{err}[/red]")
        if rc == 0:
            matches = [e for e in get_all_entries() if args.term.lower() in e.lower()]
            if matches:
                entry = fuzzy_select(matches, "Act on entry (0 to skip)")
                if entry:
                    _entry_action_menu(entry)

    elif args.command == "ls":
        cmd_args = ["pass", "ls"] + ([args.path] if args.path else [])
        out, err, rc = run_command(cmd_args)
        console.print(out if rc == 0 else f"[red]{err}[/red]")

    elif args.command == "mv":
        _, err, rc = run_command(["pass", "mv", args.old, args.new])
        console.print(
            f"[green]Moved '{args.old}' -> '{args.new}'.[/green]" if rc == 0
            else f"[red]{err}[/red]"
        )

    elif args.command == "cp":
        _, err, rc = run_command(["pass", "cp", args.old, args.new])
        console.print(
            f"[green]Copied '{args.old}' -> '{args.new}'.[/green]" if rc == 0
            else f"[red]{err}[/red]"
        )

    elif args.command == "archive":
        entry = args.entry or fuzzy_select(get_all_entries(), "Select entry to archive")
        if entry:
            _, err, rc = run_command(["pass", "mv", entry, f"archive/{entry}"])
            console.print(
                f"[green]Archived '{entry}'.[/green]" if rc == 0
                else f"[red]{err}[/red]"
            )

    elif args.command == "restore":
        archived = [e for e in get_all_entries() if e.startswith("archive/")]
        display = [e[len("archive/"):] for e in archived]
        entry = args.entry or fuzzy_select(display, "Select entry to restore")
        if entry:
            dest = Prompt.ask("Restore to", default=entry)
            _, err, rc = run_command(["pass", "mv", f"archive/{entry}", dest])
            console.print(
                f"[green]Restored to '{dest}'.[/green]" if rc == 0
                else f"[red]{err}[/red]"
            )

    elif args.command == "wizard":
        cmd_wizard()

    elif args.command == "config":
        if not args.key:
            cmd_config_show()
        elif not args.value:
            val = CONFIG.get(args.key)
            console.print(
                f"{args.key} = {val}" if val is not None
                else f"[red]Unknown key: {args.key}[/red]"
            )
        else:
            cmd_config_set(args.key, args.value)

    elif args.command == "export-vault":
        cmd_export_vault(args.file)

    elif args.command == "import-vault":
        cmd_import_vault(args.file, force=args.force)


if __name__ == "__main__":
    main()
