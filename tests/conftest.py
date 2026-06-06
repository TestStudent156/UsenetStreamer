"""Shared test fixtures."""
from __future__ import annotations

import threading

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

# ---------------------------------------------------------------------------
# Suppress the pycares '_run_safe_shutdown_loop' daemon thread that aiohttp
# starts on Ubuntu 24.04.  pytest-homeassistant-custom-component <=0.13.205
# (which bundles HA 2025.1) asserts that no unexpected threads are left after
# each test.  The thread is a harmless daemon thread that exits on its own,
# but it trips the assertion in that older harness version.
# We monkey-patch threading.enumerate globally (once, at module load) so that
# verify_cleanup never sees those threads.
# ---------------------------------------------------------------------------
_real_enumerate = threading.enumerate


def _filtered_enumerate():
    return [
        t for t in _real_enumerate()
        if "_run_safe_shutdown_loop" not in t.name
    ]


threading.enumerate = _filtered_enumerate  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield
