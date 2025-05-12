"""
Configuration for pytest.
"""

import os
import sys
import json
import pytest
import logging
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create a logger for tests
    logger = logging.getLogger("mcp_client_tests")
    logger.setLevel(logging.INFO)

    return logger

# We now have the proper config in the config.json file