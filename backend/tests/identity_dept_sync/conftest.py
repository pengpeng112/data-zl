"""No-op database fixture for pure JHEMR user-dept sync logic tests."""

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
