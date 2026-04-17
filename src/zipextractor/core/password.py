"""Password handling utilities for secure archive operations.

This module provides password strength validation, secure input handling,
and session-based password caching.
"""

from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass
from enum import Enum, auto
from typing import ClassVar

from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class PasswordStrength(Enum):
    """Password strength levels."""

    VERY_WEAK = auto()
    WEAK = auto()
    FAIR = auto()
    STRONG = auto()
    VERY_STRONG = auto()


@dataclass
class PasswordAnalysis:
    """Result of password strength analysis.

    Attributes:
        strength: Overall strength level.
        score: Numeric score (0-100).
        issues: List of issues found with the password.
        suggestions: List of suggestions to improve the password.
    """

    strength: PasswordStrength
    score: int
    issues: list[str]
    suggestions: list[str]

    @property
    def is_acceptable(self) -> bool:
        """Check if password meets minimum requirements."""
        return self.strength.value >= PasswordStrength.FAIR.value


class PasswordValidator:
    """Validates password strength and quality.

    Checks for:
    - Minimum length
    - Character variety (uppercase, lowercase, digits, symbols)
    - Common patterns and sequences
    - Dictionary words (basic check)
    """

    # Minimum requirements
    MIN_LENGTH = 8
    RECOMMENDED_LENGTH = 12

    # Common weak passwords to reject
    COMMON_PASSWORDS = frozenset([
        "password", "123456", "12345678", "qwerty", "abc123",
        "password1", "letmein", "welcome", "admin", "login",
        "passw0rd", "master", "dragon", "shadow", "michael",
        "jennifer", "123456789", "password123", "iloveyou",
    ])

    # Common keyboard patterns
    KEYBOARD_PATTERNS: ClassVar[list[str]] = [
        "qwerty", "asdfgh", "zxcvbn", "qazwsx",
        "123456", "654321", "abcdef", "fedcba",
    ]

    def analyze(self, password: str) -> PasswordAnalysis:  # noqa: PLR0912, PLR0915
        """Analyze password strength.

        Args:
            password: Password to analyze.

        Returns:
            PasswordAnalysis with strength assessment.
        """
        issues: list[str] = []
        suggestions: list[str] = []
        score = 0

        # Length check
        length = len(password)
        if length == 0:
            return PasswordAnalysis(
                strength=PasswordStrength.VERY_WEAK,
                score=0,
                issues=["Password is empty"],
                suggestions=["Enter a password"],
            )

        if length < self.MIN_LENGTH:
            issues.append(f"Password is too short (minimum {self.MIN_LENGTH} characters)")
            suggestions.append(f"Use at least {self.MIN_LENGTH} characters")
        elif length < self.RECOMMENDED_LENGTH:
            suggestions.append(f"Consider using {self.RECOMMENDED_LENGTH}+ characters")
            score += 15
        else:
            score += 25

        # Bonus for extra length
        score += min(15, (length - self.MIN_LENGTH) * 2)

        # Character variety
        has_lower = bool(re.search(r"[a-z]", password))
        has_upper = bool(re.search(r"[A-Z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_symbol = bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password))

        variety_count = sum([has_lower, has_upper, has_digit, has_symbol])

        if not has_lower:
            suggestions.append("Add lowercase letters")
        else:
            score += 10

        if not has_upper:
            suggestions.append("Add uppercase letters")
        else:
            score += 10

        if not has_digit:
            suggestions.append("Add numbers")
        else:
            score += 10

        if not has_symbol:
            suggestions.append("Add special characters (!@#$%^&*)")
        else:
            score += 15

        # Bonus for variety
        if variety_count >= 3:
            score += 10
        if variety_count == 4:
            score += 5

        # Check for common passwords
        if password.lower() in self.COMMON_PASSWORDS:
            issues.append("Password is too common")
            score = max(0, score - 40)

        # Check for keyboard patterns
        lower_pass = password.lower()
        for pattern in self.KEYBOARD_PATTERNS:
            if pattern in lower_pass:
                issues.append("Contains keyboard pattern")
                score = max(0, score - 15)
                break

        # Check for repeated characters
        if re.search(r"(.)\1{2,}", password):
            issues.append("Contains repeated characters")
            score = max(0, score - 10)

        # Check for sequential characters
        if self._has_sequential_chars(password):
            issues.append("Contains sequential characters")
            score = max(0, score - 10)

        # Determine strength level
        score = min(100, max(0, score))

        if score < 20:
            strength = PasswordStrength.VERY_WEAK
        elif score < 40:
            strength = PasswordStrength.WEAK
        elif score < 60:
            strength = PasswordStrength.FAIR
        elif score < 80:
            strength = PasswordStrength.STRONG
        else:
            strength = PasswordStrength.VERY_STRONG

        return PasswordAnalysis(
            strength=strength,
            score=score,
            issues=issues,
            suggestions=suggestions,
        )

    def _has_sequential_chars(self, password: str) -> bool:
        """Check for sequential characters (abc, 123, etc.)."""
        for i in range(len(password) - 2):
            c1, c2, c3 = ord(password[i]), ord(password[i + 1]), ord(password[i + 2])
            # Check ascending
            if c2 == c1 + 1 and c3 == c2 + 1:
                return True
            # Check descending
            if c2 == c1 - 1 and c3 == c2 - 1:
                return True
        return False

    def is_valid(
        self, password: str, min_strength: PasswordStrength = PasswordStrength.FAIR
    ) -> bool:
        """Check if password meets minimum strength requirement.

        Args:
            password: Password to check.
            min_strength: Minimum required strength level.

        Returns:
            True if password meets the requirement.
        """
        analysis = self.analyze(password)
        return analysis.strength.value >= min_strength.value


class PasswordGenerator:
    """Generates secure random passwords."""

    # Character sets
    LOWERCASE = string.ascii_lowercase
    UPPERCASE = string.ascii_uppercase
    DIGITS = string.digits
    SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Ambiguous characters to exclude for readability
    AMBIGUOUS = "l1IO0"

    def generate(  # noqa: PLR0912
        self,
        length: int = 16,
        include_uppercase: bool = True,
        include_digits: bool = True,
        include_symbols: bool = True,
        exclude_ambiguous: bool = True,
    ) -> str:
        """Generate a secure random password.

        Args:
            length: Password length.
            include_uppercase: Include uppercase letters.
            include_digits: Include digits.
            include_symbols: Include special symbols.
            exclude_ambiguous: Exclude ambiguous characters (l, 1, I, O, 0).

        Returns:
            Generated password string.
        """
        # Build character set
        chars = self.LOWERCASE

        if include_uppercase:
            chars += self.UPPERCASE
        if include_digits:
            chars += self.DIGITS
        if include_symbols:
            chars += self.SYMBOLS

        if exclude_ambiguous:
            chars = "".join(c for c in chars if c not in self.AMBIGUOUS)

        if not chars:
            chars = self.LOWERCASE

        # Generate password ensuring variety
        password = []

        # Ensure at least one of each required type
        if include_uppercase:
            if exclude_ambiguous:
                upper_chars = "".join(c for c in self.UPPERCASE if c not in self.AMBIGUOUS)
            else:
                upper_chars = self.UPPERCASE
            if upper_chars:
                password.append(secrets.choice(upper_chars))

        if include_digits:
            if exclude_ambiguous:
                digit_chars = "".join(c for c in self.DIGITS if c not in self.AMBIGUOUS)
            else:
                digit_chars = self.DIGITS
            if digit_chars:
                password.append(secrets.choice(digit_chars))

        if include_symbols:
            password.append(secrets.choice(self.SYMBOLS))

        # Add lowercase
        if exclude_ambiguous:
            lower_chars = "".join(c for c in self.LOWERCASE if c not in self.AMBIGUOUS)
        else:
            lower_chars = self.LOWERCASE
        if lower_chars:
            password.append(secrets.choice(lower_chars))

        # Fill remaining length
        while len(password) < length:
            password.append(secrets.choice(chars))

        # Shuffle to randomize order
        password_list = list(password)
        for i in range(len(password_list) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            password_list[i], password_list[j] = password_list[j], password_list[i]

        return "".join(password_list)

    def generate_passphrase(
        self,
        word_count: int = 4,
        separator: str = "-",
        capitalize: bool = True,
    ) -> str:
        """Generate a memorable passphrase.

        Args:
            word_count: Number of words in passphrase.
            separator: Character between words.
            capitalize: Capitalize first letter of each word.

        Returns:
            Generated passphrase.
        """
        # Simple word list (subset for demo - in production use full word list)
        words = [
            "apple", "banana", "cherry", "dragon", "eagle", "forest",
            "garden", "harbor", "island", "jungle", "kitchen", "lemon",
            "mountain", "nature", "ocean", "planet", "queen", "river",
            "sunset", "thunder", "umbrella", "village", "winter", "yellow",
            "zebra", "anchor", "bridge", "castle", "dolphin", "elephant",
            "falcon", "glacier", "horizon", "jasmine", "kingdom", "lantern",
            "marble", "nectar", "orange", "pyramid", "quantum", "rainbow",
            "silver", "temple", "unicorn", "violet", "whisper", "xylophone",
        ]

        selected = [secrets.choice(words) for _ in range(word_count)]

        if capitalize:
            selected = [w.capitalize() for w in selected]

        return separator.join(selected)


class PasswordCache:
    """Session-based password cache for repeated operations.

    Stores passwords in memory for the duration of the session,
    avoiding repeated password prompts for batch operations.

    Note: Passwords are stored in plain text in memory. This is
    acceptable for session caching but should be cleared on logout.
    """

    def __init__(self) -> None:
        """Initialize password cache."""
        self._cache: dict[str, str] = {}

    def store(self, archive_path: str, password: str) -> None:
        """Store password for an archive.

        Args:
            archive_path: Path to the archive.
            password: Password to cache.
        """
        self._cache[archive_path] = password
        logger.debug("Cached password for: %s", archive_path)

    def get(self, archive_path: str) -> str | None:
        """Get cached password for an archive.

        Args:
            archive_path: Path to the archive.

        Returns:
            Cached password or None if not found.
        """
        return self._cache.get(archive_path)

    def remove(self, archive_path: str) -> None:
        """Remove cached password for an archive.

        Args:
            archive_path: Path to the archive.
        """
        if archive_path in self._cache:
            del self._cache[archive_path]
            logger.debug("Removed cached password for: %s", archive_path)

    def clear(self) -> None:
        """Clear all cached passwords."""
        self._cache.clear()
        logger.debug("Password cache cleared")

    def has(self, archive_path: str) -> bool:
        """Check if password is cached for an archive.

        Args:
            archive_path: Path to the archive.

        Returns:
            True if password is cached.
        """
        return archive_path in self._cache


# Global password cache instance
_password_cache = PasswordCache()


def get_password_cache() -> PasswordCache:
    """Get the global password cache instance.

    Returns:
        PasswordCache singleton.
    """
    return _password_cache


def clear_password_cache() -> None:
    """Clear the global password cache."""
    _password_cache.clear()


def mask_password(password: str, show_length: bool = True) -> str:
    """Mask password for display.

    Args:
        password: Password to mask.
        show_length: Whether to indicate password length.

    Returns:
        Masked password string.
    """
    if show_length:
        return "*" * len(password)
    return "****"


def get_password_strength_label(strength: PasswordStrength) -> str:
    """Get human-readable label for password strength.

    Args:
        strength: Password strength level.

    Returns:
        Human-readable strength label.
    """
    labels = {
        PasswordStrength.VERY_WEAK: "Very Weak",
        PasswordStrength.WEAK: "Weak",
        PasswordStrength.FAIR: "Fair",
        PasswordStrength.STRONG: "Strong",
        PasswordStrength.VERY_STRONG: "Very Strong",
    }
    return labels.get(strength, "Unknown")


def get_password_strength_color(strength: PasswordStrength) -> str:
    """Get color code for password strength visualization.

    Args:
        strength: Password strength level.

    Returns:
        Color code string (CSS-compatible).
    """
    colors = {
        PasswordStrength.VERY_WEAK: "#dc3545",  # Red
        PasswordStrength.WEAK: "#fd7e14",  # Orange
        PasswordStrength.FAIR: "#ffc107",  # Yellow
        PasswordStrength.STRONG: "#28a745",  # Green
        PasswordStrength.VERY_STRONG: "#20c997",  # Teal
    }
    return colors.get(strength, "#6c757d")  # Gray default


# Create default instances
default_validator = PasswordValidator()
default_generator = PasswordGenerator()


def validate_password(password: str) -> PasswordAnalysis:
    """Validate password using default validator.

    Args:
        password: Password to validate.

    Returns:
        PasswordAnalysis result.
    """
    return default_validator.analyze(password)


def generate_password(length: int = 16) -> str:
    """Generate password using default generator.

    Args:
        length: Password length.

    Returns:
        Generated password.
    """
    return default_generator.generate(length)
