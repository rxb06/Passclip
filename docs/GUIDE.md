# PassCLI Guide

A complete walkthrough of what PassCLI does, who it's for, and how to get the most out of it. If you're looking for installation instructions, see [SETUP.md](SETUP.md). If you're looking for the security model, see [../SECURITY.md](../SECURITY.md).

---

## Table of Contents

- [Who is this for?](#who-is-this-for)
- [Core concepts](#core-concepts)
- [Two ways to use it](#two-ways-to-use-it)
- [Feature deep-dives](#feature-deep-dives)
- [Everyday workflows](#everyday-workflows)
- [Developer workflows](#developer-workflows)
- [Setting up a new machine](#setting-up-a-new-machine)
- [Backup and disaster recovery](#backup-and-disaster-recovery)
- [Two-factor authentication (TOTP)](#two-factor-authentication-totp)
- [Organizing your password store](#organizing-your-password-store)
- [Best practices](#best-practices)

---

## Who is this for?

### The normal user

You want a secure password manager that doesn't send your passwords to a server somewhere. You've heard `pass` is the gold standard for Unix password management but the command line looks intimidating. PassCLI's `wizard` sets everything up for you, and after that `browse` is all you need day to day.

### The developer

You use secrets constantly — API keys, database credentials, environment variables. You're tired of `.env` files that accidentally get committed. You want to inject secrets into your development environment without them ever touching disk unencrypted. The `run` command and the structured entry format are built for you.

### The power user migrating from another manager

You have a Bitwarden or LastPass export and want to move to a local, offline, GPG-encrypted store. The `import` command handles this in one step with format auto-detection.

### The security-conscious person

You don't trust cloud password managers — not because they're insecure, but because your threat model says your secrets should never leave your machine unencrypted. `pass` with a git backup is the right architecture. PassCLI makes it practical.

---

## Core concepts

### The structured entry format

Raw `pass` stores free-form text. The first line is conventionally the password, but the rest is up to you. PassCLI formalizes this with a consistent structure:

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
- Any line that isn't a `key: value` pair is treated as notes.
- This format is fully compatible with raw `pass` — the file is plain text before GPG encryption.

You don't have to use this format. If you use `pass insert` directly or edit entries with `pass edit`, the content is whatever you typed. PassCLI will still work — it reads whatever is there, and the first line is always the password.

### Entry paths

Entries are organized as paths inside your password store (`~/.password-store` by default). The path is the key you use to retrieve, edit, or delete an entry.

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

## Two ways to use it

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
- Persistent command history across sessions
- Faster for multiple operations — no subprocess startup overhead
- Quick-copy after viewing — press `c`/`u`/`l` to copy password, username, or URL without re-running the command
- `browse` is most natural here — fuzzy-pick, act, pick again

---

## Feature deep-dives

### browse — the daily driver

```bash
passcli browse
```

Opens fzf (or a filtered numbered list if fzf isn't installed) with every entry in your store. You fuzzy-search, select, and then choose what to do:

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

This is the command most people use most often. You don't need to remember paths. You type a few characters of what you're looking for, press Enter, and either the password is shown or it's in your clipboard.

**Without fzf:** If fzf isn't installed and you have more than 15 entries, PassCLI asks for a filter term first, then shows a numbered list of matches. Large vaults stay navigable even without fzf.

---

### get — retrieve with precision

```bash
passcli get email/gmail             # show full entry
passcli get email/gmail --clip      # copy password to clipboard
passcli get email/gmail --field url # print just the URL
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

**Using `--field` in scripts:**

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
Password (Enter to generate): ●●●●●●●●●●●●
  Strength: █████ Very Strong
Username: john@example.com
Email:
URL: https://github.com
Notes: personal account
```

**Auto-generate option:** Leave the password blank and press Enter. PassCLI asks for a length and whether to include symbols, then generates a secure random password.

```
Password (Enter to generate): ↵
Length [20]: 24
Include symbols? [Y/n]: y
Generated: xK#9mR!2pL@vQ8nW$3jF&5bA
  Strength: █████ Very Strong
```

Password strength is always shown immediately so you can decide whether it's strong enough before filling in the rest of the fields.

---

### generate — create strong passwords

```bash
passcli generate web/newsite          # 20 chars, default settings
passcli generate web/newsite 32       # 32 chars
passcli generate web/newsite --no-symbols  # alphanumeric only
passcli generate web/newsite --clip   # generate and copy to clipboard
```

Default length is configurable:

```bash
passcli config default_password_length 32
```

**When to use `--no-symbols`:** Some banking sites and legacy enterprise tools reject passwords with special characters.

---

### health — know the state of your vault

```bash
passcli health
```

Decrypts every entry and analyzes:

- **Strength score** per entry (Very Weak / Weak / Fair / Strong / Very Strong)
- **Length** of each password
- **Duplicate detection** — groups entries that share the same password

Both weak and fair passwords are shown in detail so you can prioritize what to fix. Each section includes an actionable tip.

**When to run it:** Periodically (monthly), after importing from another manager, or when you suspect you've reused passwords.

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

Or use a full `otpauth://` URI (as exported by most authenticator apps):

```
otp: otpauth://totp/GitHub:john@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub
```

**Where to get the OTP secret:** When setting up 2FA on a site, most show a QR code AND a text secret underneath. Copy the text secret.

---

### run — inject secrets as environment variables

```bash
passcli run <entry> -- <command>
```

Decrypts the entry, maps every field to an environment variable (`PASS_<FIELDNAME_UPPERCASE>`), and runs your command with those variables injected. The secret never touches your shell history or any file on disk.

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
```

**Why this is better than a `.env` file:**

| `.env` file approach | `passcli run` approach |
|---|---|
| Secret is on disk unencrypted | Secret never touches disk |
| Risk of accidentally committing it | Nothing to commit |
| Need to update two places when secret rotates | Update pass, everything picks it up |
| Shared across team via `.env.example` habit | Each person has their own vault |

---

### export-vault / import-vault — encrypted backup

```bash
passcli export-vault ~/backup.passvault
passcli import-vault ~/backup.passvault
```

Your password store is already encrypted per-entry by GPG. But it's spread across many `.gpg` files. If you want to transfer the store to a new machine, make a point-in-time backup, or hand off a copy to someone temporarily, you'd normally need to tar and GPG-encrypt the whole directory yourself. `export-vault` does this in one step.

**How it works:**
1. Compresses the entire store into an in-memory tar archive (excluding `.git/`)
2. Derives a 32-byte AES-256 key from your passphrase using PBKDF2-SHA256 with 600,000 iterations
3. Encrypts with AES-256-GCM (authenticated encryption — tampering is detected)
4. Writes atomically: temp file first, then rename (no partial files on crash)
5. Sets file permissions to `0600`

**The vault file format:**

```
Offset   Size    Field
------   ----    -----
0        4       Magic bytes: "PCV1"
4        32      Salt  (random, for key derivation)
36       12      Nonce (random, for AES-256-GCM)
48       N+16    Ciphertext + 16-byte GCM authentication tag
```

The vault contains your `.gpg` files — it's a second layer of encryption. Without the vault passphrase, the file is opaque. Without your GPG key, the individual entries can't be decrypted even after unpacking.

The `--force` flag on `import-vault` skips the overwrite confirmation prompt. Use it in scripts or when you're certain.

---

### find — search and act

```bash
passcli find gmail
```

Searches entry names for the term and displays matching results. Then offers to select one and act on it — the same action menu as `browse`.

Turns `find` from a read-only search into a complete workflow — search, select, and act without switching commands.

---

## Everyday workflows

### Logging in to something

1. Run `passcli browse` (or enter the shell and type `browse`)
2. Type a few characters of the site name — fzf filters instantly
3. Press Enter on the right entry
4. Press `c` to copy the password
5. Switch to your browser, paste

Three keystrokes and a paste.

### Signing up for a new service

```bash
passcli insert web/newsite
# Password (Enter to generate): ↵     ← auto-generates
# Length [20]:
# Username: john@example.com
# URL: https://newsite.com
```

Creates the entry with username, URL, and a generated password in one step.

### Logging in with 2FA

```bash
passcli get web/github --clip    # password copied
passcli otp web/github           # OTP code copied
```

Or in the shell, use `browse`, copy the password with `c`, then run `otp web/github`.

### Updating a password after a breach

```bash
passcli generate web/breached-service 32
```

Generates a new password and replaces the old one. Strength is shown immediately.

---

## Developer workflows

### Replace .env files entirely

Store your project's secrets:

```bash
passcli insert myapp/database
# password: postgres://user:pass@localhost/mydb

passcli insert myapp/stripe
# password: sk_live_abc123

passcli insert myapp/sendgrid
# password: SG.abc123
```

Run your app with secrets injected:

```bash
passcli run myapp/database -- python manage.py runserver
```

### API key management

Organize API keys with consistent naming:

```
api/openai
api/anthropic
api/github-personal
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
passcli run api/openai -- python scripts/summarize.py input.txt
```

### Database credentials per environment

```
db/myapp-local
db/myapp-staging
db/myapp-prod
```

Use shell aliases:
```bash
alias db-staging='passcli run db/myapp-staging -- python manage.py dbshell'
alias db-prod='passcli run db/myapp-prod -- python manage.py dbshell'
```

### SSH and server credentials

```bash
passcli insert ssh/prod-server
# password: your_ssh_passphrase
# username: deploy
# url: 192.168.1.100
# notes: Ubuntu 22.04, port 2222

# Retrieve and connect
SERVER=$(passcli get ssh/prod-server --field url)
USER=$(passcli get ssh/prod-server --field username)
ssh "$USER@$SERVER"
```

### CI/CD pipelines

For GitHub Actions or similar, you can't use PassCLI directly (CI machines don't have your GPG key). The pattern is:

1. Store CI secrets in PassCLI locally as your source of truth
2. When you rotate a secret, update it in PassCLI first, then push to GitHub Secrets
3. Retrieve the current value to copy-paste:
   ```bash
   passcli get ci/github-deploy --clip
   ```

PassCLI is your local source of truth. CI systems have their own secret stores — PassCLI feeds them.

---

## Setting up a new machine

### Fresh start (no existing passwords)

```bash
pip install rich cryptography pyperclip pyotp
python pass_cli.py wizard
```

The wizard generates a GPG key, initializes the store, and sets up git. Done.

### You already have a store on another machine

**Option A — Git clone** (if your store is in a git repo):

```bash
git clone git@github.com:you/your-pass-store.git ~/.password-store
pip install rich cryptography pyperclip pyotp
passcli ls    # verify it works
```

You'll need the same GPG key. Export it from your old machine:

```bash
# Old machine
gpg --export-secret-keys YOUR_KEY_ID > private.key
# Transfer securely (USB drive, scp, etc.)

# New machine
gpg --import private.key
rm private.key
```

**Option B — Vault restore** (if you have an encrypted backup):

```bash
pip install rich cryptography pyperclip pyotp
python pass_cli.py wizard               # set up GPG and empty store
passcli import-vault ~/backup.vault     # restore everything
```

---

## Backup and disaster recovery

### When to back up

Good times to export a vault:
- Before migrating to a new machine
- Before doing a big import
- Monthly, as a general safety net
- Before deleting a bunch of entries

### Creating a backup

```bash
passcli export-vault ~/backup.vault
```

Pick a strong passphrase. There's no recovery if you forget it.

For dated backups:
```bash
passcli export-vault ~/Dropbox/passcli-backup-$(date +%Y%m).vault
```

### Restoring from a backup

```bash
passcli import-vault ~/backup.vault
```

If entries already exist, you'll be warned before overwriting. Use `--force` to skip the prompt.

### Automatic pre-delete backups

PassCLI saves entries to `~/.config/passcli/backups/` before deleting them. If you accidentally delete something, check there first. Clean out the directory periodically — those backups are plaintext.

---

## Two-factor authentication (TOTP)

### Adding a TOTP secret

When a website gives you a TOTP setup QR code, it usually also offers a text secret. Add it to your entry:

```bash
passcli edit web/github
# Add a line: otp: JBSWY3DPEHPK3PXP
```

### Generating a code

```bash
passcli otp web/github
```

6-digit code, auto-copied to clipboard, auto-cleared when it expires.

### Should you store TOTP in your password manager?

Convenience vs. security trade-off. Having TOTP codes alongside your passwords in a GPG-encrypted, git-synced store is practical for most people. If your threat model demands maximum separation, keep TOTP on a dedicated authenticator app.

---

## Organizing your password store

### Recommended folder structure

```
email/
  personal
  work

web/
  github
  gitlab
  stackoverflow

finance/
  bank-checking
  credit-card

dev/
  aws-personal
  aws-work
  stripe-live
  stripe-test
  openai

ssh/
  home-server
  prod-server

wifi/
  home
  office

misc/
  passport-pin
  sim-pin
```

### Naming rules

1. **Use lowercase** — consistent, easy to tab-complete
2. **Use hyphens, not underscores or spaces** — `bank-of-america`, not `bank_of_america`
3. **Be specific enough** — `email/work` is fine if you have one work email; use `email/google-work` if you have multiple
4. **Use environment suffixes for dev credentials** — `stripe-live` vs `stripe-test`, `db-prod` vs `db-staging`
5. **Group by category, not by alphabet** — the folder structure IS your categories

### Archiving old entries

When an entry is no longer active but you don't want to delete it:

```bash
passcli archive web/old-employer-vpn
```

This moves it to `archive/web/old-employer-vpn`. Restore it any time:

```bash
passcli restore web/old-employer-vpn
```

Good candidates for archiving:
- Former employer accounts (keep for a few months)
- Old bank accounts you closed
- Services you cancelled but might return to
- Old API keys that were rotated (in case you need to debug something old)

### Moving and renaming

```bash
passcli mv web/twitter web/x          # rename
passcli mv personal/github dev/github # move to different folder
passcli cp dev/postgres dev/postgres-backup  # copy
```

---

## Best practices

### Password hygiene

**Generate, never invent.** Use `passcli generate` for every new password. Human-invented passwords are predictable even when they feel random.

**Minimum lengths:**
- Banking, email, master passwords: 32+ characters
- Social media, shopping: 20+ characters
- Wi-Fi, pins, low-stakes: 16+ characters

**Run health checks regularly.** Once a month:
```bash
passcli health
```
Address everything weak before everything fair.

**Rotate after any breach.** If a service announces a data breach:
```bash
passcli generate web/breached-service 32
```

### GPG key management

**Use a strong passphrase on your GPG key.** This is your last line of defense if someone gets your password store. Make it a passphrase (several words), not a password.

**Back up your GPG private key.** Export it to an encrypted USB drive and store it somewhere physically safe:
```bash
gpg --export-secret-keys --armor YOUR_KEY_ID > private-key-backup.asc
# Store this file encrypted, offline
```

**Never put your GPG private key in the password store.** That would be circular.

**Take vault backups before GPG key rotation:**
```bash
passcli export-vault ~/vault-pre-rotation-$(date +%Y%m%d).vault
```

### Git and sync

**Commit often, sync regularly.** Every time you add or change an entry, `pass` commits automatically. Run `passcli sync` to push.

**Use a private repository.** Never push your password store to a public repo. Entry names, folder structure, and your GPG key ID are visible in the clear.

**Enable 2FA on your git host.** The encrypted store is safe, but your git account is the access point.

### Secrets in development

**Never commit secrets to code.** Not even test secrets. Use `run` instead of `.env` files.

**Rotate API keys regularly.** Update PassCLI first, then update CI/CD variables.

**Use separate entries for production and staging.** `stripe-live` and `stripe-test` should be different entries. Prevents accidental use of production credentials in development.

---

*PassCLI is a wrapper. `pass` and GPG are doing the real work. If you ever need to step outside PassCLI — for scripting, for a feature not yet built, or for troubleshooting — raw `pass` commands work exactly as documented at [passwordstore.org](https://www.passwordstore.org/). Nothing is locked in.*
