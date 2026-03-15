"""OASIS Dashboard - A monitoring and management dashboard for OASIS framework."""

__version__ = "1.1.0"

# Load environment variables from .env file at package import
# This must be done before importing any modules that use os.environ
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Determine project root (look for .env.example as a marker)
    # Start from current file and go up until we find the project root
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir

    # Look for .env.example to identify project root
    for parent in [current_dir, *current_dir.parents]:
        if (parent / ".env.example").exists():
            project_root = parent
            break

    # Try to load .env from project root
    env_path = project_root / ".env"

    if env_path.exists():
        load_dotenv(env_path, override=False)  # Don't override existing env vars
    else:
        # Silently skip if .env doesn't exist - backward compatibility
        pass

except ImportError:
    # python-dotenv not available - that's okay, env vars can be set manually
    pass
except Exception as e:
    # Log error but don't fail - backward compatibility
    import warnings
    warnings.warn(f"Failed to load .env file: {e}", ImportWarning)
