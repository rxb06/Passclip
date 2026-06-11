# Changelog

All notable changes to Passclip are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/) conventions.

---

## [1.4.0] — 2026-06-11

The remediation release: every finding from the June 2026 security review and code-quality review, fixed across nine phases. **Support for all versions before 1.4 ends with this release** — upgrade unconditionally.

### Fixed — correctness

- **Vault restore with a custom `pass_dir`** extracted into a parallel `~/.password-store`, left the real store untouched, and reported success with "0 passwords restored". The archive's top folder is now remapped to the configured store name before extraction.
- **CSV import crashed mid-file** (`AttributeError`) on rows with fewer cells than the header — common after a file is re-saved by Excel.
- **`import --dry-run` never flagged conflicts** — the existing-entries set was only computed when *not* in dry-run, so the `(exists)` overwrite preview was dead code.
- **Wrong-magic vault error said `PCV1` is expected** (the format is `PCV2`) — actively misleading in the exact migration scenario it appears in; also fixed in `docs/user-guide.md`.
- **`otp` hint printed a literal `{entry}`** (missing f-string prefix).
- **Passwords with leading/trailing whitespace were corrupted on read** — `pass show` output was blanket-stripped; now only the trailing newline is removed.

### Fixed — security (High severity)

A follow-up Critical/High audit (the deeper import/containment pass the original review left open) found two High-severity issues in the vault import and lock-file paths; both are fixed here, with zero Critical found:

- **Malicious vault import confined to the store** — tar extraction was bounded to the store's *parent* directory, so a crafted vault member named e.g. `.bashrc` could be written anywhere under the home directory (arbitrary file write leading to code execution at next shell, or GPG/`.gpg-id` subversion). Containment is now checked against the password store itself; out-of-store members are refused.
- **Shell lock no longer follows a planted symlink** — the lock file lived inside the git-synced store and was opened without `O_NOFOLLOW`, so a compromised remote could plant a `.passclip.lock` symlink and have the next shell launch truncate an arbitrary user-writable file (`~/.bashrc`, `~/.ssh/authorized_keys`). The lock now lives in the `0700` config directory (unreachable by a remote) and is opened with `O_NOFOLLOW`.

### Fixed — security (defense in depth)

- **TOTP seeds and entry metadata no longer persist to readline history** — OTP prompts are hidden (getpass bypasses readline) and the insert flow's metadata prompts are excluded from history.
- **Non-ASCII secrets are actually auto-cleared** — the clipboard comparison ran on `str` and raised a swallowed `TypeError`, leaving e.g. `pässwörd` on the clipboard forever; comparisons are now on UTF-8 bytes.
- **The clipboard clear child no longer holds the secret in its environment** — it arrives over a stdin pipe, invisible to `ps` and `/proc/<pid>/environ`.
- **The clearer now matches how the copy actually happened** — a pyperclip that imports but has no backend no longer results in a clear that silently never fires; the native fallback verifies clipboard content before wiping (and fails safe when it cannot read).
- **`generate --clip` no longer prints the new password** to the terminal.
- **Vault tar extraction** rejects FIFOs/devices, clamps member modes to `0o755` (no setuid/world-write), and applies `filter='data'` whenever the runtime supports it (including the 3.10.12+/3.11.4+ backports).
- **Vault passphrases require ≥12 characters**, with confirmation on weak ones; the pointless backoff sleeps were removed (PBKDF2-600k is the real rate limit).
- **Rich markup injection closed**: untrusted strings (CSV names, tar member names, git/`pass` output) and stored values render literally — a password like `p[/]w` used to crash `get` with `MarkupError`. `get --field` writes raw bytes for scripting.
- **Planted flag-like entry names** (`-x.gpg`) are excluded from enumeration and typed flag-like names are rejected before reaching `pass` argv.
- **Config/backup/history directories are `0700`**; the lock file can no longer be deleted by a session that doesn't hold the lock; the documented chmod-000 history-disable recipe no longer crashes the shell.

### Changed — behavior

- **Ctrl-C behaves**: cancels the current shell command and returns to the prompt; exits gracefully at the prompt; exit code 130 on the CLI. (The old module-level handler made every `except KeyboardInterrupt` unreachable.)
- **`insert` asks before overwriting** an existing entry instead of silently forcing.
- **Entry names with spaces work in the shell** — all shell commands parse with shlex, so `get "web/my site"` and `run e -- echo "a b"` behave; unbalanced quotes fall back instead of crashing.
- **`run` returns the child's exit code** (127 when not found) instead of exiting the whole shell; injected env-var names are sanitized to `[A-Z0-9_]`.
- **`otp add` does a targeted line edit** — it no longer rewrites the entire entry file (which lowercased keys and reordered lines).
- **`restore` accepts names as `ls` shows them** (`archive/...`); `archive` refuses to double-archive; the shell accepts `otp --add`; flag-first quick copy (`passclip -u gmail`) works; unknown flags error instead of silently copying the password.
- **Removed** the `default_mode` config key — it was validated and documented but never read by any code path.

### Changed — internals & supply chain

- Nine commands that existed twice (shell + CLI; delete three times) now share one implementation each; the CLI command list is derived from the parser, so new subcommands can't silently fall through to fuzzy search.
- Version is single-sourced from `passclip.__version__`; `requirements.txt` (an unreferenced, drifted copy of the dependency list) is gone.
- Build backend pinned and hashed; all builds run `--no-isolation`; the artifact audit content-hashes `passclip.py` in both wheel and sdist against the repo and fails on empty `dist/`.
- CI: least-privilege permissions, `persist-credentials: false`, all actions SHA-pinned (including the publish action), Node-24-ready action versions, pip-audit installed from the hashed lockfile, Dependabot enabled, `cryptography` floor raised to ≥46.0.7, runs on `develop` too.
- The PyPI `pypi` environment now requires reviewer approval before publishing.
- Tooling: ruff rules expanded (`UP`, `B`, `SIM`), modern typing syntax throughout, one-time `ruff format` with format checking in CI, ruff pre-commit hooks, lint scope unified between Makefile and CI.
- Importing the module is side-effect-free: user config loads in `main()`, not at import.

### Tests

- Suite grew from 79 to 179 tests: real vault export→import roundtrips (including crafted malicious vaults), CSV import end-to-end, smart-copy routing, `main()` dispatch, clipboard clear-script execution against fakes, shell parsing, behavior pins for every deduplicated command, and markup-injection regressions.

---

## [1.2.1] — 2026-04-09

### Fixed

- **Symlink containment in vault export** — `cmd_export_vault()` now skips symlinks and any path whose resolved location escapes the password store root. Previously `rglob()` followed directory symlinks, which could include arbitrary files in an encrypted vault if a symlink was planted in the store (e.g. via a compromised git remote).
- **Symlink containment in entry listing** — `get_all_entries()` applies the same symlink + containment check. Symlinked entries or entries under symlinked directories no longer appear in listings, tab completion, health scans, or fuzzy search.
- **tar extraction filter** — `import-vault` now passes `filter='data'` to `tar.extractall()` on Python 3.12+ (version-guarded), stripping setuid bits and device nodes from extracted members. Manual member validation (symlink rejection, path traversal check) was already in place; this adds a defense-in-depth layer.
- **Atomic backup file write** — `_backup_entry()` now uses `os.open(O_CREAT|O_TRUNC, 0o600)` + `os.fdopen()` instead of `touch(mode=0o600)` + `write_text()`. Eliminates the TOCTOU window between file creation and write, consistent with `save_config()`.
- **SECURITY.md backoff values** — documented delays corrected from `(1s, 2s, 4s)` to `(1s, 3s)` to match the `3 ** (attempt - 1)` formula in code.
- **CVE-2026-39892 (cryptography)** — bumped `cryptography` from 46.0.6 to 46.0.7 in CI lockfile (`requirements-ci.txt`). Runtime dependency in `pyproject.toml` already specifies `>=41.0`; users will receive the fix on their next install.

### Changed

- **CODEOWNERS expanded** — `passclip.py`, `tests/`, `SECURITY.md`, and `.pre-commit-config.yaml` now require review, closing gaps that left the main module and test suite unprotected.
- **credactor hash-locked in CI** — `pip install credactor` replaced with `--require-hashes -r requirements-ci.txt`; credactor added to `requirements-ci.in` with SHA-256 hash. `pip-audit` version-pinned to `2.10.0`.
- **SECURITY.md** — documents symlink containment for vault export and entry listing.

### Tests

- 3 new tests for symlink exclusion in `get_all_entries()`: symlinked file excluded, symlinked directory excluded, real entries unaffected (79 total, up from 76).

---

## [1.2.0] — 2026-03-27

### Fixed

- **Vault import path traversal** — replaced `str.startswith()` containment check with `Path.is_relative_to()`, which is not fooled by sibling directories sharing a string prefix (e.g. `.password-store2/`).
- **Vault import symlink/hardlink traversal** — tar members with symlinks or hardlinks are now rejected outright. Previously they could redirect file writes outside the extraction root.
- **Vault import silent skip** — absolute paths and null bytes in tar members now abort the entire import with an error instead of being silently skipped.
- **Clipboard timing side-channel** — replaced `pyperclip.paste() == t` with `hmac.compare_digest()` for constant-time comparison in the clipboard clear helper.
- **Vault passphrase confirm timing** — replaced `!=` with `hmac.compare_digest()` for constant-time comparison.
- **OTP save failure silent** — first code generation failure after `cmd_otp_add()` now logs the error instead of silently catching it.
- **OTP display for 8-digit codes** — split at midpoint instead of hardcoded `[:3]`/`[3:]`.
- **Shell lock file race condition** — replaced non-atomic `write_text(pid)` with `fcntl.flock()`.
- **Bare exception swallowing** — narrowed 6 `except Exception: pass` blocks to specific types (`FileNotFoundError`, `OSError`, `ValueError`, etc.).

### Changed

- **Vault format bumped PCV1 → PCV2** — vault encryption now authenticates `VAULT_MAGIC + salt + nonce` as AAD. Tampering with the vault header triggers `InvalidTag` instead of a misleading "wrong passphrase" error. **Breaking:** vaults exported before this version must be re-exported.
- **Native clipboard clear no longer uses bash** — the fallback clear path (`pbcopy`/`xclip`/`wl-copy`) now uses a Python one-liner subprocess instead of `bash -c` with format strings.
- **Magic numbers replaced with named constants** — `PBKDF2_ITERATIONS` (600,000), `MAX_ENTRY_NAME_LEN` (200), `MAX_PATH_DEPTH` (10), `MAX_FIELD_LENGTH` (65,536).
- **`_insert_entry()` helper** — consolidated 3 identical `Popen(["pass", "insert", "-m", "-f", ...])` blocks into a single function.
- All GitHub Actions pinned to commit SHAs (checkout, setup-python, codeql-action).
- CI dependencies installed via `--require-hashes` from a locked `requirements-ci.txt`.
- Credactor credential scan now uploads SARIF to GitHub Security tab.
- Credactor pre-commit hook bumped to v2.2.2.
- README restructured: leads with secret injection differentiator, cross-tool comparison table (vs pass, .env), inline security properties, "Passclip is not" positioning block, Windows not supported documented.
- SECURITY.md expanded: documents constant-time clipboard comparison, vault AAD, tar extraction hardening, and Python memory zeroing limitation in detail.
- AI development disclosure moved from README to CONTRIBUTING.md.

### Added

- **Vault unlock rate limiting** — 3 attempts with exponential backoff (1s, 3s, 9s), then abort.
- **Entry field length limits** — fields capped at 64KB to prevent OOM from pasted data.
- **Stricter OTP validation** — base32 decode check, minimum 16 characters, `otpauth://` URI must contain `secret=` parameter.
- **Unknown config key warnings** — typos in `config.json` now produce a visible warning instead of being silently ignored.
- **Salt length assertion** — `_derive_vault_key()` asserts salt is exactly 32 bytes.
- **`pip-audit` CVE scanning** in CI pipeline.
- `scripts/audit_wheel.py` — verifies wheel contents match git-tracked source before publish.
- `build-audit` CI job — builds wheel and runs audit on every PR.
- `requirements-ci.in` / `requirements-ci.txt` — hash-locked CI dependency lockfile.
- `.github/CODEOWNERS` — protects workflows, scripts, `pyproject.toml`, and requirements.
- Sigstore attestations enabled in publish workflow.
- 20+ new tests: vault round-trip with AAD, salt length rejection, unknown config keys, CSV edge cases (missing fields, special characters, empty folder, duplicates), `_sanitize_entry_path` (leading dot/dash, double-dot, shell metacharacters, null byte, long names).

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

## [1.1.1] — 2026-03-21

Version bump released the same day as 1.1.2; its changes (the credactor false-positive fix, the Python 3.8/3.9 drop, README badges) are documented under [1.1.2], which superseded it within hours.

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
