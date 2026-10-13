"""pytest support: gives tests a Playwright `page`. (The files also run
standalone, e.g. `python -m tests.test_diagnostico`.)"""

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page()
        browser.close()
