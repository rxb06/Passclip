# Passclip Guide

A complete walkthrough of what Passclip does, who it's for, and how to get the most out of it. If you're looking for installation instructions, see [setup.md](setup.md). If you're looking for the security model, see [../SECURITY.md](../SECURITY.md).

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

### The engineer

You manage secrets across services, infrastructure, and CI/CD pipelines. You need credentials injected into builds without `.env` files on disk. You want structured entries you can query programmatically. The `run` command, structured `key: value` format, and fuzzy-copy shortcuts are built for this workflow.

### The security-conscious practitioner

Your threat model says secrets should never leave your machine unencrypted. You don't trust cloud password managers — not because they're insecure, but because local GPG-encrypted storage with git-based sync is the architecture you want. `pass` provides the foundation. Passclip makes it practical with health auditing, clipboard auto-clear, and entry validation.

### The power user migrating from another manager

You have a Bitwarden or LastPass export and want to move to a local, offline, GPG-encrypted store. The `import` command handles this in one step with format auto-detection.

### Anyone who uses `pass` daily

You like `pass` but the ergonomics slow you down. You want one command to grab a password, tab completion in a REPL, TOTP codes without a separate extension, and a health report that flags weak or reused credentials. Passclip's `wizard` sets everything up, and `passclip gmail` is all you need day to day.

---

## Core concepts

### The structured entry format

Raw `pass` stores free-form text. The first line is conventionally the password, but the rest is up to you. Passclip formalizes this with a consistent structure:

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

You don't have to use this format. If you use `pass insert` directly or edit entries with `pass edit`, the content is whatever you typed. Passclip will still work — it reads whatever is there, and the first line is always the password.

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

Passclip stores these as `~/.password-store/email/gmail.gpg`, etc. The `.gpg` extension is handled by `pass` transparently — you never type it.

### The password store

Everything lives in `~/.password-store/`. This directory is:
- Plain files and folders on disk
- Each `.gpg` file is GPG-encrypted
- Optionally a git repository (strongly recommended)
- Completely portable — copy it to another machine, and if you have your GPG key, you can decrypt everything

---

## Two ways to use it

### Quick copy mode (the fast path)

For the thing you do 10 times a day — grabbing a password. Just type the name:

```bash
passclip gmail                    # copies password to clipboard
passclip gmail -u                 # copies username
passclip gmail -o                 # copies OTP code
passclip gmail -s                 # shows the full entry
```

You don't need to know the exact path. `passclip gmail` matches `email/gmail`, `web/gmail`, or anything with "gmail" in the name. If there's one match, it copies instantly. If there are several, you pick from a list.

This works because Passclip treats any argument that isn't a known subcommand as a search term. No `get`, no `--clip`, no flags to remember.

### Direct CLI mode

For when you need the full command, scripting, or specific flags:

```bash
passclip get email/gmail --clip --field password
passclip insert web/github
passclip health
passclip sync
```

Run `passclip --help` to see every subcommand.

### Interactive shell mode

Run `passclip` (no arguments) to enter the persistent shell. Best for interactive sessions where you need to do several things.

```
passclip> c gmail           # copy password (fuzzy)
passclip> u gmail           # copy username (fuzzy)
passclip> o gmail           # copy OTP code (fuzzy)
passclip> browse            # fuzzy pick → action menu
passclip> health
passclip> sync
```

**Shell advantages over direct CLI:**
- **Single-letter shortcuts**: `c`, `u`, `o` — fuzzy search + copy in one command
- Tab completion for entry names — type `get em` and press Tab
- Persistent command history across sessions
- Faster for multiple operations — no subprocess startup overhead
- `browse` defaults to copy — press Enter on an entry and the password is in your clipboard

---

## Feature deep-dives

### browse — the daily driver

```bash
passclip browse
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

**Without fzf:** If fzf isn't installed and you have more than 15 entries, Passclip asks for a filter term first, then shows a numbered list of matches. Large vaults stay navigable even without fzf.

---

### get — retrieve with precision

```bash
passclip get email/gmail             # show full entry
passclip get email/gmail --clip      # copy password to clipboard
passclip get email/gmail --field url # print just the URL
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
passclip get web/github --field username

# Copy just the URL to clipboard
passclip get web/github --field url --clip
```

---

### insert — add entries the right way

```bash
passclip insert web/github
```

Prompts you through each field:

```
Password (Enter to generate): ●●●●●●●●●●●●
  Strength: █████ Very Strong
Username: john@example.com
Email:
URL: https://github.com
Notes: personal account
OTP secret (Enter to skip):
```

**Auto-generate option:** Leave the password blank and press Enter. Passclip asks for a length and whether to include symbols, then generates a secure random password.

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
passclip generate web/newsite          # 20 chars, default settings
passclip generate web/newsite 32       # 32 chars
passclip generate web/newsite --no-symbols  # alphanumeric only
passclip generate web/newsite --clip   # generate and copy to clipboard
```

Default length is configurable:

```bash
passclip config default_password_length 32
```

**When to use `--no-symbols`:** Some banking sites and legacy enterprise tools reject passwords with special characters.

---

### health — know the state of your vault

```bash
passclip health
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
4. Use `passclip generate <entry>` to replace them

---

### otp — TOTP codes without a phone

**Adding OTP to an entry:**

```bash
passclip otp --add web/github
```

This walks you through it:
1. If you copied an `otpauth://` URI or base32 secret to your clipboard, it detects it and offers to use it
2. Otherwise, paste the secret when prompted
3. It validates the secret, saves it to the entry, and shows your first code as confirmation

You can also set up OTP during `passclip insert` — there's an optional OTP secret prompt after the other fields.

**Generating a code:**

```bash
passclip otp web/github
```

Shows a live TOTP code and copies it to clipboard (auto-clears when it expires).

**Where to get the OTP secret:** When setting up 2FA on a site, most show a QR code AND a text secret underneath. Copy the text secret to your clipboard, then run `passclip otp --add`.

Passclip accepts both raw base32 secrets (like `JBSWY3DPEHPK3PXP`) and full `otpauth://` URIs.

---

### run — inject secrets as environment variables

```bash
passclip run <entry> -- <command>
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

| `.env` file approach | `passclip run` approach |
|---|---|
| Secret is on disk unencrypted | Secret never touches disk |
| Risk of accidentally committing it | Nothing to commit |
| Need to update two places when secret rotates | Update pass, everything picks it up |
| Shared across team via `.env.example` habit | Each person has their own vault |

---

### export-vault / import-vault — encrypted backup

```bash
passclip export-vault ~/backup.passvault
passclip import-vault ~/backup.passvault
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
passclip find gmail
```

Searches entry names for the term and displays matching results. Then offers to select one and act on it — the same action menu as `browse`.

Turns `find` from a read-only search into a complete workflow — search, select, and act without switching commands.

---

## Everyday workflows

### Logging in to something

```bash
passclip gmail          # password → clipboard
```

That's it. One command, one paste.

If you're already in the shell: `c gmail`. Same result.

Need the username too?
```bash
passclip gmail -u       # username → clipboard
```

### Signing up for a new service

```bash
passclip insert web/newsite
# Password (Enter to generate): ↵     ← auto-generates
# Length [20]:
# Username: john@example.com
# URL: https://newsite.com
```

Creates the entry with username, URL, and a generated password in one step.

### Logging in with 2FA

```bash
passclip github                   # password → clipboard, paste it
passclip github -o                # OTP code → clipboard, paste it
```

Or in the shell:
```
passclip> c github
passclip> o github
```

**First time?** Set up OTP with `passclip otp --add web/github` — copy the secret from the site, and Passclip picks it up from your clipboard.

### Updating a password after a breach

```bash
passclip generate web/breached-service 32
```

Generates a new password and replaces the old one. Strength is shown immediately.

---

## Developer workflows

### Replace .env files entirely

Store your project's secrets:

```bash
passclip insert myapp/database
# password: postgres://user:pass@localhost/mydb

passclip insert myapp/stripe
# password: sk_live_abc123

passclip insert myapp/sendgrid
# password: SG.abc123
```

Run your app with secrets injected:

```bash
passclip run myapp/database -- python manage.py runserver
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
OPENAI_KEY=$(passclip get api/openai --field password)
```

Or inject directly:
```bash
passclip run api/openai -- python scripts/summarize.py input.txt
```

### Database credentials per environment

```
db/myapp-local
db/myapp-staging
db/myapp-prod
```

Use shell aliases:
```bash
alias db-staging='passclip run db/myapp-staging -- python manage.py dbshell'
alias db-prod='passclip run db/myapp-prod -- python manage.py dbshell'
```

### SSH and server credentials

```bash
passclip insert ssh/prod-server
# password: your_ssh_passphrase
# username: deploy
# url: 192.168.1.100
# notes: Ubuntu 22.04, port 2222

# Retrieve and connect
SERVER=$(passclip get ssh/prod-server --field url)
USER=$(passclip get ssh/prod-server --field username)
ssh "$USER@$SERVER"
```

### CI/CD pipelines

For GitHub Actions or similar, you can't use Passclip directly (CI machines don't have your GPG key). The pattern is:

1. Store CI secrets in Passclip locally as your source of truth
2. When you rotate a secret, update it in Passclip first, then push to GitHub Secrets
3. Retrieve the current value to copy-paste:
   ```bash
   passclip get ci/github-deploy --clip
   ```

Passclip is your local source of truth. CI systems have their own secret stores — Passclip feeds them.

---

## Setting up a new machine

### Fresh start (no existing passwords)

```bash
pip install rich cryptography pyperclip pyotp
passclip wizard
```

The wizard generates a GPG key, initializes the store, and sets up git. Done.

### You already have a store on another machine

**Option A — Git clone** (if your store is in a git repo):

```bash
git clone git@github.com:you/your-pass-store.git ~/.password-store
pip install rich cryptography pyperclip pyotp
passclip ls    # verify it works
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
passclip wizard               # set up GPG and empty store
passclip import-vault ~/backup.vault     # restore everything
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
passclip export-vault ~/backup.vault
```

Pick a strong passphrase. There's no recovery if you forget it.

For dated backups:
```bash
passclip export-vault ~/Dropbox/passclip-backup-$(date +%Y%m).vault
```

### Restoring from a backup

```bash
passclip import-vault ~/backup.vault
```

If entries already exist, you'll be warned before overwriting. Use `--force` to skip the prompt.

### Automatic pre-delete backups

Passclip saves entries to `~/.config/passclip/backups/` before deleting them. If you accidentally delete something, check there first. Clean out the directory periodically — those backups are plaintext.

---

## Two-factor authentication (TOTP)

### Adding a TOTP secret

When a website gives you a TOTP setup QR code, it usually also offers a text secret. Copy it, then:

```bash
passclip otp --add web/github
```

If the secret is in your clipboard, Passclip detects it and offers to use it automatically. Otherwise, paste it when prompted. Both raw base32 secrets and `otpauth://` URIs work.

You can also add OTP during initial entry creation — `passclip insert` includes an optional OTP secret prompt.

To update an existing OTP secret, run `otp --add` again — it asks before overwriting.

### Generating a code

```bash
passclip otp web/github
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
passclip archive web/old-employer-vpn
```

This moves it to `archive/web/old-employer-vpn`. Restore it any time:

```bash
passclip restore web/old-employer-vpn
```

Good candidates for archiving:
- Former employer accounts (keep for a few months)
- Old bank accounts you closed
- Services you cancelled but might return to
- Old API keys that were rotated (in case you need to debug something old)

### Moving and renaming

```bash
passclip mv web/twitter web/x          # rename
passclip mv personal/github dev/github # move to different folder
passclip cp dev/postgres dev/postgres-backup  # copy
```

---

## Best practices

### Password hygiene

**Generate, never invent.** Use `passclip generate` for every new password. Human-invented passwords are predictable even when they feel random.

**Minimum lengths:**
- Banking, email, master passwords: 32+ characters
- Social media, shopping: 20+ characters
- Wi-Fi, pins, low-stakes: 16+ characters

**Run health checks regularly.** Once a month:
```bash
passclip health
```
Address everything weak before everything fair.

**Rotate after any breach.** If a service announces a data breach:
```bash
passclip generate web/breached-service 32
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
passclip export-vault ~/vault-pre-rotation-$(date +%Y%m%d).vault
```

### Git and sync

**Commit often, sync regularly.** Every time you add or change an entry, `pass` commits automatically. Run `passclip sync` to push.

**Use a private repository.** Never push your password store to a public repo. Entry names, folder structure, and your GPG key ID are visible in the clear.

**Enable 2FA on your git host.** The encrypted store is safe, but your git account is the access point.

### Secrets in development

**Never commit secrets to code.** Not even test secrets. Use `run` instead of `.env` files.

**Rotate API keys regularly.** Update Passclip first, then update CI/CD variables.

**Use separate entries for production and staging.** `stripe-live` and `stripe-test` should be different entries. Prevents accidental use of production credentials in development.

---

*Passclip extends `pass` — it doesn't replace it. `pass` and GPG are doing the encryption. If you ever need to step outside Passclip — for scripting, for a feature not yet built, or for troubleshooting — raw `pass` commands work exactly as documented at [passwordstore.org](https://www.passwordstore.org/). Nothing is locked in.*
