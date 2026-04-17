"""Tests for encryption module."""

from __future__ import annotations

import pytest

from zipextractor.core.encryption import (
    AES256CTREncryptor,
    EncryptedData,
    EncryptionConfig,
    EncryptionEngine,
    KeyDerivation,
    check_cryptography_available,
    generate_random_key,
    secure_compare,
    verify_password,
)
from zipextractor.core.models import EncryptionMethod


class TestKeyDerivation:
    """Tests for KeyDerivation class."""

    def test_derive_key_produces_correct_length(self) -> None:
        """Test that derive_key produces key of correct length."""
        salt = KeyDerivation.generate_salt()
        key = KeyDerivation.derive_key("password", salt, key_length=32)
        assert len(key) == 32

    def test_derive_key_produces_different_keys_for_different_salts(self) -> None:
        """Test that different salts produce different keys."""
        salt1 = KeyDerivation.generate_salt()
        salt2 = KeyDerivation.generate_salt()
        key1 = KeyDerivation.derive_key("password", salt1)
        key2 = KeyDerivation.derive_key("password", salt2)
        assert key1 != key2

    def test_derive_key_is_deterministic(self) -> None:
        """Test that same password and salt produce same key."""
        salt = b"fixed_salt_12345"
        key1 = KeyDerivation.derive_key("password", salt)
        key2 = KeyDerivation.derive_key("password", salt)
        assert key1 == key2

    def test_derive_key_different_passwords_produce_different_keys(self) -> None:
        """Test that different passwords produce different keys."""
        salt = KeyDerivation.generate_salt()
        key1 = KeyDerivation.derive_key("password1", salt)
        key2 = KeyDerivation.derive_key("password2", salt)
        assert key1 != key2

    def test_derive_key_and_iv(self) -> None:
        """Test derive_key_and_iv returns both key and IV."""
        salt = KeyDerivation.generate_salt()
        key, iv = KeyDerivation.derive_key_and_iv("password", salt)
        assert len(key) == 32
        assert len(iv) == 16

    def test_derive_key_and_iv_custom_lengths(self) -> None:
        """Test derive_key_and_iv with custom lengths."""
        salt = KeyDerivation.generate_salt()
        key, iv = KeyDerivation.derive_key_and_iv(
            "password", salt, key_length=24, iv_length=12
        )
        assert len(key) == 24
        assert len(iv) == 12

    def test_generate_salt_produces_correct_length(self) -> None:
        """Test that generate_salt produces salt of correct length."""
        salt = KeyDerivation.generate_salt(16)
        assert len(salt) == 16

    def test_generate_salt_produces_random_bytes(self) -> None:
        """Test that generate_salt produces different values."""
        salt1 = KeyDerivation.generate_salt()
        salt2 = KeyDerivation.generate_salt()
        assert salt1 != salt2


class TestAES256CTREncryptor:
    """Tests for AES256CTREncryptor class."""

    def test_method_returns_aes_256(self) -> None:
        """Test that method property returns AES_256."""
        encryptor = AES256CTREncryptor()
        assert encryptor.method == EncryptionMethod.AES_256

    def test_key_size_is_32(self) -> None:
        """Test that key_size is 32 bytes."""
        encryptor = AES256CTREncryptor()
        assert encryptor.key_size == 32

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that encrypt then decrypt returns original data."""
        encryptor = AES256CTREncryptor()
        key = generate_random_key(32)
        iv = generate_random_key(16)
        plaintext = b"Hello, World! This is a test message."

        ciphertext = encryptor.encrypt(plaintext, key, iv)
        decrypted = encryptor.decrypt(ciphertext, key, iv)

        assert decrypted == plaintext

    def test_encrypt_produces_different_output_for_different_ivs(self) -> None:
        """Test that different IVs produce different ciphertexts."""
        encryptor = AES256CTREncryptor()
        key = generate_random_key(32)
        iv1 = generate_random_key(16)
        iv2 = generate_random_key(16)
        plaintext = b"Test message"

        ciphertext1 = encryptor.encrypt(plaintext, key, iv1)
        ciphertext2 = encryptor.encrypt(plaintext, key, iv2)

        assert ciphertext1 != ciphertext2

    def test_encrypt_produces_same_length_output(self) -> None:
        """Test that ciphertext has same length as plaintext in CTR mode."""
        encryptor = AES256CTREncryptor()
        key = generate_random_key(32)
        iv = generate_random_key(16)
        plaintext = b"0" * 100

        ciphertext = encryptor.encrypt(plaintext, key, iv)

        assert len(ciphertext) == len(plaintext)

    def test_encrypt_empty_data(self) -> None:
        """Test encrypting empty data."""
        encryptor = AES256CTREncryptor()
        key = generate_random_key(32)
        iv = generate_random_key(16)

        ciphertext = encryptor.encrypt(b"", key, iv)
        decrypted = encryptor.decrypt(ciphertext, key, iv)

        assert decrypted == b""

    def test_encrypt_large_data(self) -> None:
        """Test encrypting large data."""
        encryptor = AES256CTREncryptor()
        key = generate_random_key(32)
        iv = generate_random_key(16)
        plaintext = b"X" * 1000000  # 1MB

        ciphertext = encryptor.encrypt(plaintext, key, iv)
        decrypted = encryptor.decrypt(ciphertext, key, iv)

        assert decrypted == plaintext


class TestEncryptionConfig:
    """Tests for EncryptionConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = EncryptionConfig()
        assert config.method == EncryptionMethod.AES_256
        assert config.iterations == 100000
        assert config.encrypt_filenames is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = EncryptionConfig(
            method=EncryptionMethod.AES_128,
            iterations=200000,
            encrypt_filenames=True,
        )
        assert config.method == EncryptionMethod.AES_128
        assert config.iterations == 200000
        assert config.encrypt_filenames is True


class TestEncryptedData:
    """Tests for EncryptedData dataclass."""

    def test_create_encrypted_data(self) -> None:
        """Test creating EncryptedData instance."""
        data = EncryptedData(
            ciphertext=b"encrypted",
            salt=b"salt1234567890ab",
            iv=b"iv12345678901234",
            auth_tag=b"tag12345678901234567890123456789a",
            method=EncryptionMethod.AES_256,
        )
        assert data.ciphertext == b"encrypted"
        assert data.salt == b"salt1234567890ab"
        assert data.iv == b"iv12345678901234"
        assert data.method == EncryptionMethod.AES_256


class TestEncryptionEngine:
    """Tests for EncryptionEngine class."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test full encryption/decryption cycle."""
        engine = EncryptionEngine("test_password")
        plaintext = b"Secret message that needs protection."

        encrypted = engine.encrypt(plaintext)
        decrypted = engine.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_produces_encrypted_data(self) -> None:
        """Test that encrypt returns EncryptedData with all fields."""
        engine = EncryptionEngine("password")
        plaintext = b"test"

        encrypted = engine.encrypt(plaintext)

        assert encrypted.ciphertext is not None
        assert len(encrypted.salt) == 16
        assert len(encrypted.iv) == 16
        assert len(encrypted.auth_tag) == 32
        assert encrypted.method == EncryptionMethod.AES_256

    def test_decrypt_with_wrong_password_fails(self) -> None:
        """Test that decryption with wrong password fails."""
        engine1 = EncryptionEngine("correct_password")
        engine2 = EncryptionEngine("wrong_password")
        plaintext = b"Secret message"

        encrypted = engine1.encrypt(plaintext)

        with pytest.raises(ValueError, match="Authentication failed"):
            engine2.decrypt(encrypted)

    def test_tampering_detected(self) -> None:
        """Test that data tampering is detected."""
        engine = EncryptionEngine("password")
        plaintext = b"Original message"

        encrypted = engine.encrypt(plaintext)
        # Tamper with ciphertext
        tampered = EncryptedData(
            ciphertext=b"tampered" + encrypted.ciphertext[8:],
            salt=encrypted.salt,
            iv=encrypted.iv,
            auth_tag=encrypted.auth_tag,
            method=encrypted.method,
        )

        with pytest.raises(ValueError, match="Authentication failed"):
            engine.decrypt(tampered)

    def test_encrypt_with_custom_config(self) -> None:
        """Test encryption with custom configuration."""
        config = EncryptionConfig(iterations=50000)
        engine = EncryptionEngine("password", config)
        plaintext = b"test"

        encrypted = engine.encrypt(plaintext)
        decrypted = engine.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_empty_data(self) -> None:
        """Test encrypting empty data."""
        engine = EncryptionEngine("password")

        encrypted = engine.encrypt(b"")
        decrypted = engine.decrypt(encrypted)

        assert decrypted == b""

    def test_encrypt_large_data(self) -> None:
        """Test encrypting large data."""
        engine = EncryptionEngine("password")
        plaintext = b"X" * 100000  # 100KB

        encrypted = engine.encrypt(plaintext)
        decrypted = engine.decrypt(encrypted)

        assert decrypted == plaintext

    def test_same_plaintext_different_ciphertext(self) -> None:
        """Test that same plaintext produces different ciphertext each time."""
        engine = EncryptionEngine("password")
        plaintext = b"test message"

        encrypted1 = engine.encrypt(plaintext)
        encrypted2 = engine.encrypt(plaintext)

        # Salt and IV should be different
        assert encrypted1.salt != encrypted2.salt
        assert encrypted1.iv != encrypted2.iv
        assert encrypted1.ciphertext != encrypted2.ciphertext


class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_correct_password_returns_true(self) -> None:
        """Test that correct password returns True."""
        engine = EncryptionEngine("correct_password")
        encrypted = engine.encrypt(b"test")

        result = verify_password("correct_password", encrypted)

        assert result is True

    def test_wrong_password_returns_false(self) -> None:
        """Test that wrong password returns False."""
        engine = EncryptionEngine("correct_password")
        encrypted = engine.encrypt(b"test")

        result = verify_password("wrong_password", encrypted)

        assert result is False

    def test_empty_password(self) -> None:
        """Test with empty password."""
        engine = EncryptionEngine("")
        encrypted = engine.encrypt(b"test")

        assert verify_password("", encrypted) is True
        assert verify_password("not_empty", encrypted) is False


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_generate_random_key_length(self) -> None:
        """Test generate_random_key produces correct length."""
        key = generate_random_key(32)
        assert len(key) == 32

    def test_generate_random_key_randomness(self) -> None:
        """Test generate_random_key produces unique values."""
        key1 = generate_random_key(32)
        key2 = generate_random_key(32)
        assert key1 != key2

    def test_secure_compare_equal(self) -> None:
        """Test secure_compare with equal values."""
        assert secure_compare(b"test", b"test") is True

    def test_secure_compare_not_equal(self) -> None:
        """Test secure_compare with different values."""
        assert secure_compare(b"test1", b"test2") is False

    def test_secure_compare_different_lengths(self) -> None:
        """Test secure_compare with different length values."""
        assert secure_compare(b"short", b"longer_value") is False

    def test_check_cryptography_available(self) -> None:
        """Test check_cryptography_available returns boolean."""
        result = check_cryptography_available()
        assert isinstance(result, bool)
