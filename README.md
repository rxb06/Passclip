# PassCLI v1.0.0

A feature-rich, smart wrapper for the [`pass`](https://www.passwordstore.org/) password manager.
Designed for normal users and power users/developers alike.

```bash
passcli --version   # passcli 1.0.0
```

---

## System dependencies

```bash
# macOS
brew install gnupg pass fzf

# Ubuntu/Debian
sudo apt install gnupg2 pass fzf

# Arch
sudo pacman -S gnupg pass fzf
```

`fzf` is optional but strongly recommended — it enables the fuzzy interactive entry browser.

## Python dependencies

```bash
pip install rich cryptography pyperclip pyotp
```

| Package | Required? | What it enables |
|---|---|---|
| `rich` | Yes | All terminal formatting, tables, progress bars |
| `cryptography` | Yes | AES-256-GCM vault export / import |
| `pyperclip` | Recommended | Clipboard copy with auto-clear |
| `pyotp` | Optional | TOTP code generation |

---

## Quick start

```bash
# First-time setup (guided wizard)
python pass_cli.py wizard

# Or start the interactive shell directly
python pass_cli.py
```

Make it a global command (no sudo needed):

```bash
chmod +x pass_cli.py
mkdir -p ~/.local/bin
ln -sf "$(pwd)/pass_cli.py" ~/.local/bin/passcli
```

> **Note:** Make sure `~/.local/bin` is on your `PATH`. Add this to `~/.zshrc` or `~/.bashrc` if it isn't already:
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```

---

## PassTUI (C ncurses — in development)

A native C ncurses TUI is in development under `passtui/`. It provides a full keyboard-driven interface with clean GPG passphrase handling (suspend/resume ncurses for pinentry).

```bash
cd passtui && make && ./passtui
```

---

## Usage

PassCLI works in two ways:

### 1. Direct CLI — one command, then exit

```bash
passcli get email/gmail              # show password + metadata
passcli get email/gmail --clip       # copy to clipboard (auto-clears after 45s)
passcli get email/gmail --field url  # print just one field
passcli insert web/github            # add new entry (guided prompts, auto-generate option)
passcli generate web/github 24       # generate 24-char password (shows password + strength)
passcli generate web/github --clip   # generate and copy to clipboard
passcli edit web/github              # open in $EDITOR
passcli delete web/github            # delete (previews entry, asks for confirmation)
passcli find gmail                   # search entries by name (select and act on results)
passcli ls                           # list all entries
passcli mv web/github personal/gh    # move / rename
passcli cp web/github web/github-bak # copy
passcli archive web/old-site         # move to archive/ folder
passcli restore old-site             # restore from archive/
passcli export-vault ~/backup.passvault  # export entire store as encrypted vault
passcli import-vault ~/backup.passvault  # restore store from vault
```

### 2. Interactive shell — persistent REPL with tab completion

```bash
passcli          # or: passcli shell
```

The shell supports tab-completion for all entry names, persists history across sessions, and offers quick-copy prompts after displaying entries.

---

## Feature highlights

### Structured entries
PassCLI stores entries in a human-readable, portable format:

```
MyS3cr3tP@ssw0rd
username: john@example.com
url: https://github.com
notes: work account
```

The first line is always the password. All other fields are optional `key: value` pairs.
This is compatible with `pass-import` and most pass extensions.

### Inserting entries with auto-generate

When adding a new entry, leave the password blank to auto-generate one:

```bash
passcli insert web/github
# Password (Enter to generate): ↵
# Length [20]:
# Include symbols? [Y/n]:
# Generated: xK#9mR!2pL@vQ8nW$3jF
# Strength: █████ Very Strong
```

Password strength feedback is shown immediately after entering or generating a password.

### Password health report
```bash
passcli health
```
Scans every entry and reports:
- Strength score (Very Weak → Very Strong) with a visual bar
- Length
- Duplicate passwords across entries
- Detailed tables for both **weak** and **fair** passwords, with actionable tips

### TOTP / OTP codes
Store your OTP secret in an entry field:
```
MyPassword
otp: JBSWY3DPEHPK3PXP
```
Then generate a live code:
```bash
passcli otp web/github
```
The code is also copied to clipboard and auto-clears when it expires.

### Developer: inject secrets as environment variables
```bash
passcli run aws/prod -- aws s3 ls
```
Maps each entry field to an env var:
- `password` → `PASS_PASSWORD`
- `username` → `PASS_USERNAME`
- `url` → `PASS_URL`
- (and so on for any custom field)

Your subprocess never touches the terminal and the secrets don't persist in shell history.

### Import from other password managers
```bash
passcli import bitwarden_export.csv
passcli import lastpass_export.csv
passcli import 1password_export.csv
```
Format is auto-detected from the CSV header. You can also specify it explicitly:
```bash
passcli import export.csv --format bitwarden
```

### Encrypted vault backup

Export your entire password store to a single portable file — safe to copy to cloud storage, an external drive, or another machine:

```bash
passcli export-vault ~/backup.passvault
# Vault passphrase: ••••••••••••
# Confirm passphrase: ••••••••••••
# ╭─ Export Vault ─────────────────────────────╮
# │ Vault exported successfully.               │
# │   File:    ~/backup.passvault              │
# │   Size:    4.2 KB                          │
# │   Entries: 47                              │
# │   Cipher:  AES-256-GCM · PBKDF2-SHA256     │
# ╰────────────────────────────────────────────╯
```

Restore from the vault on any machine that has PassCLI installed:

```bash
passcli import-vault ~/backup.passvault
# Vault passphrase: ••••••••••••
```

The vault is a single binary file encrypted with **AES-256-GCM**. The key is derived from your passphrase using **PBKDF2-SHA256 with 600,000 iterations**. The file has no meaning without the passphrase — it is safe to store alongside your encrypted password store in cloud storage.

### Git sync
```bash
passcli sync      # git pull + push in one step
passcli gitlog    # recent commit history
```

### Configuration
```bash
passcli config                            # show all settings
passcli config clip_timeout 60            # clear clipboard after 60s
passcli config default_password_length 24 # default generated length
```

Config is stored at `~/.config/passcli/config.json`.

---

## All commands

| Command | Description |
|---|---|
| `get [entry] [--clip] [--field F]` | Show a password (or copy/field) |
| `clip [entry]` | Copy to clipboard with auto-clear |
| `insert [entry]` | Add new entry (guided prompts, auto-generate option, strength feedback) |
| `generate [entry] [len]` | Generate a random password (shows password + strength) |
| `edit [entry]` | Edit in `$EDITOR` |
| `delete [entry]` | Delete an entry (previews metadata before confirming) |
| `browse` | Fuzzy-pick entry, choose action (show/copy/username/URL/OTP/edit/delete) |
| `ls` | List all entries |
| `find <term>` | Search by name (select and act on results) |
| `mv <old> <new>` | Move / rename |
| `cp <old> <new>` | Copy |
| `archive [entry]` | Move to `archive/` |
| `restore [entry]` | Restore from `archive/` |
| `export-vault <file>` | Export entire store as AES-256-GCM encrypted vault |
| `import-vault <file> [--force]` | Restore store from vault (warns before overwriting) |
| `otp [entry]` | Generate TOTP code |
| `run <entry> -- <cmd>` | Inject fields as env vars |
| `health` | Strength + duplicate report (shows weak and fair passwords) |
| `import <file>` | Import from CSV |
| `sync` | Git pull + push |
| `gitlog [n]` | Git history |
| `wizard` | First-time setup wizard |
| `init` | Init / re-init password store |
| `gpg_gen` | Generate GPG key |
| `gpg_list` | List GPG keys |
| `config [key] [value]` | View / set config |

---

## UX notes

- **Contextual error messages** — errors distinguish between "entry not found", "GPG decryption failed", and "key errors" with suggested fixes.
- **Fuzzy filtering without fzf** — when fzf is unavailable and you have 15+ entries, a text filter prompt narrows the list before showing numbers.
- **Quick-copy in shell** — after viewing an entry in the interactive shell, press `c` to copy password, `u` for username, or `l` for URL.

---

## Shell completions

Tab-completion scripts are provided for bash, zsh, and fish. They complete subcommands, entry names, config keys, and flags.

```bash
# Bash — add to ~/.bashrc
source /path/to/completions/passcli.bash

# Zsh — copy to fpath
cp completions/passcli.zsh ~/.zfunc/_passcli
# then add to ~/.zshrc:  fpath=(~/.zfunc $fpath); autoload -Uz compinit && compinit

# Fish — copy to completions dir
cp completions/passcli.fish ~/.config/fish/completions/
```

---

## Security notes

- All subprocess calls use list arguments — no `shell=True`, no injection risk.
- Entry names are validated against path traversal (`..`), shell metacharacters, and excessive depth before any write operation.
- Clipboard is auto-cleared after a configurable timeout (default 45s). Note: if another program overwrites the clipboard before the timer fires, the new content is not cleared. PassCLI checks clipboard content before clearing to avoid erasing unrelated data.
- TOTP clipboard auto-clears when the code expires.
- The `run` command injects secrets as environment variables into the child process only. The variables are not visible in shell history or `ps` output, but the child process (and anything it spawns) has full access for the duration of execution.
- Passwords are never stored in PassCLI — everything goes through `pass` and GPG.
- The interactive shell stores command history in `~/.config/passcli/history`. This file contains command names and entry paths (not passwords). It is created with `0600` permissions.
- Vault files use AES-256-GCM (authenticated encryption) with PBKDF2-SHA256 at 600,000 iterations. The file is meaningless without the passphrase — safe to store in cloud storage alongside your git-backed store.
- Vault exports use atomic writes (temp file + rename) to prevent partial files on disk-full or crash.
- Vault files are written with `0600` permissions (owner read/write only).
- Entries are backed up to `~/.config/passcli/backups/` before deletion. Backups are plaintext and `0600` — delete them when no longer needed.
- The interactive shell uses a PID-based lock file (`.passcli.lock`) in the password store to warn about concurrent access.

---

## Troubleshooting

**GPG agent not responding / pinentry hangs**
```bash
gpgconf --kill gpg-agent
gpg-agent --daemon
```
If pinentry prompts don't appear in your terminal, set `GPG_TTY`:
```bash
export GPG_TTY=$(tty)   # add to ~/.bashrc or ~/.zshrc
```

**Password store not found**
PassCLI looks at `~/.password-store` by default. If your store is elsewhere:
```bash
passcli config pass_dir /path/to/your/store
# or set the environment variable:
export PASSWORD_STORE_DIR=/path/to/your/store
```

**Clipboard not working**
PassCLI uses `pyperclip`, which needs a clipboard tool installed:
- **macOS**: `pbcopy` (built-in)
- **Linux X11**: `xclip` or `xsel` (`sudo apt install xclip`)
- **Linux Wayland**: `wl-copy` (`sudo apt install wl-clipboard`)
- **SSH / headless**: clipboard is not available — use `--field` to print values instead

**`pass` command not found**
Install the `pass` password manager first — see [System dependencies](#system-dependencies).

---

## Performance notes

- The `health` command decrypts every entry via GPG to check password strength. On large stores (100+ entries) this can take a while — a progress bar shows current status.
- `browse` and `find` call `pass ls` once and work from the cached list. They do not decrypt entries until you select one.
