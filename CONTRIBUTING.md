# Contributing to Passclip

Thanks for your interest in contributing. Here's how to get involved.

---

## Ways to contribute

- **Bug reports** — found something broken? Open an issue with steps to reproduce, your OS, Python version, and `passclip --version` output.
- **Feature requests** — have an idea? Open an issue and describe the use case. What problem does it solve? How would you use it?
- **Code** — fixes, improvements, new features. See below for the process.
- **Documentation** — typo fixes, better explanations, new examples. Always welcome.
- **Testing** — try it on your setup and let us know what works and what doesn't.

---

## Before you start coding

1. **Check existing issues** — someone might already be working on the same thing.
2. **Open an issue first** for anything non-trivial. A quick conversation up front saves everyone time. Describe what you want to change and why.
3. **Keep changes focused.** One fix or feature per pull request. It's easier to review and less likely to introduce regressions.

---

## Setting up for development

```bash
# Clone the repo
git clone <repo-url>
cd Passclip

# Install in editable mode with all dependencies
pip install -e ".[all,dev]"

# Make sure pass and GPG are installed (see docs/setup.md)

# Run it
python passclip.py --version
```

There's no build step. Passclip is a single Python file (`passclip.py`) with standard library + a few pip packages.

---

## Making changes

1. Create a branch from `main`:
   ```bash
   git checkout -b fix/clipboard-timeout
   ```

2. Make your changes. Keep the style consistent with the existing code:
   - Python 3.10+ compatible
   - Use `rich` for terminal output (no raw `print` for user-facing messages)
   - Subprocess calls use list arguments (never `shell=True`)
   - Entry names go through `validate_entry_name()` before any write

3. Test your changes manually. Run `pytest` to check existing tests, and verify:
   - The happy path works
   - Edge cases are handled (empty input, missing entries, bad permissions)
   - Nothing breaks in the interactive shell
   - `--help` still works for your command

4. Commit with a clear message:
   ```bash
   git commit -m "Fix clipboard not clearing when timeout is set to 0"
   ```

5. Open a pull request against `main`. Describe what you changed and why.

---

## Code style

- Keep it simple. Don't add abstractions for things that happen once.
- Functions should do one thing. If a function is getting long, break it up.
- Error messages should be helpful. Tell the user what went wrong and what to do about it.
- No `shell=True` in subprocess calls. Ever.
- Validate user input at the boundaries (entry names, config values, file paths).
- Use `_error()` for error output, `console.print()` for everything else.

---

## What makes a good pull request

- Solves a real problem or adds a clearly useful feature
- Doesn't break existing functionality
- Keeps the diff small and focused
- Has a clear commit message
- Updates docs if the user-facing behavior changed

---

## What we probably won't merge

- Massive refactors without prior discussion
- Features that add complexity without clear value
- Changes that break compatibility with plain `pass`
- Anything that introduces `shell=True` or bypasses input validation
- Dependencies that aren't strictly necessary

---

## License

By contributing, you agree that your contributions will be licensed under the same [GPLv3 license](LICENSE) that covers the project.
