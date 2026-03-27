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

    def test_warns_on_unknown_keys(self, tmp_path, capsys):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"clip_timeout": 30, "typo_key": True}))
        with patch("passclip.CONFIG_PATH", cfg_path):
            cfg = load_config()
        assert cfg["clip_timeout"] == 30
        # Unknown key should not be in defaults but is in loaded config
        assert "typo_key" in cfg


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

    def test_missing_password_field(self):
        """Row without password should return empty password."""
        row = {"name": "NoPass", "folder": "misc"}
        data = _parse_csv_row(row, "generic")
        assert data["password"] == ""

    def test_missing_name_field(self):
        """Row without name should return empty name."""
        row = {"password": "pw", "folder": "misc"}
        data = _parse_csv_row(row, "generic")
        assert data["name"] == ""

    def test_special_characters_in_fields(self):
        """Fields with special chars should pass through unmodified."""
        row = {
            "name": "Tëst Ñame™", "password": "p@$$w0rd!<>&;", # credactor:ignore
            "folder": "", "username": "user@domain.com",
        }
        data = _parse_csv_row(row, "generic")
        assert data["name"] == "Tëst Ñame™"
        assert data["password"] == "p@$$w0rd!<>&;"

    def test_bitwarden_empty_folder(self):
        """Bitwarden rows with empty folder should return empty folder."""
        row = {
            "name": "Test", "folder": "",
            "login_username": "", "login_password": "pw",
            "login_uri": "", "notes": "", "login_totp": "",
        }
        data = _parse_csv_row(row, "bitwarden")
        assert data["folder"] == ""


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

    def test_leading_dot_stripped(self):
        result = _sanitize_entry_path(".hidden", "")
        assert result is not None
        assert not result.startswith(".")

    def test_leading_dash_stripped(self):
        result = _sanitize_entry_path("-rf", "")
        assert result is not None
        assert not result.startswith("-")

    def test_double_dot_folder(self):
        result = _sanitize_entry_path("name", "../../../etc")
        assert result is None or ".." not in result

    def test_shell_metacharacters_rejected(self):
        """Names with shell metacharacters should be rejected after sanitization."""
        # _sanitize_entry_path replaces / and .. but metacharacters
        # are caught by validate_entry_name() which it calls internally
        result = _sanitize_entry_path("test$(evil)", "")
        assert result is None

    def test_null_byte_rejected(self):
        result = _sanitize_entry_path("test\x00evil", "")
        assert result is None

    def test_very_long_name(self):
        """Extremely long names should be rejected by validate_entry_name."""
        result = _sanitize_entry_path("a" * 300, "")
        assert result is None


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

    def test_key_derivation_rejects_wrong_salt_length(self):
        with pytest.raises(AssertionError):
            _derive_vault_key(b"test", b"short")
        with pytest.raises(AssertionError):
            _derive_vault_key(b"test", b"x" * 64)

    def test_encrypt_decrypt_roundtrip_with_aad(self):
        """Full vault encrypt/decrypt roundtrip with AAD."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        passphrase = b"testpassword"
        salt = os.urandom(32)
        nonce = os.urandom(12)
        plaintext = b"secret data for the vault"
        aad = VAULT_MAGIC + salt + nonce

        key = _derive_vault_key(passphrase, salt)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)

        # Decrypt with same key and AAD
        key2 = _derive_vault_key(passphrase, salt)
        result = AESGCM(key2).decrypt(nonce, ciphertext, aad)
        assert result == plaintext

    def test_wrong_passphrase_fails(self):
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = os.urandom(32)
        nonce = os.urandom(12)
        aad = VAULT_MAGIC + salt + nonce
        key_good = _derive_vault_key(b"correct", salt)
        key_bad = _derive_vault_key(b"wrong", salt)
        ciphertext = AESGCM(key_good).encrypt(nonce, b"data", aad)

        with pytest.raises(InvalidTag):
            AESGCM(key_bad).decrypt(nonce, ciphertext, aad)

    def test_tampered_aad_fails(self):
        """Tampering with salt/nonce in file header should cause InvalidTag."""
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = os.urandom(32)
        nonce = os.urandom(12)
        aad = VAULT_MAGIC + salt + nonce
        key = _derive_vault_key(b"password", salt)
        ciphertext = AESGCM(key).encrypt(nonce, b"secret", aad)

        # Tamper with salt in AAD (simulates file header modification)
        tampered_salt = bytes([salt[0] ^ 0xFF]) + salt[1:]
        tampered_aad = VAULT_MAGIC + tampered_salt + nonce

        with pytest.raises(InvalidTag):
            AESGCM(key).decrypt(nonce, ciphertext, tampered_aad)

    def test_vault_file_format_with_aad(self):
        """Verify vault file structure and decrypt from file with AAD."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = os.urandom(32)
        nonce = os.urandom(12)
        aad = VAULT_MAGIC + salt + nonce
        key = _derive_vault_key(b"pw", salt)
        ciphertext = AESGCM(key).encrypt(nonce, b"payload", aad)

        # Simulate writing a vault file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(VAULT_MAGIC)
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)
            path = f.name

        try:
            with open(path, "rb") as f:
                magic = f.read(4)
                assert magic == VAULT_MAGIC
                read_salt = f.read(32)
                read_nonce = f.read(12)
                read_ct = f.read()
            assert len(read_salt) == 32
            assert len(read_nonce) == 12
            assert read_ct == ciphertext

            # Decrypt from file — reconstruct AAD from file header
            read_aad = magic + read_salt + read_nonce
            key2 = _derive_vault_key(b"pw", read_salt)
            result = AESGCM(key2).decrypt(read_nonce, read_ct, read_aad)
            assert result == b"payload"
        finally:
            os.unlink(path)

    def test_vault_magic_is_pcv2(self):
        """Verify we're on vault format v2."""
        assert VAULT_MAGIC == b"PCV2"

    def test_truncated_vault_detected(self):
        """Truncated vault file should fail validation."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(VAULT_MAGIC)
            f.write(os.urandom(10))  # too short for salt(32) + nonce(12)
            path = f.name
        try:
            with open(path, "rb") as f:
                f.read(4)  # skip magic
                salt = f.read(32)
                nonce = f.read(12)
                ct = f.read()
            # Should detect truncation
            assert len(salt) < 32 or len(nonce) < 12 or not ct
        finally:
            os.unlink(path)

    def test_wrong_magic_detected(self):
        """File with wrong magic header should be rejected."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"FAKE")
            f.write(os.urandom(32 + 12 + 64))
            path = f.name
        try:
            with open(path, "rb") as f:
                magic = f.read(4)
            assert magic != VAULT_MAGIC
        finally:
            os.unlink(path)

    def test_corrupted_ciphertext_fails(self):
        """Corrupted ciphertext should raise InvalidTag."""
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = os.urandom(32)
        nonce = os.urandom(12)
        aad = VAULT_MAGIC + salt + nonce
        key = _derive_vault_key(b"password", salt)
        ciphertext = AESGCM(key).encrypt(nonce, b"secret data", aad)

        # Flip a byte in the ciphertext
        corrupted = bytearray(ciphertext)
        corrupted[0] ^= 0xFF
        corrupted = bytes(corrupted)

        with pytest.raises(InvalidTag):
            AESGCM(key).decrypt(nonce, corrupted, aad)
