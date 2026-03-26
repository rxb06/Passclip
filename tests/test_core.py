"""Tests for core functions: config, entry parsing, password strength,
CSV parsing, and vault crypto."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from passclip import (
    DEFAULT_CONFIG,
    VAULT_MAGIC,
    _derive_vault_key,
    _parse_csv_row,
    _sanitize_entry_path,
    format_entry,
    generate_password,
    load_config,
    parse_entry,
    password_strength,
    save_config,
    strength_bar,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Config loading, validation, and persistence."""

    def test_defaults_when_no_file(self, tmp_path):
        fake_path = tmp_path / "nonexistent" / "config.json"
        with patch("passclip.CONFIG_PATH", fake_path):
            cfg = load_config()
        assert cfg == DEFAULT_CONFIG

    def test_merges_with_defaults(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"clip_timeout": 99}))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["clip_timeout"] == 99
        assert cfg["default_password_length"] == DEFAULT_CONFIG["default_password_length"]

    def test_resets_negative_clip_timeout(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"clip_timeout": -5}))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["clip_timeout"] == DEFAULT_CONFIG["clip_timeout"]

    def test_resets_zero_clip_timeout(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"clip_timeout": 0}))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["clip_timeout"] == DEFAULT_CONFIG["clip_timeout"]

    def test_resets_short_password_length(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"default_password_length": 3}))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["default_password_length"] == DEFAULT_CONFIG["default_password_length"]

    def test_resets_invalid_default_mode(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"default_mode": "invalid"}))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["default_mode"] == DEFAULT_CONFIG["default_mode"]

    def test_accepts_valid_config(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({
            "clip_timeout": 60,
            "default_password_length": 24,
            "default_mode": "ls",
        }))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["clip_timeout"] == 60
        assert cfg["default_password_length"] == 24
        assert cfg["default_mode"] == "ls"

    def test_corrupt_json_returns_defaults(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("{not valid json!!!")
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg == DEFAULT_CONFIG

    def test_string_clip_timeout_resets(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"clip_timeout": "not_an_int"}))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["clip_timeout"] == DEFAULT_CONFIG["clip_timeout"]


class TestSaveConfig:
    """Config persistence and file permissions."""

    def test_roundtrip(self, tmp_path):
        cfg_path = tmp_path / "sub" / "config.json"
        with patch("passclip.CONFIG_PATH", cfg_path):
            save_config({"clip_timeout": 77, "pass_dir": "/tmp/store"})
        data = json.loads(cfg_path.read_text())
        assert data["clip_timeout"] == 77

    def test_file_permissions(self, tmp_path):
        cfg_path = tmp_path / "config.json"
        with patch("passclip.CONFIG_PATH", cfg_path):
            save_config(DEFAULT_CONFIG)
        mode = oct(cfg_path.stat().st_mode & 0o777)
        assert mode == "0o600"


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------


class TestParseEntry:
    """Parsing pass entries into dicts."""

    def test_password_only(self):
        assert parse_entry("secret123")["password"] == "secret123"

    def test_full_entry(self):
        content = "MyP@ss\nusername: alice\nurl: https://example.com\nnotes: test"
        data = parse_entry(content)
        assert data["password"] == "MyP@ss"
        assert data["username"] == "alice"
        assert data["url"] == "https://example.com"

    def test_empty_content(self):
        data = parse_entry("")
        assert data["password"] == ""

    def test_notes_without_key_value(self):
        content = "secret\nusername: bob\nsome loose text"
        data = parse_entry(content)
        assert "notes" in data
        assert "loose text" in data["notes"]


class TestFormatEntry:
    """Serializing dicts back to pass entry format."""

    def test_roundtrip(self):
        original = "hunter2\nusername: alice\nemail: a@b.com\nurl: https://x.com\n"
        data = parse_entry(original)
        formatted = format_entry(data)
        reparsed = parse_entry(formatted)
        assert reparsed["password"] == "hunter2"
        assert reparsed["username"] == "alice"
        assert reparsed["email"] == "a@b.com"

    def test_password_only(self):
        result = format_entry({"password": "secret"})
        assert result.startswith("secret\n")

    def test_preserves_otp_field(self):
        data = {"password": "pw", "otp": "otpauth://totp/test?secret=ABC"}
        result = format_entry(data)
        assert "otp: otpauth://" in result


# ---------------------------------------------------------------------------
# Password strength
# ---------------------------------------------------------------------------


class TestPasswordStrength:
    """Password strength scoring."""

    def test_empty(self):
        score, label, color = password_strength("")
        assert score == 0
        assert label == "Empty"

    def test_short_lowercase(self):
        score, _, _ = password_strength("abc")
        assert score <= 1

    def test_strong_password(self):
        score, _, _ = password_strength("C0mpl3x!P@ssw0rd#2024")
        assert score >= 3

    def test_very_strong(self):
        score, label, _ = password_strength("aB3$" * 6)  # 24 chars, all varieties
        assert score == 4
        assert label == "Very Strong"

    def test_long_but_no_variety(self):
        score, _, _ = password_strength("a" * 25)
        assert score < 4  # long but no character variety


class TestStrengthBar:
    """Visual strength bar output."""

    def test_min_score(self):
        bar = strength_bar(0, "red")
        assert "█" in bar
        assert "░" in bar

    def test_max_score(self):
        bar = strength_bar(4, "green")
        assert "░" not in bar


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------


class TestGeneratePassword:
    """Cryptographically secure password generation."""

    def test_default_length(self):
        pw = generate_password()
        assert len(pw) == 20

    def test_custom_length(self):
        pw = generate_password(length=32)
        assert len(pw) == 32

    def test_minimum_enforced(self):
        pw = generate_password(length=3)
        assert len(pw) == 8  # enforced minimum

    def test_has_variety(self):
        pw = generate_password(length=20, symbols=True)
        assert any(c.islower() for c in pw)
        assert any(c.isupper() for c in pw)
        assert any(c.isdigit() for c in pw)

    def test_no_symbols(self):
        pw = generate_password(length=100, symbols=False)
        import string
        assert all(c in string.ascii_letters + string.digits for c in pw)


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


class TestParseCsvRow:
    """CSV row parsing for different password manager formats."""

    def test_bitwarden(self):
        row = {
            "name": "Gmail", "folder": "email",
            "login_username": "alice", "login_password": "pw",
            "login_uri": "https://gmail.com", "notes": "", "login_totp": "",
        }
        data = _parse_csv_row(row, "bitwarden")
        assert data["name"] == "Gmail"
        assert data["username"] == "alice"
        assert data["password"] == "pw"

    def test_lastpass(self):
        row = {
            "name": "GitHub", "grouping": "dev",
            "username": "bob", "password": "secret",
            "url": "https://github.com", "extra": "work account",
        }
        data = _parse_csv_row(row, "lastpass")
        assert data["name"] == "GitHub"
        assert data["folder"] == "dev"
        assert data["notes"] == "work account"

    def test_1password(self):
        row = {
            "title": "AWS", "type": "login",
            "username": "admin", "password": "key123",
            "url": "https://aws.amazon.com",
            "notesplaintext": "", "totp secret key": "ABC123",
        }
        data = _parse_csv_row(row, "1password")
        assert data["name"] == "AWS"
        assert data["otp"] == "ABC123"

    def test_generic(self):
        row = {"name": "Test", "password": "pw", "folder": "misc"}
        data = _parse_csv_row(row, "generic")
        assert data["name"] == "Test"
        assert data["folder"] == "misc"


class TestSanitizeEntryPath:
    """Entry path sanitization for CSV imports."""

    def test_simple(self):
        assert _sanitize_entry_path("Gmail", "email") == "email/gmail"

    def test_no_folder(self):
        assert _sanitize_entry_path("Gmail", "") == "gmail"

    def test_removes_traversal(self):
        result = _sanitize_entry_path("../evil", "folder")
        # Should sanitize ".." to "-"
        assert result is None or ".." not in result

    def test_replaces_slashes(self):
        result = _sanitize_entry_path("a/b", "c/d")
        if result:
            # Original slashes replaced with hyphens, only folder separator remains
            assert result.count("/") <= 1

    def test_empty_name_falls_back_to_unnamed(self):
        result = _sanitize_entry_path("", "")
        assert result == "unnamed"


# ---------------------------------------------------------------------------
# Vault encryption roundtrip
# ---------------------------------------------------------------------------


class TestVaultCrypto:
    """AES-256-GCM vault encryption primitives."""

    def test_key_derivation_deterministic(self):
        salt = os.urandom(32)
        k1 = _derive_vault_key(b"test", salt)
        k2 = _derive_vault_key(b"test", salt)
        assert k1 == k2
        assert len(k1) == 32

    def test_key_derivation_different_salts(self):
        k1 = _derive_vault_key(b"test", os.urandom(32))
        k2 = _derive_vault_key(b"test", os.urandom(32))
        assert k1 != k2

    def test_key_derivation_different_passphrases(self):
        salt = os.urandom(32)
        k1 = _derive_vault_key(b"pass1", salt)
        k2 = _derive_vault_key(b"pass2", salt)
        assert k1 != k2

    def test_encrypt_decrypt_roundtrip(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        passphrase = b"testpassword"
        salt = os.urandom(32)
        nonce = os.urandom(12)
        plaintext = b"secret data for the vault"

        key = _derive_vault_key(passphrase, salt)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

        # Decrypt with same key
        key2 = _derive_vault_key(passphrase, salt)
        result = AESGCM(key2).decrypt(nonce, ciphertext, None)
        assert result == plaintext

    def test_wrong_passphrase_fails(self):
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = os.urandom(32)
        nonce = os.urandom(12)
        key_good = _derive_vault_key(b"correct", salt)
        key_bad = _derive_vault_key(b"wrong", salt)
        ciphertext = AESGCM(key_good).encrypt(nonce, b"data", None)

        with pytest.raises(InvalidTag):
            AESGCM(key_bad).decrypt(nonce, ciphertext, None)

    def test_vault_file_format(self):
        """Verify the vault file structure: magic + salt + nonce + ciphertext."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = os.urandom(32)
        nonce = os.urandom(12)
        key = _derive_vault_key(b"pw", salt)
        ciphertext = AESGCM(key).encrypt(nonce, b"payload", None)

        # Simulate writing a vault file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(VAULT_MAGIC)
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)
            path = f.name

        try:
            with open(path, "rb") as f:
                assert f.read(4) == VAULT_MAGIC
                read_salt = f.read(32)
                read_nonce = f.read(12)
                read_ct = f.read()
            assert len(read_salt) == 32
            assert len(read_nonce) == 12
            assert read_ct == ciphertext

            # Decrypt from file
            key2 = _derive_vault_key(b"pw", read_salt)
            result = AESGCM(key2).decrypt(read_nonce, read_ct, None)
            assert result == b"payload"
        finally:
            os.unlink(path)
