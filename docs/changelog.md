# Changelog

All notable changes to Passclip are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/) conventions.

---

## [1.1.3] — 2026-03-22

### Fixed

- `clip_timeout` is now cast to `int` before shell string interpolation in the native clipboard fallback path, preventing potential issues if the config value is not an integer.
- `load_config()` now logs a warning on corrupt or unparseable config files instead of silently falling back to defaults.

### Changed

- CI test matrix updated to 3.10, 3.11, 3.12, 3.13.
- Optional dependencies pinned to minimum versions: `pyperclip>=1.8`, `pyotp>=2.8`.

### Added

- **Config validation** — `clip_timeout` (must be >= 1), `default_password_length` (must be >= 8), and `default_mode` (must be `shell` or `ls`) are validated on load. Invalid values are silently reset to defaults.
- **Expanded test suite** — `tests/test_core.py` with 46 new tests covering config loading, entry parsing, password strength, password generation, CSV row parsing, entry path sanitization, and vault encryption roundtrip.
- **Docstrings** — added to 15 public functions (`load_config`, `save_config`, `check_dependencies`, `parse_entry`, `format_entry`, `strength_bar`, `cmd_config_show`, `cmd_config_set`, `build_parser`, `main`, and shell methods).
- **"Making it a global command" section** in `docs/setup.md` — covers PATH configuration for pip installs, platform-specific fixes, and `pipx` as an alternative.
- **Environment inheritance note** in `docs/user-guide.md` — documents that `run` passes the full parent environment to the child process.
- Fish completions for `gpg_gen`, `gpg_list`, and `shell` commands.
- "Running tests" section in `CONTRIBUTING.md`.

---

## [1.1.2] — 2026-03-21

### Fixed

- False positive in credential scan on `generate_password()` call (suppressed with inline ignore).
- Entry validation on CLI-mode `mv`, `cp`, and `restore` commands now correctly unpacks the validation result — previously the tuple return was always truthy, so invalid names could slip through.

### Changed

- Dropped Python 3.8 and 3.9 support. Minimum is now Python 3.10.
- CI test matrix updated to 3.10, 3.12, 3.13.
- Ruff target version set to `py310`.
- All lint warnings resolved (line length, unused imports, import sorting).
- Documentation updated to reflect Python 3.10+ requirement throughout.
- Narrative updated across all docs — honest about being built on `pass`, clearer about what Passclip adds on top.

### Added

- PyPI, CI, license, and Python version badges in README.
- `uv.lock` added to `.gitignore`.

---

## [1.1.0] — 2026-03-20

UX overhaul — fewer keystrokes for the things you do every day.

### Added

- **Smart fuzzy copy** — `passclip gmail` copies the password. No subcommand, no full path, no flags. Fuzzy matches against all entries. Add `-u` for username, `-o` for OTP, `-s` to show.
- **Shell shortcuts** — `c gmail`, `u gmail`, `o gmail` in the interactive shell. Single-letter commands that fuzzy-search and copy.
- **Browse defaults to copy** — pressing Enter on a selected entry copies the password instead of showing the details panel.

### Changed

- Action menu now defaults to **copy** (`c`) instead of show (`s`), with the default highlighted.
- Help text, wizard, and documentation updated to lead with quick-copy examples.
- Rebranded from PassCLI to **Passclip**.
- File renamed from `pass_cli.py` to `passclip.py`.

---

## [1.0.0] — 2026-03-20

The production-ready release. Everything has been hardened, documented, and tested for real-world use.

### Added

- **`otp --add` command** — guided flow to add or update OTP secrets on existing entries. Auto-detects `otpauth://` URIs and base32 secrets from the clipboard. Validates before saving and shows the first code as confirmation.
- **OTP prompt in `insert`** — optional OTP secret field during entry creation (when `pyotp` is installed).
- **Clipboard reading** — `_read_clipboard()` helper for reading clipboard content (used by `otp --add`).
- **`--version` flag** — `passclip --version` now prints the version.
- **Entry name validation** — blocks path traversal (`..`), shell metacharacters, leading `-` or `/`, and excessively deep paths. Applied to `insert`, `generate`, `import`, and all shell commands.
- **`--dry-run` for import** — preview what a CSV import would create without actually writing anything.
- **Pre-delete backups** — entries are saved to `~/.config/passclip/backups/` (with `0600` permissions) before deletion. Safety net for accidental deletes.
- **Concurrent access warning** — the interactive shell creates a PID-based lock file (`.passclip.lock`) and warns if another instance is already running.
- **Atomic vault exports** — vault files are written to a temp file first, then renamed into place. No partial files if the disk fills up or the process is killed.
- **Vault import error clarity** — wrong passphrase and corrupted file are now reported as distinct errors instead of a generic "decryption failed".
- **`pass_dir` config validation** — warns if the directory doesn't exist before saving it.
- **Signal handling** — Ctrl-C exits cleanly with a message instead of a Python traceback.
- **Health scan progress** — shows which entry is currently being scanned.
- **Shell completions** — bash, zsh, and fish completion scripts in `completions/`.
- **`_error()` helper** — consistent error formatting across the codebase.
- **Documentation** — `docs/setup.md`, `docs/user-guide.md`, `docs/examples.md`, `docs/integration.md`, `SECURITY.md`, `DISCLAIMER.md`, `CONTRIBUTING.md`.

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

- CLI interface for `pass` with `get`, `insert`, `generate`, `edit`, `delete`, `ls`, `find`.
- Interactive shell with command history.
- CSV import (Bitwarden, LastPass, 1Password).
- TOTP code generation.
- Password health report.
- Git sync (`sync`, `gitlog`).
- `run` command for injecting secrets as environment variables.
- `archive` / `restore` for soft-deleting entries.
- `browse` with fzf integration.
- Setup wizard.
- Configuration system (`~/.config/passclip/config.json`).
