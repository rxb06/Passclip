"""Regression tests for the secret-exposure fixes (security review 2026-06-09:
M1, M2, M6, L1, L3, L4, L8, L9)."""

import os
import subprocess
import sys
from unittest.mock import patch

import pytest

import passclip
from passclip import (
    PassShell,
    _backup_entry,
    cmd_export_vault,
    cmd_generate,
    cmd_insert,
    cmd_otp_add,
    save_config,
)

SEED = "JBSWY3DPEHPK3PXP"


# ---------------------------------------------------------------------------
# M1 — OTP secrets must never reach readline history
# ---------------------------------------------------------------------------


class TestOtpPromptsHidden:
    """OTP-secret prompts must use password=True (getpass bypasses readline)."""

    def test_insert_otp_prompt_is_hidden(self):
        answers = ["Str0ngPass!x", "", "", "", "", ""]  # pw, user, email, url, notes, otp
        with patch("passclip.Prompt.ask", side_effect=answers) as ask, \
                patch.dict("passclip.DEPS", {"pyotp": True}), \
                patch("passclip._insert_entry", return_value=(True, "")):
            cmd_insert("web/test")
        otp_calls = [c for c in ask.call_args_list if "OTP secret" in str(c.args[0])]
        assert otp_calls, "expected an OTP secret prompt"
        assert otp_calls[0].kwargs.get("password") is True

    def test_otp_add_manual_prompt_is_hidden(self):
        with patch("passclip.Prompt.ask", side_effect=[SEED]) as ask, \
                patch.dict("passclip.DEPS", {"pyotp": True}), \
                patch("passclip.get_entry_raw", return_value=("pw", None)), \
                patch("passclip._read_clipboard", return_value=None), \
                patch("passclip._insert_entry", return_value=(True, "")), \
                patch("passclip.copy_to_clipboard"):
            cmd_otp_add("web/test")
        otp_calls = [c for c in ask.call_args_list if "OTP secret" in str(c.args[0])]
        assert otp_calls, "expected the manual OTP secret prompt"
        assert otp_calls[0].kwargs.get("password") is True

    def test_metadata_prompts_suppress_history(self):
        """username/email/url/notes prompts run with readline auto-history off."""
        answers = ["Str0ngPass!x", "alice", "", "", "", ""]
        with patch("passclip.Prompt.ask", side_effect=answers), \
                patch.dict("passclip.DEPS", {"pyotp": True}), \
                patch("passclip._insert_entry", return_value=(True, "")), \
                patch("passclip.readline.set_auto_history") as sah:
            cmd_insert("web/test")
        called_with = [c.args[0] for c in sah.call_args_list]
        assert False in called_with and True in called_with


# ---------------------------------------------------------------------------
# M2 — clipboard clear must work for non-ASCII secrets
# ---------------------------------------------------------------------------


def _run_clear_script(tmp_path, clipboard_now, copied_text):
    """Run the pyperclip clear script against a fake pyperclip backed by a file."""
    (tmp_path / "pyperclip.py").write_text(
        "import os\n"
        "_STATE = os.environ['FAKE_CLIP_STATE']\n"
        "def paste():\n"
        "    with open(_STATE, encoding='utf-8') as f:\n"
        "        return f.read()\n"
        "def copy(text):\n"
        "    with open(_STATE, 'w', encoding='utf-8') as f:\n"
        "        f.write(text)\n",
        encoding="utf-8",
    )
    state = tmp_path / "state.txt"
    state.write_text(clipboard_now, encoding="utf-8")
    env = {
        **os.environ,
        "PYTHONPATH": str(tmp_path),
        "FAKE_CLIP_STATE": str(state),
        "_PASSCLIP_CLIP_TEXT": copied_text,
        "_PASSCLIP_CLIP_TIMEOUT": "0",
    }
    subprocess.run(
        [sys.executable, "-c", passclip._PYPERCLIP_CLEAR_SCRIPT],
        env=env, timeout=30, check=True,
    )
    return state.read_text(encoding="utf-8")


class TestClipboardClearScript:
    def test_non_ascii_secret_is_cleared(self, tmp_path):
        assert _run_clear_script(tmp_path, "pässwörd", "pässwörd") == ""

    def test_ascii_secret_is_cleared(self, tmp_path):
        assert _run_clear_script(tmp_path, "hunter2", "hunter2") == ""

    def test_unrelated_content_is_preserved(self, tmp_path):
        assert _run_clear_script(tmp_path, "user copied this", "hunter2") == "user copied this"


# ---------------------------------------------------------------------------
# M6 — generate --clip must not print the password
# ---------------------------------------------------------------------------


class TestGenerateClip:
    def test_clip_does_not_print_password(self, capsys):
        with patch("passclip.run_command", return_value=("", "", 0)), \
                patch("passclip.get_entry_raw", return_value=("Sup3rSecretPw!", None)), \
                patch("passclip.copy_to_clipboard") as cp:
            cmd_generate("web/test", 20, False, clip=True)
        assert "Sup3rSecretPw!" not in capsys.readouterr().out
        cp.assert_called_once_with("Sup3rSecretPw!")

    def test_without_clip_still_prints(self, capsys):
        with patch("passclip.run_command", return_value=("", "", 0)), \
                patch("passclip.get_entry_raw", return_value=("Sup3rSecretPw!", None)), \
                patch("passclip.copy_to_clipboard") as cp:
            cmd_generate("web/test", 20, False, clip=False)
        assert "Sup3rSecretPw!" in capsys.readouterr().out
        cp.assert_not_called()


# ---------------------------------------------------------------------------
# L1 — non-ASCII vault passphrase must not crash export
# ---------------------------------------------------------------------------


def test_export_vault_non_ascii_passphrase(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    (store / "entry.gpg").write_text("ciphertext")
    out_file = tmp_path / "backup.vault"
    with patch.dict("passclip.CONFIG", {"pass_dir": str(store)}), \
            patch("passclip.Prompt.ask", side_effect=["pässwörd!", "pässwörd!"]):
        cmd_export_vault(str(out_file))
    assert out_file.exists()
    assert out_file.read_bytes()[:4] == b"PCV2"


# ---------------------------------------------------------------------------
# L3 — config/backup dirs must be 0700
# ---------------------------------------------------------------------------


class TestDirPermissions:
    def test_config_dir_is_0700(self, tmp_path):
        cfg = tmp_path / "confdir" / "config.json"
        with patch("passclip.CONFIG_PATH", cfg):
            save_config({"clip_timeout": 45})
        assert (cfg.parent.stat().st_mode & 0o777) == 0o700

    def test_backup_dir_is_0700(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("passclip.get_entry_raw", return_value=("secret", None)):
            backup = _backup_entry("web/test")
        assert backup is not None
        backups = tmp_path / ".config" / "passclip" / "backups"
        assert (backups.stat().st_mode & 0o777) == 0o700


# ---------------------------------------------------------------------------
# L4 / L8 — shell history and lock-file robustness
# ---------------------------------------------------------------------------


@pytest.fixture
def shell_env(tmp_path, monkeypatch):
    """Isolated HOME + store for PassShell construction."""
    monkeypatch.setenv("HOME", str(tmp_path))
    store = tmp_path / "store"
    store.mkdir()
    return store


def test_locked_history_file_does_not_crash(shell_env, tmp_path):
    """SECURITY.md's chmod-000 history-disable recipe must not brick the shell."""
    hist = tmp_path / ".config" / "passclip" / "history"
    hist.parent.mkdir(parents=True)
    hist.touch()
    os.chmod(hist, 0)
    try:
        with patch.dict("passclip.CONFIG", {"pass_dir": str(shell_env)}):
            shell = PassShell()
            shell._release_lock()
    finally:
        os.chmod(hist, 0o600)


def test_non_holder_release_keeps_lock(shell_env):
    with patch.dict("passclip.CONFIG", {"pass_dir": str(shell_env)}):
        holder = PassShell()
        intruder = PassShell()  # lock already held
    assert holder._lock_fd is not None
    assert intruder._lock_fd is None
    lock = shell_env / ".passclip.lock"
    intruder._release_lock()
    assert lock.exists(), "non-holder must not delete the holder's lock file"
    holder._release_lock()
    assert not lock.exists()


# ---------------------------------------------------------------------------
# L9 — clipboard OTP-seed preview must be redacted
# ---------------------------------------------------------------------------


def test_clipboard_otp_preview_redacted(capsys):
    seed = SEED + SEED  # 32-char base32 secret
    with patch.dict("passclip.DEPS", {"pyotp": True}), \
            patch("passclip.get_entry_raw", return_value=("pw", None)), \
            patch("passclip._read_clipboard", return_value=seed), \
            patch("passclip.Confirm.ask", return_value=True), \
            patch("passclip._insert_entry", return_value=(True, "")), \
            patch("passclip.copy_to_clipboard"):
        cmd_otp_add("web/test")
    assert seed not in capsys.readouterr().out
