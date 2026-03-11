"""
Pure utility functions for deployment metadata processing and validation.

These functions are stateless and side-effect free, making them ideal for unit testing.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import re


def mask_secret(secret: str, visible_chars: int = 8) -> str:
    """
    Masks a secret string, showing only the first N characters.

    Args:
        secret: The secret string to mask
        visible_chars: Number of characters to keep visible (default: 8)

    Returns:
        Masked string with format "visible***"

    Examples:
        >>> mask_secret("my-secret-api-key-12345", 8)
        'my-secre***'
        >>> mask_secret("short", 8)
        'short'
    """
    if not secret or len(secret) <= visible_chars:
        return secret
    return secret[:visible_chars] + "***"


def validate_commit_sha(sha: str) -> bool:
    """
    Validates if a string is a valid 40-character hexadecimal commit SHA.

    Args:
        sha: String to validate

    Returns:
        True if valid commit SHA, False otherwise

    Examples:
        >>> validate_commit_sha("abc123def456789abcdef0123456789abcdef01")
        True
        >>> validate_commit_sha("invalid-sha")
        False
        >>> validate_commit_sha("abc123")
        False
    """
    if not sha or not isinstance(sha, str):
        return False
    return bool(re.match(r'^[a-f0-9]{40}$', sha))


def validate_short_sha(sha: str, length: int = 7) -> bool:
    """
    Validates if a string is a valid short commit SHA (7 characters by default).

    Args:
        sha: String to validate
        length: Expected length of short SHA (default: 7)

    Returns:
        True if valid short SHA, False otherwise

    Examples:
        >>> validate_short_sha("abc1234")
        True
        >>> validate_short_sha("xyz123", 6)
        False
    """
    if not sha or not isinstance(sha, str):
        return False
    return bool(re.match(rf'^[a-f0-9]{{{length}}}$', sha))


def parse_deployment_id(deployment_id: str) -> Optional[int]:
    """
    Safely parses a deployment ID string to integer.

    Args:
        deployment_id: String representation of deployment ID

    Returns:
        Integer deployment ID if valid, None otherwise

    Examples:
        >>> parse_deployment_id("12345")
        12345
        >>> parse_deployment_id("invalid")

        >>> parse_deployment_id("")

    """
    try:
        return int(deployment_id) if deployment_id else None
    except (ValueError, TypeError):
        return None


def calculate_deployment_age(build_timestamp: str) -> Optional[int]:
    """
    Calculates the age of a deployment in seconds from its build timestamp.

    Args:
        build_timestamp: ISO 8601 timestamp string (e.g., "2024-02-26T10:30:00Z")

    Returns:
        Age in seconds if valid timestamp, None otherwise

    Examples:
        >>> # Returns positive integer representing seconds since build
        >>> calculate_deployment_age("2024-02-26T10:30:00Z")  # doctest: +SKIP
        3600
    """
    try:
        build_time = datetime.fromisoformat(build_timestamp.replace('Z', '+00:00'))
        now = datetime.utcnow()
        delta = now - build_time.replace(tzinfo=None)
        return int(delta.total_seconds())
    except (ValueError, AttributeError):
        return None


def format_environment_name(env: str) -> str:
    """
    Normalizes and formats environment name to lowercase.

    Args:
        env: Raw environment name

    Returns:
        Normalized environment name

    Examples:
        >>> format_environment_name("PRODUCTION")
        'production'
        >>> format_environment_name("Staging")
        'staging'
        >>> format_environment_name("unknown")
        'unknown'
    """
    if not env or not isinstance(env, str):
        return "unknown"
    return env.lower().strip()


def is_production_environment(env: str) -> bool:
    """
    Checks if the given environment is production.

    Args:
        env: Environment name

    Returns:
        True if production environment, False otherwise

    Examples:
        >>> is_production_environment("production")
        True
        >>> is_production_environment("PRODUCTION")
        True
        >>> is_production_environment("staging")
        False
    """
    normalized = format_environment_name(env)
    return normalized == "production"


def extract_short_sha(full_sha: str, length: int = 7) -> Optional[str]:
    """
    Extracts the first N characters from a full commit SHA.

    Args:
        full_sha: Full 40-character commit SHA
        length: Number of characters to extract (default: 7)

    Returns:
        Short SHA if valid input, None otherwise

    Examples:
        >>> extract_short_sha("abc123def456789abcdef0123456789abcdef01")
        'abc123d'
        >>> extract_short_sha("abc123def456789abcdef0123456789abcdef01", 10)
        'abc123def4'
        >>> extract_short_sha("invalid")

    """
    if not validate_commit_sha(full_sha):
        return None
    return full_sha[:length]


def build_deployment_metadata(
    environment: str,
    commit_sha: str,
    build_timestamp: str,
    deployment_id: str
) -> Dict[str, Any]:
    """
    Builds a standardized deployment metadata dictionary with validation.

    Args:
        environment: Environment name
        commit_sha: Full commit SHA
        build_timestamp: ISO 8601 timestamp
        deployment_id: Deployment ID string

    Returns:
        Dictionary with validated and normalized metadata

    Examples:
        >>> meta = build_deployment_metadata(
        ...     "PRODUCTION",
        ...     "abc123def456789abcdef0123456789abcdef01",
        ...     "2024-02-26T10:30:00Z",
        ...     "12345"
        ... )
        >>> meta['environment']
        'production'
        >>> meta['commit_sha_valid']
        True
    """
    return {
        "environment": format_environment_name(environment),
        "is_production": is_production_environment(environment),
        "commit_sha": commit_sha,
        "commit_sha_valid": validate_commit_sha(commit_sha),
        "short_sha": extract_short_sha(commit_sha),
        "build_timestamp": build_timestamp,
        "deployment_id": parse_deployment_id(deployment_id),
        "deployment_id_valid": parse_deployment_id(deployment_id) is not None
    }


def sanitize_deployment_info(info: Dict[str, Any], mask_secrets: bool = True) -> Dict[str, Any]:
    """
    Sanitizes deployment info by masking secrets and validating data.

    Args:
        info: Raw deployment info dictionary
        mask_secrets: Whether to mask secret values (default: True)

    Returns:
        Sanitized deployment info dictionary

    Examples:
        >>> info = {"api_key": "secret-key-12345", "commit_sha": "abc123", "environment": "staging"}
        >>> sanitized = sanitize_deployment_info(info)
        >>> sanitized['api_key']
        'secret-k***'
        >>> sanitized['environment']
        'staging'
    """
    sanitized = info.copy()

    # Mask secrets
    if mask_secrets:
        if 'api_key' in sanitized:
            sanitized['api_key'] = mask_secret(sanitized['api_key'])
        if 'db_password' in sanitized:
            sanitized['db_password'] = mask_secret(sanitized['db_password'])

    # Normalize environment
    if 'environment' in sanitized:
        sanitized['environment'] = format_environment_name(sanitized['environment'])

    return sanitized
