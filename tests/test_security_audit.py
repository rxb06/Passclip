"""Regression tests for the Critical/High audit findings (2026-06-11).

Both tests verify the DEFENSE (malicious input is rejected / no out-of-store
write happens) in a fully isolated sandbox — a tmp HOME and throwaway files.
Nothing real is touched and no exploit is performed; they assert that the
crafted attack input is refused.
"""

import hashlib
import io
import os
import tarfile
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from passclip import (
    VAULT_MAGIC,
    PassShell,
    _derive_vault_key,
    cmd_import_vault,
)

VAULT_PASSPHRASE = "audit-passphrase-1234"  # credactor:ignore - test fixture


def _seal_vault(path, members, passphrase=VAULT_PASSPHRASE):
    """Build a valid PCV2 vault from raw (name, bytes) tar members."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    salt = os.urandom(32)
    nonce = os.urandom(12)
    key = _derive_vault_key(passphrase.encode(), salt)
    ct = AESGCM(key).encrypt(nonce, buf.getvalue(), VAULT_MAGIC + salt + nonce)
    path.write_bytes(VAULT_MAGIC + salt + nonce + ct)
    return path


# ---------------------------------------------------------------------------
# HIGH-1 — vault import must confine writes to the store, not the home dir
# ---------------------------------------------------------------------------


class TestVaultImportContainment:
    def test_member_outside_store_is_rejected(self, tmp_path, capsys):
        """A '.bashrc' member resolves under pass_dir.parent (the sandbox tmp,
        standing in for HOME) but OUTSIDE the store — it must be refused and the
        target file must never be written."""
        pass_dir = tmp_path / ".password-store"  # extract_root == tmp_path
        victim = tmp_path / ".bashrc"
        victim.write_text("ORIGINAL")
        vault = _seal_vault(tmp_path / "evil.vault", [(".bashrc", b"PWNED")])

        with (
            patch.dict("passclip.CONFIG", {"pass_dir": str(pass_dir)}),
            patch("passclip.Prompt.ask", side_effect=[VAULT_PASSPHRASE]),
        ):
            cmd_import_vault(str(vault), force=True)

        out = capsys.readouterr().out.lower()
        assert "abort" in out or "traversal" in out, "import should be aborted"
        assert victim.read_text() == "ORIGINAL", "out-of-store file must be untouched"
        assert not (pass_dir / ".bashrc").exists()

    def test_nested_outside_store_member_rejected(self, tmp_path, capsys):
        """A nested '.gnupg/gpg-agent.conf' member is likewise outside the store."""
        pass_dir = tmp_path / ".password-store"
        vault = _seal_vault(
            tmp_path / "evil.vault",
            [(".gnupg/gpg-agent.conf", b"pinentry-program /evil")],
        )
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": str(pass_dir)}),
            patch("passclip.Prompt.ask", side_effect=[VAULT_PASSPHRASE]),
        ):
            cmd_import_vault(str(vault), force=True)
        assert "abort" in capsys.readouterr().out.lower()
        assert not (tmp_path / ".gnupg").exists()

    def test_legitimate_member_still_restores(self, tmp_path):
        """The tightened check must not break a normal restore: a member under
        '.password-store/' lands correctly inside the store."""
        pass_dir = tmp_path / ".password-store"
        vault = _seal_vault(
            tmp_path / "good.vault",
            [(".password-store/web/test.gpg", b"cipher-bytes")],
        )
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": str(pass_dir)}),
            patch("passclip.Prompt.ask", side_effect=[VAULT_PASSPHRASE]),
        ):
            cmd_import_vault(str(vault), force=True)
        assert (pass_dir / "web" / "test.gpg").read_bytes() == b"cipher-bytes"

    def test_custom_pass_dir_member_outside_store_rejected(self, tmp_path, capsys):
        """With a custom store name, a sibling-directory member must still be
        refused (it resolves under the parent but not under the store)."""
        pass_dir = tmp_path / "mystore"
        sibling = tmp_path / "sibling-evil.txt"
        vault = _seal_vault(tmp_path / "evil.vault", [("sibling-evil.txt", b"x")])
        with (
            patch.dict("passclip.CONFIG", {"pass_dir": str(pass_dir)}),
            patch("passclip.Prompt.ask", side_effect=[VAULT_PASSPHRASE]),
        ):
            cmd_import_vault(str(vault), force=True)
        assert "abort" in capsys.readouterr().out.lower()
        assert not sibling.exists()


# ---------------------------------------------------------------------------
# HIGH-2 — the shell lock must live outside the synced store and not follow
# a symlink planted at its path
# ---------------------------------------------------------------------------


class TestLockFileContainment:
    def test_lock_path_is_in_config_not_store(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        store = tmp_path / ".password-store"
        store.mkdir()
        with patch.dict("passclip.CONFIG", {"pass_dir": str(store)}):
            shell = PassShell()
            try:
                lock = str(shell._lock_path)
                assert "/.config/passclip/" in lock
                assert str(store) not in lock
                assert shell._lock_fd is not None  # acquired cleanly
            finally:
                shell._release_lock()

    def test_symlink_at_lock_path_is_not_followed(self, tmp_path, monkeypatch):
        """If a symlink is planted where the lock opens, the open must refuse to
        follow it (O_NOFOLLOW) — the target file is never truncated."""
        monkeypatch.setenv("HOME", str(tmp_path))
        store = tmp_path / ".password-store"
        store.mkdir()
        victim = tmp_path / "victim"
        victim.write_text("precious-do-not-truncate")

        store_id = hashlib.sha256(str(store.resolve()).encode()).hexdigest()[:16]
        lock_dir = tmp_path / ".config" / "passclip"
        lock_dir.mkdir(parents=True)
        os.chmod(lock_dir, 0o700)
        (lock_dir / f".lock-{store_id}").symlink_to(victim)

        with patch.dict("passclip.CONFIG", {"pass_dir": str(store)}):
            shell = PassShell()  # _acquire_lock must not follow the symlink
            try:
                assert victim.read_text() == "precious-do-not-truncate"
                assert shell._lock_fd is None  # lock not acquired via the symlink
            finally:
                shell._release_lock()
