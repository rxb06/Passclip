"""Regression tests for the 2026-09-17 code review (mydocs/code-review-2026-09-17.md).

Each test names the finding it pins down, so a reintroduced bug points straight
back at the report that described it.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import passclip
from passclip import (
    _backup_entry,
    _config_value_error,
    _extract_otp_secret,
    _is_otp_field_line,
    _parse_csv_row,
    _select_gpg_key,
    _validate_otp_secret,
    cmd_config_set,
    cmd_delete,
    cmd_export_vault,
    cmd_generate,
    cmd_get,
    cmd_git_log,
    cmd_import,
    cmd_otp,
    copy_to_clipboard,
    main,
    parse_entry,
    run_command,
)

ENTRIES = ["web/aws", "web/github", "web/gmail"]


def _shell():
    with (
        patch("passclip.PassShell._setup_history"),
        patch("passclip.PassShell._acquire_lock"),
    ):
        return passclip.PassShell()


# ---------------------------------------------------------------------------
# H1 — the configured store must reach the `pass` child process
# ---------------------------------------------------------------------------


class TestPassDirReachesChild:
    def test_password_store_dir_is_exported(self):
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": "/tmp/storeB"}),
            patch("passclip.subprocess.run") as run,
        ):
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            run_command(["pass", "show", "web/gmail"])
        assert run.call_args.kwargs["env"]["PASSWORD_STORE_DIR"] == "/tmp/storeB"

    def test_interactive_child_gets_it_too(self):
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": "/tmp/storeB"}),
            patch("passclip.subprocess.run") as run,
        ):
            run.return_value = MagicMock(returncode=0)
            run_command(["pass", "edit", "web/gmail"], interactive=True)
        assert run.call_args.kwargs["env"]["PASSWORD_STORE_DIR"] == "/tmp/storeB"


# ---------------------------------------------------------------------------
# H2 — `generate` on an existing entry must not wipe its other fields
# ---------------------------------------------------------------------------


class TestGenerateRotation:
    @pytest.mark.parametrize(
        "entries,flag",
        [(["web/gmail"], "-i"), ([], "-f")],
        ids=["existing-entry-in-place", "new-entry-force"],
    )
    def test_flag_depends_on_existence(self, entries, flag):
        with (
            patch("passclip.get_all_entries", return_value=entries),
            patch("passclip.run_command", return_value=("", "", 0)) as run,
            patch("passclip.get_entry_raw", return_value=(None, "err")),
        ):
            cmd_generate("web/gmail", 20)
        assert run.call_args.args[0][:3] == ["pass", "generate", flag]


# ---------------------------------------------------------------------------
# H3 / M5 — errors on stderr, failures as a non-zero exit status
# ---------------------------------------------------------------------------


class TestScriptingContract:
    def test_field_error_never_lands_on_stdout(self, capsys):
        with patch("passclip.get_entry_raw", return_value=(None, "Entry not found.")):
            cmd_get("nope/nope", field="password")
        captured = capsys.readouterr()
        assert captured.out == "", "stdout is the scripting channel — it must stay empty"
        assert "not found" in captured.err

    def test_main_exits_non_zero_after_an_error(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["passclip", "get", "nope/nope"])
        with (
            patch("passclip.load_config", return_value=dict(passclip.DEFAULT_CONFIG)),
            patch("passclip.get_entry_raw", return_value=(None, "Entry not found.")),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 1

    def test_main_exits_zero_on_success(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["passclip", "get", "web/gmail"])
        with (
            patch("passclip.load_config", return_value=dict(passclip.DEFAULT_CONFIG)),
            patch("passclip.get_entry_raw", return_value=("pw\n", None)),
        ):
            main()  # must not raise SystemExit

    def test_error_flag_does_not_leak_between_invocations(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["passclip", "get", "nope/nope"])
        with (
            patch("passclip.load_config", return_value=dict(passclip.DEFAULT_CONFIG)),
            patch("passclip.get_entry_raw", return_value=(None, "Entry not found.")),
            pytest.raises(SystemExit),
        ):
            main()
        monkeypatch.setattr(sys, "argv", ["passclip", "get", "web/gmail"])
        with (
            patch("passclip.load_config", return_value=dict(passclip.DEFAULT_CONFIG)),
            patch("passclip.get_entry_raw", return_value=("pw\n", None)),
        ):
            main()


# ---------------------------------------------------------------------------
# H4 / M10 — deleting a folder, and backups that actually protect the delete
# ---------------------------------------------------------------------------


class TestDeleteScope:
    def test_folder_delete_names_every_entry_at_stake(self, capsys):
        with (
            patch("passclip.get_all_entries", return_value=ENTRIES),
            patch("passclip.Confirm.ask", return_value=False) as ask,
            patch("passclip.run_command") as run,
        ):
            cmd_delete("web")
        out = capsys.readouterr().out
        for entry in ENTRIES:
            assert entry in out, "the prompt must list what is about to be destroyed"
        assert "3" in ask.call_args.args[0]
        assert not run.called

    def test_unknown_name_is_refused(self):
        with (
            patch("passclip.get_all_entries", return_value=ENTRIES),
            patch("passclip.Confirm.ask", return_value=True),
            patch("passclip.run_command") as run,
        ):
            cmd_delete("typo", force=True)
        assert not run.called, "an unmatched name must never reach `pass rm -r`"

    def test_folder_delete_backs_up_every_entry(self):
        backed_up = []
        with (
            patch("passclip.get_all_entries", return_value=ENTRIES),
            patch(
                "passclip._backup_entry",
                side_effect=lambda e: (backed_up.append(e) or Path("/tmp/b.bak"), None),
            ),
            patch("passclip.run_command", return_value=("", "", 0)) as run,
        ):
            cmd_delete("web", force=True)
        assert backed_up == ENTRIES
        assert run.call_args.args[0] == ["pass", "rm", "-r", "-f", "web"]

    def test_failed_backup_aborts_the_delete(self, capsys):
        with (
            patch("passclip.get_all_entries", return_value=ENTRIES),
            patch("passclip._backup_entry", return_value=(None, "GPG agent locked")),
            patch("passclip.run_command") as run,
        ):
            cmd_delete("web/gmail", force=True)
        assert not run.called
        assert "aborted" in capsys.readouterr().err.lower()

    def test_backup_of_undecryptable_entry_reports_the_error(self, tmp_path):
        with (
            patch.dict("os.environ", {"HOME": str(tmp_path)}),
            patch("passclip.Path.home", return_value=tmp_path),
            patch("passclip.get_entry_raw", return_value=(None, "Cannot decrypt")),
        ):
            path, err = _backup_entry("web/gmail")
        assert path is None
        assert "decrypt" in err


# ---------------------------------------------------------------------------
# H5 / H6 / L7 — CSV import must not destroy secrets silently
# ---------------------------------------------------------------------------


def _csv(tmp_path, body):
    path = tmp_path / "import.csv"
    path.write_text("name,folder,username,password,url,notes\n" + body)
    return str(path)


class TestCsvImportCollisions:
    COLLIDING = "My Site,web,a,pw1,,\nmy site,web,b,pw2,,\nMY SITE,web,c,pw3,,\n"

    def test_rows_colliding_with_each_other_are_renamed(self, tmp_path):
        written = {}
        with (
            patch(
                "passclip._insert_entry",
                side_effect=lambda e, c: (written.__setitem__(e, c), (True, ""))[1],
            ),
            patch("passclip.get_all_entries", return_value=[]),
        ):
            cmd_import(_csv(tmp_path, self.COLLIDING), "generic")
        assert sorted(written) == ["web/my_site", "web/my_site-2", "web/my_site-3"]
        assert [c.splitlines()[0] for c in written.values()] == ["pw1", "pw2", "pw3"]

    def test_rename_skips_paths_already_in_the_store(self, tmp_path):
        with (
            patch("passclip._insert_entry", return_value=(True, "")) as ins,
            patch("passclip.get_all_entries", return_value=["web/my_site-2"]),
            patch("passclip.Confirm.ask", return_value=True),
        ):
            cmd_import(_csv(tmp_path, self.COLLIDING), "generic")
        paths = [c.args[0] for c in ins.call_args_list]
        assert paths == ["web/my_site", "web/my_site-3", "web/my_site-4"]

    def test_overwriting_the_live_store_requires_confirmation(self, tmp_path):
        with (
            patch("passclip._insert_entry") as ins,
            patch("passclip.get_all_entries", return_value=["web/gmail"]),
            patch("passclip.Confirm.ask", return_value=False) as ask,
        ):
            cmd_import(_csv(tmp_path, "Gmail,web,a,pw1,,\n"), "generic")
        assert ask.called
        assert not ins.called, "declining must write nothing at all"

    def test_force_skips_the_confirmation(self, tmp_path):
        with (
            patch("passclip._insert_entry", return_value=(True, "")) as ins,
            patch("passclip.get_all_entries", return_value=["web/gmail"]),
            patch("passclip.Confirm.ask") as ask,
        ):
            cmd_import(_csv(tmp_path, "Gmail,web,a,pw1,,\n"), "generic", force=True)
        assert not ask.called
        assert ins.called

    def test_dry_run_never_prompts_and_never_writes(self, tmp_path):
        with (
            patch("passclip._insert_entry") as ins,
            patch("passclip.get_all_entries", return_value=["web/gmail"]),
            patch("passclip.Confirm.ask") as ask,
        ):
            cmd_import(_csv(tmp_path, "Gmail,web,a,pw1,,\n"), "generic", dry_run=True)
        assert not ask.called
        assert not ins.called

    def test_directory_path_does_not_raise(self, tmp_path, capsys):
        cmd_import(str(tmp_path), "generic")
        assert "cannot read file" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# H7 / H8 / M1 / M7 — OTP handling
# ---------------------------------------------------------------------------


class TestOtpHandling:
    def test_unrelated_secret_field_is_not_an_otp_line(self):
        assert not _is_otp_field_line("secret: my-api-key-not-an-otp")

    def test_otp_aliases_are_otp_lines(self):
        assert _is_otp_field_line("otp: JBSWY3DPEHPK3PXP")
        assert _is_otp_field_line("totp: JBSWY3DPEHPK3PXP")
        assert _is_otp_field_line("secret: JBSWY3DPEHPK3PXP")

    def test_unpadded_base32_seed_is_accepted(self):
        """26 characters is not a multiple of 8, but pyotp pads internally."""
        assert _validate_otp_secret("JBSWY3DPEHPK3PXPJBSWY3DPEH") is None

    def test_hotp_uri_is_rejected_with_a_message(self, capsys):
        uri = "otpauth://hotp/A:b?secret=JBSWY3DPEHPK3PXP&counter=1"
        assert _validate_otp_secret(uri) is not None
        with (
            patch("passclip.get_entry_raw", return_value=(f"pw\notp: {uri}\n", None)),
            patch.dict("passclip.DEPS", {"pyotp": True}),
        ):
            cmd_otp("web/x")  # must not raise AttributeError
        err = capsys.readouterr().err.lower()
        assert "otp secret" in err
        assert "hotp" in err, "the message must name the cause, not leak an AttributeError"
        assert "attribute" not in err

    def test_garbage_secret_errors_instead_of_raising(self, capsys):
        with (
            patch("passclip.get_entry_raw", return_value=("pw\notp: NOT-VALID-BASE32!!\n", None)),
            patch.dict("passclip.DEPS", {"pyotp": True}),
        ):
            cmd_otp("web/x")
        assert "otp secret" in capsys.readouterr().err.lower()

    def test_uri_in_a_notes_blob_is_extracted_line_by_line(self):
        data = parse_entry(
            "pw\notpauth://totp/Acme:bob?secret=JBSWY3DPEHPK3PXP&issuer=Acme\nbackup code 12345\n"
        )
        secret = _extract_otp_secret(data)
        assert secret == "otpauth://totp/Acme:bob?secret=JBSWY3DPEHPK3PXP&issuer=Acme"
        assert "backup code" not in secret


# ---------------------------------------------------------------------------
# H9 / H10 / M13 — the clipboard promise must match what happens
# ---------------------------------------------------------------------------


class TestClipboardPromise:
    def test_no_auto_clear_claim_when_the_clearer_cannot_start(self, capsys):
        with (
            patch.dict("passclip.DEPS", {"pyperclip": False}),
            patch("passclip.shutil.which", return_value="/usr/bin/pbcopy"),
            patch("passclip.subprocess.run"),
            patch("passclip.subprocess.Popen", side_effect=OSError("fork failed")),
        ):
            assert copy_to_clipboard("s3cret", 45) is True
        out = capsys.readouterr().out
        assert "Auto-clearing" not in out
        assert "manually" in out

    def test_native_copy_does_not_capture_output(self):
        """xclip/wl-copy keep the pipes open while they own the selection."""
        with (
            patch.dict("passclip.DEPS", {"pyperclip": False}),
            patch("passclip.shutil.which", return_value="/usr/bin/xclip"),
            patch("passclip.subprocess.run") as run,
            patch("passclip._spawn_clipboard_clear", return_value=True),
        ):
            copy_to_clipboard("s3cret", 45)
        kwargs = run.call_args.kwargs
        assert not kwargs.get("capture_output")
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.DEVNULL
        assert kwargs["timeout"] == 5

    def test_native_copy_sends_utf8_bytes(self):
        """The clearer compares utf-8 bytes; text=True would use the locale."""
        with (
            patch.dict("passclip.DEPS", {"pyperclip": False}),
            patch("passclip.shutil.which", return_value="/usr/bin/xclip"),
            patch("passclip.subprocess.run") as run,
            patch("passclip._spawn_clipboard_clear", return_value=True),
        ):
            copy_to_clipboard("pässwörd", 45)
        assert run.call_args.kwargs["input"] == "pässwörd".encode()


# ---------------------------------------------------------------------------
# M2 / M3 — validation that existed in one place but not its twin
# ---------------------------------------------------------------------------


class TestValidationSymmetry:
    @pytest.mark.parametrize("value", ["-5", "0"])
    def test_config_set_refuses_out_of_range_clip_timeout(self, value):
        with patch("passclip.save_config") as save:
            cmd_config_set("clip_timeout", value)
        assert not save.called
        assert passclip.CONFIG["clip_timeout"] >= 1

    def test_config_set_refuses_short_password_length(self):
        with patch("passclip.save_config") as save:
            cmd_config_set("default_password_length", "4")
        assert not save.called

    def test_config_bounds_accept_legal_values(self):
        assert _config_value_error("clip_timeout", 45) is None
        assert _config_value_error("default_password_length", 20) is None
        assert _config_value_error("pass_dir", "/anywhere") is None

    @pytest.mark.parametrize(
        "choice,expected",
        [(1, "AAA"), (2, "BBB"), (0, None), (5, None), (-1, None)],
        ids=["first", "second", "cancel", "too-high", "negative"],
    )
    def test_gpg_key_selection_is_bounded(self, choice, expected):
        keys = [("AAA", "a@x"), ("BBB", "b@x")]
        with patch("passclip.IntPrompt.ask", return_value=choice):
            assert _select_gpg_key(keys) == expected


# ---------------------------------------------------------------------------
# M4 — markup in generated passwords must never crash the renderer
# ---------------------------------------------------------------------------


class TestMarkupInGeneratedPassword:
    def test_insert_survives_a_closing_tag_lookalike(self, capsys):
        password = "53WnH?>$BI#n)[/ZIym]"  # credactor:ignore - fixture
        with (
            patch("passclip.get_all_entries", return_value=[]),
            patch("passclip.generate_password", return_value=password),
            patch("passclip.Prompt.ask", return_value=""),
            patch("passclip.IntPrompt.ask", return_value=20),
            patch("passclip.Confirm.ask", return_value=True),
            patch.dict("passclip.DEPS", {"pyotp": False}),
            patch("passclip._insert_entry", return_value=(True, "")) as ins,
        ):
            passclip.cmd_insert("web/new")
        assert ins.called, "the entry must still be saved"
        assert "[/ZIym]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# M6 / M11 — field mapping and note classification
# ---------------------------------------------------------------------------


class TestFieldMapping:
    def test_lastpass_totp_column_is_mapped(self):
        row = {
            "name": "X",
            "grouping": "web",
            "username": "u",
            "password": "p",
            "url": "",
            "extra": "",
            "totp": "JBSWY3DPEHPK3PXP",
        }
        assert _parse_csv_row(row, "lastpass")["otp"] == "JBSWY3DPEHPK3PXP"

    def test_prose_with_a_colon_stays_a_note(self):
        data = parse_entry("pw\nusername: bob\nBackup codes: ask ops\nsecond line\n")
        assert data["username"] == "bob"
        assert "backup codes" not in data
        assert data["notes"] == "Backup codes: ask ops\nsecond line\n"

    def test_ordinary_fields_still_parse(self):
        data = parse_entry("pw\nusername: bob\nurl: x.com\napi-key: abc\n")
        assert data["username"] == "bob"
        assert data["url"] == "x.com"
        assert data["api-key"] == "abc"


# ---------------------------------------------------------------------------
# M8 / M9 / L6 — interactive shell argument handling
# ---------------------------------------------------------------------------


class TestShellArguments:
    def test_short_clip_flag_is_honoured(self):
        with patch("passclip.cmd_generate") as gen:
            _shell().do_generate("web/gmail -c")
        gen.assert_called_once_with("web/gmail", None, False, True)

    def test_short_no_symbols_flag_is_honoured(self):
        with patch("passclip.cmd_generate") as gen:
            _shell().do_generate("web/gmail 24 -n")
        gen.assert_called_once_with("web/gmail", 24, True, False)

    def test_unknown_flag_is_rejected_not_dropped(self, capsys):
        with patch("passclip.cmd_generate") as gen:
            _shell().do_generate("web/gmail -z")
        assert not gen.called
        assert "unknown flag" in capsys.readouterr().err.lower()

    def test_ctrl_d_at_a_nested_prompt_does_not_kill_the_shell(self, capsys):
        shell = _shell()
        with patch("passclip.cmd_find", side_effect=EOFError):
            assert shell.onecmd("find gmail") is False
        assert "cancelled" in capsys.readouterr().out.lower()

    def test_vault_commands_skip_leading_flags(self):
        with patch("passclip.cmd_import_vault") as imp:
            _shell().do_import_vault("--force backup.vault")
        imp.assert_called_once_with("backup.vault", force=True)

        with patch("passclip.cmd_export_vault") as exp:
            _shell().do_export_vault("--whatever out.vault")
        exp.assert_called_once_with("out.vault")


# ---------------------------------------------------------------------------
# M12 / M14 — commands the docs promise must exist on the CLI
# ---------------------------------------------------------------------------


class TestDocumentedCommandsExist:
    @pytest.mark.parametrize("name", ["init", "gpg_list", "gpg_gen"])
    def test_registered_as_subcommands(self, name):
        _, known = passclip.build_parser()
        assert name in known, f"docs/setup.md documents `passclip {name}`"

    def test_init_dispatches_with_a_key_id(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["passclip", "init", "ABC123"])
        with (
            patch("passclip.load_config", return_value=dict(passclip.DEFAULT_CONFIG)),
            patch("passclip.cmd_init") as init,
        ):
            main()
        init.assert_called_once_with("ABC123")

    def test_init_refuses_a_flag_like_key_id(self, capsys):
        with (
            patch("passclip.get_gpg_keys", return_value=[("AAA", "a")]),
            patch("passclip.run_command") as run,
        ):
            passclip.cmd_init("--evil")
        assert not run.called
        assert "-" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# M15 / M16 / L2 / L3 / L8 / L12 — robustness and reporting accuracy
# ---------------------------------------------------------------------------


class TestRobustness:
    def test_non_utf8_output_is_an_error_not_a_traceback(self):
        with patch(
            "passclip.subprocess.run",
            side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
        ):
            out, err, rc = run_command(["pass", "show", "web/legacy"])
        assert rc != 0
        assert "utf-8" in err.lower()

    def test_health_survives_one_undecodable_entry(self, capsys):
        def fake_run(parts, **kwargs):
            if parts[-1] == "web/legacy":
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
            return MagicMock(stdout="pw\n", stderr="", returncode=0)

        with (
            patch("passclip.get_all_entries", return_value=["web/ok", "web/legacy"]),
            patch("passclip.subprocess.run", side_effect=fake_run),
        ):
            passclip.cmd_health()  # must not raise
        assert "Could not decrypt 1 entries" in capsys.readouterr().out

    def test_export_checks_the_output_directory_before_prompting(self, tmp_path, capsys):
        store = tmp_path / ".password-store"
        store.mkdir()
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": str(store)}),
            patch("passclip.Prompt.ask") as ask,
        ):
            cmd_export_vault(str(tmp_path / "missing" / "backup.vault"))
        assert not ask.called, "no passphrase prompt before the destination is known good"
        assert "directory does not exist" in capsys.readouterr().err.lower()

    def test_export_counts_only_what_went_into_the_vault(self, tmp_path, capsys):
        """L2 + L12: the symlink is skipped, so it must not be counted either."""
        store = tmp_path / ".password-store"
        (store / "email").mkdir(parents=True)
        (store / "real.gpg").write_bytes(b"cipher")
        (store / "email" / "work.gpg").write_bytes(b"cipher-work")
        # neither the directory nor a non-entry file is an "entry"
        (store / ".gpg-id").write_text("ABC123\n")
        outside = tmp_path / "outside.gpg"
        outside.write_bytes(b"cipher-outside")
        (store / "link.gpg").symlink_to(outside)
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": str(store)}),
            patch("passclip.Prompt.ask", side_effect=["correct-horse-battery!7"] * 2),
        ):
            cmd_export_vault(str(tmp_path / "backup.vault"))
        out = capsys.readouterr().out
        assert "Skipping symlink" in out
        # 2 real .gpg entries — not the symlink, the directory, or .gpg-id
        assert "Entries: 2" in out.replace("  ", " ")

    def test_gitlog_clamps_a_negative_count(self):
        with patch("passclip.run_command", return_value=("", "", 0)) as run:
            cmd_git_log(-5)
        assert "--5" not in run.call_args.args[0]
        assert "-1" in run.call_args.args[0]

    def test_duplicate_groups_report_what_was_truncated(self, capsys):
        entries = [f"web/e{i}" for i in range(24)]
        contents = {e: (f"shared{i // 2}\n", None) for i, e in enumerate(entries)}
        with (
            patch("passclip.get_all_entries", return_value=entries),
            patch("passclip.get_entry_raw", side_effect=lambda e: contents[e]),
        ):
            passclip.cmd_health()
        assert "and 2 more duplicate groups" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Test gaps the review called out as security-relevant
# ---------------------------------------------------------------------------


class TestPreviouslyUntestedGuards:
    def test_move_rejects_a_flag_like_source(self, capsys):
        with patch("passclip.run_command") as run:
            passclip.cmd_mv("--help", "web/new")
        assert not run.called
        assert "-" in capsys.readouterr().err

    def test_copy_rejects_an_invalid_destination(self, capsys):
        with patch("passclip.run_command") as run:
            passclip.cmd_cp("web/old", "../../etc/passwd")
        assert not run.called
        assert capsys.readouterr().err

    def test_sync_reports_a_failed_pull_as_an_error(self, capsys):
        with patch("passclip.run_command", return_value=("", "no remote", 1)) as run:
            passclip.cmd_sync()
        assert run.call_count == 1, "a failed pull must not be followed by a push"
        assert "pull failed" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# M5 — the write paths, where exiting 0 on failure costs the most
# ---------------------------------------------------------------------------


class TestWritePathExitStatus:
    def test_generate_gpg_failure_is_not_a_success(self, capsys):
        with (
            patch("passclip.get_all_entries", return_value=[]),
            patch(
                "passclip.run_command",
                return_value=("", "gpg: encryption failed: Unusable public key", 1),
            ),
        ):
            cmd_generate("web/new", 20)
        assert "gpg encryption failed" in capsys.readouterr().err.lower()
        assert passclip._ERROR_SEEN, "main() must turn this into a non-zero exit"

    def test_csv_rows_that_fail_to_write_are_not_a_success(self, tmp_path, capsys):
        with (
            patch("passclip._insert_entry", return_value=(False, "gpg: no secret key")),
            patch("passclip.get_all_entries", return_value=[]),
        ):
            cmd_import(_csv(tmp_path, "X,web,u,pw,,\n"), "generic")
        out, err = capsys.readouterr()
        assert "1 failed" in out
        assert "could not be written" in err.lower()
        assert passclip._ERROR_SEEN
