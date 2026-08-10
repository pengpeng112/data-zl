"""No-op database fixture for pure signature-sync regression tests."""

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
