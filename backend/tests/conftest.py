"""Test configuration and fixtures.

Uses SQLite in-memory for unit tests that don't need PostgreSQL-specific features.
Parser tests are pure unit tests that don't need a database.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest

# Sample files
SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / ".opencode" / "skills" / "samples"
SAMPLE_ESEWA = SAMPLES_DIR / "sample_esewa.xls"
SAMPLE_NABIL = SAMPLES_DIR / "sample_nabil.pdf"
SAMPLE_STANDARD_CHARTERED = SAMPLES_DIR / "sample_standard_charter.pdf"


@pytest.fixture
def esewa_file_bytes():
    """Read the eSewa sample XLS file."""
    with open(SAMPLE_ESEWA, "rb") as f:
        return f.read()


@pytest.fixture
def nabil_file_bytes():
    """Read the Nabil sample PDF file."""
    with open(SAMPLE_NABIL, "rb") as f:
        return f.read()


@pytest.fixture
def standard_chartered_file_bytes():
    """Read the Standard Chartered sample PDF."""
    with open(SAMPLE_STANDARD_CHARTERED, "rb") as f:
        return f.read()


@pytest.fixture
def test_account_id():
    """A stable test account UUID."""
    return str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
