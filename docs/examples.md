# Examples

Real-world workflows and recipes. Each one is a self-contained scenario you can follow start to finish.

---

## 1. Grab a password without thinking

You need the password for Gmail. You don't remember the exact entry path.

```bash
passclip gmail
```

If there's one match (`email/gmail`), the password is in your clipboard. If there are several matches, you pick from a list. Done.

---

## 2. Log in to a site with 2FA

You're on GitHub's login page. You need the password, then the TOTP code.

```bash
passclip github            # password → clipboard, paste it
passclip github -o         # OTP code → clipboard, paste it
```

Two commands, two pastes. No app switching, no phone.

---

## 3. Set up a new account

You're signing up for a new service. You want a strong generated password with all the metadata stored.

```bash
passclip insert web/newsite
```

The guided prompts walk you through it:

```
Password (Enter to generate): ↵
Length [20]: 24
Include symbols? [Y/n]: y
Generated: xK#9mR!2pL@vQ8nW$3jF&5bA
  Strength: █████ Very Strong
Username: john@example.com
Email:
URL: https://newsite.com
Notes: personal account
OTP secret (Enter to skip):
```

---

## 4. Add OTP to an existing entry

A site just offered you 2FA setup. Copy the text secret from the setup page, then:

```bash
passclip otp --add web/github
```

Passclip detects the secret in your clipboard and offers to use it. Validates it and shows your first code as confirmation.

---

## 5. Inject secrets into a dev command

You have a Stripe API key stored in Passclip. You need it as an environment variable for your app, without ever putting it in a `.env` file.

```bash
passclip insert dev/stripe-live
# password: sk_live_abc123...
# username: admin@company.com

passclip run dev/stripe-live -- python manage.py runserver
```

Your app sees `PASS_PASSWORD=sk_live_abc123...` and `PASS_USERNAME=admin@company.com` in its environment. Nothing on disk, nothing in shell history.

---

## 6. Migrate from Bitwarden

You exported your Bitwarden vault as a CSV. Preview first, then import:

```bash
passclip import bitwarden_export.csv --dry-run    # see what would happen
passclip import bitwarden_export.csv               # do it
```

Auto-detects the Bitwarden format from CSV headers. After importing:

```bash
rm bitwarden_export.csv       # it has your passwords in plaintext
passclip health               # check for weak or reused passwords
passclip sync                 # push to git
```

---

## 7. Audit your entire vault

Monthly hygiene check:

```bash
passclip health
```

Output:

```
╭─── Password Health Report ────────────────────────╮
│ Strong: 42   Fair: 8   Weak: 3   Duplicates: 5    │
╰───────────────────────────────────────────────────╯

Weak Passwords (update these):
  web/old-forum        █░░░░ Very Weak   len=6
  wifi/neighbor        ██░░░ Weak        len=10

Duplicate Passwords:
  Group 1: web/twitter  |  web/reddit
```

Fix the weak ones:

```bash
passclip generate web/old-forum 24
passclip generate wifi/neighbor 20
```

---

## 8. Back up before a big change

You're about to reimport everything or switch GPG keys. Make a vault backup first:

```bash
passclip export-vault ~/backup-$(date +%Y%m%d).vault
```

Pick a strong passphrase. The vault is AES-256-GCM encrypted, independent of your GPG key.

Restore later on any machine:

```bash
passclip import-vault ~/backup-20260320.vault
```

---

## 9. Use the interactive shell for a batch session

You need to update several entries. The shell keeps you in context:

```bash
passclip
```

```
passclip> c gmail           # copy gmail password
passclip> o github          # copy github OTP
passclip> generate web/old-site 32
passclip> health
passclip> sync
passclip> quit
```

Single-letter shortcuts (`c`, `u`, `o`) do fuzzy matching — you rarely need to type the full path.

---

## 10. Set up on a new machine

**If you have a vault backup:**

```bash
pip install passclip[all]
passclip wizard               # sets up GPG key + store
passclip import-vault ~/backup.vault
```

**If you have a git-synced store:**

```bash
pip install passclip[all]
git clone git@github.com:you/your-pass-store.git ~/.password-store
# import your GPG key from the old machine first
passclip ls                   # verify everything works
```

---

## 11. Quick retrieval in scripts

Pull a specific field into a shell variable without any interactive prompts:

```bash
DB_PASS=$(passclip get db/prod --field password)
DB_HOST=$(passclip get db/prod --field url)

psql "postgresql://app:${DB_PASS}@${DB_HOST}/mydb"
```

Or inject everything at once:

```bash
passclip run db/prod -- psql
```

---

## 12. Archive old credentials

You left a job. You want to keep the credentials for a while but not clutter your daily workflow:

```bash
passclip archive web/old-employer-vpn
passclip archive web/old-employer-email
```

They move to `archive/` and stay out of `browse` and `find`. Bring them back any time:

```bash
passclip restore web/old-employer-vpn
```
