# Integration

How to integrate Passclip with pre-commit hooks, CI pipelines, and shell environments.

---

## Pre-commit: credential scanning

Passclip stores passwords encrypted via GPG, so there's nothing to accidentally commit from the tool itself. But your broader codebase might have hardcoded secrets. [Credactor](https://github.com/rxb06/Credactor) catches those before they reach your repo.

### Pre-commit framework

If you use the [pre-commit](https://pre-commit.com/) framework, add this to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/rxb06/Credactor
    rev: v2.0.1
    hooks:
      - id: credactor
```

Install the hooks:

```bash
pip install pre-commit
pre-commit install
```

Every `git commit` now scans staged files for hardcoded credentials. If anything is found, the commit is blocked with a clear report.

### Standalone git hook

If you don't use the pre-commit framework, drop a script into `.git/hooks/`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if ! command -v credactor &>/dev/null; then
    echo "credactor not installed — skipping credential scan"
    exit 0
fi

credactor --staged
```

Save as `.git/hooks/pre-commit` and make it executable:

```bash
chmod +x .git/hooks/pre-commit
```

---

## CI: credential scanning

Add a credential scan step to your GitHub Actions pipeline:

```yaml
# .github/workflows/ci.yml
credential-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.13"
    - name: Install credactor
      run: pip install credactor
    - name: Scan for credentials
      run: credactor --ci .
```

This fails the build if any hardcoded credentials are found. Use `--format sarif` and upload to GitHub Code Scanning for inline annotations on PRs.

---

## Shell completions

Tab completion makes Passclip much faster when you have dozens of entries.

### Bash

Add to `~/.bashrc`:

```bash
source /path/to/passclip/completions/passclip.bash
```

### Zsh

```bash
mkdir -p ~/.zfunc
cp completions/passclip.zsh ~/.zfunc/_passclip
```

Add to `~/.zshrc`:

```bash
fpath=(~/.zfunc $fpath)
autoload -Uz compinit && compinit
```

### Fish

```bash
cp completions/passclip.fish ~/.config/fish/completions/
```

All three completion scripts cover the full command set including `gpg_gen`, `gpg_list`, `export-vault`, `import-vault`, and `shell`. Entry names are completed dynamically from your password store.

---

## Shell aliases

Useful shortcuts for your shell profile:

```bash
# Quick access
alias pc='passclip'
alias pcb='passclip browse'

# Dev workflows
alias db-staging='passclip run db/staging -- python manage.py dbshell'
alias db-prod='passclip run db/prod -- python manage.py dbshell'
```

---

## PyPI installation

Passclip is available on PyPI:

```bash
# Core (required)
pip install passclip

# With clipboard support
pip install passclip[clipboard]

# With TOTP/OTP support
pip install passclip[otp]

# Everything
pip install passclip[all]
```

### System requirements

Passclip uses `pass` and GPG under the hood — those need to be installed separately:

```bash
# macOS
brew install gnupg pass

# Ubuntu / Debian
sudo apt install gnupg2 pass

# Arch
sudo pacman -S gnupg pass
```

Optional but recommended:

```bash
# Fuzzy finder for browse command
brew install fzf        # macOS
sudo apt install fzf    # Linux
```

---

## Making it a global command (without pip)

If you cloned the repo instead of pip-installing:

```bash
chmod +x passclip.py
mkdir -p ~/.local/bin
ln -sf "$(pwd)/passclip.py" ~/.local/bin/passclip
```

Make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```
