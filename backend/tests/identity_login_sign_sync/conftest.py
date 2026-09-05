"""No-op database fixture for pure JHEMR login/sign-way sync logic tests."""

import pytest


@pytest.fixture(autouse=True)
def clean_test_database():
    yield
