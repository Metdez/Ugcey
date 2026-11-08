"""Shared test setup (owned by the orchestrator). Do not add plan-specific fixtures here;
put them in your own tests/_fakes_<plan>.py and import them."""
import os

import pytest

os.environ.setdefault("UGECY_INTERNAL_MODE", "test")
for _key in ("FIRECRAWL_API_KEY", "FIRECRAWL_API"):  # a developer's real key must not switch tests to live search
    os.environ.pop(_key, None)


@pytest.fixture(autouse=True)
def _reset_global_deps():
    from ugecy import deps
    from ugecy.settings import get_settings

    deps.set_deps(None)
    get_settings.cache_clear()
    yield
    deps.set_deps(None)
