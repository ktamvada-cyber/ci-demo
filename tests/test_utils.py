"""
Unit tests for app.utils module.

Tests all pure functions with comprehensive coverage including:
- Happy path scenarios
- Edge cases
- Error handling
- Boundary conditions
"""

import pytest
from datetime import datetime, timedelta
from app.utils import (
    mask_secret,
    validate_commit_sha,
    validate_short_sha,
    parse_deployment_id,
    calculate_deployment_age,
    format_environment_name,
    is_production_environment,
    extract_short_sha,
    build_deployment_metadata,
    sanitize_deployment_info
)


class TestMaskSecret:
    """Test cases for mask_secret function."""

    def test_mask_long_secret(self):
        """Should mask secret longer than visible chars."""
        result = mask_secret("my-secret-api-key-12345", 8)
        assert result == "my-secre***"

    def test_mask_with_default_visible_chars(self):
        """Should use default 8 visible chars."""
        result = mask_secret("super-secret-key-abcdef")
        assert result == "super-se***"

    def test_short_secret_not_masked(self):
        """Should not mask secret shorter than visible chars."""
        result = mask_secret("short", 8)
        assert result == "short"

    def test_empty_string(self):
        """Should handle empty string."""
        result = mask_secret("", 8)
        assert result == ""

    def test_exact_length_not_masked(self):
        """Should not mask secret exactly equal to visible chars."""
        result = mask_secret("exactly8", 8)
        assert result == "exactly8"

    def test_custom_visible_chars(self):
        """Should respect custom visible_chars parameter."""
        result = mask_secret("secret-key", 3)
        assert result == "sec***"


class TestValidateCommitSha:
    """Test cases for validate_commit_sha function."""

    def test_valid_40_char_sha(self):
        """Should validate correct 40-character hex SHA."""
        assert validate_commit_sha("abc123def4567890abcdef0123456789abcdef01") is True

    def test_valid_all_lowercase(self):
        """Should accept all lowercase hex characters."""
        assert validate_commit_sha("abcdef0123456789abcdef0123456789abcdef01") is True

    def test_valid_all_numbers(self):
        """Should accept all numeric hex characters."""
        assert validate_commit_sha("0123456789012345678901234567890123456789") is True

    def test_invalid_too_short(self):
        """Should reject SHA shorter than 40 characters."""
        assert validate_commit_sha("abc123") is False

    def test_invalid_too_long(self):
        """Should reject SHA longer than 40 characters."""
        assert validate_commit_sha("abc123def456789abcdef0123456789abcdef01a234") is False

    def test_invalid_uppercase(self):
        """Should reject uppercase letters."""
        assert validate_commit_sha("ABC123def456789abcdef0123456789abcdef01") is False

    def test_invalid_special_chars(self):
        """Should reject special characters."""
        assert validate_commit_sha("abc-23def456789abcdef0123456789abcdef01") is False

    def test_empty_string(self):
        """Should reject empty string."""
        assert validate_commit_sha("") is False

    def test_none_value(self):
        """Should reject None value."""
        assert validate_commit_sha(None) is False

    def test_non_string_type(self):
        """Should reject non-string types."""
        assert validate_commit_sha(123) is False


class TestValidateShortSha:
    """Test cases for validate_short_sha function."""

    def test_valid_7_char_sha(self):
        """Should validate correct 7-character short SHA."""
        assert validate_short_sha("abc1234") is True

    def test_valid_custom_length(self):
        """Should validate custom length short SHA."""
        assert validate_short_sha("abc123", 6) is True

    def test_invalid_too_short(self):
        """Should reject short SHA with wrong length."""
        assert validate_short_sha("abc12", 7) is False

    def test_invalid_uppercase(self):
        """Should reject uppercase letters."""
        assert validate_short_sha("ABC1234") is False

    def test_empty_string(self):
        """Should reject empty string."""
        assert validate_short_sha("") is False

    def test_none_value(self):
        """Should reject None value."""
        assert validate_short_sha(None) is False


class TestParseDeploymentId:
    """Test cases for parse_deployment_id function."""

    def test_valid_numeric_string(self):
        """Should parse valid numeric string to int."""
        assert parse_deployment_id("12345") == 12345

    def test_valid_large_number(self):
        """Should handle large deployment IDs."""
        assert parse_deployment_id("999999999") == 999999999

    def test_invalid_non_numeric(self):
        """Should return None for non-numeric string."""
        assert parse_deployment_id("invalid") is None

    def test_empty_string(self):
        """Should return None for empty string."""
        assert parse_deployment_id("") is None

    def test_none_value(self):
        """Should return None for None value."""
        assert parse_deployment_id(None) is None

    def test_mixed_characters(self):
        """Should return None for mixed alphanumeric."""
        assert parse_deployment_id("123abc") is None


class TestCalculateDeploymentAge:
    """Test cases for calculate_deployment_age function."""

    def test_recent_deployment(self):
        """Should calculate age for recent deployment."""
        # Create a timestamp 1 hour ago
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        timestamp = one_hour_ago.isoformat() + "Z"
        age = calculate_deployment_age(timestamp)

        # Should be approximately 3600 seconds (±10 seconds for test execution)
        assert age is not None
        assert 3590 <= age <= 3610

    def test_very_old_deployment(self):
        """Should calculate age for old deployment."""
        # Create a timestamp 24 hours ago
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        timestamp = one_day_ago.isoformat() + "Z"
        age = calculate_deployment_age(timestamp)

        # Should be approximately 86400 seconds
        assert age is not None
        assert 86390 <= age <= 86410

    def test_invalid_timestamp(self):
        """Should return None for invalid timestamp."""
        assert calculate_deployment_age("invalid-timestamp") is None

    def test_empty_string(self):
        """Should return None for empty string."""
        assert calculate_deployment_age("") is None

    def test_none_value(self):
        """Should return None for None value."""
        assert calculate_deployment_age(None) is None


class TestFormatEnvironmentName:
    """Test cases for format_environment_name function."""

    def test_uppercase_to_lowercase(self):
        """Should convert uppercase to lowercase."""
        assert format_environment_name("PRODUCTION") == "production"

    def test_mixed_case_to_lowercase(self):
        """Should convert mixed case to lowercase."""
        assert format_environment_name("Staging") == "staging"

    def test_already_lowercase(self):
        """Should preserve already lowercase."""
        assert format_environment_name("development") == "development"

    def test_with_whitespace(self):
        """Should strip whitespace."""
        assert format_environment_name("  production  ") == "production"

    def test_empty_string(self):
        """Should return 'unknown' for empty string."""
        assert format_environment_name("") == "unknown"

    def test_none_value(self):
        """Should return 'unknown' for None value."""
        assert format_environment_name(None) == "unknown"

    def test_non_string_type(self):
        """Should return 'unknown' for non-string types."""
        assert format_environment_name(123) == "unknown"


class TestIsProductionEnvironment:
    """Test cases for is_production_environment function."""

    def test_lowercase_production(self):
        """Should recognize lowercase 'production'."""
        assert is_production_environment("production") is True

    def test_uppercase_production(self):
        """Should recognize uppercase 'PRODUCTION'."""
        assert is_production_environment("PRODUCTION") is True

    def test_mixed_case_production(self):
        """Should recognize mixed case 'Production'."""
        assert is_production_environment("Production") is True

    def test_staging_not_production(self):
        """Should return False for staging."""
        assert is_production_environment("staging") is False

    def test_development_not_production(self):
        """Should return False for development."""
        assert is_production_environment("development") is False

    def test_empty_string(self):
        """Should return False for empty string."""
        assert is_production_environment("") is False


class TestExtractShortSha:
    """Test cases for extract_short_sha function."""

    def test_extract_default_7_chars(self):
        """Should extract first 7 characters by default."""
        full_sha = "abc123def456789abcdef0123456789abcdef01a"
        assert extract_short_sha(full_sha) == "abc123d"

    def test_extract_custom_length(self):
        """Should extract custom number of characters."""
        full_sha = "abc123def456789abcdef0123456789abcdef01a"
        assert extract_short_sha(full_sha, 10) == "abc123def4"

    def test_extract_first_char(self):
        """Should extract single character."""
        full_sha = "abc123def456789abcdef0123456789abcdef01a"
        assert extract_short_sha(full_sha, 1) == "a"

    def test_invalid_sha_returns_none(self):
        """Should return None for invalid SHA."""
        assert extract_short_sha("invalid-sha") is None

    def test_short_sha_returns_none(self):
        """Should return None for short SHA."""
        assert extract_short_sha("abc123") is None


class TestBuildDeploymentMetadata:
    """Test cases for build_deployment_metadata function."""

    def test_valid_production_metadata(self):
        """Should build metadata for valid production deployment."""
        meta = build_deployment_metadata(
            "PRODUCTION",
            "abc123def456789abcdef0123456789abcdef01a",
            "2024-02-26T10:30:00Z",
            "12345"
        )

        assert meta['environment'] == "production"
        assert meta['is_production'] is True
        assert meta['commit_sha_valid'] is True
        assert meta['short_sha'] == "abc123d"
        assert meta['deployment_id'] == 12345
        assert meta['deployment_id_valid'] is True

    def test_valid_staging_metadata(self):
        """Should build metadata for staging deployment."""
        meta = build_deployment_metadata(
            "staging",
            "def456abc1230000abcdef0123456789abcdef01",
            "2024-02-26T11:00:00Z",
            "67890"
        )

        assert meta['environment'] == "staging"
        assert meta['is_production'] is False
        assert meta['short_sha'] == "def456a"

    def test_invalid_commit_sha(self):
        """Should mark invalid commit SHA."""
        meta = build_deployment_metadata(
            "staging",
            "invalid-sha",
            "2024-02-26T10:30:00Z",
            "12345"
        )

        assert meta['commit_sha_valid'] is False
        assert meta['short_sha'] is None

    def test_invalid_deployment_id(self):
        """Should mark invalid deployment ID."""
        meta = build_deployment_metadata(
            "staging",
            "abc123def456789abcdef0123456789abcdef01a",
            "2024-02-26T10:30:00Z",
            "invalid"
        )

        assert meta['deployment_id'] is None
        assert meta['deployment_id_valid'] is False


class TestSanitizeDeploymentInfo:
    """Test cases for sanitize_deployment_info function."""

    def test_mask_api_key(self):
        """Should mask API key by default."""
        info = {
            "api_key": "secret-key-12345",
            "environment": "STAGING",
            "commit_sha": "abc123"
        }
        sanitized = sanitize_deployment_info(info)

        assert sanitized['api_key'] == "secret-k***"
        assert sanitized['environment'] == "staging"

    def test_mask_db_password(self):
        """Should mask database password."""
        info = {
            "db_password": "super-secret-password",
            "environment": "production"
        }
        sanitized = sanitize_deployment_info(info)

        assert sanitized['db_password'] == "super-se***"

    def test_no_masking_when_disabled(self):
        """Should not mask secrets when mask_secrets=False."""
        info = {
            "api_key": "secret-key-12345",
            "environment": "staging"
        }
        sanitized = sanitize_deployment_info(info, mask_secrets=False)

        assert sanitized['api_key'] == "secret-key-12345"

    def test_normalize_environment(self):
        """Should normalize environment name."""
        info = {
            "environment": "PRODUCTION",
            "commit_sha": "abc123"
        }
        sanitized = sanitize_deployment_info(info)

        assert sanitized['environment'] == "production"

    def test_preserve_other_fields(self):
        """Should preserve non-secret fields."""
        info = {
            "api_key": "secret",
            "commit_sha": "abc123def",
            "deployment_id": "12345",
            "custom_field": "value"
        }
        sanitized = sanitize_deployment_info(info)

        assert sanitized['commit_sha'] == "abc123def"
        assert sanitized['deployment_id'] == "12345"
        assert sanitized['custom_field'] == "value"

    def test_handles_missing_fields(self):
        """Should handle info dict without secret fields."""
        info = {
            "environment": "staging",
            "commit_sha": "abc123"
        }
        sanitized = sanitize_deployment_info(info)

        assert 'api_key' not in sanitized
        assert sanitized['environment'] == "staging"
