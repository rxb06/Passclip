"""Shell/CLI behavior tests for Phase 6 (quality review qM6, qS1-qS9, qS12,
NTH-1/2/4/5; remediation plan Phase 6)."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from passclip import (
    PassShell,
    _split_args,
    _validate_otp_secret,
    cmd_insert,
    cmd_otp_add,
    cmd_run,
    get_entry_raw,
    main,
    smart_copy,
)

SEED = "JBSWY3DPEHPK3PXP"


def _shell():
    """A PassShell without __init__ side effects (no lock/history needed)."""
    return PassShell.__new__(PassShell)


# ---------------------------------------------------------------------------
# qM6 — shell argument splitting
# ---------------------------------------------------------------------------


class TestSplitArgs:
    def test_plain(self):
        assert _split_args("a b --flag") == ["a", "b", "--flag"]

    def test_quoted_entry_name(self):
        assert _split_args('"web/my site" --clip') == ["web/my site", "--clip"]

    def test_unbalanced_quote_falls_back(self):
        # an apostrophe is legal in entry names; must not crash the shell
        assert _split_args("o'brien") == ["o'brien"]

    def test_empty(self):
        assert _split_args("") == []


class TestDoGetParsing:
    def test_quoted_name_with_clip(self):
        with patch("passclip.cmd_get") as get:
            _shell().do_get('"web/my site" --clip')
        get.assert_called_once_with("web/my site", True, None, interactive_followup=False)

    def test_incomplete_field_flag_rejected(self, capsys):
        with patch("passclip.cmd_get") as get:
            _shell().do_get("foo --field")
        get.assert_not_called()
        assert "flag" in capsys.readouterr().out.lower()


class TestDoGenerateParsing:
    def test_tokens_routed(self):
        with patch("passclip.cmd_generate") as gen:
            _shell().do_generate("web/foo 32 --no-symbols --clip")
        gen.assert_called_once_with("web/foo", 32, True, True)

    def test_quoted_name(self):
        with patch("passclip.cmd_generate") as gen:
            _shell().do_generate('"web/my site" 16')
        gen.assert_called_once_with("web/my site", 16, False, False)


# ---------------------------------------------------------------------------
# smart_copy routing (quality test #3) + NTH-4
# ---------------------------------------------------------------------------


class TestSmartCopy:
    def test_exact_match_beats_substring(self):
        with (
            patch("passclip.get_all_entries", return_value=["mail", "email/gmail"]),
            patch("passclip.cmd_get") as get,
        ):
            smart_copy(["mail"])
        get.assert_called_once_with("mail", clip=True)

    def test_single_substring_auto_selected(self):
        with (
            patch("passclip.get_all_entries", return_value=["email/gmail", "bank"]),
            patch("passclip.cmd_get") as get,
        ):
            smart_copy(["gma"])
        get.assert_called_once_with("email/gmail", clip=True)

    def test_username_mode(self):
        with (
            patch("passclip.get_all_entries", return_value=["email/gmail"]),
            patch("passclip.get_entry_raw", return_value=("pw\nusername: alice\n", None)),
            patch("passclip.copy_to_clipboard") as cp,
        ):
            smart_copy(["gmail", "-u"])
        cp.assert_called_once_with("alice")

    def test_show_mode(self):
        with (
            patch("passclip.get_all_entries", return_value=["email/gmail"]),
            patch("passclip.cmd_get") as get,
        ):
            smart_copy(["gmail", "-s"])
        get.assert_called_once_with("email/gmail")

    def test_unknown_flag_errors_instead_of_copying(self, capsys):
        with (
            patch("passclip.get_all_entries", return_value=["email/gmail"]),
            patch("passclip.cmd_get") as get,
        ):
            smart_copy(["-S", "gmail"])  # typo'd flag must not copy the password
        get.assert_not_called()
        assert "unknown flag" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# qS4 / qS1 / qS2 — main() dispatch and exit behavior
# ---------------------------------------------------------------------------


class TestMainDispatch:
    def test_flag_first_smart_copy(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["passclip", "-u", "gmail"])
        with patch("passclip.smart_copy") as sc:
            main()
        sc.assert_called_once_with(["-u", "gmail"])

    def test_run_exit_code_propagates(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["passclip", "run", "e", "--", "cmd"])
        with patch("passclip.cmd_run", return_value=7) as run, pytest.raises(SystemExit) as exc:
            main()
        run.assert_called_once_with("e", ["cmd"])
        assert exc.value.code == 7

    def test_ctrl_c_exits_130_gracefully(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["passclip"])
        with (
            patch("passclip._start_shell", side_effect=KeyboardInterrupt),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 130
        assert "Interrupted" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# qS2 / NTH-1 / NTH-2 — cmd_run
# ---------------------------------------------------------------------------


class TestCmdRun:
    def test_returns_child_exit_code(self):
        with (
            patch("passclip.get_entry_raw", return_value=("pw", None)),
            patch("passclip.subprocess.run", return_value=MagicMock(returncode=7)),
        ):
            assert cmd_run("e", ["somecmd"]) == 7

    def test_command_not_found_returns_127(self):
        with (
            patch("passclip.get_entry_raw", return_value=("pw", None)),
            patch("passclip.subprocess.run", side_effect=FileNotFoundError),
        ):
            assert cmd_run("e", ["nope"]) == 127

    def test_no_command_is_an_error(self):
        assert cmd_run("e", []) != 0

    def test_env_names_sanitized(self):
        content = "pw\nrecovery code: 1234\n"
        with (
            patch("passclip.get_entry_raw", return_value=(content, None)),
            patch("passclip.subprocess.run", return_value=MagicMock(returncode=0)) as run,
        ):
            cmd_run("e", ["somecmd"])
        env = run.call_args.kwargs["env"]
        assert "PASS_RECOVERY_CODE" in env
        assert "PASS_RECOVERY CODE" not in env


# ---------------------------------------------------------------------------
# qS3 — insert refuses to silently overwrite
# ---------------------------------------------------------------------------


def test_insert_asks_before_overwriting():
    with (
        patch("passclip.get_all_entries", return_value=["web/test"]),
        patch("passclip.Confirm.ask", return_value=False) as confirm,
        patch("passclip._insert_entry", return_value=(True, "")) as ins,
    ):
        cmd_insert("web/test")
    confirm.assert_called()
    ins.assert_not_called()


# ---------------------------------------------------------------------------
# qS5 / NTH-3 — restore prefix strip, archive guard
# ---------------------------------------------------------------------------


class TestArchiveRestore:
    def test_restore_accepts_full_archive_path(self):
        with (
            patch("passclip.get_all_entries", return_value=["archive/web/foo"]),
            patch("passclip.Prompt.ask", return_value="web/foo"),
            patch("passclip.run_command", return_value=("", "", 0)) as run,
        ):
            _shell().do_restore("archive/web/foo")
        run.assert_called_once_with(["pass", "mv", "archive/web/foo", "web/foo"])

    def test_archive_refuses_double_archive(self, capsys):
        with patch("passclip.run_command") as run:
            _shell().do_archive("archive/foo")
        run.assert_not_called()
        assert "already archived" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# qS6 — shell understands the syntax its help advertises
# ---------------------------------------------------------------------------


def test_do_otp_accepts_dash_dash_add():
    with patch("passclip.cmd_otp_add") as add:
        _shell().do_otp("--add gmail")
    add.assert_called_once_with("gmail")


# ---------------------------------------------------------------------------
# qS8 — run_command strip parameter / whitespace-significant passwords
# ---------------------------------------------------------------------------


def test_get_entry_raw_preserves_whitespace_password():
    fake = MagicMock(stdout="  spaced pw  \n", stderr="", returncode=0)
    with patch("passclip.subprocess.run", return_value=fake):
        content, error = get_entry_raw("web/test")
    assert error is None
    assert content == "  spaced pw  "


# ---------------------------------------------------------------------------
# qS9 — otp add does a targeted line edit, not a re-serialization
# ---------------------------------------------------------------------------


def test_otp_add_preserves_entry_layout():
    original = "pw\nUser: Alice\n\nsome note: with colon\notp: OLDSECRET\ntrailing text"
    with (
        patch.dict("passclip.DEPS", {"pyotp": True}),
        patch("passclip.get_entry_raw", return_value=(original, None)),
        patch("passclip.Confirm.ask", return_value=True),
        patch("passclip._read_clipboard", return_value=None),
        patch("passclip.Prompt.ask", return_value=SEED),
        patch("passclip._insert_entry", return_value=(True, "")) as ins,
        patch("passclip.copy_to_clipboard"),
    ):
        cmd_otp_add("web/test")
    written = ins.call_args[0][1]
    assert written == (f"pw\nUser: Alice\n\nsome note: with colon\ntrailing text\notp: {SEED}\n"), (
        "all original lines must survive byte-for-byte; only the otp line changes"
    )


# ---------------------------------------------------------------------------
# qS12 — insert validates OTP secrets with the strict helper
# ---------------------------------------------------------------------------


class TestValidateOtpSecret:
    def test_too_short(self):
        assert _validate_otp_secret("ABCDEF") is not None

    def test_not_base32(self):
        assert _validate_otp_secret("1111111111111111") is not None

    def test_otpauth_missing_secret(self):
        assert _validate_otp_secret("otpauth://totp/x?issuer=y") is not None

    def test_valid(self):
        assert _validate_otp_secret(SEED) is None

    def test_insert_rejects_weak_secret_via_helper(self, capsys):
        # 8-char secret: old inline check accepted it, strict helper refuses
        answers = ["Str0ngPass!x", "", "", "", "", "ABCDEFGH"]
        with (
            patch("passclip.Prompt.ask", side_effect=answers),
            patch.dict("passclip.DEPS", {"pyotp": True}),
            patch("passclip.get_all_entries", return_value=[]),
            patch("passclip._insert_entry", return_value=(True, "")) as ins,
        ):
            cmd_insert("web/test")
        content = ins.call_args[0][1]
        assert "otp:" not in content
        assert "Invalid OTP secret" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# L15 follow-up — typed names that look like flags are rejected
# ---------------------------------------------------------------------------


def test_do_mv_rejects_flag_like_source(capsys):
    with patch("passclip.run_command") as run:
        _shell().do_mv("-x dest")
    run.assert_not_called()
