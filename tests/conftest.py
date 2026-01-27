import os
from pathlib import Path

import pytest

# Ensure Qt runs headless in CI/CLI environments without a display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture()
def prod_like_root() -> Path:
    return Path(__file__).parent / "fixtures" / "prod_like"
