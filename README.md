# PassCLI

A feature-rich, smart wrapper for the [`pass`](https://www.passwordstore.org/) password manager.
Designed for normal users and power users/developers alike.

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
pip install rich pyperclip pyotp
```

`pyperclip` enables clipboard copy with auto-clear. `pyotp` enables TOTP code generation.
Both are optional — PassCLI will warn you if a feature needs them.

---

## Quick start

```bash
# First-time setup (guided wizard)
python pass_cli.py wizard

# Or start the interactive shell directly
python pass_cli.py
```

Make it a global command:

```bash
chmod +x pass_cli.py
sudo ln -s "$(pwd)/pass_cli.py" /usr/local/bin/passcli
```

---

## Usage

PassCLI works in two ways:

### 1. Direct CLI — one command, then exit

```bash
passcli get email/gmail              # show password + metadata
passcli get email/gmail --clip       # copy to clipboard (auto-clears after 45s)
passcli get email/gmail --field url  # print just one field
passcli insert web/github            # add new entry (guided prompts)
passcli generate web/github 24       # generate 24-char password
passcli generate web/github --clip   # generate and copy to clipboard
passcli edit web/github              # open in $EDITOR
passcli delete web/github            # delete (asks for confirmation)
passcli find gmail                   # search entries by name
passcli ls                           # list all entries
passcli mv web/github personal/gh    # move / rename
passcli cp web/github web/github-bak # copy
passcli archive web/old-site         # move to archive/ folder
passcli restore old-site             # restore from archive/
```

### 2. Interactive shell — persistent REPL with tab completion

```bash
passcli          # or: passcli shell
```

The shell supports tab-completion for all entry names and persists history across sessions.

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

### Password health report
```bash
passcli health
```
Scans every entry and reports:
- Strength score (Very Weak → Very Strong) with a visual bar
- Length
- Duplicate passwords across entries

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
| `insert [entry]` | Add new entry (guided structured input) |
| `generate [entry] [len]` | Generate a random password |
| `edit [entry]` | Edit in `$EDITOR` |
| `delete [entry]` | Delete an entry |
| `browse` | Fuzzy-pick entry and choose action |
| `ls` | List all entries |
| `find <term>` | Search by name |
| `mv <old> <new>` | Move / rename |
| `cp <old> <new>` | Copy |
| `archive [entry]` | Move to `archive/` |
| `restore [entry]` | Restore from `archive/` |
| `otp [entry]` | Generate TOTP code |
| `run <entry> -- <cmd>` | Inject fields as env vars |
| `health` | Strength + duplicate report |
| `import <file>` | Import from CSV |
| `sync` | Git pull + push |
| `gitlog [n]` | Git history |
| `wizard` | First-time setup wizard |
| `init` | Init / re-init password store |
| `gpg_gen` | Generate GPG key |
| `gpg_list` | List GPG keys |
| `config [key] [value]` | View / set config |

---

## Security notes

- All subprocess calls use list arguments — no `shell=True`, no injection risk.
- Clipboard is auto-cleared after a configurable timeout (default 45s).
- TOTP clipboard auto-clears when the code expires.
- The `run` command never logs secrets to stdout or shell history.
- Passwords are never stored in PassCLI — everything goes through `pass` and GPG.
