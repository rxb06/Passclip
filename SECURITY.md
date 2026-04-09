# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.2.x | Yes |
| < 1.2 | No |

We only support the latest release. If you're running an older version, please update before reporting issues.

---

## Reporting a vulnerability

If you find a security vulnerability in Passclip, **please report it privately** rather than opening a public issue.

**How to report:**

1. Email the maintainer directly (check the repository for contact info)
2. Or use GitHub's private vulnerability reporting feature: go to the **Security** tab of this repository and click **"Report a vulnerability"**

**What to include:**

- A clear description of the vulnerability
- Steps to reproduce it
- The version of Passclip you're running (`passclip --version`)
- Your operating system and Python version
- Any proof-of-concept code or output, if applicable

**What to expect:**

- An acknowledgment within 48 hours
- A fix or mitigation plan within 7 days for critical issues
- Credit in the release notes (unless you prefer to stay anonymous)

Please **do not** open a public GitHub issue for security vulnerabilities. This gives us time to fix the problem before it's widely known.

---

## Security model

Passclip is a CLI built on top of [`pass`](https://www.passwordstore.org/), the standard Unix password manager. It does not implement its own encryption for the password store — that's all handled by GPG through `pass`. Every read and write goes through `pass`. Here's what Passclip is responsible for and what it isn't.

### What Passclip handles

- **Input validation**: entry names are checked for path traversal (`..`), shell metacharacters, excessive depth, and other tricks before any write operation.
- **Subprocess safety**: all calls to `pass`, `gpg`, `git`, and other tools use Python's `subprocess` module with list arguments. There is no `shell=True` anywhere in the codebase, which means no shell injection.
- **Clipboard management**: passwords are auto-cleared from the clipboard after a configurable timeout (default 45s). Passclip checks clipboard content before clearing (using constant-time comparison) to avoid wiping something you copied after the password. The clipboard clear helper uses no shell commands — all paths use Python subprocess with list arguments.
- **Vault encryption**: the `export-vault` / `import-vault` feature uses AES-256-GCM with a key derived via PBKDF2-SHA256 at 600,000 iterations. The magic header, salt, and nonce are authenticated as additional associated data (AAD), so tampering with any part of the vault file is detected. Vault files are written atomically (temp file + rename) to prevent partial files.
- **Vault export and entry listing**: symlinks and any path whose resolved location escapes the password store root are skipped during vault export and entry enumeration. An attacker who plants a directory symlink inside the store (e.g. via a compromised git remote) cannot cause arbitrary files to be included in a vault backup or surfaced as store entries.
- **Vault import hardening**: tar extraction rejects symlinks, hardlinks, absolute paths, null bytes, and any member whose resolved path escapes the extraction root (checked via `Path.is_relative_to()`, not string prefix matching). Extraction uses `filter='data'` on Python 3.12+ to strip setuid bits and device nodes from extracted members.
- **File permissions**: config files, history files, vault exports, and pre-delete backups are all created with `0600` permissions (owner read/write only).
- **Vault unlock rate limiting**: vault import allows a maximum of 3 passphrase attempts with exponential backoff (1s, 3s) to slow brute-force attacks against vault files.
- **Input length limits**: entry fields (username, email, URL, notes) are capped at 64KB to prevent memory exhaustion from oversized input.
- **OTP validation**: TOTP secrets are validated before storage — base32 decode is verified, minimum length enforced, and `otpauth://` URIs must contain a `secret=` parameter.
- **Concurrent access**: the interactive shell uses `fcntl.flock()` to prevent concurrent instances from corrupting state.

### What GPG / pass handles

- **Encryption at rest**: every password entry is encrypted with your GPG key. Passclip never sees or stores plaintext passwords — it calls `pass` to decrypt on demand.
- **Key management**: GPG key generation, trust, expiry, and revocation are all managed through GPG directly.
- **Git integration**: `pass` has built-in git support. Passclip's `sync` command just calls `git pull` and `git push` inside the store directory.

### What's outside our control

- **GPG agent security**: if your GPG agent is configured to cache passphrases, decrypted material stays in agent memory for the cache duration. This is a GPG setting, not a Passclip setting.
- **System clipboard**: once a password is on the clipboard, any application on your system can read it until it's cleared. The auto-clear timer helps, but there's a window of exposure.
- **Terminal scrollback**: if you display a password in the terminal (`passclip get`), it may be visible in your terminal's scrollback buffer. Consider using `--clip` instead.
- **Memory**: Python doesn't provide guaranteed memory zeroing. Decrypted passwords and vault passphrases remain in process heap memory until the garbage collector frees the objects and the OS reuses those pages — they are not overwritten with zeros. This means secrets can be recovered from process memory dumps, core dumps, or swap/hibernation files by an attacker with local access. This is a known limitation of all high-level garbage-collected languages. The same applies to GPG agent and most password managers not written in C/Rust with explicit `mlock()` + secure zeroing.

---

## Known limitations

These aren't bugs — they're trade-offs we've made or inherent limitations of the tools we build on.

### Clipboard timing window

Between copying a password to the clipboard and the auto-clear timer firing, any application can read the clipboard. This is unavoidable on all major operating systems. To minimize exposure:
- Keep the `clip_timeout` low (default is 45 seconds)
- Use `--field` to extract specific values directly if you're scripting

### Shell history

The interactive shell stores command history at `~/.config/passclip/history`. This file contains command names and entry paths (like `get email/gmail`) but **not** passwords. It's created with `0600` permissions. If this concerns you, you can disable history by removing the file and making it unwritable:

```bash
rm ~/.config/passclip/history
touch ~/.config/passclip/history
chmod 000 ~/.config/passclip/history
```

### The `run` command exposes secrets to child processes

When you run `passclip run entry -- some-command`, the entry's fields are passed as environment variables to the child process. The child process (and any processes it spawns) can read those variables. This is by design — it's how the feature works. The variables are not persisted to disk or shell history.

**Note:** On Linux, other processes running as the same user can read environment variables via `/proc/<pid>/environ`. If this is a concern in your threat model, prefer piping secrets through stdin instead of using `run`.

### Pre-delete backups are plaintext

When you delete an entry, Passclip saves a plaintext backup to `~/.config/passclip/backups/` (with `0600` permissions). These exist as a safety net so you can recover accidentally deleted entries. If you want to clean them up:

```bash
rm -rf ~/.config/passclip/backups/
```

### Vault passphrase is not recoverable

Vault files exported with `export-vault` are encrypted with a passphrase you choose. There is no recovery mechanism if you forget it. Your GPG-encrypted password store is unaffected — the vault is just an extra backup format.

---

## Hardening checklist

If you're deploying Passclip in a security-sensitive environment, here are some things to consider:

- [ ] Set `clip_timeout` to the shortest duration you can tolerate
- [ ] Use `--clip` or `--field` instead of displaying passwords in the terminal
- [ ] Set `GPG_TTY=$(tty)` in your shell profile for reliable pinentry
- [ ] Store vault backups on an encrypted drive or in a secure location
- [ ] Periodically run `passclip health` to catch weak or reused passwords
- [ ] Clean out `~/.config/passclip/backups/` regularly
- [ ] If using git sync, make sure the remote repository is private
- [ ] Review GPG key expiry dates and renew before they lapse
- [ ] Use a strong GPG passphrase — it's the last line of defense

---

## Dependencies

Passclip's security depends on these external tools and libraries:

| Dependency | Role | Version guidance |
|---|---|---|
| `gpg` (GnuPG) | Encryption of all password entries | Use 2.2+ (avoid 1.x) |
| `pass` | Password store management | 1.7+ |
| `cryptography` (Python) | AES-256-GCM for vault export/import | 41.0+ |
| `rich` (Python) | Terminal output only — no security role | Any recent version |
| `pyperclip` (Python) | Clipboard access | Any recent version |
| `pyotp` (Python) | TOTP code generation | Any recent version |

Keep these updated. In particular, `gnupg` and `cryptography` should be kept current for security patches.
