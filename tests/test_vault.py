"""Vault export/import robustness tests (quality review qM2; security review
M5, L2, M4-partial, L15)."""

import io
import os
import tarfile
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from passclip import (
    VAULT_MAGIC,
    _derive_vault_key,
    cmd_export_vault,
    cmd_get,
    cmd_import,
    cmd_import_vault,
    get_all_entries,
)

PASSPHRASE = "correct-horse-battery!7"  # credactor:ignore - test fixture, not a real secret


def _make_vault(path, passphrase, members):
    """Build a syntactically valid PCV2 vault from raw tar members."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for info, data in members:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    salt = os.urandom(32)
    nonce = os.urandom(12)
    key = _derive_vault_key(passphrase.encode(), salt)
    ciphertext = AESGCM(key).encrypt(nonce, buf.getvalue(), VAULT_MAGIC + salt + nonce)
    path.write_bytes(VAULT_MAGIC + salt + nonce + ciphertext)
    return path


def _file_member(name, data=b"x", mode=0o644):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    return info, data


def _export(store, out_file):
    with patch.dict("passclip.CONFIG", {"pass_dir": str(store)}), \
            patch("passclip.Prompt.ask", side_effect=[PASSPHRASE, PASSPHRASE]):
        cmd_export_vault(str(out_file))


def _import(store, vault_file):
    with patch.dict("passclip.CONFIG", {"pass_dir": str(store)}), \
            patch("passclip.Prompt.ask", side_effect=[PASSPHRASE]):
        cmd_import_vault(str(vault_file), force=True)


class TestVaultRoundtrip:
    """Real export -> import through the actual command functions."""

    def test_roundtrip_default_store_name(self, tmp_path):
        src = tmp_path / "a" / ".password-store"
        (src / "email").mkdir(parents=True)
        (src / "bank.gpg").write_bytes(b"cipher-bank")
        (src / "email" / "work.gpg").write_bytes(b"cipher-work")
        vault = tmp_path / "backup.vault"
        _export(src, vault)
        assert vault.exists()

        dest = tmp_path / "b" / ".password-store"
        dest.parent.mkdir()
        _import(dest, vault)
        assert (dest / "bank.gpg").read_bytes() == b"cipher-bank"
        assert (dest / "email" / "work.gpg").read_bytes() == b"cipher-work"

    def test_roundtrip_custom_pass_dir(self, tmp_path):
        """qM2: restore must land in the configured store, not '.password-store'."""
        src = tmp_path / "a" / ".password-store"
        src.mkdir(parents=True)
        (src / "bank.gpg").write_bytes(b"cipher-bank")
        vault = tmp_path / "backup.vault"
        _export(src, vault)

        dest = tmp_path / "b" / "mystore"
        dest.parent.mkdir()
        _import(dest, vault)
        assert (dest / "bank.gpg").read_bytes() == b"cipher-bank", \
            "restore must populate the configured pass_dir"
        assert not (tmp_path / "b" / ".password-store").exists(), \
            "restore must not create a parallel .password-store"


class TestMaliciousVault:
    """Crafted vaults must abort cleanly without extracting anything."""

    def test_path_traversal_member_aborts(self, tmp_path, capsys):
        vault = _make_vault(tmp_path / "evil.vault", PASSPHRASE,
                            [_file_member("../../evil.txt")])
        store = tmp_path / "deep" / "store"
        store.parent.mkdir()
        _import(store, vault)
        assert "aborted" in capsys.readouterr().out.lower()
        assert not (tmp_path / "evil.txt").exists()

    def test_fifo_member_aborts(self, tmp_path, capsys):
        info = tarfile.TarInfo(".password-store/fifo.gpg")
        info.type = tarfile.FIFOTYPE
        vault = _make_vault(tmp_path / "evil.vault", PASSPHRASE, [(info, None)])
        store = tmp_path / "b" / ".password-store"
        store.parent.mkdir()
        _import(store, vault)
        assert "aborted" in capsys.readouterr().out.lower()
        assert not (store / "fifo.gpg").exists()

    def test_setuid_and_world_writable_modes_clamped(self, tmp_path):
        vault = _make_vault(
            tmp_path / "modes.vault", PASSPHRASE,
            [_file_member(".password-store/sticky.gpg", b"x", mode=0o4777)],
        )
        store = tmp_path / "b" / ".password-store"
        store.parent.mkdir()
        _import(store, vault)
        extracted = store / "sticky.gpg"
        assert extracted.exists()
        mode = extracted.stat().st_mode
        assert mode & 0o4000 == 0, "setuid bit must be stripped"
        assert mode & 0o022 == 0, "group/other write must be stripped"


class TestVaultPassphraseQuality:
    """L2 — refuse trivially short vault passphrases."""

    def test_short_passphrase_refused(self, tmp_path, capsys):
        store = tmp_path / "store"
        store.mkdir()
        (store / "a.gpg").write_bytes(b"x")
        out_file = tmp_path / "backup.vault"
        with patch.dict("passclip.CONFIG", {"pass_dir": str(store)}), \
                patch("passclip.Prompt.ask", side_effect=["short"]):
            cmd_export_vault(str(out_file))
        assert not out_file.exists()
        assert "12" in capsys.readouterr().out


class TestMarkupEscaping:
    """M4 (untrusted-input subset) — imported/external strings render literally."""

    def test_invalid_csv_name_is_escaped(self, tmp_path, capsys):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "name,folder,username,password,url,notes\n"
            '"[red]bad$(x)[/red]",misc,u,pw,,\n'
        )
        with patch("passclip._insert_entry", return_value=(True, "")), \
                patch("passclip.get_all_entries", return_value=[]):
            cmd_import(str(csv_file), "generic")
        out = capsys.readouterr().out
        assert "[red]bad$(x)[/red]" in out, \
            "untrusted CSV name must be shown literally, not parsed as markup"

    def test_field_output_is_raw(self, capsys):
        """--field output must be byte-exact (scripting path), not rich-rendered."""
        content = "pw\nurl: p[/]w-value\n"
        with patch("passclip.get_entry_raw", return_value=(content, None)):
            cmd_get("web/test", field="url")
        assert "p[/]w-value" in capsys.readouterr().out


class TestStoreSourcedNames:
    """L15 — entries whose names could be mistaken for CLI flags are not enumerated."""

    def test_leading_dash_entry_excluded(self, tmp_path):
        store = tmp_path / "store"
        store.mkdir()
        (store / "-evil.gpg").write_bytes(b"x")
        (store / "ok.gpg").write_bytes(b"x")
        with patch.dict("passclip.CONFIG", {"pass_dir": str(store)}):
            entries = get_all_entries()
        assert entries == ["ok"]
