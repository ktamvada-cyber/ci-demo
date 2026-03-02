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


def validate_deployment_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates comprehensive deployment configuration.

    Args:
        config: Deployment configuration dictionary

    Returns:
        Validation result with errors and warnings

    Examples:
        >>> config = {"environment": "production", "replicas": 3}
        >>> result = validate_deployment_config(config)
        >>> result['valid']
        True
    """
    errors = []
    warnings = []

    # Check required fields
    required_fields = ['environment', 'commit_sha', 'replicas']
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")

    # Validate environment
    if 'environment' in config:
        env = config['environment']
        if env not in ['production', 'staging', 'development']:
            warnings.append(f"Non-standard environment: {env}")

    # Validate replicas
    if 'replicas' in config:
        replicas = config['replicas']
        if not isinstance(replicas, int) or replicas < 1:
            errors.append("Replicas must be a positive integer")
        if replicas > 10:
            warnings.append("High replica count may consume excessive resources")

    # Validate commit SHA
    if 'commit_sha' in config:
        if not validate_commit_sha(config['commit_sha']):
            errors.append("Invalid commit SHA format")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }


def generate_deployment_report(metadata: Dict[str, Any], detailed: bool = False) -> str:
    """
    Generates a formatted deployment report.

    Args:
        metadata: Deployment metadata dictionary
        detailed: Whether to include detailed information

    Returns:
        Formatted report string

    Examples:
        >>> meta = {"environment": "production", "commit_sha": "abc123"}
        >>> report = generate_deployment_report(meta)
        >>> "production" in report
        True
    """
    lines = []
    lines.append("=" * 50)
    lines.append("DEPLOYMENT REPORT")
    lines.append("=" * 50)

    if 'environment' in metadata:
        lines.append(f"Environment: {metadata['environment'].upper()}")

    if 'commit_sha' in metadata:
        sha = metadata['commit_sha']
        short_sha = extract_short_sha(sha) or sha[:7]
        lines.append(f"Commit: {short_sha}")

    if 'deployment_id' in metadata:
        lines.append(f"Deployment ID: {metadata['deployment_id']}")

    if detailed:
        lines.append("")
        lines.append("Detailed Information:")
        lines.append("-" * 50)
        for key, value in metadata.items():
            if key not in ['environment', 'commit_sha', 'deployment_id']:
                lines.append(f"  {key}: {value}")

    lines.append("=" * 50)
    return "\n".join(lines)


def calculate_rollback_safety(current_deployment: Dict[str, Any], target_deployment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates safety metrics for rolling back to a previous deployment.

    Args:
        current_deployment: Current deployment metadata
        target_deployment: Target deployment metadata for rollback

    Returns:
        Safety assessment with risk level and recommendations

    Examples:
        >>> current = {"deployment_id": "200", "build_timestamp": "2024-02-26T12:00:00Z"}
        >>> target = {"deployment_id": "190", "build_timestamp": "2024-02-26T10:00:00Z"}
        >>> safety = calculate_rollback_safety(current, target)
        >>> safety['risk_level'] in ['low', 'medium', 'high']
        True
    """
    risk_factors = []
    recommendations = []

    # Check deployment age difference
    if 'build_timestamp' in current_deployment and 'build_timestamp' in target_deployment:
        current_age = calculate_deployment_age(current_deployment['build_timestamp'])
        target_age = calculate_deployment_age(target_deployment['build_timestamp'])

        if current_age and target_age:
            age_diff_hours = (target_age - current_age) / 3600
            if age_diff_hours > 168:  # More than 1 week old
                risk_factors.append("Target deployment is more than 1 week old")
                recommendations.append("Consider deploying a newer version instead")

    # Check environment match
    if 'environment' in current_deployment and 'environment' in target_deployment:
        if current_deployment['environment'] != target_deployment['environment']:
            risk_factors.append("Environment mismatch detected")

    # Check if rolling back to production
    if 'environment' in target_deployment:
        if is_production_environment(target_deployment['environment']):
            risk_factors.append("Rolling back production deployment")
            recommendations.append("Ensure proper testing and approval process")

    # Determine risk level
    if len(risk_factors) == 0:
        risk_level = 'low'
    elif len(risk_factors) <= 2:
        risk_level = 'medium'
    else:
        risk_level = 'high'

    return {
        'risk_level': risk_level,
        'risk_factors': risk_factors,
        'recommendations': recommendations,
        'safe_to_proceed': risk_level in ['low', 'medium']
    }


def parse_deployment_tags(tags: list) -> Dict[str, str]:
    """
    Parses deployment tags into a structured dictionary.

    Args:
        tags: List of tag strings in format "key:value"

    Returns:
        Dictionary of parsed tags

    Examples:
        >>> tags = ["team:backend", "version:2.1", "priority:high"]
        >>> parsed = parse_deployment_tags(tags)
        >>> parsed['team']
        'backend'
        >>> parsed['version']
        '2.1'
    """
    result = {}

    if not tags or not isinstance(tags, list):
        return result

    for tag in tags:
        if not isinstance(tag, str) or ':' not in tag:
            continue

        parts = tag.split(':', 1)
        if len(parts) == 2:
            key, value = parts
            result[key.strip()] = value.strip()

    return result
