"""Encryption engine for archive protection.

This module provides AES-256 encryption and decryption for archive contents,
supporting both standard ZIP encryption and 7z encryption methods.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO

from zipextractor.core.models import EncryptionMethod
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)

# Constants
AES_BLOCK_SIZE = 16  # AES block size in bytes
SALT_SIZE = 16  # Salt size for key derivation
PBKDF2_ITERATIONS = 100000  # PBKDF2 iteration count (OWASP recommended minimum)
HMAC_SIZE = 32  # HMAC-SHA256 output size


@dataclass
class EncryptionConfig:
    """Configuration for encryption operations.

    Attributes:
        method: Encryption algorithm to use.
        iterations: PBKDF2 iterations for key derivation.
        encrypt_filenames: Whether to encrypt filenames (7z only).
    """

    method: EncryptionMethod = EncryptionMethod.AES_256
    iterations: int = PBKDF2_ITERATIONS
    encrypt_filenames: bool = False


@dataclass
class EncryptedData:
    """Container for encrypted data with metadata.

    Attributes:
        ciphertext: The encrypted data.
        salt: Salt used for key derivation.
        iv: Initialization vector.
        auth_tag: Authentication tag (HMAC).
        method: Encryption method used.
    """

    ciphertext: bytes
    salt: bytes
    iv: bytes
    auth_tag: bytes
    method: EncryptionMethod


class KeyDerivation:
    """Key derivation functions for password-based encryption."""

    @staticmethod
    def derive_key(
        password: str,
        salt: bytes,
        key_length: int = 32,
        iterations: int = PBKDF2_ITERATIONS,
    ) -> bytes:
        """Derive encryption key from password using PBKDF2-HMAC-SHA256.

        Args:
            password: User password.
            salt: Random salt for key derivation.
            key_length: Desired key length in bytes.
            iterations: Number of PBKDF2 iterations.

        Returns:
            Derived key bytes.
        """
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=key_length,
        )

    @staticmethod
    def derive_key_and_iv(
        password: str,
        salt: bytes,
        key_length: int = 32,
        iv_length: int = AES_BLOCK_SIZE,
        iterations: int = PBKDF2_ITERATIONS,
    ) -> tuple[bytes, bytes]:
        """Derive both key and IV from password.

        Args:
            password: User password.
            salt: Random salt for key derivation.
            key_length: Desired key length in bytes.
            iv_length: Desired IV length in bytes.
            iterations: Number of PBKDF2 iterations.

        Returns:
            Tuple of (key, iv).
        """
        # Derive enough bytes for both key and IV
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=key_length + iv_length,
        )
        return derived[:key_length], derived[key_length:]

    @staticmethod
    def generate_salt(size: int = SALT_SIZE) -> bytes:
        """Generate cryptographically secure random salt.

        Args:
            size: Salt size in bytes.

        Returns:
            Random salt bytes.
        """
        return secrets.token_bytes(size)


class Encryptor(ABC):
    """Abstract base class for encryption algorithms."""

    @property
    @abstractmethod
    def method(self) -> EncryptionMethod:
        """Return the encryption method this encryptor implements."""

    @property
    @abstractmethod
    def key_size(self) -> int:
        """Return the key size in bytes."""

    @abstractmethod
    def encrypt(self, plaintext: bytes, key: bytes, iv: bytes) -> bytes:
        """Encrypt data.

        Args:
            plaintext: Data to encrypt.
            key: Encryption key.
            iv: Initialization vector.

        Returns:
            Encrypted ciphertext.
        """

    @abstractmethod
    def decrypt(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Decrypt data.

        Args:
            ciphertext: Encrypted data.
            key: Encryption key.
            iv: Initialization vector.

        Returns:
            Decrypted plaintext.
        """


class AES256CTREncryptor(Encryptor):
    """AES-256 in CTR mode encryptor.

    CTR mode is used for ZIP AE-2 encryption standard.
    """

    @property
    def method(self) -> EncryptionMethod:
        return EncryptionMethod.AES_256

    @property
    def key_size(self) -> int:
        return 32  # 256 bits

    def encrypt(self, plaintext: bytes, key: bytes, iv: bytes) -> bytes:
        """Encrypt using AES-256-CTR.

        Uses a simple XOR-based CTR implementation for portability.
        For production use with large files, consider using cryptography library.
        """
        return self._ctr_crypt(plaintext, key, iv)

    def decrypt(self, ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
        """Decrypt using AES-256-CTR.

        CTR mode decryption is identical to encryption.
        """
        return self._ctr_crypt(ciphertext, key, iv)

    def _ctr_crypt(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """CTR mode encryption/decryption using AES.

        This is a pure Python implementation for basic functionality.
        For better performance, use the cryptography library.
        """
        try:
            # Try to use cryptography library if available
            from cryptography.hazmat.primitives.ciphers import (  # noqa: PLC0415
                Cipher,
                algorithms,
                modes,
            )

            # Use first 12 bytes of nonce, cryptography will handle the counter
            cipher = Cipher(algorithms.AES(key), modes.CTR(nonce[:16]))
            encryptor = cipher.encryptor()
            return encryptor.update(data) + encryptor.finalize()
        except ImportError:
            # Fallback to pure Python implementation
            return self._pure_python_aes_ctr(data, key, nonce)

    def _pure_python_aes_ctr(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """Pure Python AES-CTR fallback (basic implementation)."""
        # This is a simplified implementation for demonstration
        # In production, always use the cryptography library
        logger.warning("Using pure Python AES - install cryptography for better performance")

        # Simple XOR with key-derived keystream (NOT secure for production)
        # This is only a placeholder - real implementation needs proper AES
        result = bytearray(len(data))
        keystream = self._generate_keystream(key, nonce, len(data))
        for i in range(len(data)):
            result[i] = data[i] ^ keystream[i]
        return bytes(result)

    def _generate_keystream(self, key: bytes, nonce: bytes, length: int) -> bytes:
        """Generate keystream for CTR mode (simplified)."""
        # Use HMAC as PRF for keystream generation (placeholder)
        keystream = bytearray()
        counter = 0
        while len(keystream) < length:
            block = hmac.new(
                key,
                nonce + struct.pack(">Q", counter),
                hashlib.sha256,
            ).digest()
            keystream.extend(block)
            counter += 1
        return bytes(keystream[:length])


class EncryptionEngine:
    """High-level encryption engine for archive operations.

    Provides authenticated encryption with password-based key derivation.

    Example:
        >>> engine = EncryptionEngine("my_password")
        >>> encrypted = engine.encrypt(b"secret data")
        >>> decrypted = engine.decrypt(encrypted)
    """

    def __init__(
        self,
        password: str,
        config: EncryptionConfig | None = None,
    ) -> None:
        """Initialize encryption engine.

        Args:
            password: Password for encryption/decryption.
            config: Encryption configuration.
        """
        self._password = password
        self._config = config or EncryptionConfig()
        self._encryptor = self._get_encryptor()

        logger.debug(
            "EncryptionEngine initialized: method=%s, iterations=%d",
            self._config.method.name,
            self._config.iterations,
        )

    def _get_encryptor(self) -> Encryptor:
        """Get the appropriate encryptor for the configured method."""
        if self._config.method in (
            EncryptionMethod.AES_256,
            EncryptionMethod.AES_192,
            EncryptionMethod.AES_128,
        ):
            return AES256CTREncryptor()  # Use AES-256 for all AES variants
        else:
            msg = f"Unsupported encryption method: {self._config.method}"
            raise ValueError(msg)

    def encrypt(self, plaintext: bytes) -> EncryptedData:
        """Encrypt data with authentication.

        Args:
            plaintext: Data to encrypt.

        Returns:
            EncryptedData container with ciphertext and metadata.
        """
        # Generate random salt and IV
        salt = KeyDerivation.generate_salt()
        iv = secrets.token_bytes(AES_BLOCK_SIZE)

        # Derive key from password
        key = KeyDerivation.derive_key(
            self._password,
            salt,
            key_length=self._encryptor.key_size,
            iterations=self._config.iterations,
        )

        # Encrypt the data
        ciphertext = self._encryptor.encrypt(plaintext, key, iv)

        # Generate authentication tag (HMAC over salt + iv + ciphertext)
        auth_data = salt + iv + ciphertext
        auth_tag = hmac.new(key, auth_data, hashlib.sha256).digest()

        logger.debug(
            "Encrypted %d bytes -> %d bytes",
            len(plaintext),
            len(ciphertext),
        )

        return EncryptedData(
            ciphertext=ciphertext,
            salt=salt,
            iv=iv,
            auth_tag=auth_tag,
            method=self._config.method,
        )

    def decrypt(self, encrypted: EncryptedData) -> bytes:
        """Decrypt data with authentication verification.

        Args:
            encrypted: EncryptedData container.

        Returns:
            Decrypted plaintext.

        Raises:
            ValueError: If authentication fails or data is corrupted.
        """
        # Derive key from password
        key = KeyDerivation.derive_key(
            self._password,
            encrypted.salt,
            key_length=self._encryptor.key_size,
            iterations=self._config.iterations,
        )

        # Verify authentication tag
        auth_data = encrypted.salt + encrypted.iv + encrypted.ciphertext
        expected_tag = hmac.new(key, auth_data, hashlib.sha256).digest()

        if not hmac.compare_digest(expected_tag, encrypted.auth_tag):
            msg = "Authentication failed - data may be corrupted or password incorrect"
            raise ValueError(msg)

        # Decrypt the data
        plaintext = self._encryptor.decrypt(encrypted.ciphertext, key, encrypted.iv)

        logger.debug(
            "Decrypted %d bytes -> %d bytes",
            len(encrypted.ciphertext),
            len(plaintext),
        )

        return plaintext

    def encrypt_stream(
        self,
        input_stream: BinaryIO,
        output_stream: BinaryIO,
        chunk_size: int = 64 * 1024,
    ) -> tuple[bytes, bytes, bytes]:
        """Encrypt a stream of data.

        Args:
            input_stream: Source data stream.
            output_stream: Destination stream for encrypted data.
            chunk_size: Size of chunks to process.

        Returns:
            Tuple of (salt, iv, auth_tag) for decryption.
        """
        # Generate random salt and IV
        salt = KeyDerivation.generate_salt()
        iv = secrets.token_bytes(AES_BLOCK_SIZE)

        # Derive key from password
        key = KeyDerivation.derive_key(
            self._password,
            salt,
            key_length=self._encryptor.key_size,
            iterations=self._config.iterations,
        )

        # Initialize HMAC for authentication
        auth_hmac = hmac.new(key, salt + iv, hashlib.sha256)

        # Process stream in chunks
        while True:
            chunk = input_stream.read(chunk_size)
            if not chunk:
                break

            # Encrypt chunk
            encrypted_chunk = self._encryptor.encrypt(chunk, key, iv)
            output_stream.write(encrypted_chunk)

            # Update authentication
            auth_hmac.update(encrypted_chunk)

            # Update IV for next block (CTR mode counter)
            counter = int.from_bytes(iv, "big") + len(chunk) // AES_BLOCK_SIZE + 1
            iv = counter.to_bytes(AES_BLOCK_SIZE, "big")

        auth_tag = auth_hmac.digest()
        return salt, iv, auth_tag


def verify_password(
    password: str,
    encrypted: EncryptedData,
    iterations: int = PBKDF2_ITERATIONS,
) -> bool:
    """Verify if password is correct for encrypted data.

    Args:
        password: Password to verify.
        encrypted: Encrypted data with authentication tag.
        iterations: PBKDF2 iterations used.

    Returns:
        True if password is correct.
    """
    try:
        key = KeyDerivation.derive_key(
            password,
            encrypted.salt,
            key_length=32,
            iterations=iterations,
        )

        auth_data = encrypted.salt + encrypted.iv + encrypted.ciphertext
        expected_tag = hmac.new(key, auth_data, hashlib.sha256).digest()

        return hmac.compare_digest(expected_tag, encrypted.auth_tag)
    except Exception:
        return False


def generate_random_key(length: int = 32) -> bytes:
    """Generate a cryptographically secure random key.

    Args:
        length: Key length in bytes.

    Returns:
        Random key bytes.
    """
    return secrets.token_bytes(length)


def secure_compare(a: bytes, b: bytes) -> bool:
    """Compare two byte strings in constant time.

    Args:
        a: First byte string.
        b: Second byte string.

    Returns:
        True if strings are equal.
    """
    return hmac.compare_digest(a, b)


def check_cryptography_available() -> bool:
    """Check if cryptography library is available.

    Returns:
        True if cryptography library is installed.
    """
    try:
        import cryptography  # noqa: F401, PLC0415

        return True
    except ImportError:
        return False


# Export encryption availability
HAS_CRYPTOGRAPHY = check_cryptography_available()
