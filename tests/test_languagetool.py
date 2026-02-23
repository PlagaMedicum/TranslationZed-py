"""Tests for LanguageTool core client helpers."""

from __future__ import annotations

from translationzed_py.core import languagetool as lt


def test_validate_server_url_allows_https_and_local_http() -> None:
    """Accept HTTPS URLs and localhost-only HTTP URLs."""
    assert lt.validate_server_url("https://lt.example.org") == "https://lt.example.org"
    assert lt.validate_server_url("http://localhost:8081") == "http://localhost:8081"
    assert lt.validate_server_url("http://127.0.0.1:8081/") == "http://127.0.0.1:8081"


def test_validate_server_url_rejects_non_local_http() -> None:
    """Reject plain HTTP URLs for non-local hosts."""
    try:
        lt.validate_server_url("http://example.org:8081")
    except ValueError as exc:
        assert "localhost http" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for non-local http URL")


def test_draft_language_map_uses_defaults_and_locale_heuristics() -> None:
    """Build draft locale map with defaults plus heuristic fallbacks."""
    mapping = lt.draft_language_map(("EN", "BE", "RU", "UA", "FR", "PT-BR"))
    assert mapping["EN"] == "en-US"
    assert mapping["BE"] == "be-BY"
    assert mapping["RU"] == "ru-RU"
    assert mapping["UA"] == "uk-UA"
    assert mapping["FR"] == "fr"
    assert mapping["PT-BR"] == "pt-BR"


def test_check_text_uses_requested_level() -> None:
    """Send requested level to request layer without fallback when successful."""
    called_levels: list[str] = []

    def _fake_request(**kwargs):  # type: ignore[no-untyped-def]
        called_levels.append(str(kwargs["level"]))
        return {"matches": []}

    original = lt._perform_check_request
    lt._perform_check_request = _fake_request  # type: ignore[assignment]
    try:
        result_default = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )
        result_picky = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_PICKY,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert result_default.status == lt.LT_STATUS_OK
    assert result_default.used_level == lt.LT_LEVEL_DEFAULT
    assert result_picky.status == lt.LT_STATUS_OK
    assert result_picky.used_level == lt.LT_LEVEL_PICKY
    assert called_levels == [lt.LT_LEVEL_DEFAULT, lt.LT_LEVEL_PICKY]


def test_check_text_falls_back_to_default_when_picky_is_unsupported() -> None:
    """Retry with default level and set warning when picky mode is unsupported."""
    called_levels: list[str] = []

    def _fake_request(**kwargs):  # type: ignore[no-untyped-def]
        level = str(kwargs["level"])
        called_levels.append(level)
        if level == lt.LT_LEVEL_PICKY:
            raise lt.LTRequestError(
                "LanguageTool HTTP error (400).",
                code=400,
                body="Unknown parameter: level",
            )
        return {
            "matches": [
                {
                    "offset": 1,
                    "length": 2,
                    "message": "issue",
                    "replacements": [{"value": "ok"}],
                    "rule": {"id": "R1", "category": {"id": "GRAMMAR"}},
                    "type": {"typeName": "misspelling"},
                }
            ]
        }

    original = lt._perform_check_request
    lt._perform_check_request = _fake_request  # type: ignore[assignment]
    try:
        result = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_PICKY,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert called_levels == [lt.LT_LEVEL_PICKY, lt.LT_LEVEL_DEFAULT]
    assert result.status == lt.LT_STATUS_OK
    assert result.used_level == lt.LT_LEVEL_DEFAULT
    assert result.fallback_used is True
    assert "Picky unsupported" in result.warning
    assert len(result.matches) == 1


def test_check_text_returns_offline_status_for_network_failures() -> None:
    """Map offline errors to offline check result status."""

    def _fake_request(**_kwargs):  # type: ignore[no-untyped-def]
        raise lt.LTOfflineError("endpoint unreachable")

    original = lt._perform_check_request
    lt._perform_check_request = _fake_request  # type: ignore[assignment]
    try:
        result = lt.check_text(
            server_url="http://127.0.0.1:8081",
            language="en-US",
            text="Text",
            level=lt.LT_LEVEL_DEFAULT,
            timeout_ms=1200,
        )
    finally:
        lt._perform_check_request = original  # type: ignore[assignment]

    assert result.status == lt.LT_STATUS_OFFLINE
    assert result.error == "endpoint unreachable"


def test_check_text_rejects_invalid_server_url() -> None:
    """Map invalid endpoint input to error status."""
    result = lt.check_text(
        server_url="ftp://localhost:8081",
        language="en-US",
        text="Text",
        level=lt.LT_LEVEL_DEFAULT,
        timeout_ms=1200,
    )
    assert result.status == lt.LT_STATUS_ERROR
    assert "http or https" in result.error
