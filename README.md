# Passclip

[![PyPI](https://img.shields.io/pypi/v/passclip?color=blue)](https://pypi.org/project/passclip/)
[![CI](https://github.com/rxb06/Passclip/actions/workflows/ci.yml/badge.svg)](https://github.com/rxb06/Passclip/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/rxb06/Passclip)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/passclip)](https://pypi.org/project/passclip/)

A security-focused CLI interface for managing and accessing secrets.

Built on top of the Unix password manager [`pass`](https://www.passwordstore.org/), Passclip extends its simplicity with structured entries, secure clipboard handling, TOTP support, and health auditing. Designed for engineers who need reliable, script-friendly access to credentials without exposing sensitive data — enabling safer secret handling across automation, tooling, and infrastructure workflows.

---

## Install

```bash
# System deps (pass + GPG must be installed separately)
brew install gnupg pass          # macOS
sudo apt install gnupg2 pass     # Ubuntu/Debian

# Passclip
pip install passclip[all]

# First-time setup
passclip wizard
```

Or clone and run directly:

```bash
git clone https://github.com/rxb06/Passclip.git
cd Passclip
pip install -e ".[all]"
passclip wizard
```

See [docs/setup.md](docs/setup.md) for GPG key setup, Linux/Arch instructions, and troubleshooting.

---

## Quick start

```bash
passclip gmail                    # copy password (fuzzy match)
passclip gmail -u                 # copy username
passclip gmail -o                 # copy OTP code
passclip gmail -s                 # show full entry
```

No subcommand needed. Type a search term — Passclip finds the entry and copies what you need.

---

## Why does this exist?

GNU `pass` is brilliant in its simplicity — one GPG-encrypted file per password, a directory tree as your database, and git for sync. It's the Unix philosophy done right. But in daily use, that minimalism starts to show its edges:

**What `pass` gives you:**
- Rock-solid GPG encryption
- Git-based version control and sync
- A dead-simple `pass insert` / `pass show` interface
- A healthy ecosystem of community extensions

**What it doesn't:**
- There's no structured format for entries — every user invents their own convention
- No clipboard auto-clear out of the box (and the built-in `--clip` is inconsistent across platforms)
- No password strength feedback or health audit
- No TOTP without a separate extension (`pass-otp`)
- Importing from Bitwarden, LastPass, or 1Password means hunting for `pass-import`
- No interactive shell with tab completion
- No encrypted backup format independent of GPG

**What Passclip adds:**

| Gap in `pass` | What Passclip does about it |
|---|---|
| No structured entries | First line is the password, everything else is `key: value` pairs. Compatible with `pass-import`. |
| Clipboard is fire-and-forget | Auto-clear with a configurable timer. Checks clipboard before clearing. |
| No strength feedback | Visual strength bar, entropy estimate, actionable tips. |
| No health audit | `passclip health` scans every entry — flags weak passwords and duplicates. |
| TOTP needs an extension | Built in. `passclip otp --add` to set up, `passclip gmail -o` to copy a code. |
| Importing is painful | `passclip import file.csv` — auto-detects Bitwarden, LastPass, 1Password. |
| No interactive shell | Full REPL with tab completion, history, and single-letter shortcuts (`c`, `u`, `o`). |
| No GPG-independent backup | `export-vault` creates an AES-256-GCM encrypted file. Restore on any machine. |
| No secret injection for devs | `passclip run entry -- command` injects fields as env vars. |
| Deletes are permanent | Pre-delete backups to `~/.config/passclip/backups/`. |
| No entry validation | Blocks path traversal, shell metacharacters, and bad input. |

Passclip doesn't replace `pass` — it extends it. Your password store is still a directory of GPG files. You can switch back to plain `pass` at any time. No lock-in.

---

## What can it do?

**Quick copy — the daily driver:**

```bash
passclip gmail                        # fuzzy match → copy password
passclip gmail -u                     # copy username
passclip gmail -o                     # copy OTP code
passclip gmail -s                     # show full entry
```

**Full commands:**

```bash
passclip get email/gmail --clip       # copy to clipboard, auto-clears in 45s
passclip insert web/github            # add entry (guided prompts)
passclip browse                       # interactive picker → copy by default
passclip otp --add web/github         # add OTP secret to an entry
```

**Housekeeping:**

```bash
passclip health                       # password strength + duplicate report
passclip sync                         # git pull + push
passclip archive web/old-site         # stash it, don't delete it
passclip export-vault ~/backup.vault  # AES-256 encrypted backup
```

**Developer workflows:**

```bash
passclip run aws/prod -- aws s3 ls    # inject secrets as env vars
passclip import bitwarden_export.csv  # migrate from another manager
passclip import export.csv --dry-run  # preview before committing
```

**Interactive shell** — launch with `passclip`. Single-letter shortcuts: `c gmail` (password), `u gmail` (username), `o gmail` (OTP).

---

## All commands

| Command | What it does |
|---|---|
| `<term>` | **Smart copy** — fuzzy match and copy password |
| `<term> -u` | Smart copy — copy username |
| `<term> -o` | Smart copy — copy OTP code |
| `<term> -s` | Smart copy — show full entry |
| `get [entry] [--clip] [--field F]` | Show, copy, or extract a specific field |
| `clip [entry]` | Copy password to clipboard (auto-clears) |
| `insert [entry]` | Add new entry with guided prompts |
| `generate [entry] [len]` | Generate a random password |
| `edit [entry]` | Open in `$EDITOR` |
| `delete [entry]` | Delete (previews first, backs up before removing) |
| `browse` | Fuzzy-pick an entry → copy (default) |
| `ls` | List everything |
| `find <term>` | Search by name |
| `mv <old> <new>` | Move or rename |
| `cp <old> <new>` | Copy an entry |
| `archive [entry]` | Move to `archive/` |
| `restore [entry]` | Bring back from `archive/` |
| `otp [entry]` | Generate a TOTP code |
| `otp --add [entry]` | Add or update OTP secret on an entry |
| `run <entry> -- <cmd>` | Inject fields as env vars into a command |
| `health` | Password strength and duplicate report |
| `import <file> [--format F] [--dry-run]` | Import from CSV (Bitwarden, LastPass, 1Password) |
| `export-vault <file>` | Encrypted vault backup |
| `import-vault <file> [--force]` | Restore from vault |
| `sync` | Git pull + push |
| `gitlog [n]` | Recent git history |
| `config [key] [value]` | View or change settings |
| `wizard` | First-time setup |
| `init` | Init or re-init the password store |
| `gpg_gen` | Generate a new GPG key |
| `gpg_list` | List GPG keys |

---

## Pre-commit hook

Passclip uses [Credactor](https://github.com/rxb06/Credactor) to scan for hardcoded credentials before every commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/rxb06/Credactor
    rev: v2.0.1
    hooks:
      - id: credactor
```

```bash
pip install pre-commit
pre-commit install
```

See [docs/integration.md](docs/integration.md) for CI setup and more.

---

## How entries are stored

Passclip uses the same format as `pass` — GPG-encrypted files, one per entry:

```
MyS3cr3tP@ssw0rd
username: john@example.com
url: https://github.com
notes: work account
```

First line is always the password. Everything else is optional `key: value` metadata. Compatible with `pass-import` and most pass extensions.

---

## Security

- **No shell injection** — all subprocess calls use list arguments, never `shell=True`.
- **Entry name validation** — blocks path traversal (`..`), shell metacharacters, and other tricks.
- **Clipboard auto-clear** — passwords are wiped after a configurable timeout.
- **Atomic vault writes** — no partial files on disk-full.
- **Pre-delete backups** — saved to `~/.config/passclip/backups/` before deletion.
- **AES-256-GCM vaults** — encrypted with PBKDF2-SHA256 at 600,000 iterations.

Full policy: [SECURITY.md](SECURITY.md)

---

## Documentation

| Document | Description |
|---|---|
| [docs/setup.md](docs/setup.md) | Installation, configuration, and troubleshooting |
| [docs/user-guide.md](docs/user-guide.md) | Feature deep-dives, workflows, and best practices |
| [docs/examples.md](docs/examples.md) | 12 real-world workflow recipes |
| [docs/integration.md](docs/integration.md) | Pre-commit hooks, CI/CD, shell completions |
| [docs/disclaimer.md](docs/disclaimer.md) | Warranty, liability, and limitations |
| [docs/changelog.md](docs/changelog.md) | Version history |
| [SECURITY.md](SECURITY.md) | Security policy and threat model |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

---

> AI Use Transparency: AI was used for code review, bug fixes, security auditing, and documentation structuring. All output was reviewed and validated manually.

---

## License

Licensed under the [GNU General Public License v3.0](LICENSE).

---

*Passclip is a personal open-source project. It is not audited by a third party. See [docs/disclaimer.md](docs/disclaimer.md) for details.*
