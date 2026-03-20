# Disclaimer

## This is not an official password manager

PassCLI is a personal project. It is not developed, maintained, or endorsed by any company, security organization, or the original authors of GNU `pass`. It is not audited by a third-party security firm. Use it at your own risk.

## No warranty

This software is provided "as is", without warranty of any kind, express or implied. This includes, but is not limited to, warranties of merchantability, fitness for a particular purpose, and noninfringement. The full license terms are in the [LICENSE](LICENSE) file (GPLv3).

In plain English: if something goes wrong — data loss, a security breach, a corrupted vault, a password you can't recover — the author is not liable. You are responsible for your own data.

## Your passwords, your responsibility

PassCLI is a wrapper around GNU `pass` and GPG. It does not implement its own cryptography for the password store. The security of your passwords depends on:

- **Your GPG key** — if your private key is compromised or your passphrase is weak, your passwords are exposed. PassCLI can't protect against that.
- **Your system** — if your machine has malware, a keylogger, or an untrusted user with access, no password manager can save you.
- **Your backups** — if you lose your GPG key and don't have a vault backup, your passwords are gone. There is no "forgot my password" recovery.
- **Your choices** — if you store passwords in plaintext notes, email yourself vault files with weak passphrases, or reuse the same password everywhere, the tool can only do so much.

## Vault encryption

The `export-vault` / `import-vault` feature uses AES-256-GCM with PBKDF2-SHA256 (600,000 iterations). This is strong encryption, but it is only as strong as the passphrase you choose. A short or guessable passphrase defeats the purpose. There is no recovery mechanism — if you forget the vault passphrase, that vault is gone.

## Clipboard exposure

When you copy a password to the clipboard, it is briefly accessible to every application running on your system. PassCLI auto-clears the clipboard after a timeout, but there is a window where other programs could read it. This is a fundamental limitation of how clipboards work on every major operating system — it is not a bug in PassCLI.

## Not a substitute for good security practices

PassCLI makes it easier to use strong, unique passwords. But a tool is only part of the picture. You should also:

- Use a strong, unique GPG passphrase
- Keep your system and dependencies updated
- Enable full-disk encryption on your machine
- Be cautious about where you store vault backups
- Regularly audit your passwords with `passcli health`
- Understand what GPG does and doesn't protect against

## Third-party dependencies

PassCLI relies on GPG, `pass`, and several Python libraries (`rich`, `cryptography`, `pyperclip`, `pyotp`). Vulnerabilities in any of these could affect PassCLI. Keep them updated.

## Use your judgment

This project is built with care and with security in mind. But no software is perfect, and no developer can anticipate every threat model or environment. If you're protecting secrets that could cause serious harm if exposed (financial, medical, legal, infrastructure), consider whether a personal open-source project meets your risk tolerance — or whether you need a commercially supported, audited solution.

---

*By using PassCLI, you acknowledge that you have read and understood this disclaimer.*
