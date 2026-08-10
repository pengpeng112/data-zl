"""No-op database fixture for pure HIS/JHEMR title-sync logic tests."""

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
