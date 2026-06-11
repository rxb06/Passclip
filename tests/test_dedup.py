"""Behavior-pin tests for the Phase 7 dedup refactor (qS13–qS17, M4-complete,
NTH-6): the nine commands that existed twice (shell + CLI) now share one
cmd_* implementation, and secret/entry values render literally."""

import sys
from unittest.mock import call, patch

import pytest

from passclip import (
    PassShell,
    _copy_username,
    _extract_otp_secret,
    _make_totp,
    build_parser,
    cmd_delete,
    cmd_find,
    cmd_get,
    main,
)

SEED = "JBSWY3DPEHPK3PXP"


def _shell():
    return PassShell.__new__(PassShell)


# ---------------------------------------------------------------------------
# M4 complete — secret values must render literally, never as markup
# ---------------------------------------------------------------------------


class TestSecretDisplayEscaping:
    def test_markup_like_password_displays_literally(self, capsys):
        """A password like 'p[/]w' crashed cmd_get with MarkupError before."""
        with patch("passclip.get_entry_raw", return_value=("p[/]w", None)):
            cmd_get("web/test")  # must not raise
        assert "p[/]w" in capsys.readouterr().out

    def test_markup_like_username_displays_literally(self, capsys):
        content = "pw\nusername: [link=http://evil]x[/link]\n"
        with patch("passclip.get_entry_raw", return_value=(content, None)):
            cmd_get("web/test")
        assert "[link=http://evil]x[/link]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# qS13 — one shared implementation per command
# ---------------------------------------------------------------------------


class TestCmdDelete:
    def test_backs_up_before_deleting(self):
        manager = []
        with patch("passclip._preview_entry_metadata"), \
                patch("passclip.Confirm.ask", return_value=True), \
                patch("passclip._backup_entry",
                      side_effect=lambda e: manager.append("backup") or None), \
                patch("passclip.run_command",
                      side_effect=lambda *a, **k: manager.append("rm") or ("", "", 0)):
            cmd_delete("web/test")
        assert manager == ["backup", "rm"], "backup must happen before pass rm"

    def test_force_skips_preview_and_confirm(self):
        with patch("passclip._preview_entry_metadata") as preview, \
                patch("passclip.Confirm.ask") as confirm, \
                patch("passclip._backup_entry", return_value=None), \
                patch("passclip.run_command", return_value=("", "", 0)) as run:
            cmd_delete("web/test", force=True)
        preview.assert_not_called()
        confirm.assert_not_called()
        run.assert_called_once_with(["pass", "rm", "-r", "-f", "web/test"])

    def test_declined_confirm_deletes_nothing(self):
        with patch("passclip._preview_entry_metadata"), \
                patch("passclip.Confirm.ask", return_value=False), \
                patch("passclip._backup_entry") as backup, \
                patch("passclip.run_command") as run:
            cmd_delete("web/test")
        backup.assert_not_called()
        run.assert_not_called()


def test_cmd_find_offers_action_menu():
    with patch("passclip.run_command", return_value=("hit", "", 0)), \
            patch("passclip.get_all_entries", return_value=["email/gmail"]), \
            patch("passclip.fuzzy_select", return_value="email/gmail"), \
            patch("passclip._entry_action_menu") as menu:
        cmd_find("gmail")
    menu.assert_called_once_with("email/gmail")


class TestBothFrontendsShareImplementations:
    """The shell do_* methods and main()'s dispatch must call the same cmd_*."""

    CASES = [
        # (shell line, cli argv, patched cmd, expected call)
        ("do_delete", "web/x", ["delete", "web/x", "--force"],
         "cmd_delete", call("web/x", force=True)),
        ("do_ls", "web", ["ls", "web"], "cmd_ls", call("web")),
        ("do_find", "gmail", ["find", "gmail"], "cmd_find", call("gmail")),
        ("do_mv", "a b", ["mv", "a", "b"], "cmd_mv", call("a", "b")),
        ("do_cp", "a b", ["cp", "a", "b"], "cmd_cp", call("a", "b")),
        ("do_archive", "web/x", ["archive", "web/x"], "cmd_archive", call("web/x")),
        ("do_restore", "web/x", ["restore", "web/x"], "cmd_restore", call("web/x")),
        ("do_edit", "web/x", ["edit", "web/x"], "cmd_edit", call("web/x")),
    ]

    @pytest.mark.parametrize("method,arg,argv,cmd,expected",
                             CASES, ids=[c[0] for c in CASES])
    def test_shell_wrapper_delegates(self, method, arg, argv, cmd, expected):
        with patch(f"passclip.{cmd}") as target:
            getattr(_shell(), method)(arg)
        shell_args = target.call_args
        assert shell_args is not None, f"{method} must delegate to {cmd}"

    @pytest.mark.parametrize("method,arg,argv,cmd,expected",
                             CASES, ids=[c[3] + "-cli" for c in CASES])
    def test_cli_dispatch_delegates(self, monkeypatch, method, arg, argv, cmd, expected):
        monkeypatch.setattr(sys, "argv", ["passclip"] + argv)
        with patch(f"passclip.{cmd}") as target:
            main()
        assert target.call_args == expected


# ---------------------------------------------------------------------------
# qS17 — the command set is derived from the parser, not hand-maintained
# ---------------------------------------------------------------------------


def test_cli_config_empty_value_is_a_read_not_a_write(monkeypatch):
    """`passclip config pass_dir ""` historically displayed the key; the dedup
    must not turn it into cmd_config_set(key, "") (which would persist $PWD)."""
    monkeypatch.setattr(sys, "argv", ["passclip", "config", "pass_dir", ""])
    with patch("passclip.cmd_config_set") as setter:
        main()
    setter.assert_not_called()


class TestKnownCommands:
    def test_parser_returns_command_set(self):
        _parser, known = build_parser()
        for name in ("get", "insert", "run", "export-vault", "import-vault",
                     "config", "shell"):
            assert name in known

    def test_unknown_first_arg_goes_to_smart_copy(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["passclip", "gmail"])
        with patch("passclip.smart_copy") as sc:
            main()
        sc.assert_called_once_with(["gmail"])


# ---------------------------------------------------------------------------
# qS14 — single username-copy implementation
# ---------------------------------------------------------------------------


class TestCopyUsername:
    def test_username_preferred(self):
        content = "pw\nusername: alice\nemail: a@b.com\n"
        with patch("passclip.get_entry_raw", return_value=(content, None)), \
                patch("passclip.copy_to_clipboard") as cp:
            _copy_username("e")
        cp.assert_called_once_with("alice")

    def test_falls_back_to_email(self):
        with patch("passclip.get_entry_raw", return_value=("pw\nemail: a@b.com\n", None)), \
                patch("passclip.copy_to_clipboard") as cp:
            _copy_username("e")
        cp.assert_called_once_with("a@b.com")

    def test_nothing_to_copy_warns(self, capsys):
        with patch("passclip.get_entry_raw", return_value=("pw", None)), \
                patch("passclip.copy_to_clipboard") as cp:
            _copy_username("e")
        cp.assert_not_called()
        assert "No username or email" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# NTH-6 — OTP helpers
# ---------------------------------------------------------------------------


class TestOtpHelpers:
    def test_extracts_from_any_alias_key(self):
        for key in ("otp", "totp", "secret", "otpauth"):
            assert _extract_otp_secret({key: SEED}) == SEED

    def test_extracts_otpauth_uri_from_any_value(self):
        uri = f"otpauth://totp/x?secret={SEED}"
        assert _extract_otp_secret({"custom": uri}) == uri

    def test_none_when_absent(self):
        assert _extract_otp_secret({"password": "pw"}) is None

    def test_make_totp_handles_both_forms(self):
        assert _make_totp(SEED).now().isdigit()
        assert _make_totp(f"otpauth://totp/x?secret={SEED}").now().isdigit()
