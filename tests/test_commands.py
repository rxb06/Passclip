"""End-to-end tests for command functions: CSV import flow and vault file handling."""

from unittest.mock import patch

from passclip import VAULT_MAGIC, cmd_import, cmd_import_vault


def _write_csv(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


class TestCmdImport:
    """Full cmd_import flow: auto-detection, wiring to _insert_entry, dry-run."""

    BITWARDEN_CSV = (
        "folder,favorite,type,name,notes,fields,login_uri,login_username,"
        "login_password,login_totp\n"
        'email,,login,Gmail,work account,,https://gmail.com,alice@gmail.com,'
        "hunter2,JBSWY3DPEHPK3PXP\n"
    )

    def test_bitwarden_auto_detect_and_insert(self, tmp_path, capsys):
        path = _write_csv(tmp_path, "export.csv", self.BITWARDEN_CSV)
        with patch("passclip._insert_entry", return_value=(True, "")) as ins, \
                patch("passclip.get_all_entries", return_value=[]):
            cmd_import(path, "auto")
        assert ins.call_count == 1
        entry_path, content = ins.call_args[0]
        assert entry_path == "email/gmail"
        assert content.startswith("hunter2\n")
        assert "username: alice@gmail.com" in content
        assert "otp: JBSWY3DPEHPK3PXP" in content
        out = capsys.readouterr().out
        assert "1 imported" in out

    def test_short_row_does_not_crash(self, tmp_path, capsys):
        """Rows with fewer cells than the header (Excel re-saves) must not abort the import."""
        csv_content = (
            "name,folder,username,password,url,notes\n"
            "Broken,misc\n"  # missing 4 trailing fields -> DictReader fills None
            "Good,misc,bob,secret123,,\n"
        )
        path = _write_csv(tmp_path, "generic.csv", csv_content)
        with patch("passclip._insert_entry", return_value=(True, "")) as ins, \
                patch("passclip.get_all_entries", return_value=[]):
            cmd_import(path, "generic")
        # The broken row is skipped (no password); the good row still imports.
        assert ins.call_count == 1
        assert ins.call_args[0][0] == "misc/good"
        out = capsys.readouterr().out
        assert "1 imported" in out

    def test_dry_run_marks_existing_entries(self, tmp_path, capsys):
        """--dry-run must flag entries that already exist in the store."""
        path = _write_csv(tmp_path, "export.csv", self.BITWARDEN_CSV)
        with patch("passclip._insert_entry", return_value=(True, "")) as ins, \
                patch("passclip.get_all_entries", return_value=["email/gmail"]):
            cmd_import(path, "auto", dry_run=True)
        ins.assert_not_called()  # dry run never writes
        out = capsys.readouterr().out
        assert "email/gmail" in out
        assert "(exists)" in out

    def test_dry_run_new_entry_not_marked(self, tmp_path, capsys):
        path = _write_csv(tmp_path, "export.csv", self.BITWARDEN_CSV)
        with patch("passclip._insert_entry", return_value=(True, "")), \
                patch("passclip.get_all_entries", return_value=["other/entry"]):
            cmd_import(path, "auto", dry_run=True)
        out = capsys.readouterr().out
        assert "(exists)" not in out


class TestImportVaultErrors:
    """Vault file rejection paths."""

    def test_bad_magic_message_references_pcv2(self, tmp_path, capsys):
        """The wrong-magic error must name the real expected header (PCV2, not PCV1)."""
        assert VAULT_MAGIC == b"PCV2"
        vault = tmp_path / "fake.vault"
        vault.write_bytes(b"FAKE" + b"\x00" * 60)
        cmd_import_vault(str(vault))
        out = capsys.readouterr().out
        assert "PCV2" in out
        # PCV1 may be mentioned only to say old vaults are unsupported,
        # never as the expected header.
        assert "Expected magic header 'PCV1'" not in out
