# PassCLI

A smart, feature-rich wrapper around [`pass`](https://www.passwordstore.org/) — the standard Unix password manager.

Whether you just want to grab a password quickly or you're a developer who needs secrets injected into a build pipeline, PassCLI has you covered. It adds structured entries, clipboard management, TOTP codes, health reports, CSV import, encrypted vault backups, and an interactive shell — all on top of the battle-tested GPG encryption that `pass` already provides.

```
$ passcli --version
passcli 1.0.0
```

---

## Why does this exist?

GNU `pass` is brilliant in its simplicity — one GPG-encrypted file per password, a directory tree as your database, and git for sync. It's the Unix philosophy done right. But in daily use, that minimalism starts to show its edges:

**What `pass` gives you:**
- Rock-solid GPG encryption
- Git-based version control and sync
- A dead-simple `pass insert` / `pass show` interface
- A healthy ecosystem of community extensions

**What it doesn't:**
- There's no structured format for entries. `pass` stores freeform text, so there's no consistent way to attach a username, URL, or notes to a password. Every user invents their own convention, and nothing parses it.
- No clipboard auto-clear out of the box (the built-in `--clip` clears after 45s on some systems, but it's inconsistent across platforms and doesn't check if the clipboard changed).
- No password strength feedback. You can generate a password, but `pass` won't tell you if it's weak or if you're reusing it across entries.
- No health audit. If you have 100 entries and want to know which ones are weak or duplicated, you're on your own.
- No TOTP support without installing a separate extension (`pass-otp`), and even then it's a separate workflow.
- Importing from Bitwarden, LastPass, or 1Password means finding `pass-import`, installing it, and hoping the CSV format hasn't changed.
- No interactive shell. Every operation is a separate command invocation with no tab completion for entry names (unless you set up bash completions yourself).
- No encrypted backup format that's independent of GPG. If you lose your GPG key, your entire store is unrecoverable.

**What PassCLI adds:**

| Gap in `pass` | What PassCLI does about it |
|---|---|
| No structured entries | First line is the password, everything else is `key: value` pairs. Consistent, parseable, compatible with `pass-import`. |
| Clipboard is fire-and-forget | Auto-clear with a configurable timer. Checks clipboard before clearing so it doesn't wipe something you copied later. |
| No strength feedback | Shows strength immediately after generating or entering a password. Visual bar, entropy estimate, actionable tips. |
| No health audit | `passcli health` scans every entry — flags weak passwords, duplicates, and gives you a fix-it list. |
| TOTP needs an extension | Built in. Add `otp: SECRET` to any entry, run `passcli otp`, get a code. Clipboard auto-clears on expiry. |
| Importing is painful | `passcli import file.csv` — auto-detects Bitwarden, LastPass, 1Password. Dry-run mode to preview first. |
| No interactive shell | Full REPL with tab completion, persistent history, and quick-copy shortcuts. |
| No GPG-independent backup | `export-vault` creates an AES-256-GCM encrypted file. Separate passphrase, separate from GPG. Restore on any machine. |
| No secret injection for devs | `passcli run entry -- command` injects fields as env vars. No shell history exposure. |
| Deletes are permanent | Pre-delete backups to `~/.config/passcli/backups/`. Safety net for accidents. |
| No entry validation | Blocks path traversal, shell metacharacters, and other bad input before it reaches `pass`. |

PassCLI doesn't replace `pass` — it wraps it. Your password store is still a directory of GPG files. You can switch back to plain `pass` at any time and everything still works. There's no lock-in.

---

## Get started in 60 seconds

```bash
# 1. Install system deps (macOS example — see docs/SETUP.md for Linux)
brew install gnupg pass

# 2. Install Python deps
pip install rich cryptography pyperclip pyotp

# 3. Run the setup wizard
python pass_cli.py wizard

# 4. You're in
python pass_cli.py
```

Want to run it as a global command? Two lines:

```bash
chmod +x pass_cli.py
ln -sf "$(pwd)/pass_cli.py" ~/.local/bin/passcli
```

> Make sure `~/.local/bin` is on your `PATH`. If it isn't, add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile.

For the full walkthrough (GPG key setup, Linux/Arch instructions, shell completions, troubleshooting), see **[docs/SETUP.md](docs/SETUP.md)**.

---

## What can it do?

**Everyday stuff:**

```bash
passcli get email/gmail              # show password + metadata
passcli get email/gmail --clip       # copy to clipboard, auto-clears in 45s
passcli insert web/github            # add entry (prompts for fields, can auto-generate)
passcli find gmail                   # fuzzy search
passcli browse                       # interactive picker (requires fzf)
passcli otp web/github               # TOTP code, auto-copied
```

**Housekeeping:**

```bash
passcli health                       # scan all passwords for strength + duplicates
passcli sync                         # git pull + push in one step
passcli archive web/old-site         # stash it, don't delete it
passcli export-vault ~/backup.vault  # AES-256 encrypted backup of everything
```

**Developer workflows:**

```bash
passcli run aws/prod -- aws s3 ls    # inject secrets as env vars, no shell history
passcli import bitwarden_export.csv  # migrate from another manager
passcli import export.csv --dry-run  # preview before committing
```

**Interactive shell** — launch with `passcli` or `passcli shell`. You get tab completion, persistent history, and quick-copy shortcuts (`c` for password, `u` for username, `l` for URL).

For deep-dives, real-world workflows, and best practices, see **[docs/GUIDE.md](docs/GUIDE.md)**.

---

## All commands

| Command | What it does |
|---|---|
| `get [entry] [--clip] [--field F]` | Show, copy, or extract a specific field |
| `clip [entry]` | Copy password to clipboard (auto-clears) |
| `insert [entry]` | Add new entry with guided prompts |
| `generate [entry] [len]` | Generate a random password |
| `edit [entry]` | Open in `$EDITOR` |
| `delete [entry]` | Delete (previews first, backs up before removing) |
| `browse` | Fuzzy-pick an entry, then choose an action |
| `ls` | List everything |
| `find <term>` | Search by name |
| `mv <old> <new>` | Move or rename |
| `cp <old> <new>` | Copy an entry |
| `archive [entry]` | Move to `archive/` |
| `restore [entry]` | Bring back from `archive/` |
| `otp [entry]` | Generate a TOTP code |
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

## How entries are stored

PassCLI uses the same format as `pass` — GPG-encrypted files, one per entry. Inside each file:

```
MyS3cr3tP@ssw0rd
username: john@example.com
url: https://github.com
notes: work account
```

First line is always the password. Everything else is optional `key: value` metadata. This format is compatible with `pass-import` and most pass extensions, so you're never locked in.

---

## Security

PassCLI takes security seriously. Highlights:

- **No shell injection** — all subprocess calls use list arguments, never `shell=True`.
- **Entry name validation** — blocks path traversal (`..`), shell metacharacters, and other tricks.
- **Clipboard auto-clear** — passwords are wiped from the clipboard after a configurable timeout.
- **Atomic vault writes** — no partial files left behind if your disk fills up mid-export.
- **Pre-delete backups** — entries are saved to `~/.config/passcli/backups/` before deletion.
- **AES-256-GCM vaults** — encrypted with PBKDF2-SHA256 at 600,000 iterations.

For the full security policy, responsible disclosure process, and known limitations, see **[SECURITY.md](SECURITY.md)**.

---

## Documentation

| Document | Description |
|---|---|
| **[docs/SETUP.md](docs/SETUP.md)** | Installation, configuration, and troubleshooting |
| **[docs/GUIDE.md](docs/GUIDE.md)** | Feature deep-dives, workflows, and best practices |
| **[SECURITY.md](SECURITY.md)** | Security policy, threat model, and disclosure process |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | How to contribute — bugs, features, code style |
| **[docs/DISCLAIMER.md](docs/DISCLAIMER.md)** | Warranty, liability, and what you're responsible for |
| **[docs/CHANGELOG.md](docs/CHANGELOG.md)** | Version history and what changed |

---

## License

Licensed under the [GNU General Public License v3.0](LICENSE).

---

*PassCLI is a personal open-source project. It is not audited by a third party. See [docs/DISCLAIMER.md](docs/DISCLAIMER.md) for details.*
