"""Tests for password module."""

from __future__ import annotations

import pytest

from zipextractor.core.password import (
    PasswordAnalysis,
    PasswordCache,
    PasswordGenerator,
    PasswordStrength,
    PasswordValidator,
    clear_password_cache,
    generate_password,
    get_password_cache,
    get_password_strength_color,
    get_password_strength_label,
    mask_password,
    validate_password,
)


class TestPasswordStrength:
    """Tests for PasswordStrength enum."""

    def test_strength_ordering(self) -> None:
        """Test that strength levels are correctly ordered."""
        assert PasswordStrength.VERY_WEAK.value < PasswordStrength.WEAK.value
        assert PasswordStrength.WEAK.value < PasswordStrength.FAIR.value
        assert PasswordStrength.FAIR.value < PasswordStrength.STRONG.value
        assert PasswordStrength.STRONG.value < PasswordStrength.VERY_STRONG.value


class TestPasswordAnalysis:
    """Tests for PasswordAnalysis dataclass."""

    def test_is_acceptable_fair(self) -> None:
        """Test is_acceptable returns True for FAIR strength."""
        analysis = PasswordAnalysis(
            strength=PasswordStrength.FAIR, score=50, issues=[], suggestions=[]
        )
        assert analysis.is_acceptable is True

    def test_is_acceptable_strong(self) -> None:
        """Test is_acceptable returns True for STRONG strength."""
        analysis = PasswordAnalysis(
            strength=PasswordStrength.STRONG, score=70, issues=[], suggestions=[]
        )
        assert analysis.is_acceptable is True

    def test_is_acceptable_weak(self) -> None:
        """Test is_acceptable returns False for WEAK strength."""
        analysis = PasswordAnalysis(
            strength=PasswordStrength.WEAK, score=30, issues=[], suggestions=[]
        )
        assert analysis.is_acceptable is False

    def test_is_acceptable_very_weak(self) -> None:
        """Test is_acceptable returns False for VERY_WEAK strength."""
        analysis = PasswordAnalysis(
            strength=PasswordStrength.VERY_WEAK, score=10, issues=[], suggestions=[]
        )
        assert analysis.is_acceptable is False


class TestPasswordValidator:
    """Tests for PasswordValidator class."""

    @pytest.fixture
    def validator(self) -> PasswordValidator:
        """Create validator instance."""
        return PasswordValidator()

    def test_empty_password(self, validator: PasswordValidator) -> None:
        """Test empty password analysis."""
        analysis = validator.analyze("")
        assert analysis.strength == PasswordStrength.VERY_WEAK
        assert analysis.score == 0
        assert "Password is empty" in analysis.issues

    def test_short_password(self, validator: PasswordValidator) -> None:
        """Test password below minimum length."""
        analysis = validator.analyze("abc")
        assert analysis.strength == PasswordStrength.VERY_WEAK
        assert any("too short" in issue.lower() for issue in analysis.issues)

    def test_common_password(self, validator: PasswordValidator) -> None:
        """Test common password detection."""
        analysis = validator.analyze("password")
        assert any("too common" in issue.lower() for issue in analysis.issues)

    def test_keyboard_pattern(self, validator: PasswordValidator) -> None:
        """Test keyboard pattern detection."""
        analysis = validator.analyze("qwertyuiop")
        assert any("keyboard pattern" in issue.lower() for issue in analysis.issues)

    def test_repeated_characters(self, validator: PasswordValidator) -> None:
        """Test repeated character detection."""
        analysis = validator.analyze("aaaabbbccc")
        assert any("repeated characters" in issue.lower() for issue in analysis.issues)

    def test_sequential_characters(self, validator: PasswordValidator) -> None:
        """Test sequential character detection."""
        analysis = validator.analyze("abcdefghijk")
        assert any("sequential" in issue.lower() for issue in analysis.issues)

    def test_strong_password(self, validator: PasswordValidator) -> None:
        """Test strong password analysis."""
        analysis = validator.analyze("Tr0ub4dor&3Horse")
        assert analysis.strength.value >= PasswordStrength.FAIR.value
        assert analysis.score >= 40

    def test_very_strong_password(self, validator: PasswordValidator) -> None:
        """Test very strong password analysis."""
        analysis = validator.analyze("K#9fMn$2pLw@xQr5vZ!")
        assert analysis.strength.value >= PasswordStrength.STRONG.value
        assert analysis.score >= 60

    def test_suggests_lowercase(self, validator: PasswordValidator) -> None:
        """Test suggestion to add lowercase letters."""
        analysis = validator.analyze("ALLUPPERCASE123")
        assert any("lowercase" in s.lower() for s in analysis.suggestions)

    def test_suggests_uppercase(self, validator: PasswordValidator) -> None:
        """Test suggestion to add uppercase letters."""
        analysis = validator.analyze("alllowercase123")
        assert any("uppercase" in s.lower() for s in analysis.suggestions)

    def test_suggests_digits(self, validator: PasswordValidator) -> None:
        """Test suggestion to add numbers."""
        analysis = validator.analyze("NoDigitsHere")
        assert any("number" in s.lower() for s in analysis.suggestions)

    def test_suggests_symbols(self, validator: PasswordValidator) -> None:
        """Test suggestion to add special characters."""
        analysis = validator.analyze("NoSymbols123")
        assert any("special" in s.lower() for s in analysis.suggestions)

    def test_is_valid_returns_true_for_strong(
        self, validator: PasswordValidator
    ) -> None:
        """Test is_valid returns True for strong passwords."""
        assert validator.is_valid("K#9fMn$2pLw@xQr5!") is True

    def test_is_valid_returns_false_for_weak(
        self, validator: PasswordValidator
    ) -> None:
        """Test is_valid returns False for weak passwords."""
        assert validator.is_valid("weak") is False

    def test_is_valid_custom_min_strength(
        self, validator: PasswordValidator
    ) -> None:
        """Test is_valid with custom minimum strength."""
        # This should fail with STRONG requirement
        result = validator.is_valid("Medium1!", PasswordStrength.VERY_STRONG)
        assert result is False


class TestPasswordGenerator:
    """Tests for PasswordGenerator class."""

    @pytest.fixture
    def generator(self) -> PasswordGenerator:
        """Create generator instance."""
        return PasswordGenerator()

    def test_generate_default_length(self, generator: PasswordGenerator) -> None:
        """Test default password length is 16."""
        password = generator.generate()
        assert len(password) == 16

    def test_generate_custom_length(self, generator: PasswordGenerator) -> None:
        """Test custom password length."""
        password = generator.generate(length=24)
        assert len(password) == 24

    def test_generate_includes_uppercase(self, generator: PasswordGenerator) -> None:
        """Test password includes uppercase letters."""
        # Generate multiple to ensure statistical certainty
        for _ in range(10):
            password = generator.generate(include_uppercase=True)
            if any(c.isupper() for c in password):
                return
        pytest.fail("No uppercase letters found in generated passwords")

    def test_generate_includes_digits(self, generator: PasswordGenerator) -> None:
        """Test password includes digits."""
        for _ in range(10):
            password = generator.generate(include_digits=True)
            if any(c.isdigit() for c in password):
                return
        pytest.fail("No digits found in generated passwords")

    def test_generate_includes_symbols(self, generator: PasswordGenerator) -> None:
        """Test password includes symbols."""
        symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        for _ in range(10):
            password = generator.generate(include_symbols=True)
            if any(c in symbols for c in password):
                return
        pytest.fail("No symbols found in generated passwords")

    def test_generate_excludes_uppercase(self, generator: PasswordGenerator) -> None:
        """Test password excludes uppercase when disabled."""
        password = generator.generate(include_uppercase=False)
        assert not any(c.isupper() for c in password)

    def test_generate_excludes_digits(self, generator: PasswordGenerator) -> None:
        """Test password excludes digits when disabled."""
        password = generator.generate(include_digits=False)
        assert not any(c.isdigit() for c in password)

    def test_generate_excludes_symbols(self, generator: PasswordGenerator) -> None:
        """Test password excludes symbols when disabled."""
        symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        password = generator.generate(include_symbols=False)
        assert not any(c in symbols for c in password)

    def test_generate_excludes_ambiguous(self, generator: PasswordGenerator) -> None:
        """Test password excludes ambiguous characters."""
        ambiguous = "l1IO0"
        password = generator.generate(exclude_ambiguous=True)
        assert not any(c in ambiguous for c in password)

    def test_generate_includes_ambiguous(self, generator: PasswordGenerator) -> None:
        """Test password can include ambiguous characters."""
        ambiguous = "l1IO0"
        found = False
        for _ in range(100):  # Generate many to increase chance
            password = generator.generate(exclude_ambiguous=False)
            if any(c in ambiguous for c in password):
                found = True
                break
        # This might occasionally fail due to randomness, but is very unlikely
        assert found, "Ambiguous characters should occasionally appear"

    def test_generate_unique_passwords(self, generator: PasswordGenerator) -> None:
        """Test that generated passwords are unique."""
        passwords = [generator.generate() for _ in range(100)]
        assert len(set(passwords)) == 100

    def test_generate_passphrase_default(self, generator: PasswordGenerator) -> None:
        """Test default passphrase generation."""
        passphrase = generator.generate_passphrase()
        words = passphrase.split("-")
        assert len(words) == 4

    def test_generate_passphrase_custom_word_count(
        self, generator: PasswordGenerator
    ) -> None:
        """Test passphrase with custom word count."""
        passphrase = generator.generate_passphrase(word_count=6)
        words = passphrase.split("-")
        assert len(words) == 6

    def test_generate_passphrase_custom_separator(
        self, generator: PasswordGenerator
    ) -> None:
        """Test passphrase with custom separator."""
        passphrase = generator.generate_passphrase(separator="_")
        assert "_" in passphrase
        assert "-" not in passphrase

    def test_generate_passphrase_capitalize(
        self, generator: PasswordGenerator
    ) -> None:
        """Test passphrase with capitalization."""
        passphrase = generator.generate_passphrase(capitalize=True)
        words = passphrase.split("-")
        assert all(w[0].isupper() for w in words)

    def test_generate_passphrase_no_capitalize(
        self, generator: PasswordGenerator
    ) -> None:
        """Test passphrase without capitalization."""
        passphrase = generator.generate_passphrase(capitalize=False)
        words = passphrase.split("-")
        assert all(w[0].islower() for w in words)


class TestPasswordCache:
    """Tests for PasswordCache class."""

    @pytest.fixture
    def cache(self) -> PasswordCache:
        """Create cache instance."""
        return PasswordCache()

    def test_store_and_get(self, cache: PasswordCache) -> None:
        """Test storing and retrieving password."""
        cache.store("/path/to/archive.zip", "secret123")
        assert cache.get("/path/to/archive.zip") == "secret123"

    def test_get_nonexistent(self, cache: PasswordCache) -> None:
        """Test getting nonexistent password returns None."""
        assert cache.get("/nonexistent/path.zip") is None

    def test_has_returns_true(self, cache: PasswordCache) -> None:
        """Test has returns True for cached password."""
        cache.store("/path/archive.zip", "pass")
        assert cache.has("/path/archive.zip") is True

    def test_has_returns_false(self, cache: PasswordCache) -> None:
        """Test has returns False for non-cached password."""
        assert cache.has("/nonexistent.zip") is False

    def test_remove(self, cache: PasswordCache) -> None:
        """Test removing cached password."""
        cache.store("/path/archive.zip", "pass")
        cache.remove("/path/archive.zip")
        assert cache.get("/path/archive.zip") is None

    def test_remove_nonexistent(self, cache: PasswordCache) -> None:
        """Test removing nonexistent password doesn't raise."""
        cache.remove("/nonexistent.zip")  # Should not raise

    def test_clear(self, cache: PasswordCache) -> None:
        """Test clearing all cached passwords."""
        cache.store("/path1.zip", "pass1")
        cache.store("/path2.zip", "pass2")
        cache.clear()
        assert cache.get("/path1.zip") is None
        assert cache.get("/path2.zip") is None

    def test_overwrite_existing(self, cache: PasswordCache) -> None:
        """Test overwriting existing cached password."""
        cache.store("/path/archive.zip", "old_pass")
        cache.store("/path/archive.zip", "new_pass")
        assert cache.get("/path/archive.zip") == "new_pass"


class TestGlobalCache:
    """Tests for global password cache functions."""

    def test_get_password_cache_returns_cache(self) -> None:
        """Test get_password_cache returns PasswordCache instance."""
        cache = get_password_cache()
        assert isinstance(cache, PasswordCache)

    def test_get_password_cache_returns_singleton(self) -> None:
        """Test get_password_cache returns same instance."""
        cache1 = get_password_cache()
        cache2 = get_password_cache()
        assert cache1 is cache2

    def test_clear_password_cache(self) -> None:
        """Test clear_password_cache clears the global cache."""
        cache = get_password_cache()
        cache.store("/test.zip", "pass")
        clear_password_cache()
        assert cache.get("/test.zip") is None


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_mask_password_shows_length(self) -> None:
        """Test mask_password with length indication."""
        result = mask_password("secret123", show_length=True)
        assert result == "*********"
        assert len(result) == 9

    def test_mask_password_hides_length(self) -> None:
        """Test mask_password without length indication."""
        result = mask_password("secret123", show_length=False)
        assert result == "****"

    def test_get_password_strength_label(self) -> None:
        """Test get_password_strength_label returns correct labels."""
        assert get_password_strength_label(PasswordStrength.VERY_WEAK) == "Very Weak"
        assert get_password_strength_label(PasswordStrength.WEAK) == "Weak"
        assert get_password_strength_label(PasswordStrength.FAIR) == "Fair"
        assert get_password_strength_label(PasswordStrength.STRONG) == "Strong"
        assert get_password_strength_label(PasswordStrength.VERY_STRONG) == "Very Strong"

    def test_get_password_strength_color(self) -> None:
        """Test get_password_strength_color returns valid colors."""
        color = get_password_strength_color(PasswordStrength.VERY_WEAK)
        assert color.startswith("#")
        assert len(color) == 7

        color = get_password_strength_color(PasswordStrength.VERY_STRONG)
        assert color.startswith("#")
        assert len(color) == 7

    def test_validate_password_function(self) -> None:
        """Test validate_password convenience function."""
        analysis = validate_password("test123")
        assert isinstance(analysis, PasswordAnalysis)

    def test_generate_password_function(self) -> None:
        """Test generate_password convenience function."""
        password = generate_password()
        assert len(password) == 16
        assert isinstance(password, str)

    def test_generate_password_custom_length(self) -> None:
        """Test generate_password with custom length."""
        password = generate_password(length=20)
        assert len(password) == 20
