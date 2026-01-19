import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def anyio_backend():
    """Configure pytest-anyio to only use asyncio backend."""
    return "asyncio"
