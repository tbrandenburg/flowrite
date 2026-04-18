"""Path validation utilities for security."""
import os
from pathlib import Path
from typing import Optional


class PathTraversalError(ValueError):
    """Raised when path traversal is detected."""
    pass


def validate_safe_path(
    user_path: str,
    allowed_dir: Optional[str] = None,
) -> str:
    """
    Validate and canonicalize a user-provided path.

    Args:
        user_path: The path provided by user
        allowed_dir: Optional directory to restrict access to

    Returns:
        Canonicalized path if safe

    Raises:
        PathTraversalError: If path attempts traversal or is outside allowed dir
    """
    if allowed_dir:
        allowed = Path(allowed_dir).resolve()
        user_path = Path(allowed_dir) / user_path
        canonical = user_path.resolve()
        if not str(canonical).startswith(str(allowed)):
            raise PathTraversalError(
                f"Path '{user_path}' resolves outside allowed directory"
            )
    else:
        canonical = Path(user_path).resolve()

    return str(canonical)


def validate_workflow_path(
    user_path: str,
    base_dir: Optional[str] = None,
) -> str:
    """
    Validate a workflow file path.

    Args:
        user_path: Path to workflow file
        base_dir: Base directory to validate against (default: cwd)

    Returns:
        Validated canonical path

    Raises:
        PathTraversalError: If path escapes base directory
        FileNotFoundError: If file doesn't exist
    """
    if base_dir is None:
        base_dir = os.getcwd()

    validated = validate_safe_path(user_path, allowed_dir=base_dir)

    if not os.path.exists(validated):
        raise FileNotFoundError(f"Workflow file not found: {validated}")

    return validated