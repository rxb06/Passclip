"""Regression tests for the Codex review of the 1.5.0 pull requests.

Three of the four were introduced by the 1.5.0 fixes themselves, so each test
here pins behaviour that a previous fix broke.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import passclip
from passclip import _backup_entry, _default_store_dir, cmd_gpg_gen, load_config, run_command


def _shell():
    with (
        patch("passclip.PassShell._setup_history"),
        patch("passclip.PassShell._acquire_lock"),
    ):
        return passclip.PassShell()


# ---------------------------------------------------------------------------
# P1 — $PASSWORD_STORE_DIR must survive when pass_dir is not configured
# ---------------------------------------------------------------------------


class TestStoreResolution:
    def test_env_var_is_the_default_store(self, monkeypatch):
        monkeypatch.setenv("PASSWORD_STORE_DIR", "/env/store")
        assert _default_store_dir() == "/env/store"

    def test_home_default_when_env_is_unset(self, monkeypatch):
        monkeypatch.delenv("PASSWORD_STORE_DIR", raising=False)
        assert _default_store_dir().endswith("/.password-store")

    def test_env_var_is_not_overwritten_for_the_child(self, monkeypatch):
        """docs/setup.md offers PASSWORD_STORE_DIR as an alternative to
        `config pass_dir`; passing the default over it sent writes elsewhere."""
        monkeypatch.setenv("PASSWORD_STORE_DIR", "/env/store")
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": _default_store_dir()}),
            patch("passclip.subprocess.run") as run,
        ):
            run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            run_command(["pass", "insert", "-m", "-f", "web/new"])
        assert run.call_args.kwargs["env"]["PASSWORD_STORE_DIR"] == "/env/store"

    def test_explicit_config_wins_over_the_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PASSWORD_STORE_DIR", "/env/store")
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"pass_dir": "/configured/store"}))
        with patch.object(passclip, "CONFIG_PATH", cfg):
            assert load_config()["pass_dir"] == "/configured/store"

    def test_passclip_and_pass_agree_on_the_store(self, tmp_path, monkeypatch):
        """The whole point of exporting it: listings and writes must not split."""
        store = tmp_path / "envstore"
        (store / "web").mkdir(parents=True)
        (store / "web" / "gmail.gpg").write_bytes(b"cipher")
        monkeypatch.setenv("PASSWORD_STORE_DIR", str(store))
        with patch.dict("passclip.CONFIG", {"pass_dir": _default_store_dir()}):
            assert passclip.get_all_entries() == ["web/gmail"]
            with patch("passclip.subprocess.run") as run:
                run.return_value = MagicMock(stdout="", stderr="", returncode=0)
                run_command(["pass", "show", "web/gmail"])
            assert run.call_args.kwargs["env"]["PASSWORD_STORE_DIR"] == str(store)


# ---------------------------------------------------------------------------
# P1 — pre-delete backups must not overwrite one another
# ---------------------------------------------------------------------------


class TestBackupUniqueness:
    COLLIDING = ("x/a/b_c", "x/a_b/c")  # both flatten to 'x_a_b_c'

    def test_colliding_entry_names_get_separate_files(self, tmp_path):
        with (
            patch("passclip.Path.home", return_value=tmp_path),
            patch("passclip.get_entry_raw", side_effect=lambda e: (f"secret-of-{e}\n", None)),
        ):
            paths = [_backup_entry(e)[0] for e in self.COLLIDING]
        assert all(p is not None for p in paths)
        assert paths[0] != paths[1], "the second backup overwrote the first"
        contents = {p.read_text().strip() for p in paths}
        assert contents == {f"secret-of-{e}" for e in self.COLLIDING}

    def test_recursive_delete_keeps_a_backup_per_entry(self, tmp_path):
        entries = list(self.COLLIDING)
        with (
            patch("passclip.Path.home", return_value=tmp_path),
            patch("passclip.get_all_entries", return_value=entries),
            patch("passclip.get_entry_raw", side_effect=lambda e: (f"secret-of-{e}\n", None)),
            patch("passclip.run_command", return_value=("", "", 0)),
        ):
            passclip.cmd_delete("x", force=True)
        saved = sorted((tmp_path / ".config" / "passclip" / "backups").iterdir())
        assert len(saved) == len(entries), "every deleted entry needs its own backup"

    def test_backup_never_truncates_an_existing_file(self, tmp_path):
        backups = tmp_path / ".config" / "passclip" / "backups"
        backups.mkdir(parents=True)
        with (
            patch("passclip.Path.home", return_value=tmp_path),
            patch("passclip.get_entry_raw", return_value=("first\n", None)),
        ):
            first, _ = _backup_entry("web/gmail")
            second, _ = _backup_entry("web/gmail")
        assert first != second
        assert first.read_text() == "first\n"


# ---------------------------------------------------------------------------
# P2 — a cancelled key generation is not a success
# ---------------------------------------------------------------------------


class TestGpgGenExitStatus:
    @pytest.mark.parametrize("rc", [1, 2, 130])
    def test_failure_is_reported(self, rc, capsys):
        passclip._ERROR_SEEN = False
        with patch("passclip.run_command", return_value=("", "", rc)):
            cmd_gpg_gen()
        assert f"status {rc}" in capsys.readouterr().err
        assert passclip._ERROR_SEEN, "main() must turn this into a non-zero exit"

    def test_success_is_silent(self, capsys):
        passclip._ERROR_SEEN = False
        with patch("passclip.run_command", return_value=("", "", 0)):
            cmd_gpg_gen()
        assert capsys.readouterr().err == ""
        assert not passclip._ERROR_SEEN


# ---------------------------------------------------------------------------
# P2 — the destructive shell command must not swallow a mistyped flag
# ---------------------------------------------------------------------------


class TestShellDeleteFlags:
    def test_misspelled_force_is_rejected(self, capsys):
        with patch("passclip.cmd_delete") as delete:
            _shell().do_delete("web/prod --force --forc")
        assert not delete.called, "a typo must not delete the entry"
        assert "unknown flag" in capsys.readouterr().err.lower()

    def test_extra_positional_is_rejected(self, capsys):
        with patch("passclip.cmd_delete") as delete:
            _shell().do_delete("web/prod web/staging")
        assert not delete.called
        assert capsys.readouterr().err

    @pytest.mark.parametrize("flag", ["--force", "-f"])
    def test_both_force_spellings_still_work(self, flag):
        with patch("passclip.cmd_delete") as delete:
            _shell().do_delete(f"web/prod {flag}")
        delete.assert_called_once_with("web/prod", force=True)

    def test_bare_entry_still_prompts(self):
        with patch("passclip.cmd_delete") as delete:
            _shell().do_delete("web/prod")
        delete.assert_called_once_with("web/prod", force=False)
