# Setup Guide

Everything you need to get Passclip installed, configured, and feeling like home. If you're in a hurry, the [quick start](#quick-start) gets you going in under 5 minutes. The rest of this guide covers the details.

---

## Table of Contents

- [Quick start](#quick-start)
- [System requirements](#system-requirements)
- [GPG key setup](#gpg-key-setup)
- [Initializing the password store](#initializing-the-password-store)
- [Installing Passclip](#installing-passclip)
- [Making it a global command](#making-it-a-global-command)
- [Shell completions](#shell-completions)
- [Configuration](#configuration)
- [Git sync setup](#git-sync-setup)
- [Migrating from another password manager](#migrating-from-another-password-manager)
- [Troubleshooting](#troubleshooting)

---

## Quick start

Already have `pass` and GPG? Here's the fast track:

```bash
# Install from PyPI
pip install passclip[all]

# Run the setup wizard (handles GPG key + store init)
passclip wizard

# Start using it
passclip insert email/gmail       # add your first entry
passclip gmail                    # copy password to clipboard (fuzzy)
passclip gmail -u                 # copy username
passclip gmail -o                 # copy OTP
passclip                          # interactive shell
```

Don't have `pass` or GPG yet? Keep reading — the next sections walk you through everything.

---

## System requirements

### macOS

```bash
brew install gnupg pass
```

Optionally install `fzf` for the fuzzy entry browser:

```bash
brew install fzf
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install gnupg2 pass
```

Optional:

```bash
sudo apt install fzf xclip    # fzf for browse, xclip for clipboard
```

### Arch Linux

```bash
sudo pacman -S gnupg pass
```

Optional:

```bash
sudo pacman -S fzf xclip
```

### Python dependencies

Passclip needs Python 3.10 or later. Install via pip:

```bash
pip install passclip[all]
```

Or install individual extras:

```bash
pip install passclip              # core (rich + cryptography)
pip install passclip[clipboard]   # + pyperclip
pip install passclip[otp]         # + pyotp
```

| Package | Required? | What it does |
|---|---|---|
| `rich` | Yes | Terminal formatting, tables, progress bars |
| `cryptography` | Yes | AES-256-GCM vault export and import |
| `pyperclip` | Recommended | Clipboard copy with auto-clear |
| `pyotp` | Optional | TOTP / OTP code generation |

If you don't install `pyperclip`, everything still works — you just won't be able to copy to clipboard. If you don't install `pyotp`, the `otp` command (both generating codes and adding secrets) won't be available, and the OTP prompt during `insert` will be skipped.

---

## GPG key setup

If you already have a GPG key, skip this section. To check:

```bash
gpg --list-secret-keys
```

If that shows a key, you're good. If not, generate one:

```bash
# Through Passclip (easiest)
passclip gpg_gen

# Or manually
gpg --full-generate-key
```

When prompted:
- **Key type**: RSA and RSA (default) is fine
- **Key size**: 4096 bits recommended
- **Expiration**: your preference (0 = never expire)
- **Name and email**: use your real info — this is how you'll identify the key

After generating, note the key ID (the long hex string). You'll need it to initialize the password store.

### A note on pinentry

GPG uses a program called `pinentry` to ask for your passphrase. If it's not showing up properly, make sure your terminal knows where it is:

```bash
export GPG_TTY=$(tty)
```

Add that line to your `~/.zshrc` or `~/.bashrc` so it's always set.

---

## Initializing the password store

If this is a fresh setup:

```bash
# Through Passclip (recommended — handles everything)
passclip wizard

# Or manually
pass init YOUR_GPG_KEY_ID
```

The wizard does the same thing but also sets up your Passclip config file and optionally initializes git for syncing.

Your password store lives at `~/.password-store/` by default. Every entry is a GPG-encrypted file inside that directory.

---

## Installing Passclip

The recommended way is via pip:

```bash
pip install passclip[all]
```

This installs the `passclip` command globally. Verify:

```bash
passclip --version
```

### Install from source

If you prefer to install from the repo directly:

```bash
git clone https://github.com/rxb06/Passclip.git
cd Passclip
pip install -e ".[all]"
```

---

## Making it a global command

After `pip install passclip[all]`, the `passclip` binary is placed in pip's scripts directory. Whether it's immediately available depends on whether that directory is in your `PATH`.

### Verify it worked

```bash
which passclip
passclip --version
```

If either of those works, you're done.

### If you get "command not found"

Pip puts scripts in different places depending on how it's invoked:

**Linux — user install (`pip install --user`)**

The binary lands in `~/.local/bin`, which many distros don't include in `PATH` by default.

```bash
# Confirm where pip installed it
python3 -m site --user-base
# → /home/you/.local  (binary is at /home/you/.local/bin/passclip)

# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

For zsh: replace `~/.bashrc` with `~/.zshrc`.

**macOS — system Python**

Scripts may land in `~/Library/Python/3.x/bin`. Use `python3 -m site --user-base` to get the exact path for your Python version:

```bash
echo "export PATH=\"$(python3 -m site --user-base)/bin:\$PATH\"" >> ~/.zshrc
source ~/.zshrc
```

Homebrew Python and pyenv both add their bin directories to `PATH` automatically, so this usually isn't an issue if you installed Python via Homebrew.

### Recommended: use pipx

`pipx` installs Python CLI tools into isolated environments and makes them globally available — no PATH configuration needed.

```bash
# Install pipx
brew install pipx                 # macOS
pip install --user pipx           # Linux, then run: pipx ensurepath

# Install Passclip
pipx install "passclip[all]"

# Verify
passclip --version
```

This is the cleanest option if you want Passclip available everywhere without touching your shell config.

### From a source install

`pip install -e ".[all]"` (run from the cloned repo) registers the `passclip` entrypoint the same way as a regular install — the binary goes into pip's scripts directory. The same PATH rules above apply. You don't need to `cd` into the repo or invoke `python passclip.py` directly.

---

## Shell completions

Tab completion makes a huge difference when you have dozens of entries. We ship completion scripts for bash, zsh, and fish.

### Bash

Add to your `~/.bashrc`:

```bash
source /path/to/passclip/completions/passclip.bash
```

### Zsh

Copy the completion file into your fpath:

```bash
mkdir -p ~/.zfunc
cp completions/passclip.zsh ~/.zfunc/_passclip
```

Then make sure your `~/.zshrc` has:

```bash
fpath=(~/.zfunc $fpath)
autoload -Uz compinit && compinit
```

### Fish

```bash
cp completions/passclip.fish ~/.config/fish/completions/
```

After setting up completions, you can tab-complete subcommands, entry names, config keys, and flags.

---

## Configuration

Passclip stores its config at `~/.config/passclip/config.json`. You can view and change settings from the command line:

```bash
# See all current settings
passclip config

# Change a setting
passclip config clip_timeout 60
passclip config default_password_length 24
```

### Available settings

| Key | Default | What it controls |
|---|---|---|
| `clip_timeout` | `45` | Seconds before clipboard is auto-cleared (minimum: 1) |
| `default_password_length` | `20` | Default length for generated passwords (minimum: 8) |
| `default_mode` | `shell` | What happens when you run `passclip` with no args (`shell` or `ls`) |
| `pass_dir` | `~/.password-store` | Path to your password store |

Invalid values are automatically reset to defaults on load. For example, setting `clip_timeout` to `0` or a negative number resets it to `45`. Setting `default_password_length` below `8` resets it to `20`. Setting `default_mode` to anything other than `shell` or `ls` resets it to `shell`.

### Changing the password store location

If your store isn't in the default location:

```bash
passclip config pass_dir /path/to/your/store
```

Or set the environment variable (this is what `pass` itself uses too):

```bash
export PASSWORD_STORE_DIR=/path/to/your/store
```

---

## Git sync setup

`pass` has built-in git support. If you initialized your store with git (the wizard offers this), you can push and pull with:

```bash
passclip sync
```

This does a `git pull --rebase` followed by `git push` inside your password store directory.

### Setting up a remote

If you haven't added a git remote yet:

```bash
cd ~/.password-store
git remote add origin git@github.com:you/your-pass-store.git
git push -u origin main
```

After that, `passclip sync` handles everything.

### Viewing git history

```bash
passclip gitlog       # last 10 commits
passclip gitlog 25    # last 25 commits
```

---

## Migrating from another password manager

Passclip can import CSV exports from Bitwarden, LastPass, and 1Password.

### Step 1: Export from your current manager

- **Bitwarden**: Settings > Export Vault > CSV
- **LastPass**: Account Options > Advanced > Export
- **1Password**: File > Export > CSV

### Step 2: Preview the import

Always preview first to make sure things look right:

```bash
passclip import your_export.csv --dry-run
```

This shows exactly what would be created without actually writing anything.

### Step 3: Import

```bash
passclip import your_export.csv
```

Passclip auto-detects the format from the CSV headers. If auto-detection gets it wrong, you can specify:

```bash
passclip import your_export.csv --format bitwarden
passclip import your_export.csv --format lastpass
passclip import your_export.csv --format 1password
```

### Step 4: Clean up

After verifying everything imported correctly:

1. Delete the CSV file — it contains your passwords in plaintext
2. Run `passclip health` to check for weak or duplicate passwords
3. Run `passclip sync` to push the new entries to your git remote

---

## Troubleshooting

### GPG agent not responding / pinentry hangs

The GPG agent sometimes gets stuck. Kill it and let it restart:

```bash
gpgconf --kill gpg-agent
gpg-agent --daemon
```

If pinentry prompts don't show up in your terminal:

```bash
export GPG_TTY=$(tty)
```

Add that to your shell profile so you don't have to type it every time.

### "Password store not found"

Passclip looks at `~/.password-store` by default. If your store is somewhere else:

```bash
passclip config pass_dir /path/to/your/store
```

Or set the environment variable:

```bash
export PASSWORD_STORE_DIR=/path/to/your/store
```

### "GPG encryption failed" when generating or inserting

The password store is not initialized, or the configured GPG key is no longer available.

```bash
passclip gpg_list    # check available keys
passclip init        # re-initialize with an available key
```

### "Cannot decrypt" or "GPG key error"

Passclip gives you specific messages:
- **"Entry not found"** — the entry doesn't exist. Run `ls` to see what's available.
- **"Cannot decrypt"** — your GPG key is locked or it's the wrong key. Try `gpg --card-status` to check.
- **"GPG key error"** — the encryption key is missing or unusable. Run `gpg_list` to verify.

### Clipboard not working

Passclip uses `pyperclip` for clipboard access, which needs a clipboard tool on your system:

- **macOS**: `pbcopy` is built in, nothing to install
- **Linux (X11)**: install `xclip` or `xsel` — `sudo apt install xclip`
- **Linux (Wayland)**: install `wl-clipboard` — `sudo apt install wl-clipboard`
- **SSH / headless servers**: clipboard isn't available. Use `--field` to print values to stdout instead

### "pass: command not found"

You need to install the `pass` password manager. See [System requirements](#system-requirements) at the top of this page.

### fzf not found (browse command)

The `browse` command works best with `fzf` installed. Without it, you'll get a numbered list with a text filter instead.

```bash
# macOS
brew install fzf

# Ubuntu / Debian
sudo apt install fzf
```

### Tab completion not working in the shell

The interactive shell uses Python's `readline` for completion. On macOS, the system Python may have a readline that doesn't support completion.

```bash
# Ensure you're using Homebrew Python (not system Python)
which python3

# If using pyenv or conda, ensure readline is available
pip install gnureadline   # macOS fallback
```

### Vault import says "wrong passphrase"

Double-check that you're entering the exact passphrase you used when exporting. The vault is encrypted with AES-256-GCM — there's no way to recover it without the correct passphrase. There's also no "forgot passphrase" option.

Your GPG-encrypted store is still intact though — the vault is just a backup format. You haven't lost anything.

### Health scan is slow

The `health` command has to decrypt every single entry through GPG to check password strength. If you have hundreds of entries, this takes a while. The progress bar shows where it's at. There's no way around it — the entries are encrypted and need to be decrypted one by one.

### Import skips entries

Entries are skipped if they have no name or no password. Check your CSV:
- Bitwarden: secure notes export as a different type — only login entries have passwords
- LastPass: "secure notes" and "form fills" have no password field

Run the import and note which entries show a skip marker — you can add them manually with `passclip insert`.
