# PassCLI Playbook

## A complete guide to using PassCLI — what it is, why I created, and how to get the most from it

---

## Table of Contents

1. [What is PassCLI and why does it exist?](#1-what-is-passcli-and-why-does-it-exist)
2. [pass vs PassCLI — the honest comparison](#2-pass-vs-passcli--the-honest-comparison)
3. [Who should use PassCLI?](#3-who-should-use-passcli)
4. [Installation and first-time setup](#4-installation-and-first-time-setup)
5. [Core concepts](#5-core-concepts)
6. [The two modes of operation](#6-the-two-modes-of-operation)
7. [Feature deep-dives](#7-feature-deep-dives)
   - [export-vault / import-vault](#export-vault--import-vault--encrypted-backup)
8. [Developer workflows](#8-developer-workflows)
9. [Normal user workflows](#9-normal-user-workflows)
10. [Entry naming conventions and organisation](#10-entry-naming-conventions-and-organisation)
11. [Best practices](#11-best-practices)
12. [Security model](#12-security-model)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. What is PassCLI and why does it exist?

PassCLI is a wrapper around [GNU pass](https://www.passwordstore.org/) — the standard Unix password manager. It does not replace `pass`, it sits on top of it and talks to it directly. All your passwords remain GPG-encrypted by `pass` itself; PassCLI never touches the encryption.

**The problem PassCLI solves:**

`pass` is powerful but raw. It is a Unix tool in the classic sense — minimal, composable, unforgiving. You are expected to know what you are doing. For a developer who lives in the terminal this is fine. For a normal person, or even a developer who just wants to get a password quickly without remembering the exact path, it creates friction.

PassCLI removes that friction:

- You do not need to remember exact entry paths — fuzzy search finds them
- You do not need to know GPG key IDs — the wizard handles it
- You do not need to install and configure shell completions — they work out of the box
- You do not need separate extensions for OTP, CSV import, or health checks — they are built in
- You do not need to write shell scripts to inject secrets into your dev environment — one command does it

PassCLI is the interface layer that makes `pass` accessible to everyone while not taking anything away from power users.

---

## 2. pass vs PassCLI — the honest comparison

This is important. If you are considering using PassCLI, you deserve an honest comparison.

### What raw `pass` gives you

```bash
pass show email/gmail          # show a password
pass insert email/gmail        # insert (prompts for password only)
pass generate email/gmail 20   # generate a password
pass edit email/gmail          # edit in $EDITOR
pass rm email/gmail            # delete
pass find github               # search by name
pass ls                        # list all
pass git push                  # git push
```

This is clean, fast, and scriptable. If this is all you need, `pass` alone is sufficient.

### Where raw `pass` has gaps

| Gap | Raw pass | PassCLI |
|---|---|---|
| Find an entry without knowing its path | `pass find term` — shows names, then you retype the path | `browse` — fuzzy-pick and act in one step |
| Store username + URL alongside password | Manual free-form text, no convention | Structured guided prompts, consistent format |
| Generate password while adding an entry | Two-step: `pass generate` then `pass edit` to add metadata | Leave password blank during `insert` to auto-generate inline |
| See password strength | No built-in feature | Shown when retrieving, inserting, and generating |
| Find weak or reused passwords | No built-in feature | `health` scans all entries, shows weak + fair passwords and duplicates with tips |
| Generate TOTP codes | Requires `pass-otp` extension, manual setup | `otp` command built in, no extension needed |
| Import from Bitwarden/LastPass | Requires `pass-import` Python package | `import` command built in |
| Inject secrets as env vars for dev | Write your own shell script each time | `run <entry> -- <command>` |
| Guided first-time setup | Read the man page | `wizard` walks you through everything |
| Tab completion for entry names | Requires shell-specific setup | Works out of the box in the shell |
| Clipboard auto-clear | `pass -c` copies, but no countdown or confirmation | Countdown shown, clears after configurable timeout |
| Sync git in one step | `pass git pull && pass git push` | `sync` |
| Retrieve one specific field | Parse the output yourself | `--field username` |
| Copy username or URL from browse | Not possible without scripting | `browse` → `u` (username) or `l` (URL) |
| Act on search results | `pass find` shows names, you retype | `find` → select result → action menu |
| Error diagnostics | Generic error messages | Specific messages: not found / can't decrypt / GPG key error |
| Portable encrypted backup | Copy the whole `.password-store/` dir (GPG-only per file) | `export-vault` → single AES-256-GCM encrypted file |

### What PassCLI does NOT do differently

- Encryption — `pass` and GPG handle this entirely. PassCLI calls `pass`, not GPG directly.
- Storage format — your `.gpg` files are standard pass files. You can stop using PassCLI at any time and use `pass` directly — nothing is locked in.
- Git integration — `pass git` is still doing the work. PassCLI just wraps the common operations.

### The honest verdict

PassCLI is not an upgrade in the sense of being fundamentally better. It is an upgrade in the sense of being more usable. If you are happy with raw `pass`, keep using it. If you want to spend less time remembering paths, less time writing scripts, and less time worrying about whether your passwords are weak, PassCLI is worth it.

---

## 3. Who should use PassCLI?

### The normal user

You want a secure password manager that does not send your passwords to a server somewhere. You have heard `pass` is the gold standard for Unix password management but the command line looks intimidating. PassCLI's `wizard` sets everything up for you, and after that `browse` is all you need day to day.

### The developer

You use secrets constantly — API keys, database credentials, environment variables. You are tired of `.env` files that accidentally get committed. You want to inject secrets into your development environment without them ever touching disk unencrypted. The `run` command and the structured entry format are built for you.

### The power user migrating from another manager

You have a Bitwarden or LastPass export and want to move to a local, offline, GPG-encrypted store. The `import` command handles this in one step with format auto-detection.

### The security-conscious person

You do not trust cloud password managers — not because they are insecure, but because your threat model says your secrets should never leave your machine unencrypted. `pass` with a git backup is the right architecture. PassCLI makes it practical.

---

## 4. Installation and first-time setup

### System dependencies

```bash
# macOS
brew install gnupg pass fzf

# Ubuntu/Debian
sudo apt install gnupg2 pass fzf

# Arch
sudo pacman -S gnupg pass fzf
```

`fzf` is optional but strongly recommended. It is what makes `browse` and fuzzy selection work beautifully.

### Python dependencies

```bash
pip install rich pyperclip pyotp
```

| Package | Required? | What it enables |
|---|---|---|
| `rich` | Yes | All terminal formatting, tables, progress bars |
| `cryptography` | Yes | AES-256-GCM vault export / import |
| `pyperclip` | Recommended | Clipboard copy/auto-clear |
| `pyotp` | Optional | TOTP code generation |

### Making it a global command

```bash
chmod +x pass_cli.py
mkdir -p ~/.local/bin
ln -sf "$(pwd)/pass_cli.py" ~/.local/bin/passcli
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### First-time setup with the wizard

```bash
passcli wizard
```

The wizard walks you through:

1. Checking that `pass` and `gpg` are installed
2. Creating a GPG key (or selecting an existing one)
3. Initialising the password store with that key
4. Optionally setting up git tracking
5. Adding your first entry

After the wizard, you are done. Everything is configured.

---

## 5. Core concepts

### The structured entry format

Raw `pass` stores free-form text. The first line is conventionally the password, but the rest is up to you. PassCLI formalises this with a consistent structure:

```
MyActualPassword123!
username: john@example.com
email: john@example.com
url: https://github.com
notes: work account, 2FA enabled
otp: JBSWY3DPEHPK3PXP
```

**Rules:**
- Line 1 is always the password. Always.
- Remaining lines are `key: value` pairs.
- Any line that is not a `key: value` pair is treated as notes.
- This format is fully compatible with raw `pass` — the file is plain text before GPG encryption.

You do not have to use this format. If you use `pass insert` directly or edit entries with `pass edit`, the content is whatever you typed. PassCLI will still work — it reads whatever is there, and the first line is always the password.

### Entry paths

Entries are organised as paths inside your password store (`~/.password-store` by default). The path is the key you use to retrieve, edit, or delete an entry.

```
email/gmail
email/work
web/github
web/aws-prod
dev/stripe-live
dev/stripe-test
ssh/personal-server
```

PassCLI stores these as `~/.password-store/email/gmail.gpg`, etc. The `.gpg` extension is handled by `pass` transparently — you never type it.

### The password store

Everything lives in `~/.password-store/`. This directory is:
- Plain files and folders on disk
- Each `.gpg` file is GPG-encrypted
- Optionally a git repository (strongly recommended)
- Completely portable — copy it to another machine, and if you have your GPG key, you can decrypt everything

---

## 6. The two modes of operation

### Direct CLI mode

Run a single command and exit. Best for scripts, quick lookups, and keyboard shortcuts.

```bash
passcli get email/gmail
passcli get email/gmail --clip
passcli insert web/github
passcli health
passcli sync
```

All commands work this way. Run `passcli --help` to see every subcommand.

### Interactive shell mode

Run `passcli` (no arguments) to enter the persistent shell. Best for interactive sessions where you need to do several things.

```
passcli> browse
passcli> get email/gmail
passcli> otp web/github
passcli> health
passcli> sync
```

**Shell advantages over direct CLI:**
- Tab completion for entry names — type `get em` and press Tab
- Persistent command history across sessions (stored at `~/.config/passcli/history`, permissions `0600`)
- Faster for multiple operations — no subprocess startup overhead
- Quick-copy after viewing — press `c`/`u`/`l` to copy password, username, or URL without re-running the command
- `browse` is most natural here — fuzzy-pick, act, pick again

---

## 7. Feature deep-dives

### browse — the daily driver

```bash
passcli browse
# or in the shell:
passcli> browse
```

Opens fzf (or a filtered numbered list if fzf is not installed) with every entry in your store. You fuzzy-search, select, and then choose what to do:

```
  s Show          View full entry details
  c Copy          Copy password to clipboard
  u Username      Copy username to clipboard
  l URL           Copy URL to clipboard
  o OTP           Generate TOTP code
  e Edit          Open in $EDITOR
  d Delete        Delete this entry
  q Cancel
```

Letter keys are easier to remember than numbers. The action menu also includes username and URL copying, which saves trips back to `get --field`.

This is the command most people use most often. You do not need to remember paths. You type a few characters of what you are looking for, press Enter, and either the password is shown or it is in your clipboard.

**When to use it:** Any time you want a password and you do not want to think.

**Without fzf:** If fzf is not installed and you have more than 15 entries, PassCLI will ask for a filter term first, then show a numbered list of matching entries. This makes large vaults navigable even without fzf.

---

### get — retrieve with precision

```bash
passcli get email/gmail             # show full entry
passcli get email/gmail --clip      # copy password to clipboard
passcli get email/gmail --field url # print just the URL
passcli get email/gmail --field username --clip  # copy username to clipboard
```

When you retrieve without `--clip`, the full structured entry is displayed in a panel with a password strength indicator:

```
╭─── email/gmail ──────────────────────────╮
│ Password: MyS3cr3tP@ssw0rd!              │
│ Username: john@example.com               │
│ Url: https://gmail.com                   │
│                                          │
│ █████░ Strong                            │
╰──────────────────────────────────────────╯
```

**Quick-copy in the interactive shell:** After the entry panel is displayed, a prompt appears:

```
  c=copy password  u=username  l=URL  Enter=done
```

Press `c` to copy the password, `u` to copy the username, or `l` to copy the URL — no need to re-run the command with `--clip`. This only appears in the interactive shell, not in direct CLI mode (to keep CLI mode scriptable).

**When to use `--field`:** In scripts and shell functions where you only want one piece of data.

```bash
# Get just the username for a login form
passcli get web/github --field username

# Copy just the URL to clipboard
passcli get web/github --field url --clip
```

---

### insert — add entries the right way

```bash
passcli insert web/github
```

Prompts you through each field:

```
╭─ New Entry ──────────────────────────────╮
│ Fill in the fields below.                │
│ Leave password blank to auto-generate.   │
╰──────────────────────────────────────────╯
Password (Enter to generate): ●●●●●●●●●●●●
  Strength: █████ Very Strong
Username: rutvikbelapurkar
Email:
URL: https://github.com
Notes: personal account
```

**Auto-generate option:** Leave the password blank and press Enter. PassCLI will ask for a length and whether to include symbols, then generate a secure random password and show it to you.

```
Password (Enter to generate): ↵
Length [20]: 24
Include symbols? [Y/n]: y
Generated: xK#9mR!2pL@vQ8nW$3jF&5bA
  Strength: █████ Very Strong
```

Password strength is always shown immediately after you type or generate a password, so you can decide whether it is strong enough before filling in the rest of the fields.

Only the password is required (typed or generated). Everything else is optional.

**When to use raw mode instead:**

```bash
passcli insert web/github --raw
```

Use `--raw` when you want to paste a full entry that is already in the structured format, or when you are scripting an import.

---

### generate — create strong passwords

```bash
passcli generate web/newsite          # 20 chars, default settings
passcli generate web/newsite 32       # 32 chars
passcli generate web/newsite --no-symbols  # alphanumeric only (for sites that reject symbols)
passcli generate web/newsite --clip   # generate and immediately copy to clipboard
```

After generation, the password and its strength are displayed:

```
Generated password for 'web/newsite'.
  Password: xK#9mR!2pL@vQ8nW$3jF
  Strength: █████ Very Strong
```

Default length is configurable:

```bash
passcli config default_password_length 32
```

**When to use `--no-symbols`:** Some banking sites and legacy enterprise tools reject passwords with special characters. `--no-symbols` generates a strong alphanumeric password for these cases.

---

### health — know the state of your vault

```bash
passcli health
```

Decrypts every entry and analyses:

- **Strength score** per entry (Very Weak / Weak / Fair / Strong / Very Strong)
- **Length** of each password
- **Duplicate detection** — groups entries that share the same password

Sample output:

```
╭─ Password Health Report ─────────────────╮
│ Strong: 42   Fair: 8   Weak: 3           │
│ Duplicates: 4   Errors: 1                │
╰──────────────────────────────────────────╯

Weak Passwords (update these):
  Entry              Strength     Len  Dup
  email/old-work     ██░░░ Weak    8   YES
  web/forum-legacy   █░░░░ Weak    6
  misc/wifi-guest    ██░░░ Weak    9   YES
  Tip: run generate <entry> to replace with a strong password

Fair Passwords (consider upgrading):
  Entry              Strength     Len  Dup
  web/social-media   ███░░ Fair   12
  dev/test-api       ███░░ Fair   14

Duplicate Passwords:
  Group 1: email/old-work  |  misc/wifi-guest
  Tip: use unique passwords for each account
```

Both weak and fair passwords are shown in detail so you can prioritise what to fix. Each section includes an actionable tip.

**When to run it:** Periodically (monthly), after importing from another manager, or when you suspect you have reused passwords.

**What to do with the results:**
1. Start with duplicates — reused passwords are the highest risk
2. Work through weak passwords from shortest to longest
3. Upgrade fair passwords when you have time
4. Use `passcli generate <entry>` to replace them

---

### otp — TOTP codes without a phone

```bash
passcli otp web/github
```

Generates a live TOTP code and copies it to clipboard (auto-clears when it expires).

**Setup:** Add your OTP secret to any entry as a field named `otp`:

```
MyPassword123
username: john
url: https://github.com
otp: JBSWY3DPEHPK3PXP
```

Or store a full `otpauth://` URI (as exported by most authenticator apps):

```
MyPassword123
otp: otpauth://totp/GitHub:john@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub
```

**Where to get the OTP secret:**
- When setting up 2FA on a site, most show a QR code AND a text secret underneath. Copy the text secret.
- If you use Google Authenticator, Authy, or similar, you can export secrets from those apps (varies by app).
- This replaces your authenticator app for entries you store here.

**When to use it:** Any site where you have 2FA enabled. You retrieve the password and the OTP code from the same place, without picking up your phone.

---

### run — the developer superpower

```bash
passcli run <entry> -- <command>
```

Decrypts the entry, maps every field to an environment variable (`PASS_<FIELDNAME_UPPERCASE>`), and runs your command with those variables injected. The secret never touches your shell history or any file on disk.

**Examples:**

```bash
# Run a Django migration with production DB credentials
passcli run db/prod -- python manage.py migrate

# Start a dev server with API keys loaded
passcli run myapp/env -- npm run dev

# Run AWS CLI with credentials from pass
passcli run aws/personal -- aws s3 ls

# Run a one-off script with Stripe keys
passcli run stripe/live -- python scripts/charge.py
```

**What the environment looks like inside your command:**

If your entry contains:
```
sk_live_abc123xyz
username: admin@company.com
url: https://api.stripe.com
```

Your process sees:
```
PASS_PASSWORD=sk_live_abc123xyz
PASS_USERNAME=admin@company.com
PASS_URL=https://api.stripe.com
```

Your code reads them:
```python
import os
stripe.api_key = os.environ["PASS_PASSWORD"]
db_user = os.environ["PASS_USERNAME"]
```

**Why this is better than a `.env` file:**

| `.env` file approach | `passcli run` approach |
|---|---|
| Secret is on disk unencrypted | Secret never touches disk |
| Risk of accidentally committing it | Nothing to commit |
| Need to update two places when secret rotates | Update pass, everything picks it up |
| Shared across team via `.env.example` habit | Each person has their own vault |
| Visible in process environment to other users | Injected only into the child process |

---

### import — migrate from another manager

```bash
passcli import ~/Downloads/bitwarden_export.csv
passcli import ~/Downloads/lastpass_export.csv
passcli import ~/Downloads/1password_export.csv
passcli import ~/Downloads/passwords.csv --format generic
```

Format is auto-detected from the CSV header. Supported formats:

| Manager | Export location | Format auto-detected? |
|---|---|---|
| Bitwarden | Tools → Export → File format: .csv | Yes |
| LastPass | Advanced Options → Export | Yes |
| 1Password | File → Export → All Items → CSV | Yes |
| Generic CSV | Any CSV with name/password columns | Fallback |

**What happens during import:**
1. Each row becomes a structured entry
2. Folder structure is preserved (Bitwarden folders → pass subdirectories)
3. TOTP secrets are stored as the `otp` field if present
4. Entries with no name or no password are skipped
5. Existing entries are overwritten (`-f` flag)

**After importing, always run:**
```bash
passcli health
```
Imported passwords are often weak or reused. The health report gives you a prioritised list of what to fix first.

---

### find — search and act

```bash
passcli find gmail
```

Searches entry names for the term and displays matching results. After showing matches, PassCLI offers to select one and act on it — the same action menu as `browse` appears:

```
Search results:
  email/gmail
  email/gmail-work

Act on entry (0 to skip):
  1  email/gmail
  2  email/gmail-work
```

This turns `find` from a read-only search into a complete workflow — search, select, and act without switching commands.

---

### sync — git in one step

```bash
passcli sync    # pull then push
passcli gitlog  # see recent history
```

`sync` is equivalent to:
```bash
pass git pull
pass git push
```

**When to use it:** After making changes on any machine. Make it a habit — run `sync` when you sit down and when you finish.

---

### config — adjust defaults

```bash
passcli config                            # show all settings
passcli config clip_timeout 60            # clear clipboard after 60s instead of 45
passcli config default_password_length 32 # generate 32-char passwords by default
passcli config pass_dir ~/vaults/work     # point to a different store
```

Config is stored at `~/.config/passcli/config.json` with `0600` permissions (owner-read-only).

---

### export-vault / import-vault — encrypted backup

```bash
passcli export-vault ~/backup.passvault
passcli import-vault ~/backup.passvault
passcli import-vault ~/backup.passvault --force   # skip overwrite prompt
```

#### Why this exists

Your password store is already encrypted per-entry by GPG. But it is spread across many `.gpg` files in `~/.password-store/`. If you want to:
- Transfer the store to a new machine without a git remote
- Make a point-in-time backup to an external drive or cloud storage
- Hand off a copy of the store to a trusted person temporarily

…you would normally need to tar and GPG-encrypt the whole directory yourself. `export-vault` does this in one step and uses a separate passphrase so the vault can live somewhere different from your GPG key.

#### How it works

**Export:**
1. PassCLI walks the entire `~/.password-store/` directory (excluding `.git/`)
2. Compresses everything into an in-memory gzip-compressed tar
3. Derives a 32-byte AES-256 key from your passphrase using PBKDF2-SHA256 with 600,000 iterations
4. Encrypts the tar with AES-256-GCM (authenticated encryption — tampering is detected)
5. Writes a single binary file: `PCV1` magic header + salt + nonce + ciphertext
6. Sets file permissions to `0600`

**Import:**
1. Reads the `PCV1` magic header — rejects non-vault files immediately, before asking for a passphrase
2. Prompts for the passphrase
3. Decryption failure (wrong passphrase or tampered file) gives a single generic message — no information about which part failed
4. If your current store has entries, shows a warning with the count and asks to confirm before overwriting
5. Extracts the tar back to `~/.password-store/`

#### The vault file format

```
Offset   Size    Field
------   ----    -----
0        4       Magic bytes: "PCV1"
4        32      Salt  (random, for key derivation)
36       12      Nonce (random, for AES-256-GCM)
48       N+16    Ciphertext + 16-byte GCM authentication tag
```

The vault contains your `.gpg` files. Each `.gpg` file is still GPG-encrypted inside the vault — the vault is a second layer of encryption. Without the vault passphrase, the file is opaque. Without your GPG key, the individual entries cannot be decrypted even after unpacking.

#### Practical use

**Machine migration (no git remote):**

```bash
# On old machine:
passcli export-vault ~/Desktop/vault.passvault
# Copy the file to new machine (USB, AirDrop, etc.)

# On new machine (after installing PassCLI and importing your GPG key):
passcli import-vault ~/Desktop/vault.passvault
```

**Periodic backup to cloud storage:**

```bash
# Run monthly or after major changes
passcli export-vault ~/Dropbox/passcli-backup-$(date +%Y%m).passvault
```

The file is safe to store in Dropbox, iCloud, or Google Drive — without the passphrase it is opaque ciphertext. Keeping dated backups (by month) lets you roll back if you accidentally delete entries.

**What the `--force` flag does:**

Without `--force`, if `~/.password-store/` already has entries, `import-vault` shows:

```
╭─ ⚠ Existing Store Detected ─────────────────╮
│ Your current password store has 47 entries. │
│ Importing will overwrite files with the     │
│ same names.                                 │
╰─────────────────────────────────────────────╯
Overwrite existing password store? [y/N]:
```

With `--force`, it proceeds without asking. Use `--force` in scripts or when you are certain.

#### What is NOT included in the vault

The `.git/` directory is excluded. This keeps the vault compact — git history can be megabytes for active stores, but only the encrypted files matter for a backup. When you import a vault on a new machine, `pass git init` will reinitialise git if needed.

---

## 8. Developer workflows

### Workflow: Replace .env files entirely

**Step 1: Store your project's secrets**

```bash
passcli insert myapp/database
# password: postgres://user:pass@localhost/mydb
# username: app_user

passcli insert myapp/stripe
# password: sk_live_abc123
# username: restricted_key

passcli insert myapp/sendgrid
# password: SG.abc123
```

**Step 2: Run your app with secrets injected**

```bash
passcli run myapp/database -- python manage.py runserver
```

Or create a wrapper script (do not commit this either, but it is safe since it contains no secrets):

```bash
#!/usr/bin/env bash
# dev.sh
passcli run myapp/database -- \
  bash -c 'passcli run myapp/stripe -- passcli run myapp/sendgrid -- python manage.py runserver'
```

For multiple entries at once, use a shell function in your `.zshrc`:

```bash
# Load all secrets for a project into current shell
pload() {
  local project="$1"
  for entry in $(passcli ls "$project/" 2>/dev/null | grep -v "/$"); do
    eval "$(passcli get "$project/$entry" --field password | \
      awk -v key="PASS_${entry^^}" '{print "export " key "=" $0}')"
  done
}
```

### Workflow: API key management

Organise API keys with consistent naming:

```
api/openai
api/anthropic
api/github-personal
api/github-work
api/aws-personal
api/aws-work-dev
api/aws-work-prod
```

Each entry structured as:
```
sk-abc123...
username: service-account@company.com
url: https://api.openai.com
notes: gpt-4 access, created 2025-01-01, rotates quarterly
```

The `notes` field is where you record rotation schedules, what the key has access to, and who owns it. This metadata is invaluable six months later.

Retrieve for scripts:
```bash
OPENAI_KEY=$(passcli get api/openai --field password)
```

Or inject directly:
```bash
passcli run api/openai -- python scripts/summarise.py input.txt
# Your script reads os.environ["PASS_PASSWORD"]
```

### Workflow: SSH and server credentials

```bash
passcli insert ssh/prod-server
# password: your_ssh_passphrase_or_root_password
# username: deploy
# url: 192.168.1.100
# notes: Ubuntu 22.04, port 2222

# Retrieve the IP
SERVER=$(passcli get ssh/prod-server --field url)
USER=$(passcli get ssh/prod-server --field username)
ssh "$USER@$SERVER"
```

### Workflow: Database credentials per environment

```
db/myapp-local
db/myapp-staging
db/myapp-prod
```

Pattern: `passcli run db/myapp-staging -- python manage.py dbshell`

Use a shell alias:
```bash
alias db-staging='passcli run db/myapp-staging -- python manage.py dbshell'
alias db-prod='passcli run db/myapp-prod -- python manage.py dbshell'
```

### Workflow: CI/CD pipelines

For GitHub Actions or similar, you cannot use PassCLI directly (CI machines do not have your GPG key). The pattern here is:

1. Store your CI secrets in PassCLI locally as the source of truth
2. When you rotate a secret, update it in PassCLI first, then push to GitHub Secrets
3. Retrieve the current value to copy-paste into CI:
   ```bash
   passcli get ci/github-actions-deploy --clip
   ```

PassCLI is your local source of truth. CI systems have their own secret stores — PassCLI feeds them, not the other way around.

---

## 9. Normal user workflows

### Workflow: Day-to-day login

1. Run `passcli browse` (or just `passcli` to enter the shell, then type `browse`)
2. Type a few characters of the site name — fzf filters instantly
3. Press Enter on the right entry
4. Press `c` to copy the password — it is in your clipboard for 45 seconds
5. Switch to your browser, paste
6. Need the username too? Press `u` in the action menu

That is the entire workflow. Three keystrokes and a paste.

### Workflow: Adding a new account

When you create an account on a new site, you have two options:

**Option A: Generate a standalone password**

```bash
passcli generate web/newsite --clip
```

This generates a strong password, shows it with its strength, AND copies it to clipboard. Paste it into the signup form. The entry is already saved.

**Option B: Create a full entry with all fields** (recommended)

```bash
passcli insert web/newsite
# Password (Enter to generate): ↵     ← auto-generates a password
# Length [20]:
# Include symbols? [Y/n]:
# Username: john@example.com
# URL: https://newsite.com
```

This creates the entry with username, URL, and a generated password in one step — no need to run `generate` and `edit` separately.

If the site requires you to type the password twice (confirm field), use:

```bash
passcli browse
# select the entry, press s (Show)
# press c to copy password
```

### Workflow: Logging in with 2FA

```bash
passcli> browse
# select web/github
# press c (Copy) — password is in your clipboard
# run browse again or use otp:
passcli> otp web/github           # OTP code generated and copied

# Or in sequence from CLI:
passcli get web/github --clip    # password copied
passcli otp web/github           # OTP code generated and copied
```

### Workflow: Migrating from Bitwarden

1. In Bitwarden: Tools → Export Vault → File Format: `.csv` → Export
2. Run:
   ```bash
   passcli import ~/Downloads/bitwarden_export.csv
   ```
3. Verify:
   ```bash
   passcli ls
   passcli health
   ```
4. Delete the CSV file immediately — it contains all your passwords in plain text:
   ```bash
   rm ~/Downloads/bitwarden_export.csv
   ```

---

## 10. Entry naming conventions and organisation

Good naming makes the difference between a vault you can navigate and one you dread opening.

### Recommended structure

```
email/
  personal
  work
  newsletters

web/
  github
  gitlab
  stackoverflow

finance/
  bank-of-america-checking
  chase-credit
  coinbase
  robinhood

dev/
  aws-personal
  aws-work
  stripe-live
  stripe-test
  openai
  anthropic

ssh/
  home-server
  prod-server
  staging-server

wifi/
  home
  office
  parents

misc/
  passport-pin
  sim-pin
  safe-combination
```

### Naming rules

1. **Use lowercase** — consistent, easy to tab-complete
2. **Use hyphens, not underscores or spaces** — `bank-of-america`, not `bank_of_america`
3. **Be specific enough** — `email/work` is fine if you have one work email; use `email/google-work` if you have multiple
4. **Use environment suffixes for dev credentials** — `stripe-live` vs `stripe-test`, `db-prod` vs `db-staging`
5. **Group by category, not by alphabet** — the folder structure IS your categories

### The archive folder

When an entry is no longer active but you do not want to delete it:

```bash
passcli archive web/old-employer-vpn
```

This moves it to `archive/web/old-employer-vpn`. It stays encrypted and in git history. Restore it any time:

```bash
passcli restore web/old-employer-vpn
```

Use archives for:
- Former employer accounts (keep for a few months)
- Old bank accounts you closed
- Services you cancelled but might return to
- Old API keys that were rotated (in case you need to debug something old)

**Delete safety:** When deleting an entry, PassCLI shows a preview of the entry's metadata (username, email, URL) before asking for confirmation. This helps you verify you are deleting the right entry when names are similar.

---

## 11. Best practices

### Password hygiene

**Generate, never invent.** Use `passcli generate` for every new password. Human-invented passwords are predictable even when they feel random. Let the generator do it.

```bash
passcli generate web/newsite 32  # 32 chars for high-value accounts
passcli generate wifi/home 20 --no-symbols  # for devices that do not like symbols
```

**Minimum lengths:**
- Banking, email, password manager master: 32+ characters
- Social media, shopping: 20+ characters
- Wi-Fi, pins, low-stakes: 16+ characters

**Run health checks regularly.** Once a month:
```bash
passcli health
```
Address everything red before anything yellow.

**Rotate after any breach.** If a service you use announces a data breach, rotate that password immediately:
```bash
passcli generate web/breached-service
```

### GPG key management

**Use a strong passphrase on your GPG key.** This is your last line of defence if someone gets your password store. Make it a passphrase (several words), not a password.

**Back up your GPG private key.** Export it to an encrypted USB drive and store it somewhere physically safe:
```bash
gpg --export-secret-keys --armor YOUR_KEY_ID > private-key-backup.asc
# Store this file encrypted, offline
```

**Never put your GPG private key in the password store.** That would be circular. The backup lives separately.

**Take vault backups before GPG key rotation.** If you re-encrypt the store with a new GPG key, create a vault export first in case you need to roll back:
```bash
passcli export-vault ~/vault-pre-rotation-$(date +%Y%m%d).passvault
```

### Git and sync

**Commit often, sync regularly.** Every time you add or change an entry, `pass` commits automatically. Run `passcli sync` to push those commits.

**Use a private repository.** Never push your password store to a public repo. Entry names, folder structure, and your GPG key ID are all in the clear in git.

**Enable 2FA on your git host.** The encrypted store is safe, but your git account is the access point — protect it.

**Do not store the GPG private key in the same repo as the store.** If someone clones the repo, they should only have ciphertext, never the key.

### Secrets in development

**Never commit secrets to code.** Not even test secrets. Use PassCLI's `run` command instead of `.env` files.

**Rotate API keys regularly.** When you rotate, update PassCLI first, then update any CI/CD variables:
```bash
passcli generate api/stripe-live  # or insert new key
# then manually update GitHub Secrets / Vercel / etc.
```

**Use separate entries for production and staging.** `stripe-live` and `stripe-test` should be different entries. This prevents accidental use of production credentials in development.

---

## 12. Security model

Understanding what PassCLI protects and what it does not is essential.

### What is protected

- **Password content** — encrypted by GPG. Without your private key and passphrase, the ciphertext is useless.
- **Clipboard contents** — auto-cleared after a configurable timeout (default 45s). Verified by comparing content before clearing.
- **Shell history** — stored at `~/.config/passcli/history` with `0600` permissions. Only you can read it.
- **Config file** — stored at `~/.config/passcli/config.json` with `0600` permissions.
- **Vault files** — AES-256-GCM authenticated encryption with PBKDF2-SHA256 (600,000 iterations). Tampering is detected. Wrong passphrase gives a single generic error — no oracle to distinguish decryption failure from corruption. Written with `0600` permissions.

### What is not protected (and what to know about it)

- **Entry names and folder structure** — visible in the git repository and on the filesystem in plain text. Anyone with access to your password store directory (or your git repo) can see what services you use.
- **Metadata** — git history reveals when entries were added, modified, or deleted. Commit messages show which entries were touched.
- **Your GPG key ID** — stored in `.password-store/.gpg-id`, committed to git, visible in plain text. This identifies which key to use for encryption.
- **Plaintext passwords in memory** — during `health` checks, passwords are decrypted and processed in Python memory. Python does not guarantee immediate memory clearing. On a single-user machine this is acceptable.
- **Process environment** — when using `passcli run`, the injected env vars are visible to the child process and any process that can inspect it (e.g., `ps auxe` on Linux). This is inherent to Unix process environment design.

### The threat model PassCLI is designed for

| Threat | Protected? |
|---|---|
| Cloud provider breach (e.g., GitHub) | Yes — only encrypted ciphertext in the repo |
| Stolen laptop (disk access) | Yes — GPG encryption protects the store |
| Phishing / malware that reads files | Partially — GPG protects the store, but malware that can read files can also read your GPG key |
| Shoulder surfing | Yes — passwords shown only on explicit request, clipboard auto-clears |
| Accidental secret commit to code | Yes — `run` command means secrets never touch disk as plaintext |
| Brute force of your passwords | Yes — generated passwords are random and high-entropy |
| Weak/reused passwords | Yes — `health` command detects these |
| Forgotten passwords on old accounts | Yes — archive system prevents loss while keeping the store clean |
| Vault backup intercepted in transit / at rest | Yes — AES-256-GCM; file is opaque without the vault passphrase |

### What PassCLI is not designed for

- **Shared team vaults** — `pass` supports multiple GPG recipients but PassCLI does not expose this yet. For team use, look at `pass` directly or a dedicated secrets manager like HashiCorp Vault.
- **Mobile access** — PassCLI is terminal-only. For mobile, sync your store and use a `pass`-compatible mobile app ([Password Store for Android](https://github.com/android-password-store/Android-Password-Store), [Pass for iOS](https://mssun.github.io/passforios/)).
- **Hardware security keys** — GPG hardware key support (YubiKey) is handled by GPG itself, not PassCLI. It is compatible but PassCLI does not configure it.

---

## 13. Troubleshooting

### "No entries found" when running browse or health

Your password store is empty or PassCLI cannot find it.

```bash
passcli config pass_dir     # check where it's looking
ls ~/.password-store        # verify the store exists
passcli ls                  # list entries directly
```

If the store is in a different location:
```bash
passcli config pass_dir /path/to/your/.password-store
```

### "GPG encryption failed" when generating or inserting

The password store is not initialised, or the configured GPG key is no longer available.

```bash
passcli gpg_list    # check available keys
passcli init        # re-initialise with an available key
```

### "Cannot decrypt" or "GPG key error" when retrieving entries

PassCLI now provides specific error messages:
- **"Entry not found"** — the entry does not exist. Run `ls` to see available entries.
- **"Cannot decrypt"** — your GPG key is locked or the wrong key. Try `gpg --card-status` to check.
- **"GPG key error"** — the encryption key is missing or unusable. Run `gpg_list` to verify your keys.

### "Command not found: pass"

`pass` is not installed or not in your PATH.

```bash
brew install pass          # macOS
sudo apt install pass      # Ubuntu
```

### OTP says "No OTP secret found"

Your entry does not have an `otp:` field.

Edit the entry and add one:
```bash
passcli edit web/github
# In your editor, add a line:
# otp: YOUR_SECRET_KEY_HERE
```

The secret key is the text shown when you set up 2FA on the site (the "manual entry" option next to the QR code).

### Clipboard does not auto-clear

`pyperclip` is not installed, or no clipboard tool is available.

```bash
pip install pyperclip
# macOS: pbcopy is built in, pyperclip will use it automatically
# Linux: install xclip or wl-clipboard
sudo apt install xclip   # X11
sudo apt install wl-clipboard  # Wayland
```

### Tab completion not working in the shell

The shell (`passcli` with no arguments) uses Python's `readline` for completion. On macOS, the system Python may have a readline that does not support completion.

```bash
# Ensure you are using Homebrew Python
which python3
# Should be /usr/local/bin/python3 or /opt/homebrew/bin/python3

# If using pyenv or conda, ensure readline is available
pip install gnureadline   # macOS fallback
```

### Import skips entries

Entries are skipped if they have no name or no password. Check your CSV:
- Bitwarden: secure notes export as a different type — only login entries have passwords
- LastPass: "secure notes" and "form fills" have no password field

Run the import and note which entries show `✗` — those are the skipped ones. You can add them manually with `passcli insert`.

### "Decryption failed. Wrong passphrase or corrupted vault."

This message appears when `import-vault` cannot decrypt the vault file. Possible causes:

1. **Wrong passphrase** — the most common cause. PassCLI intentionally gives the same message for wrong passphrase and corrupted file to avoid oracle attacks.
2. **Corrupted vault file** — if the file was truncated or modified in transit, GCM authentication fails.
3. **Wrong vault file** — verify the file starts with the `PCV1` magic header:
   ```bash
   python3 -c "print(open('backup.passvault', 'rb').read(4))"
   # Should print: b'PCV1'
   ```

If you have the correct passphrase and the file is valid, try exporting again from a machine where the store is intact.

### "Not a valid PassCLI vault file."

The file you passed to `import-vault` does not have the `PCV1` header. Either it is not a vault file, or it was created by an incompatible version. Double-check the file path.

### "Not in sudoers" when trying to create a global command

See the [Installation section](#4-installation-and-first-time-setup) — use `~/.local/bin` instead of `/usr/local/bin`. No sudo required.

---

*PassCLI is a wrapper. `pass` and GPG are doing the real work. If you ever need to step outside PassCLI — for scripting, for a feature not yet built, or for troubleshooting — raw `pass` commands work exactly as documented at [passwordstore.org](https://www.passwordstore.org/). Nothing is locked in.*
