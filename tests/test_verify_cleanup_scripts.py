from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    """Return repository root path for shell script execution."""
    return Path(__file__).resolve().parents[1]


def _run_script(script_name: str, *, root_override: Path) -> None:
    """Run a repository shell script against an overridden root path."""
    env = dict(os.environ)
    env["ROOT_DIR_OVERRIDE"] = str(root_override)
    subprocess.run(
        ["bash", f"scripts/{script_name}"],
        cwd=_repo_root(),
        env=env,
        check=True,
    )


def test_clean_cache_preserves_fixture_caches(tmp_path: Path) -> None:
    """Cache cleanup removes non-fixture caches and preserves fixture caches."""
    fixture_cache = tmp_path / "tests" / "fixtures" / "demo" / ".tzp" / "cache"
    fixture_legacy = tmp_path / "tests" / "fixtures" / "demo" / ".tzp-cache"
    non_fixture_cache = tmp_path / "project" / ".tzp" / "cache"
    non_fixture_legacy = tmp_path / "project" / ".tzp-cache"

    for path in (fixture_cache, fixture_legacy, non_fixture_cache, non_fixture_legacy):
        path.mkdir(parents=True, exist_ok=True)

    _run_script("clean_cache.sh", root_override=tmp_path)

    assert fixture_cache.exists()
    assert fixture_legacy.exists()
    assert not non_fixture_cache.exists()
    assert not non_fixture_legacy.exists()


def test_clean_config_only_removes_fixture_configs(tmp_path: Path) -> None:
    """Config cleanup touches fixture configs only."""
    fixture_cfg = tmp_path / "tests" / "fixtures" / "demo" / ".tzp" / "config"
    fixture_legacy = tmp_path / "tests" / "fixtures" / "demo" / ".tzp-config"
    non_fixture_cfg = tmp_path / "project" / ".tzp" / "config"

    for path in (fixture_cfg, fixture_legacy, non_fixture_cfg):
        path.mkdir(parents=True, exist_ok=True)

    _run_script("clean_config.sh", root_override=tmp_path)

    assert not fixture_cfg.exists()
    assert not fixture_legacy.exists()
    assert non_fixture_cfg.exists()
