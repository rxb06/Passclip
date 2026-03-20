# Changelog

All notable changes to PassCLI are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/) conventions.

---

## [1.0.0] — 2026-03-20

The production-ready release. Everything has been hardened, documented, and tested for real-world use.

### Added

- **`--version` flag** — `passcli --version` now prints the version.
- **Entry name validation** — blocks path traversal (`..`), shell metacharacters, leading `-` or `/`, and excessively deep paths. Applied to `insert`, `generate`, `import`, and all shell commands.
- **`--dry-run` for import** — preview what a CSV import would create without actually writing anything.
- **Pre-delete backups** — entries are saved to `~/.config/passcli/backups/` (with `0600` permissions) before deletion. Safety net for accidental deletes.
- **Concurrent access warning** — the interactive shell creates a PID-based lock file (`.passcli.lock`) and warns if another instance is already running.
- **Atomic vault exports** — vault files are written to a temp file first, then renamed into place. No partial files if the disk fills up or the process is killed.
- **Vault import error clarity** — wrong passphrase and corrupted file are now reported as distinct errors instead of a generic "decryption failed".
- **`pass_dir` config validation** — warns if the directory doesn't exist before saving it.
- **Signal handling** — Ctrl-C exits cleanly with a message instead of a Python traceback.
- **Health scan progress** — shows which entry is currently being scanned.
- **Shell completions** — bash, zsh, and fish completion scripts in `completions/`.
- **`_error()` helper** — consistent error formatting across the codebase.
- **Documentation** — `docs/QUICK_START.md`, `docs/SETUP.md`, `docs/USE_CASES.md`, `SECURITY.md`, `DISCLAIMER.md`, `CONTRIBUTING.md`.

### Changed

- **`cmd_import()` rewritten** — extracted `_parse_csv_row()` and `_sanitize_entry_path()` for clarity. Better error handling for malformed CSV files. Warns on duplicate entry names before importing.
- **`cmd_sync()` aborts on pull failure** — no longer attempts to push if the pull failed.
- **`get_all_entries()` warns on missing store** — instead of silently returning an empty list, tells you what to do.

### Fixed

- Clipboard auto-clear now works properly (checks content before clearing to avoid wiping unrelated data).
- Vault import no longer gives a generic error for wrong passphrases.

---

## [0.9.0] — Pre-release

### Added

- Encrypted vault export and import (`export-vault`, `import-vault`) using AES-256-GCM with PBKDF2-SHA256 (600,000 iterations).
- Better error messages in `get_entry_raw()` — distinguishes "not found", "can't decrypt", and "GPG key error".
- File permission hardening — history file and config created with `0600`.
- Input sanitization — strips `..`, leading dots and dashes from entry names.

### Changed

- Major CLI overhaul — structured argument parser, subcommands, interactive shell with tab completion.

---

## [0.1.0] — Initial release

### Added

- Basic `pass` wrapper with `get`, `insert`, `generate`, `edit`, `delete`, `ls`, `find`.
- Interactive shell with command history.
- CSV import (Bitwarden, LastPass, 1Password).
- TOTP code generation.
- Password health report.
- Git sync (`sync`, `gitlog`).
- `run` command for injecting secrets as environment variables.
- `archive` / `restore` for soft-deleting entries.
- `browse` with fzf integration.
- Setup wizard.
- Configuration system (`~/.config/passcli/config.json`).
