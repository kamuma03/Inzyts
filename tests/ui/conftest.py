import pytest
import os

@pytest.fixture(scope="session")
def base_url():
    """Return the base URL of the running application."""
    # Default to localhost:5173 (Vite dev server) if not specified
    return os.getenv("BASE_URL", "http://localhost:5173")

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Override browser context arguments if needed."""
    return {
        **browser_context_args,
        "viewport": {
            "width": 1280,
            "height": 720,
        },
    }
